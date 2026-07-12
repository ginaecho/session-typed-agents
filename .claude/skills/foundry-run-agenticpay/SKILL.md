---
name: foundry-run-agenticpay
description: Run the agenticpay_settlement benchmark on Azure AI Foundry (the deadlock-vs-checked-protocol demo) across a matrix of Foundry model deployments, and read the results. Use when the user asks to run, sweep, or report on the agenticpay_settlement case on Azure AI Foundry, or asks to compare multiple Foundry model deployments on that benchmark.
---

# Run agenticpay_settlement on Azure AI Foundry

This skill is a runbook, not code — it tells a copilot or agent the exact
steps to execute the `agenticpay_settlement` benchmark case through Azure
AI Foundry (Microsoft's hosted service for running LLM "agents" — one
agent per role in this benchmark, each agent a thread of conversation with
a chosen model deployment) and how to read the results.

**What this benchmark shows:** two AI agents (a Buyer and a Seller) each
follow a perfectly reasonable rule — "don't pay until the goods arrive" /
"don't ship until you're paid." Read alone, each rule is sound caution.
Together they form a circular wait (a *deadlock*: everyone is stuck
waiting for someone else to move first, forever). A **checker** — a tool
called Scribble that mathematically analyzes a multi-agent conversation
protocol before any agent runs — can prove the rules are unsafe and forces
a fix: route the payment through a neutral third party (an *escrow*) that
holds funds until delivery is confirmed. The benchmark measures: does the
unchecked pair really deadlock, and does the checked (fixed) protocol
really complete, and at what token/call cost?

Full technical detail (why the arms are wired this way, what harness gap
exists, the field-by-field result table) lives in
`experiments/cases/agenticpay_settlement/foundry_run.md` — read that file
for anything this skill doesn't cover. This skill is the condensed
step-by-step version for a copilot execution loop.

## Prerequisites (do these once, on the machine that will run Foundry calls)

1. **Sign in to Azure**: run `az login` in a terminal on that machine. The
   harness authenticates using your logged-in Azure CLI session, not a
   separate API key.
2. **Set the required config keys** in `stjp_core/.env` (create the file if
   it doesn't exist — it is not checked into the repo, since it holds
   secrets/endpoints):

   | key | what it is |
   |---|---|
   | `AZURE_AI_PROJECT_ENDPOINT` | the URL of your Azure AI Foundry project |
   | `AZURE_OPENAI_DEPLOYMENT` | the name of one model deployment in that project (this gets overridden per model when you sweep the matrix — see below) |

   The full reference table (including two optional keys not needed for
   this benchmark) is in `stjp_core/CLAUDE.md` under "Env vars (in
   `.env`)".
3. **Create five model deployments** in your Azure AI Foundry project — one
   per model you want to compare. A "deployment" in Foundry is a named,
   ready-to-call instance of a model; the *name* you give it (not the
   underlying model's public name) is what this benchmark uses to select
   it. Record the five names — you will pass them as arguments in the
   sweep step below. This skill uses `opus-4.7`, `opus-4.6`, `sonnet-5`,
   `sonnet-4.6`, `haiku-4.5` as placeholder examples throughout; replace
   them with whatever you actually named your deployments.
4. Make sure the Python environment the `experiments/` scripts need is set
   up (dependencies installed) — see the repo's normal setup instructions.

## Step 1 — Generate the checked ("STJP") protocol draft for this case (one-time)

The benchmark's "checked" arms need a machine-validated protocol file that
doesn't exist yet for this case. Generate it:

```bash
cd experiments
python scripts/draft_llm_protocols.py agenticpay_settlement 10
python scripts/re_anchor_goals.py agenticpay_settlement valid
```

The first command asks an LLM (via Foundry) to draft a protocol from the
case's task description, up to 10 tries, and keeps the first draft that
passes the Scribble checker. The second command maps the benchmark's
success criteria (called "goals" — specific messages that must occur, like
"the escrow was funded with a positive amount") onto that draft's exact
message names. Both write into
`experiments/cases/agenticpay_settlement/protocols/llm_drafts/valid/`.
This step costs real LLM calls (through whichever deployment your `.env`
currently points at) but is independent of the model matrix — do it once,
not once per model.

## Step 2 — Run the two comparison arms

From the `experiments/` directory:

```bash
cd experiments
python scripts/case_runner.py agenticpay_settlement 6 \
  --arms unchecked_skills,spec_llmvalid,min_llmvalid
```

- `unchecked_skills` — each agent only gets its own hand-written rule.
  Expected: deadlock, 0 of 6 trials complete.
- `spec_llmvalid` — each agent gets the checked protocol from Step 1, in a
  detailed format.
- `min_llmvalid` — same checked protocol, in a compact format (usually
  cheaper in tokens, same correctness).
  Expected: both complete 6 of 6 trials.

`6` is the trial count used for the sibling `trade_deadlock` case's
published result; raise it (e.g. to 10 or 20) for a tighter estimate, at
proportional cost in LLM calls.

## Step 3 — Sweep the model matrix

Azure AI Foundry only looks at one model deployment per run (it is
selected once when the run starts, from the `AZURE_OPENAI_DEPLOYMENT`
value at that moment) — so comparing five models means running Step 2
five times, once per deployment name. A small wrapper script automates
that loop:

```bash
cd experiments/cases/agenticpay_settlement
./run_foundry_matrix.sh opus-4.7 opus-4.6 sonnet-5 sonnet-4.6 haiku-4.5
```

Replace the five names with your actual Foundry deployment names from
Prerequisites step 3. This script:
1. Sets `AZURE_OPENAI_DEPLOYMENT` to each name in turn.
2. Runs the Step 2 command for that deployment.
3. Tags the resulting output folder with the deployment name (in a
   `deployment.txt` file) and records it in
   `experiments/cases/agenticpay_settlement/runs/model_matrix_index.csv`,
   so you can tell which folder came from which model afterwards.
4. If one deployment's run fails (e.g. a misconfigured or missing
   deployment name), it logs the failure and moves on to the next
   deployment rather than stopping the whole sweep.

