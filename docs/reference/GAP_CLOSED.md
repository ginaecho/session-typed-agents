# Gap Closure: Refinement Predicates Compiled into Projected Tools

**Date:** 2026-05-13
**Implementer:** automated, against the design in
`testing_ideas/STJP_discussion_13May2025.md` §"Monitor design"
and the figure in `testing_ideas/monitoring_tool_from_intent.png`.

## The gap (before)

Refinement contracts existed in two places that did not talk to each other:

1. **Global type / sidecar.** `protocols/P1_v2.scr` carried the structural
   MPST protocol; `protocols/P1_v2.refn` carried the payload predicates,
   keyed by `(sender, receiver, label)`. Refinements were parsed by
   `refinement_checker.py`.

2. **Projected agents.** `agent_generator.py` projected the EFSM of each
   role into a Claude subagent markdown or a Python `Agent` stub. The stub's
   `act(direction, peer, label, payload=None)` validated only the *structural*
   triple (direction, peer, label) against the local automaton. **Payload
   was opaque to the agent.**

Refinement checking happened **after the fact**, on captured trace events,
inside `SessionMonitor(efsms, refinements)`. By that point the agent had
already decided to send and emitted on the wire. The agent's own tools
contained no payload constraint at all; refinements appeared in skill
markdown only as English prose decision rules (e.g. "if value > $10,000"),
which is precisely the failure mode the
DELEGATE-52-aligned empirical finding identified: **LLM agents follow
structural local types at near-100% but fail value-dependent constraints
because the constraint is only natural language to them.**

This contradicts the design in `monitoring_tool_from_intent.png`, which
specifies:

```
LocalType_A  =  send(B, Transfer, amount: Money) where amount < 50000
                                                 ─────────────────────
                                                          ↓ compile
                func_check_A_to_B_Transfer(msg) :=
                  if msg.amount < 50000 then ALLOW else REJECT
```

— a compiled boolean function attached to the send action itself.

## What was implemented

The predicate is now **compiled into the projected tool function** so the
check fires at the call site, before the EFSM advances and before any wire
emission.

### Edit 1 — `refinement_checker.py`

Added a typed exception so generated stubs and external monitors raise the
same class:

```python
class RefinementViolation(Exception):
    """Raised when a payload fails the refinement predicate at the call site."""
```

### Edit 2 — `agent_generator.py`

Both generators take an optional
`refinements: dict[(sender, receiver, label) -> Refinement]` argument.
`generate_all_agents` will auto-load the sibling `.refn` when given
`protocol_path`.

**Python stub.** For every outgoing transition `(peer, label)` the stub now
emits a tool method:

```python
def send_HighRevenue_to_TaxSpecialist(self, x):
    """
    Refinement invariant (compiled from .refn):
        type: float
        require: x > 50000.0
    Raises RefinementViolation BEFORE the send if the payload fails.
    """
    return self.act("send", "TaxSpecialist", "HighRevenue", x)
```

Each refined send has a named guard function compiled at module scope:

```python
def _check_HighRevenue_to_TaxSpecialist(x):
    try:
        x = float(x)
    except (ValueError, TypeError) as _e:
        raise RefinementViolation("…type error: …")
    if not (x > 50000.0):
        raise RefinementViolation("…predicate failed: x > 50000.0 (x=…)")
    return x
```

The predicate text is rendered as **literal Python** in the stub source —
this is the direct realisation of the figure's "After predicate compilation
(executable monitor function)" step. `act()` consults a `_REFINEMENT_GUARDS`
dispatch table on every send, so even a caller that bypasses the convenience
methods cannot bypass the guard:

```python
if direction == "send":
    guard = _REFINEMENT_GUARDS.get((peer, label))
    if guard is not None:
        payload = guard(payload)  # raises BEFORE state advance
self.state = matching[0]["target"]
```

**Claude subagent markdown.** The same predicate now surfaces in two places
the LLM reads:

