# Choice Guards & the Enforcement Gate — closing the "wrong branch" hole

*Implemented 2026-06-12. Companion: `SCRIBBLE_EXTENSIONS.md` (the layering
this extends), `GAP_CLOSED.md` (the 2026-05-13 payload-guard closure this
parallels), `docs/results/RUN_REPORT_2026-06-11.md` Part 3 (the failure analysis
that motivated it).*

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [1. The problem this closes](#1-the-problem-this-closes)
- [2. The chain, script by script](#2-the-chain-script-by-script)
  - [Stage 0 — DEFINE: the `.refn` sidecar (data, not code)](#stage-0--define-the-refn-sidecar-data-not-code)
  - [Stage 1 — PARSE: `stjp_core/compiler/refinement_checker.py`](#stage-1--parse-stjp_corecompilerrefinement_checkerpy)
  - [Stage 2 — STATE: compile the rule into the agent's contract](#stage-2--state-compile-the-rule-into-the-agents-contract)
  - [Stage 3 — CHECK: `stjp_core/monitor/monitor.py` (observer)](#stage-3--check-stjp_coremonitormonitorpy-observer)
  - [Stage 4 — ENFORCE: `experiments/baselines/foundry_runner.py` gate mode](#stage-4--enforce-experimentsbaselinesfoundry_runnerpy-gate-mode)
- [3. Verified behaviour (offline replay, no LLM)](#3-verified-behaviour-offline-replay-no-llm)
- [3b. First production run (2026-06-12, `runs/20260612T151309-n2-dual`)](#3b-first-production-run-2026-06-12-runs20260612t151309-n2-dual)
- [4. What this does NOT change](#4-what-this-does-not-change)
- [5. How to add a guard to a new case](#5-how-to-add-a-guard-to-a-new-case)
<!-- MENU:END -->

## 1. The problem this closes

The finance n=10 run had 2/18 typed-arm attempts take the **standard branch
on high revenue** — skipping the audit, then filing the report. Every layer
correctly accepted it, because:

- **Classic MPST cannot express value-dependent choice.** At an internal
  choice the type says "you may send A or B"; *which one given the data* is
  not in the type. Stock Scribble has no syntax for it.
- The agent's contract at the choice state listed both branches with equal
  standing; the >$50k rule lived only in prose, and prose is not enforcement.
- The drafted-protocol arms had **no `.refn` sidecar at all** — only the
  canonical vocabulary had guards.

Research basis: Bocchi et al. CONCUR'10 (asserted MPST — assertions at choice
points); Bocchi/Chen/Demangeon/Honda/Yoshida FORTE'13 (monitored session
types); *Specifying Stateful Asynchronous Properties for Distributed
Programs* (assertions ranging over previously received values). This is the
sidecar-layer implementation of those ideas — **stock `scribble-java/` remains
untouched** (see SCRIBBLE_EXTENSIONS.md §0: no fork).

## 2. The chain, script by script

One rule travels through four stages. Everything is keyed off the `.refn`
sidecar next to the protocol; nothing else needs editing when a rule changes.

### Stage 0 — DEFINE: the `.refn` sidecar (data, not code)

`experiments/cases/<case>/protocols/llm_drafts/valid/v1.refn` (and any
`.refn` beside any `.scr`). New block type alongside the existing
payload-guard blocks:

```
[choice at RevenueAnalyst]
when: float(RawRevenueData) > 50000
require: HighRevenueNotification
over: StandardRevenueNotification
```

`when` is a sandboxed Python expression over **previously observed message
payloads, referenced by label name** (stateful assertion). Semantics:
when TRUE the role must take `require`; sending a label in `over` is a
violation — and symmetrically when FALSE.

Written for: finance (`>$50k ⇒ high branch`) and banking
(`>$10k ⇒ approval route`, `Approval=='true' ⇒ Approved`, which also closes
the *denied-but-debited* hole the severity grader flagged).

### Stage 1 — PARSE: `stjp_core/compiler/refinement_checker.py`

- New `ChoiceGuard` dataclass: `{role, when, require, over[]}` with
  `evaluate(values) -> True | False | None` (None = a referenced label has
  not been observed yet → guard not active; never guesses).
- `parse_refn_text` now yields both kinds of entries in one dict:
  `(sender, receiver, label) -> Refinement` and
  `('__choice__', role, idx) -> ChoiceGuard`. The sentinel first element
  cannot collide with a role name, so every existing
  `refinements.get((s, r, label))` caller is untouched.
- Accessor: `choice_guards_for(refinements, role)`.
- Predicates run in the same AST-validated sandbox as payload guards
  (no attribute access beyond safe string methods, no imports, no builtins).

### Stage 2 — STATE: compile the rule into the agent's contract

The rule is injected **at the decision state**, not as preamble prose —
LLMs follow point-of-decision instructions far better.

- `stjp_core/generation/agent_generator.py::_build_behavior_instructions`
  (the verbose `spec` contract): adds a top-level **"Decision Rules (HARD)"**
  section *and* an inline `**DECISION RULE (HARD)**` bullet inside the
  exact `### State N` block whose sends include `require` + an `over` label.
- `experiments/baselines/instructions.py::build_spec_minimal_instructions`
  (the terse `min` contract): emits one line directly under the choice state:

```
state 26: SEND HighRevenueNotification(String) to TaxVerifier -> state 27
state 26: SEND StandardRevenueNotification(String) to TaxVerifier -> state 34
state 26 DECISION RULE (HARD): IF float(RawRevenueData) > 50000 THEN SEND
HighRevenueNotification; ELSE SEND StandardRevenueNotification. ...
```

No builder signature changed — both already received the parsed refinements.

### Stage 3 — CHECK: `stjp_core/monitor/monitor.py` (observer)

The per-role monitor is now **value-tracking** (stateful):

- `RoleMonitor.observed_values: {label -> payload}` records every payload
  the role sees (send or receive), recorded *after* guard evaluation so a
  guard never ranges over the very message being judged.
- On every SEND, `_check_choice_guards` evaluates each of the role's guards
  against the observed values → new verdict
  **`ViolationType.CHOICE_GUARD` (`"choice_guard_violation"`)** carrying the
  guard, its truth value, the observed values, and what should have been sent.
- The EFSM still advances on a choice-guard violation (the message *was*
  protocol-legal and did happen) — the monitor stays aligned with reality
  and reports the wrong branch. This is observer mode: harm becomes
  **visible**.

The monitor is plain Python — no LLM, no prompt, O(guards) per send — and is
instantiated per role from the same projection that builds the contract
(generated *when the local types are generated*, as required).

### Stage 4 — ENFORCE: `experiments/baselines/foundry_runner.py` gate mode

`FoundryRunner(gate=True)` — registered as the new arm
**`spec_llmvalid_gate` ("WITH-spec-llmvalid-GATE")** in
`experiments/baselines/registry.py` (and added to the Foundry wave +
prompt-truncation sets in `experiments/scripts/case_runner.py`).

Per parsed action, BEFORE delivery:

1. Probe a **deep-copied** role monitor with the would-be event (so a
   rejection leaves the live contract state untouched).
2. Any verdict (`off_protocol`, `unexpected_peer`, `refinement_failed`,
   `choice_guard_violation`) ⇒ the message is **not delivered**: not appended
   to history, invisible to the receiver, no protocol step consumed. A
   `gated` marker (with reason) is written to `events.jsonl`, and the
   offending role's next turn is prefixed with the monitor's verdict and the
   expected actions ("re-prompt").
3. Accepted events are committed to the live gate monitor so contract state
   advances with reality.
4. Liveness: every rejection counts toward the existing `consec_wait`
   bound, so a role that keeps insisting ends the attempt (bounded retry)
   rather than looping forever. Gated counts land in the attempt's usage
   (`extra.gated`).

This converts "violation is unlikely" (prompt) into "violation cannot
complete" (gate) — for irreversible actions, the only place where *can't
happen* is true.

## 3. Verified behaviour (offline replay, no LLM)

Projection of the current finance valid draft + the new `.refn`, replayed
through `SessionMonitor`:

| trace | verdict |
|---|---|
| `RawRevenueData(75000)` … then `StandardRevenueNotification` | **`choice_guard_violation`** (guard True, required High) |
| `RawRevenueData(75000)` … then `HighRevenueNotification` | clean |
| `RawRevenueData(30000)` … then `HighRevenueNotification` | **`choice_guard_violation`** (guard False, required Standard) |
| guard before `RawRevenueData` observed | guard inactive (None) — no false positives |

## 3b. First production run (2026-06-12, `runs/20260612T151309-n2-dual`)

`spec_llmvalid` (observer) vs `spec_llmvalid_gate` (enforced), real Foundry
agents, n=2:

- **The gate intercepted a real off-contract send**: RevenueAnalyst tried
  `HighRevenueNotification` at state 25 (before `ExpenseData` had arrived);
  the gate rejected it pre-delivery and re-prompted. The observer arm's
  RevenueAnalyst made the *same* jump in parallel — delivered, and the trace
  cascaded off-protocol for 3 further steps. Delivered-violation counts:
  observer 9/15 events, **gate 0/7**.
- Gate cost less: 46.1k vs 59.2k tokens/trial (−22%), 177s vs 249s (−29%) —
  rejected actions are cheaper than delivered wrong actions.
- **Both arms scored 0% goals this run** — NOT a guard regression: every
  failed attempt stalled at events=1 because ExpenseAnalyst WAITed instead of
  sending `ExpenseData` (the pre-existing role-passivity problem;
  see RUN_REPORT §3 "EFSM-driven scheduling"). The scheduler fix — prompt
  exactly the roles whose local type has an enabled SEND — would tell
  ExpenseAnalyst "you are at a SEND state" instead of polling it generically.
- Harness note: `evaluate_run.VOCABULARY_ARMS` must include any new arm that
  receives a vocabulary (fixed for `spec_llmvalid_gate` same day).

## 4. What this does NOT change

- **`scribble-java/` is untouched** — the global type still validates with
  stock Scribble; guards live entirely in the sidecar layer.
- **Set A/B metrics & old runs** — choice guards add a new verdict type;
  existing verdicts and events schemas are unchanged. Old `.refn` files parse
  exactly as before.
- **Subsessions / composition** — already exists
  (`stjp_core/compiler/composer.py`, `// @use Child from "file.scr";`
  spliced before validation) and is the intended vehicle for
  "new demand → child protocol composed into the old one"
  (see `docs/PROTOCOL_EVOLUTION.md` + `docs/EVOLUTION_DEMO_DESIGN.md`).
  **Behavioural subtyping** (is the evolved local type a safe replacement?)
  is *not* implemented — currently approximated by contract hash-diff
  ("unchanged role ⇒ trivially safe"); a proper subtyping check is roadmap.

## 5. How to add a guard to a new case

1. Open (or create) the `.refn` next to the `.scr` the arms actually project
   from — for `_llmvalid` arms that is `protocols/llm_drafts/valid/v1.refn`,
   NOT the canonical `protocols/v1.refn`.
2. Add a `[choice at <Role>]` block. Reference only labels the role has
   *already seen* at that choice (the monitor can only bind observed values).
3. No other step: parser, both contract builders, monitor, and gate all pick
   it up from the sidecar automatically on the next run.
4. If you regenerate the LLM draft, re-check the guard's labels still exist —
   same drift rule as `goals.yaml` (see DIARY 2026-06-12 §2).
