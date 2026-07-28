# governed_push — a real `git push` executed through the typed channel

Stage 4 increment 1 of
[`SPEC_TO_GATE_PLAN.md`](../../../docs/reference/SPEC_TO_GATE_PLAN.md):
the first working-session action that runs **through** the typed channel
rather than beside it. Where [`publish_flow`](../publish_flow/) replays a
push through the gate as a demonstration, this case's driver
(`tools/governed_push.py`) executes the **actual** `git push` — and only
if the gate delivers the `PushRequest`.

## What the type encodes

[`protocols/v1.scr`](protocols/v1.scr) (Scribble-validated, prediction P6
in
[`SPEC_TO_GATE_PREREGISTRATION.md`](../../../docs/predictions/SPEC_TO_GATE_PREREGISTRATION.md)):

```
RulesAck(String)    from Agent to Registry;   // quote of the live git-rules section
RulesOk(String)     from Registry to Agent;   // Registry verified the quote against AGENT.md bytes
PushRequest(String) from Agent to Repo;       // payload: branch name (refinement: gc/, no keyword)
PushAck / PushRejected from Repo to Agent;    // the real push's actual outcome
```

"Rules loaded before the first push" is type structure: Agent's projected
local type cannot send `PushRequest` from its initial state. The
2026-07-25 failure mode — acting on a rule never retrieved
([`SESSION_RECORD_2026-07-25.md`](../../../docs/reference/SESSION_RECORD_2026-07-25.md)
§9, "retrieval failure") — becomes unrepresentable instead of
forbidden-in-prose. The `RulesAck` payload is a quote of the section
*heading onward* (not the menu link — quoting the menu would be proof of
skimming), and Registry re-verifies it against the live file, so a stale
quote fails.

## Graded results (registered before the runs)

- **P6 — pass.** The committed protocol validates `(True, '')` under the
  real Scribble-Java compiler, first draft.
- **P7 — failed as registered; amendment recorded, outcome achieved.**
  The registered wording predicted the *session monitor* would block the
  out-of-order `PushRequest` at the call site. It does not: the monitor is
  permutation-tolerant by design (an earlier message may still be in
  flight asynchronously) and only reports the unfulfilled obligation at
  trace end — the same semantics that surprised the 2026-07-25 session
  (record §8), re-confirmed here by test. The amendment: an irreversible
  side effect is a **synchronization point**, so the driver gates
  strictly — it advances each role's projected state machine in delivery
  order and refuses any send not enabled in the sender's current state,
  the effect-side analogue of the ledger's blocking mode. With that gate,
  `--skip-rules` is refused before any git command runs, naming the
  missing step. The finding is worth a sentence in the paper: observation
  may be permutation-tolerant; **effects must be gated synchronously**.
- **P8 — pass.** Against a local bare fixture remote: the full sequence
  verified the quote, passed the branch refinement, executed the real
  push (branch present on the remote afterwards), and produced a 4-event
  globally conformant trace written to `runs/`. A `claude/`-prefixed
  branch on the same real path is refused pre-execution with the
  registry's remediation.

## The honest boundary

Nothing yet *forces* an agent to call `tools/governed_push.py` instead of
raw `git push` — the channel is the strongest available path, not the only
path. Closing that requires environment support (the wrapper owning the
credentials, or the platform executing pushes only through the channel).
Until then this increment upgrades the fence (a hook that must be enabled)
to a field with a gate in it (a checked execution path that exists and is
used), and the dogfooding record below is the evidence it is used.

Run it:

```bash
python tools/governed_push.py                    # push current branch, governed
python tools/governed_push.py --skip-rules       # see the P7 refusal
```
