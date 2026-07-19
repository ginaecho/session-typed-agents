# What a Benchmark Run Costs — and Which Commands Need Azure

**Date: 2026-07-19.** A practical guide to two questions people ask before
pressing enter: *does this command spend money?* and *roughly how much?*

## Menu

- [Which commands need Azure at all](#which-commands-need-azure-at-all)
- [How the cost builds up](#how-the-cost-builds-up)
- [Estimate for one full finance run](#estimate-for-one-full-finance-run)
- [Estimate for the scaling-chart run](#estimate-for-the-scaling-chart-run)
- [Dollar table by model](#dollar-table-by-model)
- [How to spend almost nothing first](#how-to-spend-almost-nothing-first)
- [What this estimate is based on (and its soft spots)](#what-this-estimate-is-based-on-and-its-soft-spots)

## Which commands need Azure at all

The benchmark watches real AI agents talk to each other, and the agents are
hosted models rented from Azure AI Foundry (Microsoft's agent-hosting
service) — nothing runs locally. So the dividing line is simple:
**producing evidence (running agents) needs Azure; looking at evidence that
already exists does not.**

A concrete example of each side of the line:

| Command | Azure? | Why |
|---|---|---|
| `python scripts/case_runner.py finance 10 --sequential` | **Yes** | every agent turn is a live model call (`baselines/_foundry_client.py` reads `AZURE_AI_PROJECT_ENDPOINT` and your `az login`) |
| `python scripts/scaling_chart.py run` | **Yes** | it is a wrapper that calls `case_runner` on two cases |
| `python scripts/scaling_chart.py plot` | No | reads `summary.json` files already on disk, draws the chart |
| `python scripts/case_runner.py finance --summarize-only <run_dir>` | No | re-aggregates an existing run |
| `python scripts/re_anchor_goals.py finance valid --check` | No | audits a goals file against the protocol, zero LLM calls |
| `python scripts/roles_sweep.py` | No | structural proxy from Scribble projections, zero LLM calls |

## How the cost builds up

Three multipliers stack, and each one is easy to underestimate:

1. **Arms.** A full run drives every registered configuration ("arm") —
   15 of them as of 2026-07-19.
2. **Retries.** A trial that fails its goals is re-run up to 3 times, and
   every attempt's tokens count. The failing baseline arms therefore cost
   roughly 3× their single-attempt price — the *failures* are the
   expensive part, not the successes.
3. **Re-read history.** Each agent turn re-sends the conversation so far,
   so input tokens dominate (roughly 80% input / 20% output). An arm whose
   prompt contains the whole protocol pays that tax on every single turn.

Small example of multiplier 3: the full-STJP arm finishes finance in about
11 calls at ~13k tokens per trial (the one hard number in the repo,
`README.md` "Key Results"), while the whole-plan-as-text arm needs ~42
calls at ~120k tokens — same task, 9× the tokens, purely because every
turn re-reads a big prompt and idle agents get polled.

## Estimate for one full finance run

`case_runner.py finance 10` = 15 arms × 10 trials, retries included:

| Arm group | Arms | ~tokens/trial | Why |
|---|---|---|---|
| Failing baselines | bare, 4× MAF, unchecked_skills | ~50k each | fail → all 3 attempts, ~24 steps each |
| Whole-plan-as-text | maf_groupchat_llmvalid, global_decentralized | ~120k each | every turn re-reads the entire protocol |
| Local contract, no gate | spec_llmvalid, min_llmvalid | ~35k avg | own slice only, no early stop |
| Gate variants | spec + 3× min gate variants | ~25k each | enforced, leaner |
| Full STJP scheduler | min_llmvalid_sched | ~13k | measured anchor |

Total: roughly **7 million tokens**, best read as a **5M–10M range** — the
failing arms are the swing factor, because a trial that flails through all
3 retries doubles its own cost.

## Estimate for the scaling-chart run

`scaling_chart.py run` uses only 4 arms but two cases, and the 10-role case
pays bigger prompts:

- 6-role `report_pipeline`: ≈ 1.8M tokens
- 10-role `report_pipeline_large`: ≈ 3.1M tokens
- Total ≈ **5M tokens**

## Dollar table by model

The deployment name decides the price (`AZURE_OPENAI_DEPLOYMENT`, default
`gpt-4o` in `baselines/foundry_runner.py`), and it swings the bill by more
than 15×. Using ~80/20 input/output split and public per-million rates
(gpt-4o ≈ $2.50 in / $10 out; gpt-4o-mini ≈ $0.15 / $0.60):

| Scenario | gpt-4o | gpt-4o-mini |
|---|---|---|
| `finance 10`, all 15 arms | **~$20–45** | ~$2 |
| Both scaling cases, 4 arms | **~$15–20** | ~$1.5 |
| Both together | **~$35–65** | **~$3–4** |

One-time setup steps (drafting the protocol with an LLM, re-anchoring
goals) are a handful of calls — cents, not dollars.

## How to spend almost nothing first

Prove the plumbing before paying for the sweep:

```bash
# one arm, one trial, on a cheap deployment — a fraction of a cent
python scripts/case_runner.py finance 1 --arms min_llmvalid_sched
```

Check the run directory has `events_*.jsonl`, `summary.json`, and
`prompts/`, then commit to the full run. The `--arms` flag scales cost
linearly: 4 arms ≈ 4/15 of the full price.

## What this estimate is based on (and its soft spots)

Anchored to the one measured number in the repo (13,314 tokens/trial for
the full STJP arm on finance) and the docs' 120k figure for global text;
the failing-arm figures are reasoned from step counts, not measured — so
treat the totals as ±50%, not ±10%. Prices are the public gpt-4o family
rates; if you run on a different deployment (the headline results used
gpt-5.4), re-do the dollar column with that model's rates. After your
first real run, replace this page's guesses with the actual
`summary.json` totals — one `--summarize-only` pass prints them.
