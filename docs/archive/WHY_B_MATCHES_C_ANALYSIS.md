# Why does "global protocol as text" match "projected local types"? — verified analysis

**2026-06-17.** Triggered by the fair question: is it fishy that setting B
(paste the whole validated protocol as text) does as well as — or better than —
the projected-local-types settings? I checked the traces. **It is not a bug, but
there are two real problems with the comparison, and one clean signal that did
survive.** Plain-language throughout (see `GLOSSARY.md`).

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [Problem 1 — the comparison is confounded by the orchestration layer](#problem-1--the-comparison-is-confounded-by-the-orchestration-layer)
- [Problem 2 — the task is too small to need local types](#problem-2--the-task-is-too-small-to-need-local-types)
- [Problem 3 — the monitor is stricter than session-type theory requires (and that, not the skills, is what fails C on the standard branch)](#problem-3--the-monitor-is-stricter-than-session-type-theory-requires-and-that-not-the-skills-is-what-fails-c-on-the-standard-branch)
- [The one clean signal that DID survive](#the-one-clean-signal-that-did-survive)
- [Honest bottom line](#honest-bottom-line)
- [What would actually show local types' usefulness (proposed next test)](#what-would-actually-show-local-types-usefulness-proposed-next-test)
<!-- MENU:END -->

## Problem 1 — the comparison is confounded by the orchestration layer

The settings do not differ *only* in "global text vs local contract." They also
use **different runners**:

| setting | type format | who decides who speaks next |
|---|---|---|
| **B** (global text) | whole protocol pasted | a **central LLM orchestrator** (Microsoft Agent Framework GroupChat) picks the next speaker each turn |
| **C** (local types) | per-agent contract | **no orchestrator** — round-robin; each agent decides on its own when to act |
| **C+** (local + gate) | per-agent contract | round-robin **+ a checker that blocks a wrong message before delivery** |

So B vs C changes **two things at once**: the type format *and* whether there is a
central coordinator. B's central orchestrator is doing real coordination work — it
sequences the agents. That advantage is being mis-attributed to "global text."

**Evidence.** Every C failure was the *same* standard-branch ordering mistake:
`TaxVerifier` sent its `Approval` before `RevenueAnalyst` had sent the required
`NotifyStandardRole` to `TaxSpecialist`. In the decentralized round-robin runner,
`TaxVerifier` jumps in as soon as it can; nothing holds it back, so it acts out of
order and the run desyncs and never finishes. In B, the central orchestrator never
calls on `TaxVerifier` until the notification has happened — so the same mistake
never occurs. That is the orchestrator's doing, not the global-text format's.

**To compare type-format fairly, hold orchestration constant** — e.g. add an arm
"global text on the round-robin runner," or "local types under the GroupChat
orchestrator." Right now we have neither, so B-vs-C is not a clean test.

## Problem 2 — the task is too small to need local types

Local (per-agent) types exist to help with **scale** and **need-to-know**: when the
protocol is large, reading the *whole* thing every turn is expensive and confusing,
and each agent should only see its own part. The finance case has **15 messages,
6 roles, 1 binary choice** — small enough that the whole protocol fits in context
with no penalty. Measured consequence:

- **Per-call prompt cost is essentially identical**: B 1,800 tokens/call, C 2,080,
  C+ 2,105. Projection gives *no* per-call saving here, because one agent's slice of
  a 15-message protocol is not much smaller than the whole. The saving only appears
  when the protocol is big.
- C's *total* cost looks high (166k vs B's 26k) only because C made **78 calls vs
  B's 14** — that is the round-robin polling + retries (Problem 1 again), not the
  contract size.

A strong model (gpt-5.4) also rarely breaks such a simple protocol, so the gate has
little to catch — enforcement looks like pure overhead.

## Problem 3 — the monitor is stricter than session-type theory requires (and that, not the skills, is what fails C on the standard branch)

Verified against the actual projected contracts. On the standard branch, after
`RevenueAnalyst` sends `StandardBranchAck`, **two independent actions are ready at
once, by different agents**:

- `RevenueAnalyst` must send `NotifyStandardRole` to `TaxSpecialist`, and
- `TaxVerifier` must send `Approval` to `RevenueAnalyst`.

`TaxVerifier`'s own local contract is literally: receive `StandardBranchAck` →
**send `Approval`**. `NotifyStandardRole` is a `RevenueAnalyst`→`TaxSpecialist`
message that **does not appear in `TaxVerifier`'s contract at all** — it cannot see
it and cannot wait for it. So `TaxVerifier` sending `Approval` immediately is
**perfect obedience to its local skill**. `RevenueAnalyst` likewise was following
its sequence; it just got beaten to the punch.

These two messages are **concurrent** — independent channels, no causal
dependency. The global protocol *wrote* them in one order
(`NotifyStandardRole` then `Approval`), but that written order is **not enforceable
by the local types**, and session-type theory does not require it to be. Our
runtime monitor, however, enforces the single written linearization, so when
`TaxVerifier`'s `Approval` arrives before `RevenueAnalyst`'s `NotifyStandardRole`,
the monitor calls it off-protocol — even though it is a legal interleaving. The
agents then desync and never produce the final report.

**Conclusion: C's standard-branch failures are NOT the agents disobeying their
skills, and NOT faulty skills.** Both roles obeyed their contracts. The cause is a
harmless race that (a) the no-coordinator round-robin runner exposes and (b) the
monitor judges too strictly. B's orchestrator serializes the race away; C+'s gate
blocks the early `Approval` and makes `TaxVerifier` wait. Both compensate for a
monitor that over-enforces, not for bad skills.

**FIXED 2026-06-17 (monitor correctness).** The monitor (`stjp_core/monitor/monitor.py`)
now implements proper asynchronous multiparty-session-type concurrency: each local
monitor commutes past any action on a *different channel* (different peer **or**
different direction), respecting first-in-first-out order only within the same
channel. A legal-but-early message that a role can reach by doing its other-channel
obligations first is accepted, and those obligations are tracked as still-owed.
Verified:
- The standard-branch race (`Approval` before `NotifyStandardRole`) is now **accepted**.
- Genuine off-protocol messages and wrong-branch choice-guard violations are **still
  flagged**.
- Re-grading the whole n=10 run (`20260617T081755`) with the corrected monitor
  (`experiments/scripts/regrade_conformance.py`):

  | arm | events | violations (old monitor) | violations (corrected monitor) |
  |---|---|---|---|
  | B global text | 100 | 17 | **0** |
  | C local types | 157 | 15 | **0** |
  | C-min | 150 | 15 | **0** |
  | C+ gate | 105 | 0 | 5* |

  **Every protocol-following arm — B, C, and C-min — is fully conformant (0
  violations) under the correct monitor.** All of their old "violations" were
  false positives from enforcing a total order on concurrent events. The agents
  followed the protocol/local types correctly all along.

  *The gate arm's 5 are a genuine *duplicate* `Approval` in its recorded trace
  (`…Approval, NotifyStandardRole, Approval`). That duplicate is itself an artifact
  of running the gate with the *old buggy* monitor: it wrongly blocked the benign
  early `Approval`, re-prompted `TaxVerifier`, who then sent it again. Re-running
  the gate with the corrected monitor would remove the false block and the
  duplicate. (Goal-completion is a separate axis and is unaffected by re-grading
  observe-mode arms.)

**What the fix does and does not change.** It corrects the *conformance* score:
C followed its local types (now correctly 0 violations). It does **not** by itself
change C's *goal-completion* in observe mode — the agents still got confused by the
out-of-order `Approval` and stopped before the final report. That remaining gap is a
*runtime coordination* problem (no coordinator in the round-robin runner), which the
gate, an orchestrator, or the new EFSM scheduler (`delm_runner.py`) all resolve.
A tighter protocol draft (`TaxSpecialist` acknowledges, then `TaxVerifier` approves)
would remove the race at the source.

## The one clean signal that DID survive

Within the **same** runner (round-robin), adding the gate took the result from
**50% → 100%**: C (observer) 50%, C+ (gate) 100%. The gate caught exactly the
out-of-order `Approval` and made `TaxVerifier` wait — turning the standard-branch
failure into a success. That is an unconfounded demonstration that **enforcement
adds value over observation**. What is *not* shown is that local types beat global
text — because of Problems 1 and 2.

## Honest bottom line

- Nothing is mis-measured; the monitors and numbers are correct.
- But the current arms **cannot** show "local types beat global text," because the
  global-text arm also gets a central orchestrator (confound) and the task is too
  small to exercise projection's advantages (scale, need-to-know).
- What is real and shown: (a) having the validated protocol at all beats intent-only
  by a mile (0% → 100%, disasters → none); (b) enforcement beats observation within
  the same runner (50% → 100%).

## What would actually show local types' usefulness (proposed next test)

To make the value of local types visible, the next benchmark case should add the
ingredients the current one lacks. In rough priority:

1. **Hold orchestration constant.** Add "global text on round-robin" and/or "local
   types under an orchestrator," so type-format is isolated from coordination.
2. **A larger, more complex protocol** — more roles (say 8–12), several choices,
   a loop/recursion, deeper nesting — so reading the whole protocol every turn
   becomes costly and error-prone (hurting global-text) while each local slice
   stays small.
3. **More mandatory orderings and value constraints** = more places to go wrong =
   more for the gate to catch that observation/global-text miss.
4. **Need-to-know / information-hiding**: a task where an agent should *not* see
   another's data; global text leaks the whole protocol to everyone, local types
   do not. (Both a correctness and a privacy argument.)
5. **A weaker / cheaper model.** B's compliance is the model *choosing* to follow
   text; on a weaker model that should degrade while the gate holds. (We already
   saw global-text drop to 40% on gpt-4o.)

This also dovetails with the criticality redesign
(`BENCHMARK_DESIGN_V3_CRITICALITY.md`): the new case should have a genuine critical
dependency so "happened to be right" (B) and "cannot be wrong" (gate) can finally
separate.