Override trial count or the arm list with environment variables, e.g.
`N_TRIALS=10 ./run_foundry_matrix.sh ...`. See the script's header comment
and `foundry_run.md` Section 4 for details.

## Where results land

Each run writes to a new, timestamped folder under
`experiments/cases/agenticpay_settlement/runs/`. Inside each folder:

- `summary.json` — the headline numbers per arm: what fraction of trials
  completed (`success_rate_pct`), average tokens spent per trial
  (`avg_tokens_per_trial`), average model calls per trial
  (`avg_calls_per_trial`), average wall-clock seconds per trial.
- `summary_eval.json` — whether the specific success criteria ("goals")
  were actually met, not just whether the conversation reached its
  terminal message.
- `events_<arm_name>.jsonl` — the full, message-by-message transcript for
  that arm, one JSON record per line.
- `prompts/<arm_name>/` — the exact instructions given to each simulated
  agent, so you can double check what it was actually told.
- `deployment.txt` — (only present if written by `run_foundry_matrix.sh`)
  which Foundry model deployment produced this folder.

## How to read the results (the comparison table)

For each model deployment, build a table like this straight from that
deployment's `summary.json` (all field names are exact JSON keys under
`scenarios.<arm_key>`):

| Measure | `unchecked_skills` | `spec_llmvalid` | `min_llmvalid` |
|---|---|---|---|
| Trades completed | `succeeded` / `n_trials` | `succeeded` / `n_trials` | `succeeded` / `n_trials` |
| Messages ever sent | `events` | `events` | `events` |
| Tokens per trial | `avg_tokens_per_trial` | `avg_tokens_per_trial` | `avg_tokens_per_trial` |
| Calls per trial | `avg_calls_per_trial` | `avg_calls_per_trial` | `avg_calls_per_trial` |

Expected pattern, matching the published result for the sibling
`trade_deadlock` case (`docs/results/RESULT_1_DEADLOCK.md`):
`unchecked_skills` at 0 completed trades out of N, with real messages sent
being at or near zero (the agents are stuck waiting, not doing anything
wrong — there is simply nothing legal left for either of them to send);
`spec_llmvalid` and `min_llmvalid` both at N out of N completed, with
`min_llmvalid` using noticeably fewer tokens per trial than `spec_llmvalid`
for the same outcome.

To compare across the five models, put one such table per model side by
side, or hand all five `summary.json` files plus
`model_matrix_index.csv` to the `foundry-benchmark-runner` subagent
(`.claude/agents/foundry-benchmark-runner.md`) and ask it to assemble the
combined comparison and flag anything that errored.

## Known gap in the harness (do not paper over this)

There is currently no way to run the "checked" arms directly against this
case's own hand-authored protocol file
(`experiments/cases/agenticpay_settlement/protocols/v1.scr`) without first
generating a separate, LLM-drafted copy of it (Step 1). This is a real
limitation of the benchmark harness, not a missing step in this skill —
full explanation in `foundry_run.md` Section 6. If Step 1's LLM-drafted
protocol turns out structurally different from the hand-authored one
(rare, but possible), note that in your report rather than treating the
two as interchangeable.
