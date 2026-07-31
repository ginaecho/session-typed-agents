# Archive Index — superseded documents, kept as frozen history

Nothing in this folder is current, and nothing in it gets edited — each file
is a snapshot of what the project believed at the time it was written. The
project keeps them because a benchmark whose design history can be replayed
is more trustworthy than one that only shows its final answer: for example,
you can open `EXPERIMENT_DESIGN_V3_EXECUTION.md` here, confirm its
predictions were committed *before* the 2026-07-02 run, and then check them
against the graded results — that audit is only possible because the
superseded design was archived instead of deleted.

Each entry below says what the file was and which current document replaced
it (the "successor"). Successor links point back up into `docs/`.

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [Designs and strategies](#designs-and-strategies)
- [Run reports and demo write-ups](#run-reports-and-demo-write-ups)
- [Research reports, analyses, and notes](#research-reports-analyses-and-notes)
- [Proposals that were retired](#proposals-that-were-retired)
<!-- MENU:END -->

## Designs and strategies

- [`TESTING_STRATEGY.md`](TESTING_STRATEGY.md) — The 2026-06-18 ground-up rethink of how to benchmark STJP fairly. Superseded by [`../2_TESTING_STRATEGIES.md`](../guides/2_TESTING_STRATEGIES.md) (same content, rewritten in plain English).
- [`BENCHMARK_DESIGN.md`](BENCHMARK_DESIGN.md) — The v2 scoring specification ("did the agents achieve the ultimate goal, and how?"). Its content was absorbed into [`../3_BENCHMARK_DESIGN_EXPLAINED.md`](../guides/3_BENCHMARK_DESIGN_EXPLAINED.md).
- [`BENCHMARK_DESIGN_V2_FROZEN.md`](BENCHMARK_DESIGN_V2_FROZEN.md) — A frozen snapshot of the v2 benchmark taken 2026-06-12, right after the grand n=10 run, kept as a revert point. Superseded by [`../3_BENCHMARK_DESIGN_EXPLAINED.md`](../guides/3_BENCHMARK_DESIGN_EXPLAINED.md).
- [`BENCHMARK_DESIGN_V3_CRITICALITY.md`](BENCHMARK_DESIGN_V3_CRITICALITY.md) — The criticality-aware testing design (severity grades S0–S4, critical properties C1–C3). Superseded for readers by [`../3_BENCHMARK_DESIGN_EXPLAINED.md`](../guides/3_BENCHMARK_DESIGN_EXPLAINED.md); kept as the technical original of that design.
- [`EXPERIMENT_DESIGN.md`](EXPERIMENT_DESIGN.md) — The v1 four-scenario experiment design (live Microsoft Agent Framework + Azure AI Foundry, 6 agents). Superseded by `EXPERIMENT_DESIGN_v2.md` below.
- [`EXPERIMENT_DESIGN_v2.md`](EXPERIMENT_DESIGN_v2.md) — The 8-arm comparison design (MPST vs intent-only). Superseded by `EXPERIMENT_DESIGN_V3_EXECUTION.md` below.
- [`EXPERIMENT_DESIGN_V3_EXECUTION.md`](EXPERIMENT_DESIGN_V3_EXECUTION.md) — The pre-registered execution-plane design whose predictions the 2026-07-02 run graded. Its results write-up is [`../results/RESULT_04_FULL_STACK.md`](../results/RESULT_04_FULL_STACK.md).

## Run reports and demo write-ups

- [`RUN_REPORT_2026-07-02.md`](RUN_REPORT_2026-07-02.md) — The technical report of the pre-registered 2026-07-02 finance run. Rewritten in plain English as [`../results/RESULT_04_FULL_STACK.md`](../results/RESULT_04_FULL_STACK.md).
- [`RESULTS_finance_n10.md`](RESULTS_finance_n10.md) — The technical report of the n=10 finance run (2026-05-21). Rewritten as [`../results/RESULT_03_PROTOCOL_LADDER.md`](../results/RESULT_03_PROTOCOL_LADDER.md).
- [`DEADLOCK_DEMO.md`](DEADLOCK_DEMO.md) — The technical original of the deadlock demo (2026-06-17). Rewritten as [`../results/RESULT_01_DEADLOCK.md`](../results/RESULT_01_DEADLOCK.md).
- [`TOKEN_EFFICIENCY_DEMO.md`](TOKEN_EFFICIENCY_DEMO.md) — The technical original of the token-efficiency demo (2026-06-17, companion to the deadlock demo). Rewritten as [`../results/RESULT_02_TOKEN_EFFICIENCY.md`](../results/RESULT_02_TOKEN_EFFICIENCY.md).

## Research reports, analyses, and notes

- [`STJP_RESEARCH_REPORT.md`](STJP_RESEARCH_REPORT.md) — The full technical report (2026-06-12) through the n=5 gate result. Its material now lives across the numbered guides and [`../results/`](../results/README.md).
- [`WHY_B_MATCHES_C_ANALYSIS.md`](WHY_B_MATCHES_C_ANALYSIS.md) — The honest confound analysis of why "protocol pasted as text" matched "projected contracts" on a strong model. Its conclusions now live in [`../2_TESTING_STRATEGIES.md`](../guides/2_TESTING_STRATEGIES.md).
- [`DRAFTING_IMPROVEMENTS.md`](DRAFTING_IMPROVEMENTS.md) — Why early LLM-drafted protocols failed validation, and the fan-out normalizer fix. The current story of the drafting step is [`../8_INTENT_TO_PROTOCOL_TRAINING.md`](../guides/8_INTENT_TO_PROTOCOL_TRAINING.md).
- [`GOVERNANCE_TOOLKIT_ASSESSMENT.md`](GOVERNANCE_TOOLKIT_ASSESSMENT.md) — Assessment of the Microsoft Agent Governance Toolkit for reuse. Synthesized into [`../reference/STJP_V3_PLAN.md`](../reference/STJP_V3_PLAN.md).
- [`RELATED_WORK_DELM.md`](RELATED_WORK_DELM.md) — Review of DeLM (decentralized language models) as related work. Synthesized into [`../reference/STJP_V3_PLAN.md`](../reference/STJP_V3_PLAN.md).
- [`STJP_discussion_13May2025.md`](STJP_discussion_13May2025.md) — Meeting notes from the 13 May discussion. The ongoing journal lives in [`../diary/DIARY.md`](../diary/DIARY.md).

## Proposals that were retired

- [`EVOLUTION_DEMO_DESIGN.md`](EVOLUTION_DEMO_DESIGN.md) — Design for the "the demand changed on Tuesday" evolution demo. The protocol-evolution capability it sketched is documented in [`../reference/PROTOCOL_EVOLUTION.md`](../reference/PROTOCOL_EVOLUTION.md).
- [`SKILLS_COMPILER_PROPOSAL.md`](SKILLS_COMPILER_PROPOSAL.md) — Early "skills compiler" proposal (action-flow type-checking + security validation). Retired; the idea that survived is documented in [`../reference/SKILL_COMPACTION.md`](../reference/SKILL_COMPACTION.md).
- [`APPLICATION_SCENE_VIEW_PROPOSAL.md`](APPLICATION_SCENE_VIEW_PROPOSAL.md) — Proposal for an "application-scene view" of the live demo (2026-06-08, never built). Retired without a direct successor; presentation assets live in the repo-root `pitch/` directory.
