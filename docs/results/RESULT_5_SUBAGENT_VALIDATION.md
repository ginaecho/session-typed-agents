# Result 5 — Subagent validation of the 2026-07 components (no Foundry)

**At a glance (2026-07-04).** The three new STJP components — Critic/Revisor
(the Critic checks rules that span several messages, e.g. "who may see what";
the Revisor is the loop that automatically repairs a plan the Critic
rejects), skill compaction, incremental sub-protocol extension — were validated two
ways: a deterministic integration stress suite over generated complex
protocols (**211/211 checks, 10 seeded iterations**), and three
agent-in-the-loop experiments (n=10 each) where **independent Claude
subagents** played the roles against the deterministic STJP machinery, with
no Azure AI Foundry anywhere in the loop. The classic ladder reproduced
end-to-end:

| condition | success | deadlock | agent calls/trial | monitor violations | critic findings |
|---|---|---|---|---|---|
| unchecked prose skills | **0/10** | 10/10 | 8.8 (wasted) | 42 | 0* |
| STJP contract + gate + scheduler | **10/10** | 0 | **7.0 (protocol minimum)** | **0** | **0** (4 policies, 70 msgs) |
| STJP on the incrementally EXTENDED protocol (+SettlementAudit child, new Auditor role) | **10/10** | 0 | 9.0 (minimum) | **0** | **0** (5 policies) |

\* the unchecked arm barely produced messages to judge — it starved: 39/40
first-round decisions were WAIT (the Buyer/Seller circular wait), one agent
improvised an off-vocabulary message, nothing ever completed.

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [The story](#the-story)
- [Where everything lives](#where-everything-lives)
- [Honest caveats](#honest-caveats)
<!-- MENU:END -->

## The story

1. **Bottom-up detection (compaction gauntlet, 10 runs).** A subagent
   compacted the four *prose* trade skills into local types; the
   deterministic pipeline flagged the system UNSAFE **10/10** times, with a
   pinpoint diagnosis (unreceivable `SettlementComplete`, a starving Escrow
   role — the agent that should hold funds in trust until both sides
   deliver, but never received its message — and the circular wait). A
   second subagent, given that diagnosis, produced a
   revision that the deterministic synthesizer + Scribble accepted **10/10
   times on the first attempt** — every one converging on the escrow-first
   design. What runtime discovers in 88 wasted agent calls (the unchecked
   arm), the static pipeline refutes in milliseconds.
2. **Runtime governance (interaction trials).** With the lean contract
   rendered from the Scribble-validated projection, the enforcement gate,
   and enabled-only scheduling, haiku-class agents completed the trade
   **10/10** at exactly the protocol-minimum number of agent calls, with
   zero violations under four cross-message policies (ordering,
   aggregate, information-flow with declassification). A scripted
   off-contract send was rejected by the gate *before delivery* and the
   trial still completed.
3. **Evolution (extended protocol).** The `SettlementAudit` child was added
   by the real incremental pipeline (child verified once + cached;
   projection diff touched only Escrow + the new Auditor). Live subagents
   drove the new decision points **10/10** correctly, and the pipeline's
   *standalone dependency-free monitors* independently confirmed every
   trace conformant (10/10 Escrow, 10/10 Auditor).
4. **The stress suite earned its keep**: over 10 generated 4-7-role
   protocols with nested choices it ran round-trip synthesis, 5 mutation
   classes, critic oracles, the revisor loop, and chained extensions —
   211/211 — and caught one real bug before any user could (the extension
   header-matcher spliced `do` calls into aux blocks on composed parents;
   fixed in `compiler/incremental.py`).

## Where everything lives

- Full report + method + limitations:
  `experiments/subagent_trials/reports/SUBAGENT_TRIALS_REPORT.md`
- Raw per-trial metrics: `experiments/subagent_trials/reports/*.json`
- Stress suite + report: `experiments/scripts/integration_stress.py`,
  `experiments/reports/stress/integration_stress.{json,md}`
- The engine (reusable, Foundry-free): `experiments/subagent_trials/engine.py`

## Honest caveats

Role agents were haiku-class on short linear contracts; n=10 samples
decision stochasticity on one scenario per case (scenario diversity is the
stress suite's job); in the extended case, decision points already sampled
live 20/20 in the base case were replayed rather than re-sampled (the
incremental philosophy applied to the experiment itself — disclosed in the
full report).
