# W19 — Self-observed coordination failures, and the protocol that would have prevented them

Worker report for the case-study assignment: this project (STJP) was itself
built this week by a coordinator ("planner") directing about 20 worker
agents. That build hit four real coordination failures. None of the rules
that would have prevented them lived in any committed file — they lived
only in prose instructions and shared assumptions between the planner and
the workers. This report records what happened, names the missing
protocol feature in each case, and then builds and validates a small
formal protocol (a *Scribble* file — Scribble is this project's static
protocol checker, the tool that rejects a proposed message-exchange plan
if it can *deadlock* — every participant stuck waiting on a message
nobody will ever send — or can't be split into per-agent contracts) that
would have closed each gap.

This is a case study of **one system** (this repository's own build). It
is offered as motivation and as a worked example — not as a statistical
claim. A sample of one cannot show how often these failures happen in
general; it can only show, concretely, that they happened here, and what
would have stopped them.

Everything below is drawn from the incident record supplied for this task
(a planner's summary of its own session log). Nothing is invented beyond
those facts.

---

## The meta-finding, stated first

This project's central argument is that documented artifacts under-state
the coordination a deployed multi-agent system actually needs — that the
gap between "what's written down" and "what the system needs to not fall
over" is real and worth measuring. The clearest evidence for that claim
this week didn't come from an experiment. It came from watching the
project's *own* build process fail in exactly the way the project studies.

The rules that were actually load-bearing during this build —
"a worker must report its own completion, nobody will notify it";
"only one worker may hold the shared repository checkout at a time";
"the coordinator, not the workers, owns the payload shape crossing a
boundary" — were never written into a skill file, a schema, or any
artifact a later reader could open and check. They lived in the planner's
prompts to each worker, in conventions repeated by hand each time a new
worker started, and in the planner's own memory of what had already gone
wrong once. When a worker's instance of that convention was missing or
ambiguous, the convention did nothing to stop the failure — a human (or
the planner) had to notice the stall or the vanished commit and intervene
by hand.

That is exactly the documented-vs-deployed gap this project's mining
experiments try to measure from the outside, in other people's
repositories. Here it showed up from the inside, in this one. The section
below on the candidate protocol is an attempt to take four rules that
existed only as prose during this build and turn them into a formal
protocol — one a checker can accept or reject, rather than a convention a
human has to remember to repeat.

---

## Incident 1 — Stalled waiting for a signal that was never coming

**What happened.** Two different workers (referred to here as "W1" and
"W3") each paused mid-task and reported they would "wait for the
completion notification" before continuing. But the notification system
in this build only ever signals the **coordinator** — it has no path to
a worker at all. Each worker sat idle until the planner noticed the
stall and manually resumed it with an explicit instruction: "no
notification is coming to you; drive to completion."

**Root cause.** Nobody had ever written down, anywhere both sides could
check it, which direction a completion signal travels. The coordinator
assumed workers would report on their own; each worker assumed it would
be told when to proceed. Both assumptions are reasonable in isolation —
the failure is that the *direction* of the signal (who sends it, who
receives it) was a shared convention in someone's head, not a stated
contract either side could verify against.

**The protocol feature that would have prevented it.** An explicit
completion message that a worker's contract requires it to **send**. In
the candidate protocol below, a worker's local contract (the part of the
global protocol projected down to just that role — see
`docs/1_TECH_SETUP.md` for what "projection" means) literally has no
"wait to receive a completion notice" state in it. After it receives its
task card, its very next allowed action is to choose between sending
`Done` or sending `Blocked` — there is nothing else it is allowed to do.
A worker cannot even attempt to "wait for a notification" that isn't in
its contract, because a checker enforcing that contract would reject any
other move. The fix isn't a better reminder — it's making "wait to
receive" structurally absent from the role that must never do it.

---

## Incident 2 — Two writers on one shared resource

**What happened.** Twice, at different points in the build, a worker
(referred to here as "W8" and "W15") checked out its working branch
inside the **shared** main repository directory — the coordinator's own
working copy — instead of its own private *worktree* (a separate,
isolated checkout of the same repository that a worker can modify without
touching anyone else's checkout). Doing this silently moved the shared
checkout's `HEAD` (the pointer to "what commit is currently checked out")
out from under the coordinator mid-operation. The coordinator observed a
committed fix apparently "vanish" — what had actually happened is that
`HEAD` had been moved to point somewhere else by the other worker's
checkout, not that the commit was lost. W8 noticed its own mistake and
restored the shared directory; W15 did not, and the coordinator had to
diagnose and fix it.

**Root cause.** "Each worker gets its own worktree, don't touch the
shared directory" was a rule stated in prose to each worker, not a
permission that was granted and could be checked. Nothing made "the
shared directory belongs to nobody but the coordinator right now" a fact
a worker's tooling could look up and refuse to violate. A worker acting
in good faith, but under a slightly different mental model of "which
directory is mine," had no way to be told it was wrong before the damage
was already done.

**The protocol feature that would have prevented it.** An exclusive
workspace-grant message, sent before any worker is allowed to touch a
shared directory at all. In the candidate protocol, `AssignWorkspace` is
the first message a worker ever receives, and it is what makes "this
worktree, and only this worktree, is yours" a fact recorded in the
protocol rather than a sentence in a prompt. Any use of a directory that
wasn't granted this way is now a **checkable protocol violation** — a
runtime monitor watching the exchange has something concrete to compare
against, instead of nothing.

---

## Incident 3 — A message-format mismatch killed a run instantly

**What happened.** The first live run of the judge-panel orchestration (a
component of this project that runs several LLM judges over a shared set
of test cases) crashed on its very first line of work. The case data
arrived as a JSON-encoded **string** — a payload that had been serialized
to text — where the receiving script expected a **structured object**
(a dictionary/list Python could index directly). The concrete symptom
was `args.cases undefined`: the script tried to treat the string as
already-parsed data. One defensive parse (detect the string case, decode
it) fixed the immediate crash, but the run had already died before any
actual judging work happened.

**Root cause.** The payload type of a message from the coordinator to
the orchestrator was never checked at the boundary between them. Nothing
in the handoff declared "this field is a structured object, not a string
that happens to look like one" in a way that could be verified before the
receiving code ran. The mismatch was only caught by the code crashing.

**The protocol feature that would have prevented it.** Typed message
payloads, checked at the boundary. Every message in the candidate
protocol declares a payload type up front (in this small protocol, all
payloads are declared as `String`, but the mechanism is the same one this
project already uses elsewhere for numeric fields — see the `Double`
payloads in `experiments/cases/finance/protocols/v1.scr` for an example
of a differently-typed field). A checker validates that every sender
actually produces the declared type and every receiver is written to
consume it, before the protocol is accepted at all — the mismatch between
"string" and "structured object" becomes a rejection at validation time,
not a crash on the first live message.

---

## Incident 4 — Concurrent writes to one branch

**What happened.** The coordinator's push to the shared `main` branch was
rejected mid-task because the human project owner merged pull requests
into `main` at the same time. The coordinator had to rebase its work onto
the branch's new tip before it could push. This one was handled safely —
nothing was lost — but only because the coordinator happened to check for
the rejection and react correctly.

**Root cause.** There was no turn-taking or ownership contract for who is
allowed to write to a shared branch at a given moment. It worked out this
time because Git itself refused the conflicting push and the coordinator
noticed the rejection — the safety net was Git's own protection, not
anything this build's coordination rules provided.

**The protocol feature that would have prevented it.** A branch-ownership
hand-off message: a resource asked for a push turn, granted it to exactly
one holder, and required that holder to explicitly release it before
anyone else could be granted the next turn. In the candidate protocol,
this is modeled by the `Repo` role: a worker sends `PushRequest`, `Repo`
answers with `PushGrant`, and only after the worker sends `PushDone` can
`Repo` grant the next request. This is the same shape of fix as Incident
2 (exclusive use of a shared resource, made explicit and checkable) but
applied to the shared branch rather than the shared working directory —
worth naming separately because it is a distinct resource with a distinct
failure mode (Git's own rejection saved this one; nothing saved Incident
2).

---

## The candidate protocol

`experiments/cases/planner_workers/` is a new candidate case built from
the four incidents above. It is deliberately small — one `Coordinator`,
two `Worker` roles, and one `Repo` role standing in for the shared
repository — modeling the *pattern* behind the failures, not
reproducing the full ~20-agent build.

**Protocol shape** (`experiments/cases/planner_workers/protocols/v1.scr`):

- `AssignWorkspace` + `TaskCard`, from `Coordinator` to each worker
  (fixes Incident 2 — the workspace grant is now an explicit message,
  not a prose rule).
- Each worker's very next move is a choice between sending `Done` or
  sending `Blocked` — there is no receive-shaped "wait for notice" state
  anywhere in a worker's local contract (fixes Incident 1). The
  coordinator answers every report with a `ReviewVerdict`.
- A worker whose work was accepted sends `PushRequest` to `Repo`; `Repo`
  answers with `PushGrant`; the worker sends `PushDone` to release it.
  `Repo` will not grant the next request until the current holder
  releases (fixes Incident 4, and generalizes the fix for Incident 2 to
  the shared branch specifically). A worker whose work was blocked sends
  `PushSkip` instead, so `Repo`'s state is never left guessing which
  branch happened.
- Every message declares a payload type (`String` throughout this small
  protocol), checked by the same boundary-typing mechanism used
  elsewhere in this project for other payload types (Incident 3's fix —
  this project already applies it to numeric fields in other cases; this
  case applies the identical mechanism).

**It passes the real Scribble checker.** Command run from the repo root,
using the project's own validator:

```
python3 -c "
from pathlib import Path
from stjp_core.compiler.validator import ScribbleValidator
v = ScribbleValidator()
ok, err = v.validate_protocol(Path('experiments/cases/planner_workers/protocols/v1.scr'))
print('VALID' if ok else 'INVALID')
print(err)
"
```

Verdict: **`VALID`** (empty error string — Scribble's convention is
silence on success).

As a second check, projecting the protocol down to `Worker1`'s local
contract confirms the Incident-1 fix directly — the projected contract
begins with a send-shaped choice, not a receive:

```
AssignWorkspace(String) from Coordinator;
TaskCard(String) from Coordinator;
choice at self {
  Done(String) to Coordinator;
  ReviewVerdict(String) from Coordinator;
  PushRequest(String) to Repo;
  PushGrant(String) from Repo;
  PushDone(String) to Repo;
} or {
  Blocked(String) to Coordinator;
  ReviewVerdict(String) from Coordinator;
  PushSkip(String) to Repo;
}
```

A worker running under this contract cannot "wait for a completion
notification" — that state does not exist for it to wait in.

**What this is not, yet.** This is a validated candidate case, not a
finished benchmark entry. `experiments/cases/planner_workers/case.yaml`
has an intent, roles, and three example goals, but no trials have been
run against it and no benchmark arms have been chosen — that is future
work, tracked in `experiments/cases/planner_workers/README.md`.

---

## Honesty about strength of evidence

Everything in this report is drawn from one build, of one project,
observed once. It is useful precisely because it is concrete and
verifiable — the incidents happened, the fixes above are traceable to
specific messages in a protocol that a real checker accepts — but it is
not a measurement of how often these failure modes occur across
projects, teams, or agent frameworks in general. Treat it as a worked
example of the gap this project studies, not as a statistic about that
gap's size.
