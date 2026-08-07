# The Benchmark — what it is and how to run it

**Date: 2026-08-07.** This is the one-page guide to the benchmark for
anyone joining the project. It explains, in plain English, what the
benchmark measures, what we compare, which test cases we run (ranked, with
reasons), and the exact steps to run it yourself. Every other benchmark
document lives in this same folder and is listed at the bottom.

---

## 1. What this benchmark measures

We build teams of AI agents — several AI "roles" that talk to each other
to finish one job (for example: an author writes code, four reviewers
check it, a merger combines it, and a deploy role ships it).

Today, people steer such teams with plain-written instruction files.
Nobody checks those files for logical mistakes, so a team can get stuck
waiting on each other forever, skip a required approval, or do something
irreversible in the wrong order (like deploying before tests pass).

Our system (called **STJP**) works differently: it first writes the
team's plan in a form a checking tool can verify is safe, then gives each
role only its own small slice of the plan, and enforces the plan while
the team runs.

The benchmark answers three questions, with numbers:

1. **Does the team finish the job correctly more often?**
2. **Is it cheaper?** (fewer AI calls, fewer tokens — tokens are the
   small billing units AI providers charge by — and fewer dollars)
3. **Is it safer?** (does it ever do an irreversible step out of order?)

## 2. What we compare — the 10 setups

A **setup** (called an "arm" in our files, like one arm of a clinical
trial) is one way of configuring the team. All setups run the *same* job
with the *same* AI model; the only difference is how much of the plan
each role gets, and how strictly it is enforced.

There are five levels of structure, each tested on two different "engines"
that take turns for the team:

- **our simple turn-taker** — roles speak in a fixed circle, one after
  another;
- **Microsoft's group-chat tool** (part of the Microsoft Agent Framework,
  "MAF") — an extra AI "orchestrator" reads the conversation and decides
  who speaks next. Setups on this engine have names starting with `maf_`.

| level of structure | our turn-taker | Microsoft's tool |
|---|---|---|
| Real published skill files, **no plan at all** (the baseline) | `skills` | `maf_skills` |
| Every role gets the **whole checked plan** as text | `globalvalid` | `maf_globalvalid` |
| Every role gets **only its own slice** of the plan | `localvalid` | `maf_localvalid` |
| Own slice **plus a checker that blocks** rule-breaking messages | `localvalid_gate` | `maf_localvalid_gate` |
| Own slice + checker **plus the plan itself picks whose turn it is** | `localvalid_sched` | `maf_localvalid_sched` |

`localvalid_sched` is our full system. Reading down a column shows what
each added piece of structure buys; reading across a row shows whether the
engine matters. The word "valid" in a name means the plan passed our
safety checker before anyone ran it.

## 3. The 4 AI models

Every setup runs on four models — two families, each at a strong and a
weaker level — so we can show results do not depend on one vendor or one
model size:

| | closed-source (GPT) | open-weight (DeepSeek) |
|---|---|---|
| **strong** | `gpt-5.6-sol` | `DeepSeek-V4-Pro` |
| **weaker** | `gpt-5-mini` | `DeepSeek-V4-Flash` |

All four are deployments on the same Azure account.

## 4. The test cases, ranked — which to run first and why

Each test case is a realistic team job. We ranked them by four things:
**team size** (our savings grow with more roles), **how much it looks
like real work**, **where the files came from** (copied from real
published projects beats written by us), and **how much decision-making
it involves** (branching and looping jobs show the turn-picker's value
best; simple straight-line jobs are the honest, conservative
counterweight).

**Tier 1 — run these six first (the headline set):**

| rank | case | roles | why it ranks here |
|---|---|---|---|
| 1 | `sdlc_release_gate` | 7 | A software release gate: one author, four independent reviewers, a merger, a deploy role. Copied word-for-word from a real public project. Every software company runs this workflow, and its worst failure (deploying before tests finish) is instantly recognizable. |
| 2 | `gem_dev_team` | 7 | A full self-running software team (planner, builder, reviewer, tester, and so on). Also copied from a real public project — the "AI coding team" story every developer knows. |
| 3 | `report_pipeline_large` | 10 | The biggest team. Best shows why giving each role only its own slice matters: the whole-plan-to-everyone approach gets more expensive as the team grows; ours does not. Deliberately a simple straight-line job, kept in as the honest counterweight. |
| 4 | `react18_migration` | 6 | A phased software upgrade done the way real developers do it, copied from a real public project. A genuine developer pain point. |
| 5 | `finance` | 6 | Our first published case — every earlier result table used it, so it connects old and new results. Its approval-depends-on-the-amount branching is a realistic business process. |
| 6 | `rag` | 6 | Search-and-answer with a fact-check loop — the most common multi-role AI pattern people build today. |

