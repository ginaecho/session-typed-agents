# planner_workers

**Status:** validated candidate case. `experiments/cases/planner_workers/protocols/v1.scr`
passes the real Scribble checker (`stjp_core.compiler.validator.ScribbleValidator.validate_protocol`
returns `(True, "")` — see `docs/reference/reports/seam/W19_SELF_OBSERVED_COORDINATION_FAILURES.md`
for the exact command and output). Benchmark goals, trial counts, and arm
selection have not been tuned yet; that is future work, not part of this
submission.

## Where this case came from

This protocol was drafted from a real incident record — the coordination
failures a planner agent and its ~20 worker agents actually hit while
building this repository this week (recorded in the report above, not
invented for this case). It models the pattern behind those failures:

- A coordinator hands each worker its own private workspace and a task
  card (`AssignWorkspace`, `TaskCard`).
- A worker's local contract has no "wait to receive a completion signal"
  state. It must **send** either `Done` or `Blocked` before anything else
  happens on its side — see the projected contract in the report, which
  starts with a send-shaped choice, not a receive.
- A shared repository (`Repo`) hands out one push turn (`PushGrant`) at a
  time and will not grant the next request until the current holder sends
  `PushDone` (or `PushSkip`, if it never asked). Two workers can never
  hold the shared branch together.

The case is deliberately small — one coordinator, two workers, one shared
repo role — to model the pattern that caused the failures, not to
reproduce the full ~20-agent build.

## Files

- `case.yaml` — intent, roles, goals
- `protocols/v1.scr` — the Scribble global protocol (passes validation)

No `runs/` directory yet; no benchmark trials have been run against this
case.
