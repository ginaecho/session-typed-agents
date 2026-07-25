# STJP Benchmark — experiments/

A versioned benchmark that compares multi-agent runs **with vs. without** STJP
session-type machinery (session types are machine-checked message contracts —
who may send what to whom, in what order), across many multiparty protocols.
Each protocol is a `cases/<case_id>/` directory; one case-agnostic runner
(`scripts/case_runner.py`) drives the full arm matrix for any case. An *arm*
is one configuration being compared — like the treatment and control groups
of a medical trial.

The runner imports the STJP library from `../stjp_core/`. The arm definitions
live in `baselines/` (see `baselines/README.md`); the metric design is in
`../docs/archive/EXPERIMENT_DESIGN_v2.md`.

## Menu

- [What lives where](#what-lives-where)
- [The arm matrix (15 arms)](#the-arm-matrix-15-arms)
- [Two evaluations per run](#two-evaluations-per-run)
- [The cases](#the-cases)
- [Running the benchmark](#running-the-benchmark)
- [case.yaml schema](#caseyaml-schema)
- [Adding a new case](#adding-a-new-case)
- [Authoring rules](#authoring-rules)
- [Findings tracked across cases](#findings-tracked-across-cases)

## What lives where

```
experiments/
  cases/                     one directory per benchmark protocol (table below)
    <case_id>/
      case.yaml              case config (schema below)
      protocols/
        v1.scr               canonical Scribble global protocol
        v1.refn              refinement contracts (value constraints, sidecar)
        llm_drafts/          LLM-drafted protocols consumed by the *_llmvalid
          valid/  {v1.scr, goals.yaml}    and *_unsafe arms — produced by
          unsafe/ {v1.scr, goals.yaml}    scripts/draft_llm_protocols.py
      runs/
        <ISO-timestamp>-n<N>-dual/   one benchmark run
          events_<arm>.jsonl         per-event JSONL, one file per arm
          prompts/<arm>/             every role's full system prompt (audit trail)
          summary.json               Set A (conformance) + process-cost metrics
          summary_eval.json          Set B (goal-achievement) metrics
      LATEST                 text pointer -> newest run dir
  baselines/                 the arm runners + registry (baselines/README.md)
  scripts/                   case_runner.py (the driver) and all helper scripts
  reports/                   committed result write-ups (n100 suite, stress, tables)
  subagent_trials/           Foundry-free validation harness driven by Claude
                             subagents (subagent_trials/README.md)
  seam_bench/                mining + judging pipeline for team-seam defects in
                             real-world skills (data, mining, judge, eval)
  harness_adapters/          the same benchmark on other runtimes, e.g. LangGraph
                             (harness_adapters/README.md)
  apps/live_demo/            Flask UI that walks an audience through a live run
                             (apps/live_demo/README.md)
  tests/                     benchmark self-tests, incl. the verdict corpus
                             ("testing the testers")
  INDEX.html                 cross-case dashboard (regenerate: scripts/index_builder.py)
  _smoke_all.sh              smoke-run every case once
```

## The arm matrix (15 arms)

Each run drives up to 15 arms; the variable is what protocol information the
agents get and how strongly the runtime enforces it. The full per-arm table
and the pairwise comparisons live in `baselines/README.md`; the executable
source of truth is the `SCENARIOS` list in `baselines/registry.py`. In short,
the arms form a ladder:

- **intent-only** — `bare`, `maf_native`, `maf_foundry`, `maf_groupchat`:
  agents get prose intent and role descriptions, no protocol at all.
- **unchecked skills** — `unchecked_skills`: agents get plausible human-written
  per-role skill files that were never formally checked (the deadlock demo's
  no-checker arm).
- **global type as text** — `maf_groupchat_unsafe` (an LLM-drafted protocol
  that Scribble — the protocol-description language whose checker proves
  deadlock-freedom — *rejected*), `maf_groupchat_llmvalid` (one Scribble
  *accepted*),
  `global_decentralized` (the accepted text, but on the decentralized runner —
  no orchestrator).
- **projected per-role local type + monitor** — `spec_llmvalid` (verbose
  contract), `min_llmvalid` (lean SEND/RECV table). *Projection* means each
  role is handed only its own slice of the global protocol.
- **+ enforcement gate** — `spec_llmvalid_gate`, `min_llmvalid_gate`,
  `min_llmvalid_gate_nohint`, `min_llmvalid_gate_lastrecv`: an in-line monitor
  *rejects* off-contract messages before delivery instead of just recording
  them. For example, if a role tries to skip the audit step, the gate bounces
  the message back with the reason, and the role must try again.
- **+ protocol-derived scheduler** — `min_llmvalid_sched`: the full STJP
  execution plane; the runner polls only roles whose contract says they can
  act next, instead of taking turns in a fixed circle (round-robin polling).

## Two evaluations per run

Full definitions in `../docs/archive/EXPERIMENT_DESIGN_v2.md`.

- **Set A — global-type conformance** — the typed monitor walks each role's
  projected state machine (EFSM) and records every off-contract event;
  `summary.json` carries `violations` / `violation_types`. Meaningful only
  for arms given a protocol.
- **Set B — goal achievement** — did the run actually accomplish the task?
  `summary_eval.json` carries `strict` / `role_pair` / `semantic` per arm.
  `case_runner.py` computes strict + role-pair at the end of every run;
  `--semantic` adds the LLM-judged scoring rule.
- **Process cost** — tokens, LLM calls, wall-clock, attempts — in `summary.json`.

Note that `success_rate_pct` in `summary.json` is **goal-based**, not
"zero monitor violations" — see `CLAUDE.md`, "Reading a run summary".

## The cases

Every case is a self-contained directory. One row per case; role counts come
from each `case.yaml`.

| case | roles | what it tests |
|---|---|---|
| [`cases/_corpus/`](cases/_corpus/) | — | 30 generated Scribble protocols (no `case.yaml`) — the corpus behind mutation testing (E1) |
| [`cases/agenticpay_settlement/`](cases/agenticpay_settlement/) | 4 | Goods-for-payment trade adapted from real AgenticPay buyer/seller agents; their individually-reasonable rules form a circular wait (deadlock) that Scribble's checker forces an Escrow-first fix for — the escrow being a neutral third party that holds funds until both sides deliver |
| [`cases/auction/`](cases/auction/) | 4 | Sealed-bid auction with three bidders; refinements require positive bids and reserved announcement keywords |
| [`cases/banking/`](cases/banking/) | 5 | Banking transfer with an amount-dependent approval branch — large transfers must route through an Approver; rejections exit cleanly |
| [`cases/clinical_enrollment/`](cases/clinical_enrollment/) | 5 | Clinical-trial enrolment: screening, sequenced consent + baseline, ethics approval — all before enrolling |
| [`cases/code_review/`](cases/code_review/) | 5 | Pull-request review and merge: two reviewer approvals plus a CI coverage threshold before the merge decision |
| [`cases/composition/`](cases/composition/) | — | Protocol composition demo (no `case.yaml`): `audit` + `banking` sub-protocols composed into a finance pipeline |
| [`cases/finance/`](cases/finance/) | 6 | Quarterly finance report with high-revenue audit branching — the classic refinement-vs-sequencing failure pair |
| [`cases/finance_nested/`](cases/finance_nested/) | 5 | 2x2 nested choice where the branch cue lives in the payload, not the label — built to expose wrong-label picks at inner choices |
| [`cases/intel_report/`](cases/intel_report/) | 6 | Editor coordinates three intelligence feeds, then draft-review-publish — fan-in with a strict ordering the LLM is tempted to skip |
| [`cases/iterative_polling/`](cases/iterative_polling/) | 3 | Shape D — loop sessions: Client polls Server in a recursion with a minimal continue-vs-stop choice |
| [`cases/nested_retry/`](cases/nested_retry/) | 4 | Shape F — loop plus nested branching: editorial revise-vs-accept, each side with its own inner choice |
| [`cases/planner_workers/`](cases/planner_workers/) | 4 | Coordinator hands tasks to two workers; a shared repository grants one push turn at a time (mutual exclusion on the shared branch) |
| [`cases/rag/`](cases/rag/) | 6 | Retrieval-augmented generation with a bounded verification loop: parallel retrieval, draft, fact-check, revise until verified |
| [`cases/report_pipeline/`](cases/report_pipeline/) | 6 | THE TOKEN-EFFICIENCY DEMO: a completable 6-role linear pipeline where the metric is tokens/calls to finish, not whether it finishes |
| [`cases/report_pipeline_large/`](cases/report_pipeline_large/) | 10 | Scale variant of report_pipeline: global-text token cost grows with protocol size, the projected local contract stays flat |
| [`cases/retry_loop/`](cases/retry_loop/) | 3 | Shape E — loop plus simple branching: Manager accepts or rejects each Worker attempt, with Auditor confirmation on accept |
| [`cases/trade_deadlock/`](cases/trade_deadlock/) | 4 | THE DEADLOCK DEMO: hand-written "don't pay until goods arrive" / "don't ship until paid" skills deadlock; Scribble catches it at design time |
| [`cases/trade_settlement/`](cases/trade_settlement/) | 5 | The user's *intent prose* hides a circular dependency; tests whether the validator catches it and whether agents then reach settlement |
| [`cases/travel/`](cases/travel/) | 6 | All-or-nothing travel booking: confirm all three bookings and charge, or roll every booking back and charge nothing |
| [`cases/travel_saga/`](cases/travel_saga/) | 5 | Travel booking happy path across three suppliers, with price-bound refinements (rollback deferred to v2) |
| [`cases/skills_safety/airline_seat/`](cases/skills_safety/airline_seat/) | 3 | Real OpenAI Agents SDK airline skills: nothing says a flight must be assigned before the seat update — "do A before B, skill goes straight to B" |
| [`cases/skills_safety/booking_saga/`](cases/skills_safety/booking_saga/) | 3 | Real LangGraph booking-saga skills: "no room until paid" meets "no charge until room confirmed" — a deadlock neither skill shows alone |
| [`cases/skills_safety/code_execution/`](cases/skills_safety/code_execution/) | 3 | Real AutoGen coder/executor pattern: the executor runs code immediately, with no reviewer-approval gate encoded anywhere |
| [`cases/skills_safety/content_pipeline/`](cases/skills_safety/content_pipeline/) | 4 | Real CrewAI content-team prompts: nothing forces the Editor's review before the Publisher publishes |
| [`cases/skills_safety/doc_coauthor_ship/`](cases/skills_safety/doc_coauthor_ship/) | 4 | Corrected re-implementation of doc_pipeline from real Anthropic skills: the review loop moves to the role whose skill actually contains it |
| [`cases/skills_safety/doc_pipeline/`](cases/skills_safety/doc_pipeline/) | 4 | Real Anthropic public skills: no skill encodes Draft -> Brand Approval -> Ship, so an unreviewed announcement can go out company-wide |
| [`cases/skills_safety/pr_merge/`](cases/skills_safety/pr_merge/) | 4 | Real GitHub Copilot customization files: nothing makes the merge wait for the security review |
| [`cases/skills_safety/pr_review_merge/`](cases/skills_safety/pr_review_merge/) | 4 | Corrected re-implementation of pr_merge: multi-round review with the merge gated on BOTH concurrent reviewer approvals |

The `skills_safety/` sub-family shares one design: each case starts from
*real, published* agent skill files (provenance in each case's `SOURCES.md`)
whose team-level ordering is never written down anywhere, and asks whether a
formal protocol prevents the resulting disaster. `cases/escrow_trade.fail` is
a retired marker file, not a case directory.

## Running the benchmark

```bash
python scripts/case_runner.py finance 1            # 1 trial each (smoke)
python scripts/case_runner.py finance 10           # 10 trials each
python scripts/case_runner.py --all 10             # every case, n=10
python scripts/case_runner.py finance 10 --semantic        # + LLM-judged Set B
python scripts/case_runner.py finance 10 --resume <run_dir># resume a partial run
python scripts/case_runner.py finance --summarize-only <run_dir>  # re-aggregate
python scripts/run_subset.py finance 1 bare spec_llmvalid  # just these arms
python scripts/index_builder.py                    # refresh INDEX.html
```

The arms that consume an LLM-drafted protocol need a one-time per-case setup
first — see [Adding a new case](#adding-a-new-case) step 4.

## case.yaml schema

```yaml
case_id: finance                       # must match the directory name
description: |                         # one-paragraph human description
  Quarterly finance report with high/standard branching.
version: v1                            # which protocols/v* to use
protocol_name: QuarterlyFinanceReport  # the Scribble `global protocol <NAME>`
roles:                                 # ordered; first role usually starts
  - Fetcher
  - RevenueAnalyst
  # ...
terminal_label: GenerateReport         # session ends when this label is sent
max_steps: 24                          # per-trial safety bound
branch_hints: [high, standard]         # cycled across trials so each branch runs
role_descriptions:                     # prose, held constant across ALL arms
  Fetcher: retrieves raw revenue data on request
  # ... one line per role
intent: |                              # user-facing prose driving the scenario
  We need a Quarterly Finance Report pipeline ...
goals:                                 # outcome predicates checked post-trace
  - id: G1
    description: High-path revenue must exceed $50,000
    metric: revenue_amount
    predicate: float(x) > 50000        # python expression, x = payload
    anchor: {sender: Fetcher, receiver: TaxSpecialist, label: HighRevenue}
    threshold: "> 50000"
    branch: high                       # OPTIONAL — goal applies only on this
                                       # branch; vacuously satisfied elsewhere.
                                       # Omit for goals mandatory on every branch.
```

`protocols/v1.refn` uses the `refinement_checker.py` sidecar format — one
value constraint per message:

```
[Fetcher -> TaxSpecialist : HighRevenue]
type: float
require: x > 50000.0
```

## Adding a new case

1. `mkdir -p cases/<case_id>/protocols`
2. Write `cases/<case_id>/case.yaml`, `protocols/v1.scr`, `protocols/v1.refn`.
3. Smoke the intent-only arms: `python scripts/case_runner.py <case_id> 1`.
4. For the arms that consume an LLM-drafted protocol, draft it first:
   ```
   python scripts/draft_llm_protocols.py <case_id>
   python scripts/re_anchor_goals.py <case_id> valid
   python scripts/re_anchor_goals.py <case_id> unsafe
   ```

## Authoring rules

- **Protocols must validate** against Scribble before they enter the benchmark
  (`case_runner` refuses to start on an invalid `.scr`). Author them
  deadlock-free: every role must participate in every branch of a choice,
  because a role left out of one branch never learns the branch was taken and
  can block the whole session waiting for a message that will never come —
  exactly the failure the `trade_deadlock` case demonstrates.
- **Refinements** should include at least one numerical predicate so the
  comparison surfaces both the structural gap (wrong message order) and the
  value gap (right message, impossible payload — e.g. `HighRevenue(10)` on a
  branch that requires `> 50000`).
- **Goals** are evaluated after the trace completes. Tag a goal with `branch:`
  if it only applies on one branch — otherwise a trial that legitimately took
  the other branch fails the goal spuriously, because its anchor message never
  had a reason to appear.
- **Naming**: `case_id` is lowercase snake_case; role names are PascalCase.

## Findings tracked across cases

1. **Refinement-violation finding** — LLM agents handed a structural protocol
   still pick payload values that violate value-dependent constraints (the
   protocol says *send HighRevenue*, and they do — but with an amount the
   contract forbids). Closed at the call site via compiled refinement guards
   (see `../docs/reference/GAP_CLOSED.md`).
2. **Sequencing-violation finding** — agents handed both protocol and
   refinement still pick the wrong *message label* at the right *state* (e.g.
   skipping the audit step). The benchmark characterises its prevalence across
   protocol shapes.
