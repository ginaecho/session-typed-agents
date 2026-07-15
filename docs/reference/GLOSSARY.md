# Glossary — plain-language meaning of every term used in the STJP docs

Written 2026-06-17 because the reports had grown acronym-heavy. Each entry gives
the plain meaning first; the short form (if any) is in brackets.

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [The benchmark measurements](#the-benchmark-measurements)
- [The severity ladder (how harmful a deviation is)](#the-severity-ladder-how-harmful-a-deviation-is)
- [The three "critical property" checks (when following the protocol truly matters)](#the-three-critical-property-checks-when-following-the-protocol-truly-matters)
- [The settings being compared (the "arms")](#the-settings-being-compared-the-arms)
- [The machinery](#the-machinery)
- [STJP itself](#stjp-itself)
- [The intent-to-protocol training program (docs/8, docs/reference/SEAM_*.md)](#the-intent-to-protocol-training-program-docs8-docsreferenceseam_md)
<!-- MENU:END -->

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
  It is the system's **active enforcer**, and it runs in one of two modes:
  *observe* mode records a violation but lets the message through, while
  *enforce* mode rejects a disallowed message before delivery. The same
  component in both modes — there is no separate enforcer.
- **The gate** — the monitor run in *enforcing* mode: it rejects a wrong message
  before delivery instead of merely recording it. "Gate" is the engine-code name
  for the monitor's enforce mode, not a second component.
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

## The intent-to-protocol training program (docs/8, docs/reference/SEAM_*.md)

These terms are specific to the effort to train a model to do the first
step of STJP's pipeline (turning a plain-English request into a validated
protocol) automatically.

- **The intent-to-protocol translation step** *(nickname: "the seam")* — the
  step where a plain-language request becomes a formal, Scribble-checked
  protocol. Today an LLM drafts it and a human signs off; the training
  program's goal is to make a smaller, specialized model do it well.
- **Bisimulation** — a formal equivalence check between two state machines
  meaning "these two behave identically no matter what happens" — the
  strictest practical notion of "these two protocols mean the same thing."
- **Gold** *(as in "gold pair" or "gold protocol")* — a known-correct
  reference protocol or answer that a candidate is scored against.
- **Canary** — a planted check item with a known correct answer, mixed into
  a batch to verify the checking process itself is working (e.g. a judge
  that accepts an intentionally mismatched intent/protocol pair has failed
  the canary).
- **Escrow** *(as used in the example protocols)* — a neutral third party
  that holds funds until both sides of a deal deliver.
- **Geometric median** — a robust way to combine several scores into one so
  that a single extreme outlier cannot drag the combined result too far.
- **Smoke test** — a quick end-to-end check: run the whole pipeline once,
  for real, to confirm it visibly works before trusting it at scale.
- **SFT** (supervised fine-tuning) — training a model on labeled correct
  examples (as opposed to reinforcement learning, below).
- **GRPO** (Group Relative Policy Optimization) — a reinforcement-learning
  method that scores each sampled output against the average of a sampled
  group, instead of training a separate value-estimating model.
- **LoRA** (Low-Rank Adaptation) — a fine-tuning technique that trains a
  small add-on set of weights instead of the whole model, making training
  cheap enough to run on a single GPU.
- **AST re-emission** — regenerating a protocol's text from its parsed
  structure (its abstract syntax tree) rather than editing the original
  text, so that comments and any other hidden text are dropped from the
  output.
