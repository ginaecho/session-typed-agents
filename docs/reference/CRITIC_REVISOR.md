# Critic & Revisor — the cross-message policy layer

STJP's runtime story is a quartet (see the STJP article, §3):

| component | judges | when | code |
|---|---|---|---|
| **Checker** (Scribble) | the protocol's *shape* — deadlock-freedom, projectability | compile time | `compiler/validator.py` |
| **Monitor** | *one message at a time* against one role's EFSM + refinements | runtime | `monitor/monitor.py` |
| **Critic** | the *whole conversation* — properties spanning many messages | compile time **and** runtime | `critic/critic.py` |
| **Revisor** | nothing — it *repairs* the rules when the Critic flags them | authoring time | `critic/revisor.py` |

Implemented 2026-07-04. The Critic and Revisor are deterministic-first: the
judging path contains **no LLM**. The LLM appears only where STJP always puts
it — drafting (policies from intent; protocol repairs) — with Scribble and
the Critic re-judging every draft.

---

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [1. Why a Critic at all](#1-why-a-critic-at-all)
- [2. The `.policy` sidecar](#2-the-policy-sidecar)
- [3. Static mode — before any agent runs](#3-static-mode--before-any-agent-runs)
- [4. Runtime mode — over the trace](#4-runtime-mode--over-the-trace)
- [5. The Revisor — closing the loop](#5-the-revisor--closing-the-loop)
- [6. Connected into the authoring loop](#6-connected-into-the-authoring-loop)
- [7. Tests](#7-tests)
- [8. Research basis](#8-research-basis)
<!-- MENU:END -->

## 1. Why a Critic at all

The Monitor is deliberately local: it holds one role's projected EFSM and
answers "is *this* message legal *now*?". Some safety properties are
invisible at that granularity, because **every individual message is legal**
and the breach only exists across several of them:

- **Information flow** — confidential data received from A is forwarded,
  hop by hop, until it reaches an unauthorized role. Each hop is a
  protocol-legal message; the *chain* is the leak.
- **Ordering obligations** — "publication must be preceded by approval."
  If one choice branch skips the approval, every message in that branch is
  still individually well-typed.
- **Separation of duty** — the same role both requests and approves an
  audit. Both messages type-check.
- **Aggregates** — a retry loop runs 7 times when policy says 2.

These are exactly the failures the STJP article assigns to the Critic: *"a
policy problem no single message would reveal."*

## 2. The `.policy` sidecar

Policies live next to the protocol version, like `.refn`:

```
experiments/cases/finance/protocols/v1.scr      the global type
experiments/cases/finance/protocols/v1.refn     payload refinements (Monitor)
experiments/cases/finance/protocols/v1.policy   cross-message policies (Critic)
```

Four kinds; edge patterns are `Sender -> Receiver : Label` with `*`
wildcards (full grammar in `stjp_core/critic/policies.py`):

```ini
[flow]
id: F1
description: raw audited figures must never flow to the ExpenseAnalyst
source: TaxSpecialist -> * : AuditedRevenue     # where the taint enters
forbidden_role: ExpenseAnalyst                  # or: forbidden: <edge>
# declassify: <edge>                            # optional laundering step

[sequence]
id: S1
description: approval precedes the analysis reaching the Writer
before: TaxVerifier -> RevenueAnalyst : RevenueAuditApproval
after: RevenueAnalyst -> Writer : RevenueAnalysis

[separation]
id: D1
description: no self-approval
first: * -> * : RevenueAuditRequest
second: * -> * : RevenueAuditApproval

[aggregate]
id: A1
description: one audit round-trip per run
count: RevenueAnalyst -> TaxVerifier : RevenueAuditRequest
max: 1
```

An LLM can draft the sidecar from the user intent
(`critic.draft_policies_from_intent`, mirroring `evaluation/goal_elicitor.py`)
— **a human approves it**, same as the G1–G6 goals.

## 3. Static mode — before any agent runs

`run_static_critic()` parses the global type into an AST
(`critic/protocol_paths.py`), enumerates every execution path (choices
multiply paths; `rec` loops are unrolled once and flagged), and checks each
policy on each path:

- *flow* runs a conservative taint propagation (may-flow): once a role has
  observed tainted data, everything it later sends propagates the taint,
  unless the edge matches `declassify`. A violation carries the full witness
  chain — the hop-by-hop route the data can take.
- *sequence* / *separation* / *aggregate* are checked per path exactly.

A static finding means **the protocol itself permits the breach** — even
perfectly conformant agents could commit it. This is the same
shift-left move as the deadlock check: catch it before the expensive run.

```bash
python -m stjp_core.critic.critic experiments/cases/finance/protocols/v1.scr
# CRITIC PASS — 2 path(s), no cross-message policy issues
```

## 4. Runtime mode — over the trace

`run_runtime_critic(events, policies)` applies the same checks to the actual
trace (the events `.jsonl` the benchmark already writes, or
`monitor.TraceEvent` objects), exact rather than conservative:

```bash
python -m stjp_core.critic.critic v1.scr --trace runs/LATEST/events_min_llmvalid_sched.jsonl
```

Static approximations become exact here: an `[aggregate]` over a loop that
static analysis could only flag as "potentially unbounded" is counted
precisely at runtime.

## 5. The Revisor — closing the loop

`critic/revisor.py` implements the repair loop:

```
CriticReport ──► LLM drafts a revised global protocol
                     │
                     ▼
              Scribble validate  (shape still safe?)
                     │
                     ▼
              static Critic      (policies now hold on EVERY path?)
                     │
         both pass ──► accepted        either fails ──► feedback, retry
```

`revise_protocol()` runs one repair; `critic_revise_loop()` iterates
critic → revise → re-judge until clean (or budget exhausted). The Revisor
prompt teaches the four repair strategies (insert the missing `before` step,
re-route/declassify a flow, reassign a duty, prune repetitions) and the
Scribble well-formedness rules, but its output is **never trusted** — only
validated.

## 6. Connected into the authoring loop

`authoring/evolution_loop.py` gained step **[2.5] CRITIC**: when a `.policy`
sidecar exists for the case, every Scribble-valid draft is critiqued before
skills generation. Findings are fed back to the Architect LLM *exactly like a
Scribble error*, so the standard fix loop now enforces both layers:

```
LLM draft ─► Scribble (shape) ─► Critic (policy) ─► skills ─► skills compiler
                 ▲                    │
                 └────── findings ────┘
```

No sidecar → no change in behaviour (the gate is opt-in per case).

## 7. Tests

`stjp_core/tests/test_critic_revisor.py` — offline, mock/injected LLM, real
Scribble: policy parsing; branch-skipping sequence violation; taint chain
with/without declassify; runtime verdicts; the mock Revisor loop; an
injected-LLM revision; and a clean protocol passing all four kinds.

## 8. Research basis

- Bocchi, Chen, Demangeon, Honda, Yoshida — *Monitoring Networks through
  Multiparty Session Types* (FORTE'13 / TCS'17): local monitors from
  projections; the Critic is the complementary **global** observer.
- Castellani, Dezani-Ciancaglini, Pérez — *Self-adaptation and secure
  information flow in multiparty communications* (secure sessions line):
  information-flow safety on sessions, the [flow] policy's ancestry.
- Bocchi, Honda, Tuosto, Yoshida — *A Theory of Design-by-Contract for
  Distributed Multiparty Interactions* (CONCUR'10): assertions beyond one
  payload; [sequence]/[aggregate] are trace-level contracts.
- The Revisor loop is the `architect.py` fix-loop pattern applied to policy
  errors instead of compiler errors.
