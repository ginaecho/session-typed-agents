# Glossary — plain-language meaning of every term used in the STJP docs

Written 2026-06-17 because the reports had grown acronym-heavy. Each entry gives
the plain meaning first; the short form (if any) is in brackets.

## The benchmark measurements

- **Goal-Completion Rate** *(was "GCR")* — the percentage of trials in which the
  agents achieved every goal that applied on that run, *including* the final
  "report delivered to the user" goal, all in a single attempt. 100% = every trial
  fully finished the task correctly on the first try.

- **Critical-Goal Completion** *(was "CGC")* — a stricter version of the above: the
  trial counts only if the agents finished the goals **and** satisfied every
  *critical property* (see below — used the real data, read all the inputs, got
  authorization before the irreversible step). "Did they really achieve it,"
  not just "did a report appear."

- **Cost-to-goal** — the average number of tokens spent *per delivered report*,
  i.e. total tokens divided by the completion rate. It charges an arm for the
  tokens wasted on trials that failed. An arm that is cheap per trial but rarely
  finishes has a high cost-to-goal.

- **Time-to-goal** — the same idea for wall-clock seconds: seconds per delivered
  report.

- **Monitor acceptance / delivered violations** — how many messages the runtime
  checker accepted as on-contract versus how many off-contract messages actually
  reached their recipient.

## The severity ladder (how harmful a deviation is)

Instead of counting every difference as a "violation," each off-contract action is
graded by consequence (this answers the fair objection that "different ≠ wrong"):

- **Benign** *(was "S0")* — a harmless reorder or a different word for the same
  thing. Not counted against correctness.
- **Waste** *(was "S1")* — a duplicate or pointless message. Costs tokens only.
- **Skipped obligation** *(was "S2")* — a required step was missed or done out of
  order.
- **Never finished** *(was "S3")* — the run stalled and never delivered.
- **Disaster** *(was "S4")* — an *irreversible* action happened before the step
  that authorizes it (e.g. the report was filed before the audit, or money moved
  before approval). The worst class.

## The three "critical property" checks (when following the protocol truly matters)

- **Data provenance / "no guessing"** *(was "C1")* — the number an agent reports
  must be the real number it received, not one it invented.
- **Context completeness / "read everything first"** *(was "C2")* — the agent must
  have taken in all its required inputs before producing its output, and the
  output must actually reflect them.
- **Authorization before an irreversible step** *(was "C3")* — the same idea as the
  "disaster" severity above, checked directly.

## The settings being compared (the "arms")

- **Intent only** — the agents get the plain-English task and their role
  descriptions, nothing more. (The everyday multi-agent setup.)
- **+ Global protocol** — the agents additionally get the whole validated protocol
  pasted in as text.
- **Projected local contract** — each agent gets only *its own* part of the
  protocol (what it may send, what it must wait for, what values are valid).
- **Minimal local contract** — the same, compressed to one line per step.
- **Enforcement gate** — the projected local contract plus a checker that *blocks*
  a wrong message before it is delivered and asks the agent to try again.

## The machinery

- **Multiparty Session Types** *(was "MPST")* — the branch of type theory that
  describes a conversation among several parties as a single "global type," then
  mechanically splits it into one local type per party. The formal foundation STJP
  builds on.
- **Scribble** — the existing, off-the-shelf tool that checks a global type for
  problems (deadlocks, unreachable steps) and performs the split. STJP uses it
  unchanged.
- **Global type / global protocol** — the whole conversation written down once:
  who sends what to whom, in what order.
- **Projection** — the mechanical step that turns the one global protocol into a
  separate per-role contract for each agent.
- **Local type / local contract / projected contract** — one agent's own slice of
  the protocol, produced by projection.
- **Per-role state machine** *(was "EFSM", extended finite-state machine)* — the
  contract written as states and allowed transitions; the monitor walks it to
  decide whether each message is allowed.
- **Runtime monitor** — a small plain-Python program (not an AI agent) that sits
  beside each agent and checks every message against that agent's state machine.
- **The gate** — the monitor run in *enforcing* mode: it rejects a wrong message
  before delivery instead of merely recording it.
- **Choice guard** — a rule attached to a decision point saying which branch the
  data requires (e.g. "if revenue is over $50,000 you must take the audit
  branch"). Checked by the monitor against values it has already seen.
- **Refinement / payload guard** — a rule on a message's value (e.g. "this number
  must be positive").

## STJP itself

- **STJP** — "Session-Typed Joint-Pipeline" (also written Session-Typed Agent
  Pipelines): this project. It turns a plain-English intent into a verified
  protocol, splits it into per-agent contracts, and watches/at-will-enforces them
  with runtime monitors.
