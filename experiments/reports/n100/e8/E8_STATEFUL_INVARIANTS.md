# E8 — Stateful invariants: the violation class per-message guards cannot see

*2026-07-05, branch `gc/stjp_stateful_extension`. Prototype 1 of
`docs/EXTENSIONS_PLAN`. Licensing theory: **Chen & Honda, CONCUR'12** — stateful
asynchronous properties are assertions over virtual state that evolves across
the whole conversation. STJP's structural advantage: the gate sits at delivery
and sees the ordered message stream, so v1 checks these invariants centrally at
the gate.*

## The violation class

`budget_run`: a recursion loop of debit requests. **Per-message limit $5,000**
(a normal payload guard the shipped system already has) and a **session budget
$10,000** (a cumulative property). Three debits of $4,000 each are *individually*
legal — every message passes every per-message guard — yet the cumulative total
$12,000 is a violation **no per-decision predicate can see**.

## What was built (all on this branch)

- **Checker.** `SessionLedger` in
  `stjp_core/compiler/refinement_checker.py`: the `.refn` sidecar gains three
  clause kinds — `state name : type = init`, `on Label(field) : state op= expr`,
  `invariant expr [@S4]`. Updates apply only on accepted messages (replays are
  bit-reproducible); an unevaluable update is skipped + logged, never a false
  block; `state … reset on Label` gives loop-reset, else state persists.
- **Central monitor hook.** `SessionMonitor(…, gate=…)` steps the ledger over the
  ordered stream and emits `stateful_invariant_violation` at the **exact crossing
  message**, attributed to its sender. Observe mode flags; gate mode rolls the
  virtual state back (rejects pre-delivery).
- **Static validator.** `validate_session_ledger` checks every `on` label exists
  in G, updates reference only declared state + the label's field, invariants
  reference only declared state (constants modelled as never-updated `state`).
- **Verdict corpus — 12/12** (`experiments/tests/verdict_corpus/stateful/`):
  crossing-exactness, legal-silence, gate rollback, `@S4` severity, loop persist
  vs `reset on`, negative-balance lower bound, commutativity (both orders),
  unevaluable-no-false-block. **Built and passed before this benchmark.**
- **Integration proven.** The `budget_run` protocol validates in Scribble; a
  cumulative-overrun trace is **structurally conformant** to every per-role EFSM
  yet the ledger flags it — the point of the experiment.

## E8 result (deterministic seeded corpus, n=50 overrun + 50 legal, seed fixed)

| arm | detects overruns | at exact crossing | false positives | post-budget debits delivered |
|---|---|---|---|---|
| **(a) current STJP** (per-message guard only) | **0 / 50** | — | 0 / 50 | 0 |
| **(b) +invariants, observe** | **50 / 50** | **50 / 50** | **0 / 50** | 50 (observe-only) |
| **(c) +invariants, gate** | **50 / 50** | **50 / 50** | **0 / 50** | **0** |

Every debit in every trace is ≤ the $5k per-message limit **by construction**, so
arm (a)'s 0/50 is not a strawman — it is the shipped system, structurally blind
to the cumulative property. Arm (b) flags the overrun at the *exact* message that
crosses $10k with zero false alarms on the 50 legal-total runs. Arm (c) rejects
that crossing message pre-delivery, so **no post-budget debit is ever paid**,
while everything before the crossing proceeds normally.

**Pre-registered prediction: CONFIRMED** (`docs/predictions/EXTENSIONS_PREREGISTRATION.md`).

Reproduce: `python experiments/subagent_trials/e8_budget_bench.py --n 50`
(→ `e8_summary.json`). Verdict corpus:
`python experiments/tests/verdict_corpus/stateful/stateful_corpus.py`.

## Live-subagent portion (n=30/arm)

*Status: harness ready (`budget_run` case + arms wired into `engine_ladder`),
run pending.* The plan's live trials instruct the Requester to procure $12k of
items across the loop; arms (a) observe-blind, (b) observe-flag, (c) gate-reject.
Prediction: arm (c) delivers 0 post-budget debits and completes with the
Treasurer re-prompted onto a legal (reject-or-downsize) path. The deterministic
result above already establishes the mechanism; the live run measures whether a
weak model, handed the ledger invariant, stays within budget.

## Paper insertion

New paragraph in §7 after E2 — "E8 — Stateful invariants: the violation class
per-message guards cannot see" — with a grouped-bar panel (detection / FP by
arm). Cite `\citep{chen12}` in the design paragraph and §3.4 (already wired).
The single quotable number: **0/50 → 50/50** on a violation class the shipped
system cannot see.
