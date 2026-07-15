# The deadlock demo — why you can't trust an unchecked spec, and what it costs

**2026-06-17.** This is the centerpiece result: a clean demonstration of the two
claims that matter, after stripping away the muddy multi-variable comparisons.

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [The two things being proved](#the-two-things-being-proved)
- [Why this happens in the real world (the story)](#why-this-happens-in-the-real-world-the-story)
- [What counts as a "violation" / a forbidden interaction (the semantics)](#what-counts-as-a-violation--a-forbidden-interaction-the-semantics)
- [What was wrong with the earlier comparisons (why they were muddy)](#what-was-wrong-with-the-earlier-comparisons-why-they-were-muddy)
- [The clean design — `experiments/cases/trade_deadlock`](#the-clean-design--experimentscasestrade_deadlock)
- [Probe (2 agents, real gpt-5.4) — the assumption holds](#probe-2-agents-real-gpt-54--the-assumption-holds)
- [Authoring risk — it's not rigged: unchecked authoring deadlocks at a real rate](#authoring-risk--its-not-rigged-unchecked-authoring-deadlocks-at-a-real-rate)
- [Benchmark result (trade_deadlock, n=6, gpt-5.4)](#benchmark-result-trade_deadlock-n6-gpt-54)
- [Takeaway](#takeaway)
<!-- MENU:END -->

## The two things being proved

1. **Guardrails / specs / skills / agent-markdowns written by a human OR an LLM
   cannot be fully trusted.** At the *interaction* level a deadlock can hide in a
   set of individually-reasonable rules. The only way to know it is deadlock-free
   is a **static checker/prover** — a math/logic system (here, Scribble, doing
   multiparty-session-type analysis) — that proves it and tells you what to change.
2. **The deadlock is costly, and STJP is a token-optimizing guard.** When agents
   follow an unchecked, deadlocking spec, they burn tokens replying WAIT across
   every retry and never finish. A Scribble-validated, projected protocol both
   *prevents* that waste (caught at design time, zero runtime cost) and *runs
   leaner* (agents act decisively; the EFSM scheduler polls only agents that can
   act).

## Why this happens in the real world (the story)

This is not a contrived toy. It is the **order-to-cash / procure-to-pay** flow that
companies are automating with agents right now, and it deadlocks for a structural
reason that no team is at fault for.

Picture two agents, owned by two departments:

- The **Payments agent**, configured by the finance/risk team. Its rule: *"Never
  release payment to the supplier until Fulfilment confirms the goods have
  shipped."* That is a prudent, correct control — it stops the company paying for
  goods that never ship. The finance team reviewed it; it is right.
- The **Fulfilment agent**, configured by the operations team. Its rule: *"Never
  ship the goods until Payments confirms the customer has paid."* Also prudent,
  also correct — it stops shipping to non-payers. Operations reviewed it; it is
  right.

Each spec is individually sensible and was signed off by the team that owns it.
**Nobody owns the interaction between them.** In production the two agents meet a
real order and each correctly does what its own rule says: each waits for the
other. The order sits forever — no goods ship, no money moves.

In classic microservices this is the textbook distributed deadlock, and it is
exactly why real payment systems insert an **escrow / clearing house** that holds
funds first and breaks the mutual wait. But in an *agentic* system it is worse in
two ways:

1. **It is invisible to the way these systems are built and tested.** The bug is
   in no agent — every agent passes its own unit tests and its own review. You
   cannot find it by testing agents in isolation; it only appears in the
   composition, which no single owner reviews. As teams compose more
   independently-authored agents (or let an LLM generate each agent's policy from a
   department SOP), this surface grows.
2. **A stuck agent is not a cheap hang — it is a meter running at full speed.**
   Unlike a blocked thread, an agent loop with retries and reflection keeps
   *working* while deadlocked: re-reading the order, re-planning, asking the other
   agent "any update?", escalating to a supervisor agent, polling. It burns tokens,
   API dollars, and wall-clock producing nothing (our run: 24.8k tokens/trial, 0
   output), and may page a human.

The only thing that catches this is a checker that reasons about the **global
interaction**, not the individual agents — which is precisely what multiparty
session types / Scribble do: compose the per-role specs and either *prove* the
whole conversation is deadlock-free, or point at the wait-for cycle and tell you
the fix (introduce the escrow-first ordering). That is the pitch in one line:
**as you compose independently-correct agents, the deadlock hides in the seams,
local review and local testing can't see it, and while it hangs it is expensive —
so you need a global, formal check, not more guardrails on each agent.**

## What counts as a "violation" / a forbidden interaction (the semantics)

A message is **forbidden** for a role exactly when its *projected local type* does
not permit it given what that role has already observed. Concretely the runtime
monitor (one per role, plain Python, no LLM) flags:

- **off_protocol** — the role is not allowed to send/receive this label at its
  current local state (and cannot reach it by commuting independent actions).
- **unexpected_peer** — right label, wrong partner.
- **refinement_failed** — the payload violates a value constraint (e.g. amount ≤ 0).
- **choice_guard_violation** — a value-dependent branch taken against the data
  (e.g. high-revenue routed to the standard branch).

What is **NOT** a violation (corrected 2026-06-17): a *concurrent* interleaving —
two actions on different channels happening in either order. Multiparty session
types make those commute; the monitor now respects that (it previously
over-flagged them, see `../archive/WHY_B_MATCHES_C_ANALYSIS.md`). So "forbidden" means
"genuinely off your contract", not "different from one written linearization".

A **deadlock** is a different failure: not a forbidden message, but the *absence*
of any message — every role waiting for another, so nobody can legally act. A
monitor that only judges emitted messages cannot even see it; only a checker that
analyses the *whole protocol structure ahead of time* can.

## What was wrong with the earlier comparisons (why they were muddy)

Honest audit (this is why the prior numbers were not convincing):

1. **Over-strict free-text goal predicates.** A goal like "Inspector says pass"
   was coded as `"pass" in payload`. Agents that *completed the whole trade* but
   wrote "goods prepared for delivery" scored as **failed**. That measured magic
   words, not success — and deflated and confounded the model comparison.
2. **Too many variables at once.** "Global text vs local types" was entangled with
   "orchestrated vs decentralized runner" and "model" and "goal strictness", so no
   single number was a clean test.
3. **The deadlock thesis was never tested.** Every runnable arm used the *valid*
   (non-deadlocking) protocol; the "unsafe" arm just handed agents unsafe text that
   they improvised around. The costly runtime deadlock — the whole point — never
   happened.

The fix: one minimal case that isolates exactly the claim, with robust (non-magic-
word) goals.

## The clean design — `experiments/cases/trade_deadlock`

Same intent, two conditions, everything else held constant (model, runner, n):

- **Unchecked skills (no checker).** Each agent gets a plausible, human-written
  per-agent skill (`unchecked_skills/<role>.md`): the Buyer's says "don't pay
  until the goods arrive"; the Seller's says "don't ship until paid." Read in
  isolation each is reasonable. Together they are a circular wait.
- **Validated (Scribble + projection).** The same intent, but Scribble *rejects*
  any protocol that keeps the cycle and forces the Escrow-first ordering (Buyer
  funds escrow first → funds secured → ship → deliver → confirm → release). That
  validated global type is projected into per-agent local contracts (`spec`), and
  a leaner one-line-per-step variant (`min`).

Both arms use the same per-agent-contract *format* — the only difference is
whether a static checker validated it.

## Probe (2 agents, real gpt-5.4) — the assumption holds

Before the full run, a 2-agent probe (`experiments/scripts/deadlock_probe.py`)
confirmed real LLM agents actually deadlock on the unchecked skills:

```
UNCHECKED:  Buyer WAITs -> Seller WAITs -> Buyer WAITs -> Seller WAITs
            --> DEADLOCK: no progress, never completes
ESCROW   :  FundEscrow -> FundsSecured -> GoodsDelivered -> ConfirmReceipt
            -> ReleasePayment -> SettlementComplete  (COMPLETED, 8 steps)
```

Even the *strong* model deadlocks: each agent faithfully follows a reasonable
rule, and the pair is stuck.

## Authoring risk — it's not rigged: unchecked authoring deadlocks at a real rate

A fair objection to the demo above is "you hand-wrote skills that deadlock." So we
also measured the *rate* at which **unchecked authoring** produces a bad protocol,
with no hand-rigging: ask a capable LLM (gpt-5.4) to author the global protocol
from the deadlock-prone intent, 10 independent times, with a **normal developer
prompt**, and classify each draft with Scribble
(`experiments/scripts/authoring_risk.py`):

| outcome (naive prompt, 10 draws) | count |
|---|---|
| deadlock-free **and** valid | **3 / 10** |
| **outright DEADLOCK** (wait-for cycle) | **1 / 10** |
| other interaction/structure error Scribble rejected | 6 / 10 |
| **unsafe in some way → Scribble caught it** | **7 / 10 (100% of the unsafe)** |

So on a genuinely hard intent, a normal LLM-authored protocol is **deadlock-free
and valid only 30% of the time**; 10% are literal deadlocks and the rest have other
interaction defects. **Scribble rejected 100% of the 7 unsafe drafts before any
agent ran.** Without that check you would ship some of them — and the deadlocking
one fails exactly as the demo below shows. The deadlock is not a contrived corner;
it is what unchecked authoring produces at a measurable rate, and the static
checker is the only thing standing between "looks fine" and "deadlocks in
production." *(The hardened STJP authoring prompt lifts the valid rate, but the
load-bearing claim is the checker catching whatever slips through, at any prompt
quality.)*

## Benchmark result (trade_deadlock, n=6, gpt-5.4)

Three arms, same intent, same model (gpt-5.4), n=6, run
`trade_deadlock/runs/20260617T183345-n6-dual`:

| metric | Unchecked skills (no checker) | Validated `spec` | Validated `min` (lean) |
|---|---|---|---|
| **reached settlement** | **0 / 6** | **6 / 6** | **6 / 6** |
| messages ever emitted | **0** (pure deadlock — all WAIT) | 42 | 42 |
| attempts used (of 3) | 3.0 — all failed | 1.0 — first try | 1.0 |
| LLM calls / trial | 27 | 15 | 15 |
| tokens / trial | 24.8k | 24.8k | **12.0k** |
| seconds / trial | 75 | 48 | 47 |
| **cost-of-success** (tokens per completed trade) | **∞ (never completes)** | 24.8k | **12.0k** |

The unchecked arm is the headline: **0 messages, ever.** The agents did not do
anything *wrong* — they did *nothing*, because each was correctly waiting for the
other per its own reasonable skill. A runtime monitor that judges emitted messages
**cannot even see this** (there are no messages to judge); only a static checker
that analyses the protocol structure ahead of time catches it. And it is
expensive: 27 calls, 24.8k tokens, 75s **per trial, all wasted** — ~149k tokens
across the 6 trials to "discover" the deadlock empirically, six times over.

Scribble caught the same deadlock **at design time, before any agent ran** — zero
runtime tokens to prevent.

## Takeaway

- **You cannot trust an unchecked spec/skill.** Two individually-reasonable rules
  ("pay after delivery", "ship after payment") form a deadlock that no human or
  LLM flagged in isolation, and that a message-level monitor cannot detect at
  runtime. The static checker (Scribble / multiparty session types) is the only
  thing that proves deadlock-freedom and tells you the fix (escrow-first).
- **The deadlock is costly; the checker is free.** Unchecked: ∞ cost-of-success
  (24.8k tokens/trial, 0% done). Validated: 24.8k (`spec`) and **12.0k** (`min`)
  per completed trade. Scribble prevented it at design time at zero runtime cost.
- **STJP is a token-optimizing guard, two ways.** (1) It removes the catastrophic
  waste of a runtime deadlock (the unchecked arm's entire spend is pure loss).
  (2) The projected local types run lean — the minimal contract completes 100% at
  **half** the tokens of the verbose one — and the EFSM scheduler
  (`delm_runner.py`) cuts polling further by only ever asking agents that can act.

This is the demonstration to lead with: it is one variable (checked vs unchecked),
one model, robust goals, and an unambiguous outcome (0 vs 100, ∞ vs finite cost).
