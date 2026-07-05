# E10 — Crash handling: no session left in limbo (Prototype 3)

*2026-07-05, branch `gc/stjp_stateful_extension`. Prototype 3 of
`docs/EXTENSIONS_PLAN`. Licensing theory: **Viering–Chen–Eugster–Hu–Ziarek,
ESOP 2018** — failure-aware local types with typed try/handle regions and a
robust coordinator: a crash of any role inside a region routes every live role
into a statically-checked handler, and the type system proves the handlers are
safe. STJP's mapping is direct: the scheduler is the coordinator, the monitors
hold the per-role EFSMs, and the audit's 22 non-terminal trials were the untyped
version of exactly this problem.*

## What was built (all on this branch)

- **`.fail` sidecar + parser** — `stjp_core/compiler/crash_handling.py`:
  `region … covers …`, `on crash <Role> : <msgs> ; goal := <Terminal>` (or
  `ESCALATE`), `timeout <Role|*> = k polls`. The escrow spec is
  `experiments/cases/escrow_trade.fail`.
- **Four STATIC validator checks** (`validate_fail`): **coverage** (every
  crashable role has a handler or ESCALATE), **projectability** (each handler is
  a well-formed mini protocol over the *live* roles), **recoverability** (every
  handler reaches a typed terminal — "no crash leaves the session in limbo"),
  and **no-authorization-bypass** (a handler whose trace would trip a Critic
  safety policy is rejected — this is what stops a recovery path from shortcutting
  authorization).
- **Runtime** — `detect_crashes` (a role idle past its `timeout` budget is
  declared crashed, with a deterministic lexicographic tie-break) and
  `resolve_crash` (→ `typed_degraded` / `typed_abort` / `limbo`). CGC accounting
  gains a third outcome, **typed-degraded** (`goal := Refunded`), distinct from
  both success and limbo.
- **Verdict corpus — 12/12** (`experiments/tests/verdict_corpus/crash/`): crash
  at region boundaries, coordinator crash → ESCALATE, timeout that resolves one
  poll before the limit (no false crash), two roles timing out in one round
  (tie-break), degraded-goal accounting, and all four validator rejections
  including the **adversarial settlement-shortcut**. Passed before the benchmark.

## E10 result — deterministic (no LLM)

**Crash-point grid** — crash each escrow role at each of its EFSM states:

| arm | outcomes over 14 crash cells | disasters |
|---|---|---|
| **(a) current STJP** (no crash-handling) | **14/14 LIMBO** | — |
| **(b) STJP + crash-handling** | **9 typed-degraded + 5 typed-abort, 0 limbo** | **0** |

Every crash in the shipped system leaves the session in limbo (this is the
22-trial audit failure, now shown systematically). With CF, **every** crash
reaches a *typed* terminal — a `Refunded` degradation for a party crash, an
`ESCALATE` typed-abort when the coordinator (Escrow) itself crashes — and **0
disasters**, because the handler is validated to never bypass authorization.

**Checker mutation** (extends E1's preciseness discipline to the new checker):
**5/5 seeded bad `.fail` files rejected** — uncovered pair, no-terminal handler,
sender==receiver, dead-role receiver, and the settlement-shortcut. The new
checker gets the same soundness audit as the old one.

**Deadlock replay on real data** — the 19 genuine gated-arm deadlocks (a stalled
role *is* a crash): **baseline 19/19 limbo → +CF 19/19 typed terminal.** The
property that would have made the 22-trial audit a compile error now exists.

Reproduce: `python experiments/subagent_trials/e10_crash_bench.py`;
verdict corpus `python experiments/tests/verdict_corpus/crash/crash_corpus.py`.

## E10 result — live flaky-role (haiku roles)

<!-- LIVE_RESULTS -->

## Paper insertion

The Limitations paragraph flips from roadmap to result; new §7 item "E10 — Crash
handling." The 22-trial audit story gets its closing sentence: *the property
that would have made this a compile error now exists* — every crash reaches a
statically-checked typed terminal, and the validator rejects any handler that
would recover by bypassing authorization. Cite `\citep{viering18}`.
