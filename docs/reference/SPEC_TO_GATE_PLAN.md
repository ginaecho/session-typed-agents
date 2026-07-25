# Spec-to-gate plan — compiling a governance document's rules into mechanisms

The plan for turning rules that live as prose in a spec or agent markdown
(like `AGENT.md`) into the strongest mechanism each rule admits. It is the
direct follow-through of two findings from
[`SESSION_RECORD_2026-07-25.md`](SESSION_RECORD_2026-07-25.md): prose rules
scored zero of three while mechanical checks scored four of four (§9), and
the enforceability partition (§10, now
[`ENFORCEABILITY_PARTITION.md`](ENFORCEABILITY_PARTITION.md)) says exactly
which mechanism each rule admits. Expected outcomes for every runnable stage
are registered **before** running in
[`SPEC_TO_GATE_PREREGISTRATION.md`](../predictions/SPEC_TO_GATE_PREREGISTRATION.md).

One design rule governs everything here: **the language model may author a
checker; it must never be the checker.** Extraction of rules from prose is
authoring-time work (LLM-assisted, human-reviewed, committed). What runs at
the moment of action is deterministic code — because the 2026-07-25 record
shows that is the only thing that reliably held.

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [Stage 0 — the rule registry (done)](#stage-0--the-rule-registry-done)
- [Stage 1 — the conflict and precedence pass (done)](#stage-1--the-conflict-and-precedence-pass-done)
- [Stage 2 — the gate generator (done)](#stage-2--the-gate-generator-done)
- [Stage 3 — the typed publish channel (done)](#stage-3--the-typed-publish-channel-done)
- [Stage 4 — the working session as a session (future)](#stage-4--the-working-session-as-a-session-future)
- [Stage 5 — parallel dispatch of the enabled set (registered, gated)](#stage-5--parallel-dispatch-of-the-enabled-set-registered-gated)
- [Grading record](#grading-record)
<!-- MENU:END -->

## Stage 0 — the rule registry (done)

**Deliverable:** `tools/rules/AGENT_RULES.yaml` — `AGENT.md`'s enforceable
rules normalized to machine-readable records: `id`, `subject` (the thing
constrained: `branch_name`, `commit_author`, …), `statement` (the quoted
prose), `tier` (from the enforceability partition), `constraint` (a typed,
deterministic predicate: `prefix_required`, `substring_forbidden`,
`identity_required`, `trailer_forbidden_except_owner`), and `remediation`
(the guidance a gate shows on violation).

**Why a registry instead of parsing markdown at check time:** the registry
is the reviewed compilation product. Extraction from prose is where the
language model helps and where it errs; freezing the result as data means
the checkers downstream are deterministic and diffable, and a wrong
extraction is a visible one-line fix.

Beside it, `tools/rules/PLATFORM_SESSION_RULES.yaml` transcribes what the
hosted-session platform actually mandates (observed in this session and on
2026-07-25: a `claude/...` working branch, an assistant co-author trailer, a
bot commit identity). It is a rule source like any other — which is the
point: conflicts between sources become data, not vibes.

## Stage 1 — the conflict and precedence pass (done)

**Deliverable:** `tools/check_rule_conflicts.py`. Loads every rule source,
groups rules by subject, and decides compatibility mechanically (a required
prefix `claude/` is incompatible with a required prefix `gc/`; a required
trailer whose value contains a forbidden substring is incompatible with the
forbiddance; two different required identities are incompatible).

For each incompatibility there are exactly three outcomes:

1. **Undeclared conflict → hard error.** No `PRECEDENCE.yaml` covers the
   pair: exit nonzero with "no precedence declared; refusing to guess."
   This converts the most dangerous failure class of 2026-07-25 — the
   *silent* resolution toward the nearer instruction, which has no moment
   of transgression to notice — into a loud, mechanical stop.
2. **Declared winner → resolved.** `tools/rules/PRECEDENCE.yaml` ranks the
   sources (repo rules outrank platform defaults for anything that lands in
   the repository); the report names the winner and the loser.
3. **Declared exception → tolerated with a surfacing obligation.** The one
   exception on record: a platform-created working-branch *name* the agent
   cannot rename. The report says it must be stated in the agent's reply
   and merged or renamed away by the owner.

**What this is *not*:** a runtime component. It runs at compile/setup time,
where a type error belongs. (Runtime precedence — instructions arriving
mid-session — is expressible later as payload provenance plus a refinement,
per the partition; not built here.)

## Stage 2 — the gate generator (done)

**Deliverable:** `tools/gen_gate.py` — emits a deterministic gate script
from the registry's lint-tier constraints alone, including per-rule
remediation text. Parity is proven, not assumed:
`tools/tests/run_gate_parity.py` builds a throwaway git repository with six
labelled fixtures and requires the generated gate and the hand-written
`tools/check_git_rules.py` to return identical verdicts (pre-registered as
P3).

**Why generate what was already hand-written:** the hand-written checker
proves the *mechanism*; the generator proves the *pipeline* — that a rule
added to the registry becomes an enforced check with no new code. The
long-term shape: the intent-to-protocol translator (the seam — the
translation step from plain-language intent to formal protocol) gains a
second output lane, and a spec's lint-tier sentences compile to gates the
same way its ordering sentences compile to protocol.

## Stage 3 — the typed publish channel (done)

**Deliverable:** `experiments/cases/publish_flow/` — the fence-to-field
move for one irreversible outward act, `git push`:

- `protocols/v1.scr` — `PushRequest(String)` from Agent to Repo (payload:
  the branch name), Repo answers `PushAck` or `PushRejected`. Validated by
  the real Scribble-Java compiler, built from source in this container.
- `protocols/v1.refn` — the payload predicate compiled from the same
  registry rules: branch starts with `gc/` and contains no forbidden
  keyword.
- `check_publish_flow.py` — a deterministic driver (no agents, no
  statistics) that replays a forbidden push and a clean push through the
  projected monitor. The forbidden one is refused **before delivery** with
  the registry's remediation text; the clean one completes to the accepting
  state.

**The distinction this stage demonstrates:** the pre-push hook from the
first round of fixes is a *fence* — it protects only clones that enabled
it (and the 2026-07-25 session ran under a global hooks path that a
repo-local fence never touches). A typed channel is the *field*: when the
only executable path to `git push` is the projected send tool, the rule is
checked at the call site with nothing to forget and nothing to bypass —
the same mechanism `GAP_CLOSED.md` built for payload rules generally.

## Stage 4 — the working session as a session (future)

The generalization of stage 3, not built yet: model an agent working
session's *significant actions* as protocol messages (`RulesAck` for "the
git rules are loaded", `PushRequest`, `RegisterPrediction`, `RunStart`), so
that orderings like "rules retrieved before the first push" and
"registration precedes the trial" become type structure — unrepresentable
to violate — rather than document placement. Scribble already checks such
orderings; the missing piece is only the mapping from working session to
session. Faithfulness of that mapping (does the proposed type capture the
document's intent?) is the seam-faithfulness problem and stays with the
judge-panel program; *coverage* is mechanical: every normative sentence in
the source doc must map to a message, a refinement, a lint rule, or an
explicit residual entry — an unmapped rule fails the compile.

## Stage 5 — parallel dispatch of the enabled set (registered, gated)

Design and predictions in
[`PARALLEL_SCHEDULER_PREREGISTRATION.md`](../predictions/PARALLEL_SCHEDULER_PREREGISTRATION.md).
**No runner code is changed by this plan** — `AGENT.md` forbids touching the
runner without re-running all cases, and this environment cannot run the
live suite. The pre-registration exists so the change, when made, is made
against predictions that predate it.

## Grading record

Filled after the runs; see the pre-registration for the predictions.

| Prediction | Result |
|---|---|
| P1 — conflict pass, no precedence: 4 undeclared conflicts, hard error | **pass** — exactly `branch_name`, `commit_author`, `commit_committer`, `commit_trailer`, each "UNDECLARED: … refusing to guess", exit 1 |
| P2 — conflict pass, with precedence: 3 resolved + 1 tolerated, exit 0 | **pass** — 3 RESOLVED to AGENT.md, `branch_name` TOLERATED with the surfacing obligation, 0 undeclared, exit 0 |
| P3 — generated gate ≡ hand-written checker on 6/6 fixtures | **pass** — 6/6 agree, all matching the expected verdicts |
| P4 — publish-flow protocol validates under real Scribble | **pass** — `(True, '')` on the first committed draft (compiler built from source in-container) |
| P5 — forbidden push refused pre-delivery; clean push conformant | **pass** — 1 refusal with remediation shown; corrected push delivered, globally conformant, accepting state |

One known scope note from P3, recorded rather than smoothed over: the
hand-written checker additionally accepts the owner's two Microsoft
identities and GitHub's web-editor committer (facts of AGENT.md's mirror
flow); the registry currently encodes only the primary identity. The six
registered fixtures do not exercise that difference. Extending the registry
schema to identity *lists* is a one-field change when wanted.
