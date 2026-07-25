# Pre-registration — parallel dispatch of the enabled set (design only; no code changed yet)

Registered 2026-07-25, before any implementation. This document exists so
that when the scheduler change is made, its expected outcome is already on
record — and so that the change is NOT made casually: `AGENT.md` classifies
"modifying the runner/monitor without re-running all cases" as a known
mistake, and this environment cannot re-run the live cases (no Azure
credentials). **Gate for implementation: a session that can re-run the case
suite.**

## The observation (verified 2026-07-25)

`enabled_senders()` in `stjp_core/runtime/delm_runner.py:91` returns the
*set* of roles whose projected local state has an enabled send — the roles
the validated global type proves may act now. Both runtimes discard the set:
the decentralized runner loops one role at a time, and
`experiments/baselines/foundry_runner.py:301` takes `enabled[0]`. Because
the global type's well-formedness is exactly the proof that the enabled
actions are causally independent, dispatching the whole set concurrently is
sound by the same theorem that makes per-role monitoring sound (the
monitorability result the paper already cites). The serialization is
policy, not necessity. The related-work correction that produced this
observation is recorded in `SESSION_RECORD_2026-07-25.md` §4.3.

## The change (when implemented)

In the scheduler loop: instead of `actor = enabled[0]`, dispatch every role
in the enabled set concurrently within the step; deliver results in any
order; per-role monitors unchanged; the event log remains one linearization
(sound for every ordering the type permits — one methodology sentence, also
registered here, closes the "single sequential log" critique).

## Predictions

1. **Safety unchanged:** zero new protocol violations across the full case
   suite relative to the serialized scheduler, on every arm that uses the
   scheduler. Any new violation falsifies the soundness argument and stops
   the change.
2. **Call count unchanged** (±0): the same messages are sent, only their
   dispatch overlaps.
3. **Wall-clock improves only where the protocol has width:** cases whose
   protocols have parallel structure (e.g. two analysts both enabled after
   a fan-out) improve, bounded above by the average width of the enabled
   set; strictly linear protocols (width always 1) show **no improvement**
   — registered against ourselves so a null result on linear cases cannot
   later be spun as a loss, nor a win claimed where the type has no width.
4. **The poll-vs-rotation counters** (already implemented) are the
   measurement; no new metric will be introduced after seeing results.

## Why this is worth doing

It upgrades the answer to "a central scheduler cannot scale" from "fewer
calls than taking turns in a fixed circle" to "the validated type computes
the safe parallel schedule" — a guarantee no hand-built flow graph offers,
since a hand-built graph gets concurrency only where an engineer drew it.