- A new top-level `## Refinement Invariants (HARD — enforced at call site)`
  section listing every predicate that applies to this role.
- Per-action annotations in `## Allowed Actions by State`, e.g.
  `SEND to TaxSpecialist: HighRevenue(Double) -> state 12  [must satisfy `x > 50000.0`]`.

This is the LLM-facing side of the fix; the Python stub is the runtime
side. The LLM sees the constraint at decision time *and* the harness
rejects violators before emission.

### Edit 3 — call-site enforcement test

`test_callsite_refinement.py` exercises the Fetcher role on the existing
`P1_v2.scr` + `P1_v2.refn`:

| Check | What it proves |
|---|---|
| violating payload via tool method raises RefinementViolation | predicate fires |
| violation message names the predicate | error is actionable for the LLM |
| state did NOT advance after failed guard | atomic — no half-step |
| history is empty after failed guard | no spurious record |
| passing payload advances state | non-regression of normal path |
| passing payload returns the next state | EFSM contract intact |
| history records the send | observable correctly |
| act() bypass with bad payload still blocked by guard | bypass-proof |
| state unchanged after blocked bypass | atomicity holds for bypass too |
| unrefined send proceeds normally | guard scoped to refined sends only |

All 10 checks pass.

## Before / after

```
BEFORE                                AFTER
─────────────────────────────────     ─────────────────────────────────
agent.act("send", B, "Transfer",      agent.send_Transfer_to_B(amount)
          amount)                       │
  │                                     ▼ compiled predicate runs
  ▼ EFSM check (structural only)        if not (amount < 50000):
  state := next                            raise RefinementViolation
  emit on wire                          ▼ EFSM check (structural)
  │                                     state := next
  ▼ later: SessionMonitor reads         emit on wire
    events.jsonl
  if predicate fails: log audit       (no after-the-fact monitor needed;
                                       violation surfaces as a tool error
                                       the LLM can self-correct from)
```

## What remains open

The fix closes the call-site enforcement gap. It does **not** address:

1. **Static discharge of obligations.** `z3-solver` is in the venv but
   unused. A future pass should statically verify that each branch of a
   choice produces predicates a downstream role can satisfy, à la
   Bocchi/Honda asserted MPST well-formedness. Today, contradictions are
   only caught at runtime.

2. **JSON-schema-shaped tool descriptions.** For frameworks that consume
   structured tool schemas (OpenAI / Anthropic function-calling), the
   predicate currently appears in the prose tool description but not as
   a JSON-Schema `minimum` / `pattern` constraint. Adding a schema-export
   path would let the model's structured-output enforcer reject violators
   even earlier.

3. **Syncing prose decision rules with `.refn`.** `skills_generator.py`
   produces English thresholds in `*_skills.md` (e.g. "value > $10,000")
   that can drift from the `.refn` (`x > 50000.0`). Either generate the
   skill prose *from* the `.refn` or check them for consistency.

4. **Receiver-side assumption checks.** Today only sender obligations are
   compiled in. The natural extension is to also generate a receive-side
   guard that asserts the assumption (logging if a peer sends something
   the receiver was told to expect to satisfy `P` but doesn't).

5. **Existing callers.** `agent_generator.py` has no callers in the
   current repo (grepped 2026-05-13). No call sites needed updating. If
   `evolution_loop.py` later starts producing agent stubs as a final
   pipeline step, it should call
   `generate_all_agents(..., protocol_path=<scr_path>)` so refinements
   auto-load.

## Files changed

| File | Change |
|---|---|
| `refinement_checker.py` | + `RefinementViolation` exception class |
| `agent_generator.py` | rewrite: compile refinements into per-send tool methods and into `act()` dispatch; surface invariants in Claude subagent markdown |
| `test_callsite_refinement.py` | new — 10 checks, all passing |
| `GAP_CLOSED.md` | this file |
