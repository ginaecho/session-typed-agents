# Benchmark Case Ranking — which real use cases to run, in what order

**Date: 2026-08-05.** Companion to [`BENCHMARK_PLAN_V3.md`](BENCHMARK_PLAN_V3.md)
(§10.6 explains why we picked this set of test setups; §10.7 rule R6 lists
extra checks we owe). This document ranks every runnable case in
`experiments/cases/` for the fair-comparison campaign (our full round of
test runs) and says how much of the campaign's budget each case deserves.

## Menu

- [Ranking criteria](#ranking-criteria)
- [Tier 1 — headline cases (run first)](#tier-1--headline-cases-run-first)
- [Tier 2 — strong supporting cases](#tier-2--strong-supporting-cases)
- [Tier 3 — do not spend campaign budget here](#tier-3--do-not-spend-campaign-budget-here)
- [Recommendation](#recommendation)
- [Honest caveat for the report](#honest-caveat-for-the-report)
- [Inventory notes](#inventory-notes)

## Ranking criteria

We ranked cases on two main measures, plus two tie-breakers that decide
what the benchmark can actually prove:

1. **Number of roles (team size)** — more roles is better. Two of our key
   benefits — smaller prompts from "projection" (giving each role only its
   own instructions instead of the whole plan) and time saved by the
   scheduler (the part that decides whose turn is next) — both grow with
   team size. Our published results show 55% savings at 4 roles, rising to
   91% at 6 roles. Bigger teams show the benefit of our approach most
   clearly.
2. **How familiar the case is to real developers** — the more a case looks
   like real work, the better. A reviewer should look at it and think "my
   organization runs exactly this workflow."
3. *(tie-breaker)* **Where the case files came from ("provenance")** —
   best to worst: skill files copied word-for-word from real published
   projects; skill files adapted from real projects; files we wrote
   ourselves for this benchmark ("purpose-built"). Cases whose
   `skills_original/` files were copied unchanged from public code
   repositories (recorded in a `SOURCES.md` file) support the claim "this
   happens with real deployed work, not with examples we invented to make
   our point."
4. *(tie-breaker)* **How rich the decision-making is** — cases with
   branching decisions and repeating loops are better than simple,
   straight-line ("linear") cases. In a simple round-by-round turn order
   ("round-robin"), roles waste turns waiting at decision points.
   Straight-line cases don't show the scheduler's value as clearly — and
   a cheap shortcut nicknamed `lastrecv` ("just ask whoever received the
   last message") comes close to matching the scheduler there. See
   FAIRNESS_REVIEW, Problem 4, for that finding.

## Tier 1 — headline cases (run first)

Run our core set of 10 setups (PLAN_V3 §10.8) on all six cases below, with
all 4 AI models (the 2-by-2 set in PLAN_V3 §1). (A "setup," which we call an "arm" elsewhere in this project,
is one configuration being compared — for example, with or without the
safety checker.)

| # | case | roles | where it came from | pattern | why it ranks here |
|---|---|---|---|---|---|
| 1 | `skills_safety/sdlc_release_gate` | **7** | **copied word-for-word** from github/awesome-copilot (MIT license) | branching + looping | Release gating: one author plus FOUR independent reviewers (quality, security, architecture, responsible AI), then a merger and a DevOps role. Every software organization runs a workflow like this; its worst possible failure — what we call "S4" elsewhere in this project — is deploying before tests are done. Best mix of size, realism, and industry recognition. |
| 2 | `skills_safety/gem_dev_team` | **7** | **copied word-for-word** from awesome-copilot `gem-*` | branching + looping | A full self-running software team (orchestrator, planner, builder, reviewer, critic, browser-tester, DevOps) — the "AI coding team" story every developer recognizes. |
| 3 | `report_pipeline_large` | **10** | written by us for this benchmark | straight-line | The most roles of any case here, and it best shows why smaller, per-role instructions matter: giving every role the whole plan gets more expensive as the team grows, while giving each role only its own part stays the same size. Its one weakness is being straight-line rather than branching — which is exactly why we keep it in the headline set, as a conservative counterweight (see the caveat below). |
| 4 | `skills_safety/react18_migration` | 6 | **copied word-for-word** from awesome-copilot `react18-*` | branching + looping | A phased software-framework upgrade (audit, then dependencies, then old-style components, then batching, then tests), run the way developers actually do it. A real pain point for developers. |
| 5 | `finance` | 6 | written by us for this benchmark | branching | Our **first published case** (30 test runs; every finding used it). We keep it at the top regardless of where it came from, because it connects to every earlier results table, and its compliance-approval branching is a genuinely realistic business process. |
| 6 | `rag` | 6 | written by us for this benchmark | branching + **looping** | Search-and-answer with a fact-check loop that stops after a limit — the single most common multi-role AI pattern developers build today. We wrote this case ourselves, but the pattern itself is unquestionably realistic. |

## Tier 2 — strong supporting cases

Add these as budget allows, in this order. Run `intel_report` first (it
covers an extra required check — see row 8), then one AgenticPay case (a
finance-technology story).

| # | case | roles | where it came from | why |
|---|---|---|---|---|
| 7 | `travel` | 6 | written by us for this benchmark | An all-or-nothing rollback across flight, hotel, and car bookings — if one part fails, the rest must be undone, including proper error handling. A classic industry pattern. |
| 8 | `intel_report` | 6 | written by us for this benchmark | Three sources feeding into one role ("fan-in") — the pattern where the cheap "ask whoever received the last message" shortcut fails, and our scheduler (which follows a diagram of each role's allowed next moves) has to prove its worth. Running this case covers a required check on that shortcut for a case with this fan-in pattern. |
| 9 | `agenticpay_multi_buyer` / `agenticpay_multi_seller` | 5 | **adapted from a real project** (SafeRL-Lab/AgenticPay, MIT license) | Many participants competing for the same resource can get stuck ("deadlock") during payment — a realistic problem in financial technology and the growing trend of AI agents handling commerce. |
| 10 | `banking` | 5 | written by us for this benchmark | Whether a payment is approved depends on its amount, with a separate path for rejected requests. This is the case behind a real story in our paper: four draft attempts were rejected before the fifth one passed. |
| 11 | `clinical_enrollment` | 5 | written by us for this benchmark | Consent must come before enrollment — a realistic story from a regulated industry (healthcare). |
| 12 | `skills_safety/pr_review_merge` | 4 | **copied word-for-word** from awesome-copilot | Only 4 roles, but the **best of the small cases**: a core developer workflow (reviewing and merging a code change), with branching and looping, and we already have evidence for it (see CASE 11). |
| 13 | `skills_safety/doc_coauthor_ship` | 4 | **copied word-for-word** from Anthropic's `anthropics/skills` (Apache-2.0 license) | Documents must pass a brand review before shipping. Extra value: the skill files come from Anthropic's own public repository, which makes the source especially convincing. |
| 14 | `agenticpay_settlement` | 4 | adapted from a real project | Small, but we keep it for consistency with earlier work: it is the second case in our published results (with tables based on 10 runs), and it is the case we use to demonstrate deadlock. |

## Tier 3 — do not spend campaign budget here

- **Old versions, replaced by newer ones** — run only the corrected,
  newer case: `skills_safety/pr_merge` was replaced by `pr_review_merge`;
  `skills_safety/doc_pipeline` was replaced by `doc_coauthor_ship`;
  `report_pipeline` (6 roles) was replaced by `report_pipeline_large`
  (10 roles) — keep the 6-role version only as one data point on the
  team-size chart (`scripts/scaling_chart.py`).
- **Small real-skill test cases** (3–4 roles): `skills_safety/code_execution`
  (from the AutoGen framework), `skills_safety/booking_saga` (from
  LangGraph), `skills_safety/airline_seat` (from the OpenAI Agents SDK),
  `skills_safety/content_pipeline` (from CrewAI). Their value is showing
  that the same failure pattern shows up across four different frameworks'
  real published work — not adding many extra test runs. Run these with a
  small number of trials, for the appendix only.
- **Cases that demonstrate one specific pattern**: `retry_loop`,
  `iterative_polling`, `nested_retry` (cover the loop and branch
  patterns), `auction` (many bidders feeding into one decision),
  `planner_workers`, `finance_nested` (a nested, two-level decision),
  `travel_saga`, `trade_settlement` / `trade_deadlock` (demonstrate
  deadlock), `memory_race` (two roles overwriting each other's update,
  checked by a tool that tracks the true state). Each one exists to prove
  a single point in one section of the report; none belongs in the main
  test grid.

## Recommendation

1. **Main test round** = our core set of 10 setups × the 6 Tier-1 cases ×
   2 models. This covers 7-role and 10-role teams, three developer-team
   cases copied word-for-word from real projects, and both cases already
   used in our earlier published results.
2. **Then run Tier 2**, starting with `intel_report` (including the extra
   `lastrecv` shortcut-comparison check on it) and one AgenticPay case.
3. **Only run Tier 3** cases where a specific report section needs them
   (the deadlock demo, the race-condition check, the team-size chart, or
   the appendix showing the pattern holds across frameworks).

Before any test run for a case, its **intent package** must exist. (The
intent package is the written description of what the team is trying to
accomplish, used to brief the AI roles — see PLAN_V3 §10.7 rule R4.) Build
it with: `python experiments/scripts/intent_pipeline.py synth --all`. This
produces a computer-generated package, openly labeled as such
(`approved_by: auto-llm`, meaning a script approved it, not a person).

## Honest caveat for the report

The two biggest developer cases (`sdlc_release_gate` and `gem_dev_team`)
both have branching and looping — exactly the pattern where the
scheduler's time savings show up best. Ranking them first makes sense
because they look like real work, but the report must also include the
straight-line case (`report_pipeline_large`) in the same headline results
table. That way, the savings figure is shown across the full range of
patterns (straight-line, then branching, then looping), not only where it
looks best. This matches our published comparison across cases (55% up to
91% savings) and keeps the claim solid enough to survive an audit.

## Inventory notes

- We took this list of cases on 2026-08-05 from each case's settings file
  (`experiments/cases/*/case.yaml`, which lists its roles and goals) and
  its protocol file (the `.scr` file, which uses the keywords `choice at`
  for decision points and `rec` for loops). Where a case came from real
  published skills, that is recorded in `skills_safety/*/SOURCES.md`
  (source project, license, and the date we copied it).
- "Copied word-for-word" means the `skills_original/` files were copied
  unchanged from the public code repository named in that case's
  `SOURCES.md` file (which also records the commit and copy date).
  "Adapted from a real project" means we started from real personas or
  skill files and added our own logic for settlement or contention (also
  written up in `SOURCES.md`). "Written by us for this benchmark" means we
  wrote the case ourselves.
- Role counts and patterns: `sdlc_release_gate` 7 (branching + looping),
  `gem_dev_team` 7 (branching + looping), `report_pipeline_large` 10
  (straight-line), `react18_migration` 6 (branching + looping), `finance`
  6 (branching, 6 goals), `rag` 6 (branching + looping), `travel` 6
  (branching), `intel_report` 6 (fan-in), `agenticpay_multi_*` 5,
  `banking` 5 (branching), `clinical_enrollment` 5, `pr_review_merge` 4
  (branching + looping), `doc_coauthor_ship` 4 (branching + looping),
  `agenticpay_settlement` 4 (straight-line).
