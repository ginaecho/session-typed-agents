# publish_flow — the typed publish channel (fence → field)

A deterministic mechanism demo, not a benchmark case: no agents, no
statistics, no arms. It shows the strongest placement for a rule like
"the branch shall not contain the forbidden keyword" — not a hook that a
clone may or may not have enabled (a *fence*), but a payload refinement on
the only path to the irreversible act (the *field*).

## The pieces

- [`protocols/v1.scr`](protocols/v1.scr) — `PushRequest(String)` from Agent
  to Repo (payload: the branch name); Repo answers `PushAck` or
  `PushRejected`. **Validated by the real Scribble-Java compiler** (built
  from source in the working container; prediction P4, registered before
  the run in
  [`SPEC_TO_GATE_PREREGISTRATION.md`](../../../docs/predictions/SPEC_TO_GATE_PREREGISTRATION.md)).
- [`protocols/v1.refn`](protocols/v1.refn) — the payload predicate,
  compiled from the same rule registry that generates the git gate
  (`tools/rules/AGENT_RULES.yaml`): branch starts with `gc/` and contains
  no forbidden keyword.
- [`check_publish_flow.py`](check_publish_flow.py) — replays a forbidden
  push and a corrected push through the projected gate and monitor.

## The result (prediction P5, graded pass)

The push carrying this very session's platform-assigned branch name was
**refused before delivery** — one refinement violation, with the registry's
remediation shown at the point of refusal:

```
gate REFUSED pre-delivery: PushRequest('claude/stjp-opus5-improvements-1qri4e')
  — predicate failed: x.startswith("gc/") and ("claude" not in x.lower())
  remediation: create a gc/-prefixed branch and push that instead
```

The corrected push (`gc/stjp-opus5-improvements`) was delivered, answered
with `PushAck`, and the session reached its accepting state with zero
violations.

## Why this matters

On 2026-07-25 the same forbidden branch name was pushed for real, because
the rule lived as prose 200 lines from the action and the session's global
hooks path bypassed any repo-local hook
([`SESSION_RECORD_2026-07-25.md`](../../../docs/reference/SESSION_RECORD_2026-07-25.md)
§7). The gate here has nothing to forget and nothing to bypass: the check
runs at the call site, before the effect, exactly as
[`GAP_CLOSED.md`](../../../docs/reference/GAP_CLOSED.md) compiles payload
rules into projected send tools. Design context and the staged plan:
[`SPEC_TO_GATE_PLAN.md`](../../../docs/reference/SPEC_TO_GATE_PLAN.md).

Run it:

```bash
python experiments/cases/publish_flow/check_publish_flow.py
```
