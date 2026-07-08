# COST_ESTIMATE — what the n=100 validation suite cost in Claude API tokens

*2026-07-05. The whole arm-ladder suite was run with **cheap haiku subagents
playing the agent roles** while opus only orchestrated. This estimates the
dollar cost from the two things we actually know: the per-trial token counts the
Agent tool reported (`subagent_tokens`) and the published per-token API pricing.
It is an **estimate from observed token counts × list price**, not a metered
invoice — see the caveat.*

## Pricing used (per 1M tokens, cached 2026-06-24 from the `claude-api` skill)

| Model | Input | Output |
|---|---|---|
| Haiku 4.5 | $1.00 | $5.00 |
| Sonnet 5 | $3.00 ($2.00 intro through 2026-08-31) | $15.00 ($10.00 intro) |
| Opus 4.8 | $5.00 | $25.00 |

## Method

The Agent tool reported **total** `subagent_tokens` per trial-driver:
**~22–38k** for haiku drivers, **~36–44k** for sonnet. We don't have the exact
input/output split, but for these trials **input dominates** — the system
prompt, the tool schemas, and the entire accumulated protocol view are re-sent
on every poll, while the output is a short JSON decision. Using an **~85% in /
15% out** blend:

- **Haiku** blended ≈ 0.85·$1.00 + 0.15·$5.00 = **$1.60 / 1M**
- **Sonnet (intro)** blended ≈ 0.85·$2.00 + 0.15·$10.00 = **$3.20 / 1M**
  (standard, post-intro: **$4.80 / 1M**)
- **Opus** blended ≈ 0.85·$5.00 + 0.15·$25.00 = **$8.00 / 1M**

### The one honest caveat — this is an upper bound

`subagent_tokens` counts the **driver's CLI/orchestration overhead** (tool-call
schemas, JSON framing, per-poll reasoning), not just the role's decision. So
these figures are what it *would have cost to run the trials as billed API
subagents* — they **overstate** the pure agent-role cost. A lean
LangGraph-metered run (role prompt in, ~1 line of JSON out ≈ 1–3k tok/trial)
would be **~10–20× cheaper per trial**; see the lower bound below.

## Per-trial cost

| Model | tokens/trial | blended rate | **$/trial** |
|---|---|---|---|
| Haiku | ~30k | $1.60/1M | **~$0.05** (range $0.035–0.06) |
| Sonnet (intro) | ~40k | $3.20/1M | **~$0.13** (standard ~$0.19) |

## Per-arm cost-to-goal, in dollars (the `$` column in the ladder tables)

The ladder tables report **cost-to-goal in calls** (`total calls ÷
GCR-fraction`) because the no-Foundry runs weren't token-metered. To put that in
money, price **one lean call**: a production agent call is ~1,000 input tokens
(role prompt + short view) + ~50 output tokens. At Haiku 4.5's $1.00 / $5.00 per
1M:

> **lean call ≈ 1,000·$1.00/1M + 50·$5.00/1M = $0.00100 + $0.00025 ≈ $0.00125**
> (≈ **$1.25 per 1,000 calls**)

`Cost-to-goal ($) = Cost-to-goal (calls) × $0.00125`:

| arm | revenue_audit calls → **$** | escrow_trade calls → **$** |
|---|---|---|
| A: Intent only | 900 → **$1.12** | 3349 → **$4.19** |
| B: Global text | 330 → **$0.41** ⚠️ | 3512 → **$4.39** |
| C-min: Local contract | 7275 → **$9.09** | 2708 → **$3.38** |
| C+spec: Local + gate | 928 → **$1.16** | 2883 → **$3.60** |
| C+min: Local + gate | 900 → **$1.12** | 2978 → **$3.72** |
| **STJP: +scheduler** | **300 → $0.38** | **714 → $0.89** |

**STJP is the cheapest *safe* arm in both cases** ($0.38 / $0.89). ⚠️ In
`revenue_audit`, B's $0.41 undercuts STJP only because it *races* — it reaches
the goal in one round by filing before approval, which is the **95-disaster**
result, not a genuine saving. C-min's $9.09 is the real blowout: its 32%
liveness means ~3× the calls per delivered audit.

This is a **lean-deployment** price. It is *lower* than the as-run figures below
because those were played by CLI-driver subagents whose per-call token use is
dominated by orchestration overhead — the $ column is what a metered production
deployment would pay, the per-trial figures below are what these particular
experiment drivers cost.

## Whole-suite cost (if billed as API subagents)

| Run | trials | $/trial | **subtotal** |
|---|---|---|---|
| Haiku n=100 ladder (2 cases × 6 arms × 100) | ~1,200 | $0.05 | **~$60** ($42–73) |
| Sonnet P0b + E3 (B n=30, A/C+min n=10 each) | ~80 | $0.13 | **~$10** |
| **Total** | | | **≈ $70–85** |

## What this says

- The **entire n=100 arm-ladder** — the headline 95-disaster result, both use
  cases, all six arms — cost on the order of **$60 in haiku tokens**; the
  stronger-tier sonnet replication (P0b/E3) added **~$10**. The whole validated
  suite is **under $100.**
- Running the *roles* on **haiku** while **opus** only *orchestrated* is exactly
  what kept it this cheap. Haiku is ~5× cheaper than sonnet and ~5× cheaper than
  opus on output, so the same 1,200 trials with:
  - **sonnet** roles ≈ **~$160**
  - **opus** roles ≈ **~$300+**
- **Lean lower bound.** Metered through the LangGraph harness (role-only tokens,
  no CLI driver overhead), the same 1,200 haiku trials would land around
  **$5–10**, not $60. The overhead is the driver, not the agent.

## Provenance / limits

- Token counts: per-trial `subagent_tokens` reported by the Agent tool during the
  runs (haiku ~22–38k, sonnet ~36–44k). Not independently re-metered.
- Prices: `claude-api` skill pricing table, cached 2026-06-24.
- These are **estimates**, not metered invoices. Real metered numbers need an
  LLM API key; the LangGraph harness
  (`experiments/harness_adapters/langgraph_ladder.py`) is wired to capture exact
  input/output token usage the moment one is provided — at which point the "lean
  lower bound" above becomes a measured figure.

See also:
- [`LADDER_NOFOUNDRY.md`](LADDER_NOFOUNDRY.md) — the suite this prices.
- [`P0B_MIDTIER_SONNET.md`](P0B_MIDTIER_SONNET.md) and
  [`E3_CAPABILITY_SWEEP.md`](E3_CAPABILITY_SWEEP.md) — the sonnet runs.
- [`../../harness_adapters/README.md`](../../harness_adapters/README.md) — the
  metering-ready harness that turns the lean lower bound into a measured number.
- Plain-English docs: `docs/6_RUN_REPORTS_EXPLAINED.md`
  [§2 (Reading the results table)](../../../docs/6_RUN_REPORTS_EXPLAINED.md#2-reading-the-results-table)
  and
  [§10 (what this reproduction actually cost)](../../../docs/6_RUN_REPORTS_EXPLAINED.md#what-this-reproduction-actually-cost-in-dollars).
