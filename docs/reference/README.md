# Reference docs — index

One line per document, grouped by what you are trying to do. Start with the
[`GLOSSARY.md`](GLOSSARY.md) if any term here is unfamiliar — it is the
canonical plain-language list for every term the STJP docs use.

## 2026-07-25 — related work and the mechanisms built from it

Two **key documents** carry this update; each links every script that was
implemented or revised, so they are the entry points:

- [`RELATED_WORK_2026-07-25.md`](RELATED_WORK_2026-07-25.md) — **key
  document.** The July 2026 literature sweep (which competing papers make
  our framing sentences false, which third-party numbers to cite, the edit
  list for the paper) plus the linked table of everything implemented in
  response the same day.
- [`../../paper-writing/RELATED_WORK_DISCUSSION_2026-07-25.md`](../../paper-writing/RELATED_WORK_DISCUSSION_2026-07-25.md)
  — **key document.** The discussion notes feeding the next paper version:
  why a workflow graph is not a global type, what TraceFix's bound really
  bounds, the comparison table, the residual-as-risk-register argument, a
  candid self-review, and the same linked artifact list.

Supporting records behind the two key documents:

- [`SESSION_RECORD_2026-07-25.md`](SESSION_RECORD_2026-07-25.md) — unsanitised record of the session that produced the sweep: the findings, the assistant's own errors and the corrections to them, and what happened when an agent was handed this project's prose rules and broke three of them while obeying every mechanical check.
- [`ENFORCEABILITY_PARTITION.md`](ENFORCEABILITY_PARTITION.md) — every rule in `AGENT.md` sorted by what would enforce it (type / refinement / lint / nothing), with the honest residual list, its compensating controls, and the three conditions that predict when a prose rule gets broken.
- [`SPEC_TO_GATE_PLAN.md`](SPEC_TO_GATE_PLAN.md) — the staged plan (with graded pre-registered results P1–P8) for compiling a governance document's rules into mechanisms: rule registry, conflict/precedence pass, generated git gate, typed publish channel, and the governed real push.

## Benchmark internals

> **All benchmark guidance moved to [`../benchmarks/`](../benchmarks/README.md)
> on 2026-08-07** — the campaign plan, run steps, case ranking, fairness
> audit, timings, token accounting, the older runner's procedure
> (`HOW_TO_RUN_BENCHMARKS.md`), and the superseded Plan v2 all live there
> now. Start at `../benchmarks/README.md`.

- [`GLOSSARY.md`](GLOSSARY.md) — plain-language meaning of every term used in the STJP docs (metrics, severity ladder, arms, machinery).
- [`HOW_TO_USE_TRACES.md`](HOW_TO_USE_TRACES.md) — how to re-derive every headline number yourself from the raw per-trial traces committed in the repo.
- [`GOAL_QUALITY_AUDIT.md`](GOAL_QUALITY_AUDIT.md) — the audit that re-verified the benchmark's goal checks measure what they claim, and the fixes it produced.
- [`SDLC_HOSTED_WORKFLOW_SPEC.md`](SDLC_HOSTED_WORKFLOW_SPEC.md) — the build recipe for packaging one benchmark case as a cloud-hosted agent group (all 10 setups in one workflow).
- [`NUSCR_BACKEND_COMPARISON.md`](NUSCR_BACKEND_COMPARISON.md) — the verified head-to-head of the two protocol checkers (scribble-java vs the nuscr fork), including the harness bug found and fixed along the way.
- [`HOW_TO_IMPLEMENT_SUBSESSIONS.md`](HOW_TO_IMPLEMENT_SUBSESSIONS.md) — how a large standing policy is factored into reusable child protocols and recompiled incrementally when it changes.
- [`MINED_SKILLS_SOURCES.md`](MINED_SKILLS_SOURCES.md) — verified registry of every public repository the "real-world skills" evidence came from, with working permalinks and license checks.
- [`REAL_SKILLS_REEXAMINED.md`](REAL_SKILLS_REEXAMINED.md) — a line-by-line re-read of the real source files behind the two "real skills" cases, and the corrected protocols that came out of it.

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
