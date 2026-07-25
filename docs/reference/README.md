# Reference docs — index

One line per document, grouped by what you are trying to do. Start with the
[`GLOSSARY.md`](GLOSSARY.md) if any term here is unfamiliar — it is the
canonical plain-language list for every term the STJP docs use.

## Benchmark internals

- [`GLOSSARY.md`](GLOSSARY.md) — plain-language meaning of every term used in the STJP docs (metrics, severity ladder, arms, machinery).
- [`BENCHMARK_PLAN_V2.md`](BENCHMARK_PLAN_V2.md) — the hardened evaluation plan: eight experiments, each testing exactly one component, with real-vs-pending status for every number.
- [`HOW_TO_USE_TRACES.md`](HOW_TO_USE_TRACES.md) — how to re-derive every headline number yourself from the raw per-trial traces committed in the repo.
- [`MINED_SKILLS_SOURCES.md`](MINED_SKILLS_SOURCES.md) — verified registry of every public repository the "real-world skills" evidence came from, with working permalinks and license checks.
- [`REAL_SKILLS_REEXAMINED.md`](REAL_SKILLS_REEXAMINED.md) — a line-by-line re-read of the real source files behind the two "real skills" cases, and the corrected protocols that came out of it.
- [`RELATED_WORK_2026-07.md`](RELATED_WORK_2026-07.md) — July 2026 literature sweep: which competing 2026 papers make our framing sentences false, which third-party numbers we should be citing instead of our own, and the paper edits each one forces.

## Scribble & protocol tooling

- [`SCRIBBLE_EXTENSIONS.md`](SCRIBBLE_EXTENSIONS.md) — how STJP adds refinement contracts, cross-file composition, and delegation *around* stock Scribble without forking it.
- [`CHOICE_GUARDS_AND_GATE.md`](CHOICE_GUARDS_AND_GATE.md) — closing the "wrong branch" hole: value-dependent decision rules checked by the monitor, and the gate that blocks bad messages before delivery.
- [`GAP_CLOSED.md`](GAP_CLOSED.md) — closing the payload-rule hole: value rules compiled into each agent's own send tools, so a bad value is rejected before it leaves the agent.
- [`CRITIC_REVISOR.md`](CRITIC_REVISOR.md) — the cross-message policy layer: catching breaches (leaks, skipped approvals, self-approval) that no single message reveals, and repairing the protocol when found.
- [`PROTOCOL_EVOLUTION.md`](PROTOCOL_EVOLUTION.md) — absorbing a change-request email into an updated, re-validated protocol by composing the change in as a child sub-protocol.
- [`SKILL_COMPACTION.md`](SKILL_COMPACTION.md) — the bottom-up entry point: take skills that already exist, reduce each to its interaction contract, and let the compiler prove the team safe or unsafe before any run.
- [`STJP_V3_PLAN.md`](STJP_V3_PLAN.md) — the next-version architecture: STJP as a policy generator for governance toolkits, and as the safety layer of a fast decentralized runtime.
- [`NUSCR_CLOUD_INSTALL.md`](NUSCR_CLOUD_INSTALL.md) — installing the newer nuscr compiler fork (better at looping protocols), including the route that works inside restricted cloud sandboxes.
- [`NUSCR_AND_SKILL_SAFETY_PLAN.md`](NUSCR_AND_SKILL_SAFETY_PLAN.md) — the implementation plan that delivered the nuscr backend and the "real skills gone wrong" demo.

## Training & seam

The "seam" is the intent-to-protocol translation step — a plain-language
request becomes a Scribble-validated protocol; these docs plan and execute
training a model to do it.

- [`TRAINING_ROADMAP.md`](TRAINING_ROADMAP.md) — one page, no insider terms: who does what, in what order, and what it costs.
- [`SEAM_AUTOTRAINING_PLAN.md`](SEAM_AUTOTRAINING_PLAN.md) — the strategy: verifiable rewards for validity, judge panels for faithfulness, and the corpus that feeds both.
- [`SEAM_TRAINING_EXECUTION_PLAN.md`](SEAM_TRAINING_EXECUTION_PLAN.md) — the executable version: exact stacks, hyperparameters, judge-isolation mechanics, preregistered go/no-go gates, and worker task cards.
- [`GPU_TRAINING_RUNBOOK.md`](GPU_TRAINING_RUNBOOK.md) — the practitioner runbook: the exact commands and provider setups (Modal / RunPod / Azure ML) to actually run the training phases.
- [`reports/seam/`](reports/seam/README.md) — the program's internal worker and scout reports, indexed one line each.

## Operations

- [`COST_ESTIMATES.md`](COST_ESTIMATES.md) — what a run costs and which commands need Azure.
- [`FOUNDRY_VISIBILITY.md`](FOUNDRY_VISIBILITY.md) — making agents, threads, and traces actually show up in the Azure AI Foundry portal, surface by surface.
- [`CODE_AUDIT_2026-07-19.md`](CODE_AUDIT_2026-07-19.md) — code audit verdict.
