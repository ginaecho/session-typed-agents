# Seam reports — index

Internal working reports from the seam-training program. The "seam" is the
intent-to-protocol translation step — a plain-language request becomes a
Scribble-validated protocol — and the program's goal is to train a model to
do that step well. `W*` files are worker task-card reports and `R*` files
are read-only scout reports; both id schemes come from
[`../../SEAM_TRAINING_EXECUTION_PLAN.md`](../../SEAM_TRAINING_EXECUTION_PLAN.md)
(§9 task cards, §1 operating model).

## Program-level reports

- [`AUDIT_INTENT_TO_PROTOCOL_2026-07-11.md`](AUDIT_INTENT_TO_PROTOCOL_2026-07-11.md) — independent verification that the seam implementation is really on this branch and really works: exact commands plus verbatim output tails, so no worker's prose has to be trusted.
- [`BRANCH_CONSOLIDATION.md`](BRANCH_CONSOLIDATION.md) — record of consolidating everything the program produced onto one branch, with the merge log and the list of superseded branches safe to delete.
- [`PANEL_SMOKE_2026-07-11.md`](PANEL_SMOKE_2026-07-11.md) — first live run of the faithfulness judge panel: 3 known-good (intent, protocol) pairs plus 1 planted mismatch, judged by 14 isolated seats.

## Worker reports (W*)

- [`W1_eval_harness.md`](W1_eval_harness.md) — the Seam-Bench evaluation harness: metric block, data splits, JSONL schema, and the report generator.
- [`W2_grammar_gcd.md`](W2_grammar_gcd.md) — a Lark grammar for the Scribble surface syntax plus the vLLM adapter for grammar-constrained decoding (forcing every model draft to be parseable protocol text).
- [`W3_data_builders.md`](W3_data_builders.md) — the D1–D3 training-data builders (protocol expansion, back-translation to intents, repair tuples) and the signature-based dedupe/splitter.
- [`W4_t0_runner.md`](W4_t0_runner.md) — the T0 baseline runner: how well untrained API models draft protocols, filling the pending E5 cells.
- [`W6_judge_panel.md`](W6_judge_panel.md) — the faithfulness judge panel implementation: five isolation layers, canary battery, and code-only aggregation.
- [`W8_miner.md`](W8_miner.md) — the real-world skills miner (D5) with its provenance/license ledger; a measured-yield report (deterministic-only yield was 0%, and why that was expected).
- [`W15_recursion_gen.md`](W15_recursion_gen.md) — a recursion generator for D1: the recursion axis of the training data grew from ~9 families to 200+.
- [`W16_llm_read_extraction.md`](W16_llm_read_extraction.md) — LLM-read extraction over W8's 13 mined teams: can a model recover coordination structure that deterministic parsing could not?
- [`W17_coordination_scale_up.md`](W17_coordination_scale_up.md) — a coordination filter plus a mining scale-up, growing the "real skills don't state their coordination" evidence past n=2.
- [`W19_SELF_OBSERVED_COORDINATION_FAILURES.md`](W19_SELF_OBSERVED_COORDINATION_FAILURES.md) — case study: four real coordination failures from this project's own planner-and-workers build, and the protocol that would have prevented each.

## Scout reports (scouts/R*)

- [`scouts/R1_literature.md`](scouts/R1_literature.md) — literature sweep: does anything in the 2024–2026 literature change the training plan's design or its novelty claim?
- [`scouts/R2_training_stack.md`](scouts/R2_training_stack.md) — training-stack verification: TRL/vLLM/xgrammar version compatibility, the pin block, and GPU-provider comparison, checked against primary sources.
- [`scouts/R3_datasets_mining.md`](scouts/R3_datasets_mining.md) — survey of comparable NL-to-formal-spec datasets and a ranked, sized shortlist of D5 mining targets.
- [`scouts/R4_plan_redteam.md`](scouts/R4_plan_redteam.md) — adversarial red-team of the plan: blockers, majors, and minors, each later adjudicated in the plan's §11 revision log.
- [`scouts/R5_factsheet.md`](scouts/R5_factsheet.md) — mechanical fact-sheet: API pricing, stable package versions, GPU rental prices, and model-license checks.

## Raw traces

- `traces/` — machine-readable journals backing the reports above (e.g. `panel_smoke_2026-07-11.journal.jsonl`, the raw record behind `PANEL_SMOKE_2026-07-11.md`).
