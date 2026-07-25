# Pre-registration — spec-to-gate toolchain (rule registry, conflict pass, gate generator, typed publish channel)

Registered 2026-07-25, **before** any of the four deliverables below was run.
Per the fairness checklist (BENCHMARK_PLAN_V2 §11) and the standing rule in
`AGENT.md` ("Experiments: one variable, registered first"), the expected
outcome of each check is written here first and graded after. These are
deterministic tools, not statistical arms — but the same discipline applies,
because a checker whose expected catches are written down after it runs can
never miss.

Design context: [`SPEC_TO_GATE_PLAN.md`](../reference/SPEC_TO_GATE_PLAN.md).
Amendments, if any, will be recorded below in their own section with reasons,
before the affected run.

## P1 — Conflict pass, no precedence declared

Input: the two rule sources in `tools/rules/` — `AGENT_RULES.yaml`
(normalized from `AGENT.md`) and `PLATFORM_SESSION_RULES.yaml` (transcribed
from the real hosted-session defaults observed in this session and on
2026-07-25: platform-created `claude/...` branch, required assistant
co-author trailer, bot author/committer identity).

**Prediction:** run WITHOUT a precedence declaration, the checker reports
exactly **4 conflicted subjects** — `branch_name`, `commit_trailer`,
`commit_author`, `commit_committer` — each marked *undeclared*, and exits
nonzero with a "no precedence declared; refusing to guess" report. It must
NOT silently pick a winner: silent resolution is the failure mode this tool
exists to kill (SESSION_RECORD_2026-07-25 §7, §9 "precedence failure").

## P2 — Conflict pass, precedence declared

Same input plus `tools/rules/PRECEDENCE.yaml` (repo rules outrank platform
rules; one declared exception: a platform-created working-branch *name* the
agent cannot rename is tolerated with a warning that must be surfaced in the
agent's reply).

**Prediction:** exactly **3 subjects resolve to the AGENT.md rule**
(`commit_trailer`, `commit_author`, `commit_committer`), **1 subject
resolves to tolerated-with-warning** (`branch_name`), **0 undeclared
conflicts**, exit code 0.

## P3 — Generated gate agrees with the hand-written checker

`tools/gen_gate.py` generates a gate script purely from the machine-readable
constraints in `AGENT_RULES.yaml`. Both the generated gate and the
hand-written `tools/check_git_rules.py` run over the same fixture set: a
throwaway git repository with six labelled cases (clean commit; wrong author
identity; forbidden keyword in the message body; assistant co-author
trailer; branch named `claude/x` with a clean commit; branch named `gc/x`
with a clean commit).

**Prediction:** verdict agreement on **6 of 6** fixtures (violation /
no-violation per fixture, same subjects flagged). Any disagreement is a bug
in the generator or an ambiguity in the registry — either way reported, not
patched into agreement silently.

## P4 — The typed publish channel validates

`experiments/cases/publish_flow/protocols/v1.scr` (Agent sends
`PushRequest` carrying the branch name to Repo; Repo answers `PushAck` or
`PushRejected`).

**Prediction:** the committed protocol validates under the real
Scribble-Java compiler (built in this container from source, the same way
the 2026-07-25 session built it). If any intermediate draft is rejected by
the compiler, the rejection is reported in the case README as an authoring
catch — not hidden.

## P5 — The gate refuses the forbidden branch pre-delivery

The demo driver replays two pushes through the projected monitor with the
`.refn` payload predicate (`branch starts with gc/, contains no forbidden
keyword`).

**Prediction:** the push with branch `claude/stjp-opus5-improvements-1qri4e`
(this very session's platform-assigned branch) produces **exactly one
refinement violation attributed to Agent and is refused before delivery**,
with the registry's remediation text shown; the push with branch
`gc/stjp-opus5-improvements` is delivered, the session reaches its accepting
state, and **zero violations** are recorded.

## Later registration, same day — Stage 4 increment 1 (P6–P8)

Registered 2026-07-25, after P1–P5 were graded and **before** any of the
three artifacts below was written or run. The increment: `governed_push` —
the first working-session action executed *through* the typed channel
rather than beside it. Roles: Agent, Registry (verifies that the rules
section quoted in `RulesAck` matches the current AGENT.md bytes), Repo (the
real `git push`, executed only on gate-passed delivery).

### P6 — the GovernedPush protocol validates

**Prediction:** the committed `experiments/cases/governed_push/protocols/v1.scr`
(RulesAck → RulesOk → PushRequest → PushAck/PushRejected) validates under
the real Scribble-Java compiler. Any rejected intermediate draft is
reported in the case README as an authoring catch, not hidden.

### P7 — skipping the rules step is refused as off-protocol, pre-execution

**Prediction:** driving the channel with the rules step skipped (the
`--skip-rules` flag, simulating the 2026-07-25 retrieval failure — acting
without having loaded the rules) is refused **before any git command
runs**: the Agent-side projected state machine expects `RulesAck` as the
first send, so the premature `PushRequest` is an ordering violation at the
call site. The refusal names the missing step. Note the asymmetry with
asynchronous permutation tolerance: a *receiver* may see messages out of
order, but a role's **own sends** are ordered by its local type, so this
block is sound, not over-strict.

### P8 — the full sequence executes a real push, conformantly

**Prediction:** against a local bare fixture remote, the full sequence on
a `gc/`-prefixed branch (a) verifies the quoted rules text against the
live AGENT.md, (b) passes the branch-name refinement, (c) executes the
real `git push`, and (d) yields a globally conformant trace reaching the
accepting state, written to a session log. On a forbidden branch name the
push is refused pre-execution by the same refinement as P5.

If P6–P8 hold, the final push of this very increment to
`gc/stjp-opus5-improvements` will itself be performed through
`tools/governed_push.py` — the channel used in production the day it is
built, not only demonstrated.

## Grading

Each prediction is graded pass/fail in the case README and the plan document
after the runs, quoting actual output. A failed prediction stays failed;
the fix and re-run are recorded separately.