**Tier 2 — add as budget allows:** `travel` (booking rollback across
flight, hotel, and car), `intel_report` (three sources feeding one
writer — the pattern where cheap turn-picking shortcuts fail),
the AgenticPay cases (payment teams adapted from a real project,
including the deadlock demonstration case `agenticpay_settlement`),
`banking`, `clinical_enrollment`, `pr_review_merge`, and
`doc_coauthor_ship` (built from Anthropic's own published skill files).

**Tier 3 — don't spend budget here:** older versions of cases that were
replaced, tiny 3–4-role demos, and single-purpose demonstration cases.
Each is run only if a specific report section needs it.

The full ranking, with every criterion and every case, is in
[`BENCHMARK_CASE_RANKING.md`](BENCHMARK_CASE_RANKING.md).

## 5. How a run is scored

Scoring is mechanical — a script checks the recorded conversation; no AI
judge, no opinions.

- **Did it finish?** Each case defines a handful of goals (for the
  release case: the security review passed before merging, the deploy
  happened, and so on). A run succeeds only if every goal appears in the
  conversation. Setups that were never shown the plan's official message
  names are graded on content rather than exact names — that keeps the
  comparison fair to them.
- **Did it break rules?** Every message is checked against the plan.
  Rule-breaks are graded on a five-level severity scale, from harmless
  reordering up to "did something irreversible out of order."
- **What did it cost?** Tokens are the main measure; failed attempts
  count too (the honest-bookkeeping rule). Every summary also converts
  tokens to **dollars** using each model's verified price sheet, because
  the four models differ in price by more than 10×.
- **How sure are we?** Every percentage carries a statistical confidence
  range; headline claims need 30 runs per cell.

## 6. How to run it — the short version

One-time machine setup (Azure login, the two protocol-checking tools,
Microsoft's agent framework) and the traps a fresh machine will hit are
in [`BENCHMARK_IMPLEMENTATION_STEPS.md`](BENCHMARK_IMPLEMENTATION_STEPS.md) —
**read its section 0a first; it will save you a day.**

Then, per case, in order:

1. **Build the task package** (the written job description the team works
   from, plus one short brief per role):
   `python experiments/scripts/intent_pipeline.py synth <case>`
2. **Check the plan is safe** (both checkers, verdicts recorded):
   `python experiments/scripts/validate_protocol_provenance.py <case>`
3. **Do a small check run first** — 1 trial of each of the 10 setups on
   each of the 4 models (40 trials), to confirm everything works before
   spending real money. The campaign driver is
   `experiments/scripts/hosted_campaign.py`; use `--preflight-only` to
   test the plumbing without running trials.
4. **Run the full campaign** — 10 setups × 4 models × 30 trials.
   **This costs real money — get the project owner's go-ahead first.**
   If a run is interrupted, continue it with `--resume <run-folder>`;
   finished cells are skipped, nothing is re-paid.
5. **Score and price it** — scoring runs automatically; then
   `python experiments/scripts/cost_summary.py <run-folder> --write`
   adds the dollar figures.

Results land in `experiments/cases/<case>/runs/<run-folder>/` — the raw
conversation logs, the exact instructions every role was given, the task
description used, and the score summaries. Every trial also leaves a
verifiable record on the Azure portal, so no result depends on trusting
our local files.

Standing rules: only run paid trials when the project owner has said go;
one campaign at a time; "stop" means stopping the servers, the driver,
and any watcher loops together.

## 7. Where the results live

This folder is the **methodology** — what we test and how to run it. The
**results** live in two places:

- [`../results/`](../results/README.md) — the numbered evidence reports
  (`RESULT_01` through `RESULT_13`), each written in plain English: why
  the experiment was run, the numbers, and what they mean.
- [`analysis/`](analysis/) (in this folder) — shorter per-model,
  per-case analysis notes from individual runs.

The raw data behind every report — conversation logs, prompts, and score
summaries — is committed under `experiments/cases/<case>/runs/`.

## 8. Every document in this folder

| document | what it is for |
|---|---|
| **`README.md`** (this file) | The plain-English overview: what, why, and how to run it. |
| [`BENCHMARK_HANDOFF.md`](BENCHMARK_HANDOFF.md) | The detailed handoff for whoever runs the campaign next: the full reasoning behind the 10 setups, the fairness rules, and the complete run checklist. |
| [`BENCHMARK_PLAN_V3.md`](BENCHMARK_PLAN_V3.md) | The full design document and its history. Section 10.8 is the authoritative list of setup names. |
| [`BENCHMARK_IMPLEMENTATION_STEPS.md`](BENCHMARK_IMPLEMENTATION_STEPS.md) | The step-by-step setup and run guide, including every known infrastructure trap. |
| [`BENCHMARK_CASE_RANKING.md`](BENCHMARK_CASE_RANKING.md) | The full case ranking summarized in section 4 above. |
| [`BENCHMARK_FAIRNESS_REVIEW.md`](BENCHMARK_FAIRNESS_REVIEW.md) | The skeptical audit that found the unfairness problems and led to the current design. (Uses older setup names; PLAN_V3 §10.8 maps them.) |
| [`BENCHMARK_TIMELOG.md`](BENCHMARK_TIMELOG.md) | Measured timings from real runs, for estimating how long remaining work will take. |
| [`MAF_TOKEN_ACCOUNTING_HANDOFF.md`](MAF_TOKEN_ACCOUNTING_HANDOFF.md) | How token counting works for the Microsoft-tool setups, and how older runs were reconciled. |
| [`HOW_TO_RUN_BENCHMARKS.md`](HOW_TO_RUN_BENCHMARKS.md) | The run procedure for the **older, pre-campaign** local runner (`case_runner.py`) — still valid for re-running earlier published results. New campaign runs use the steps in section 6 above instead. |
| [`analysis/`](analysis/) | Per-model, per-case analysis write-ups from earlier runs. |

One historical document is deliberately **not** here: the previous plan
(v2), which designed the already-completed tool-hardening experiments
reported in [`../results/RESULT_06_BENCHMARK_HARDENING.md`](../results/RESULT_06_BENCHMARK_HARDENING.md).
It lives in [`../archive/BENCHMARK_PLAN_V2.md`](../archive/BENCHMARK_PLAN_V2.md)
with the other superseded designs, so this folder only contains what you
need for the current campaign.
