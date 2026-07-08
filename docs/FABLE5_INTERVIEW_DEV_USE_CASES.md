# An Interview with Fable 5: STJP as a Development Blueprint for Token-Efficient Multi-Agent Systems

> **Format.** Fable 5 (Anthropic's Claude, Mythos-class tier) was asked to read this
> repository — [`/docs`](README.md), [`/pitch`](../pitch/), and the experiment
> reports under [`experiments/reports/`](../experiments/reports/) — and answer
> three questions from the project owner. This document is the interview,
> lightly edited, with every claim hyperlinked to the evidence in this repo.
>
> **Interview date:** 2026-07-08.
>
> The three questions:
> 1. Which **development use cases** (e.g., coordinating subagents) can use the
>    STJP blueprint — a global protocol supported by multiparty session type
>    (MPST) theorems — to **reduce token cost**?
> 2. When *you* (Fable 5) organize a group of subagents, how would the STJP
>    blueprint help you?
> 3. Would you want to use this tool?

---

## Q1 — Which development use cases can adopt the STJP blueprint to cut token cost?

**Fable 5:** Your own repo already demonstrates the pattern on 17 cases under
[`experiments/cases/`](../experiments/cases/), and they generalize cleanly. The
ones where the token-saving mechanism applies are any development scenario where
**multiple agents must exchange messages in a required order**, because STJP
attacks the three places tokens actually go: per-turn coordination deliberation,
polling of idle agents, and runtime discovery of statically-refutable design bugs.

### Where the tokens are saved (measured in this repo's reports)

| Lever | Mechanism | Evidence |
|---|---|---|
| **Projection** — each agent gets only its local slice, not the global prose | Smaller prompt every call, plus far less "is it my turn?" deliberation (1,534 → 552 thinking tokens/turn) | [`RESULT_2_TOKEN_EFFICIENCY.md`](results/RESULT_2_TOKEN_EFFICIENCY.md): 24.1k → 8.8k tokens, **−63%**, same 100% completion |
| **EFSM scheduler** — poll only agents that *can* act | Idle agents never burn a call saying "WAIT" | [`RESULT_4_FULL_STACK.md`](results/RESULT_4_FULL_STACK.md): −66% calls; 13.3k vs 120.3k tokens for the same protocol pasted as text — **9× cheaper**, 4× faster |
| **Static check before running** — Scribble + the Bocchi–Chen–Demangeon–Honda–Yoshida composition theorem (FORTE'13) | Deadlocks and orphan messages refuted in milliseconds instead of discovered after burning calls | [`trade_deadlock`](../experiments/cases/trade_deadlock/): unchecked skills **0/100** success, all deadlock (infinite cost-to-goal); the compaction gauntlet flags UNSAFE 10/10 with a pinpoint diagnosis ([`RESULT_5_SUBAGENT_VALIDATION.md`](results/RESULT_5_SUBAGENT_VALIDATION.md)) |
| **Deterministic gate + monitor** — O(1) state-machine step, no LLM in the hot path | Conformance checking and evaluation cost ~zero tokens — no LLM-as-judge | [`RESULTS.md`](results/RESULTS.md): per-event cost is a microsecond FSM step plus a sandboxed predicate; the composition theorem gives the *global* guarantee from local checks alone |
| **Scale effect** — global-text cost grows with roles; the projected local contract stays flat | The more roles, the bigger the projection win | E6 roles sweep ([`REPORT_N100.md`](../experiments/reports/n100/REPORT_N100.md)): coordination-cost ratio grows **9.2× → 17.1×**; scale case [`report_pipeline_large`](../experiments/cases/report_pipeline_large/) (10 roles) |

### The developer use cases we already have — hyperlinked

For *development* the question is: **how do developers use agents and
subagents, and where does the blueprint cut their token bill?** Five patterns
cover it, and each one already exists as a runnable case in this repo:

**1. Coordinating subagents** — [`trade_deadlock`](../experiments/cases/trade_deadlock/) + [`experiments/subagent_trials/`](../experiments/subagent_trials/).
The developer writes plausible per-agent skills; a hidden circular wait makes
the fleet starve. The static check refutes it in milliseconds instead of after
~88 wasted agent calls; under the contract+gate+scheduler, real Claude
subagents complete at the protocol-minimum call count — unchecked 0/100,
STJP 100/100 ([`RESULT_1`](results/RESULT_1_DEADLOCK.md),
[`RESULT_5`](results/RESULT_5_SUBAGENT_VALIDATION.md),
[`RESULT_7`](results/RESULT_7_N100_SCALE.md)).

**2. Agent pipelines with review/approval gates** — [`code_review`](../experiments/cases/code_review/),
[`report_pipeline`](../experiments/cases/report_pipeline/),
[`finance`](../experiments/cases/finance/).
The everyday dev shape: produce → review → approve → merge/publish, with a
branch on a value (CI coverage, revenue threshold). The ordering lives in the
projected contract, so agents stop re-deriving it every turn: **8.8k vs 24.1k
tokens** for the same report ([`RESULT_2`](results/RESULT_2_TOKEN_EFFICIENCY.md)),
**13.3k/delivered, 9× cheaper** on the full stack
([`RESULT_4`](results/RESULT_4_FULL_STACK.md)). Scale test:
[`report_pipeline_large`](../experiments/cases/report_pipeline_large/).

**3. Loops with budgets** — [`rag`](../experiments/cases/rag/),
[`retry_loop`](../experiments/cases/retry_loop/),
[`iterative_polling`](../experiments/cases/iterative_polling/),
[`nested_retry`](../experiments/cases/nested_retry/).
Retrieve-verify-retry, poll-until-done, revise-until-accepted — the loop
budget lives in the type, the loop can't run away, and only the enabled agent
is called each iteration.

**4. Skill/prompt authoring itself** — [`skills_safety`](../experiments/cases/skills_safety/).
Compact a developer's prose skills into local types and check them *before*
deployment: UNSAFE flagged 10/10 with an actionable diagnosis, repaired
first-try 10/10 (E1 in [`RESULT_5`](results/RESULT_5_SUBAGENT_VALIDATION.md)).
One static refutation at authoring time is the cheapest token saving there is.

**5. Growing the system without re-verifying everything** —
[`composition`](../experiments/cases/composition/) + the incremental-extension
pipeline (E3 in [`RESULT_5`](results/RESULT_5_SUBAGENT_VALIDATION.md)).
Add a sub-protocol or a new role; only the touched roles get re-verified and
re-prompted — the multi-agent analogue of an incremental build.

> **Update (2026-07-08):** patterns 1 and 2 were subsequently reproduced on
> *real skills fetched from Anthropic's and GitHub Copilot's own public
> collections* (anthropics/skills, github/awesome-copilot), run twice — once
> with Haiku-class subagents and once with Sonnet-class subagents. Without a
> coordination plan each model failed a different team 0/10; under full STJP
> both models delivered 40/40 at the 4-call protocol minimum, 3× cheaper.
> Plain-language write-up:
> [`results/RESULT_9_REAL_SKILLS_TWO_MODELS.md`](results/RESULT_9_REAL_SKILLS_TWO_MODELS.md).

The remaining cases ([`banking`](../experiments/cases/banking/),
[`clinical_enrollment`](../experiments/cases/clinical_enrollment/),
[`travel_saga`](../experiments/cases/travel_saga/),
[`trade_settlement`](../experiments/cases/trade_settlement/),
[`auction`](../experiments/cases/auction/),
[`intel_report`](../experiments/cases/intel_report/), …) are domain demos that
stress the same five shapes — branching approvals, sagas/rollback, fan-in —
in business settings.

The general rule that falls out of the evidence: STJP pays off when the
interaction has **≥3 roles, ordering constraints, branching or loops, and an
irreversible step somewhere**. For a 2-step linear handoff, writing the protocol
costs more than it saves; from the E6 sweep, the benefit grows superlinearly
with role count.

---

## Q2 — When you organize a group of subagents, how would the STJP blueprint help you?

**Fable 5:** This is a genuinely apt question, because my own orchestration
tooling is an *informal, partial* version of what STJP formalizes:

- My **workflow scripts** (deterministic pipeline/parallel fan-outs over
  subagents) are roughly your **scheduler**: I only invoke an agent when its
  inputs are ready, so I already avoid the "poll everyone, most say WAIT" waste.
- My **structured-output schemas** on subagent calls are a weak **gate**: a
  subagent's reply is validated against a JSON Schema and retried on mismatch —
  but only per-message *shape*, not cross-message *ordering or state*.
- What I **don't** have is the static layer. Nothing type-checks my
  orchestration plan before I spawn agents. I can write a fan-out where a
  verifier waits on a finding that no finder is prompted to produce, or a
  loop-until-dry that can starve — the exact "unreceivable message / circular
  wait" bugs the Scribble check refutes in milliseconds. Today I'd discover
  that by burning the tokens, which is precisely the unchecked arm of the
  ladder in [`RESULT_5_SUBAGENT_VALIDATION.md`](results/RESULT_5_SUBAGENT_VALIDATION.md).

Concretely, the STJP blueprint would help me in four ways:

1. **Verify the choreography before spending.** Compile my planned fan-out
   (roles = finders, verifiers, synthesizer; messages = findings, verdicts,
   report) to a global protocol and let the checker prove every message has a
   receiver and no stage starves — *before* the first subagent spawns. One
   millisecond check versus a failed 30-agent run.
2. **Projection = minimal per-subagent prompts.** I currently hand each
   subagent a prose task description that includes context about the whole
   plan. Projecting a validated global protocol would give each subagent only
   its slice — "receive `Findings` from Finder, send `Verdict` to Synthesizer" —
   which is the [`RESULT_2`](results/RESULT_2_TOKEN_EFFICIENCY.md) mechanism
   verbatim: smaller input per call, and the subagent stops spending output
   tokens reasoning about the overall coordination.
3. **Typed message labels instead of LLM judging.** When results are anchored
   to protocol messages (the goal-anchoring insight in
   [`RESULTS.md`](results/RESULTS.md)), I can check "did the verifier actually
   verify finding X" with an O(1) trace scan rather than another LLM call. The
   monitor's violation record `(role, step, state, expected)` is also exactly
   the audit trail I'd want when a multi-agent run goes wrong.
4. **Safe incremental evolution.** When I add a stage mid-task (say, a new
   "security lens" verifier), the incremental-extension result (E3 in
   [`RESULT_5`](results/RESULT_5_SUBAGENT_VALIDATION.md): only Escrow + the new
   Auditor re-verified, everyone else untouched) is the right model — re-verify
   and re-prompt only the roles whose slice changed, instead of rewriting the
   whole orchestration.

One honest caveat in the other direction: most of my subagent work today is
**hub-and-spoke and stateless** — an orchestrator sends one task, an agent
returns one result, with no peer-to-peer messages and no long-lived agent
state. For that degenerate shape, my deterministic script already *is* the
protocol, and STJP's machinery is overkill. STJP's advantage kicks in exactly
where this repo's cases live: true **multiparty** interactions with branching,
loops, and agent-to-agent messages (group chat, A2A, long-running pipelines) —
which is also where multi-agent frameworks are heading.

---

## Q3 — Would you want to use this tool?

**Fable 5:** **Yes, selectively — and this repo itself proves it works with
agents like me.** The [`experiments/subagent_trials/`](../experiments/subagent_trials/)
result is the most persuasive datapoint for my situation: haiku-class Claude
subagents, governed by nothing but a projected lean contract + gate + EFSM
scheduler, hit **10/10 (and 100/100 at n=100) success at the protocol-minimum
call count** (7.0 calls for 7 messages) with zero violations — while the same
agents with plausible prose skills deadlocked every single time
([`RESULT_5`](results/RESULT_5_SUBAGENT_VALIDATION.md),
[`RESULT_7`](results/RESULT_7_N100_SCALE.md)). That is my exact operating mode
— spawned, independent, prompt-only subagents — and it shows the blueprint
substitutes *deterministic structure for model deliberation*, which is the
cheapest token there is: the one never generated.

**Where I'd adopt it:** any orchestration with ≥3 interdependent roles,
ordering constraints tied to irreversible actions (merge, publish, file, pay),
or loops with budgets — I'd want the static check before spawning and the
projection for prompts.

**Where I'd skip it:** simple parallel fan-out / map-reduce, where writing the
`.scr` protocol costs more than it saves.

**The decision rule the evidence suggests:** the more roles and the more
ordering, the more STJP pays — from **9.2× up to 17.1×** on coordination cost
alone (E6, [`REPORT_N100.md`](../experiments/reports/n100/REPORT_N100.md)).

---

## Appendix — the sources this interview drew on

- [`docs/README.md`](README.md) — documentation index
- [`docs/results/RESULTS.md`](results/RESULTS.md) — monitor mechanics + the composition theorem
- [`docs/results/RESULT_1_DEADLOCK.md`](results/RESULT_1_DEADLOCK.md) — the catastrophic-failure case
- [`docs/results/RESULT_2_TOKEN_EFFICIENCY.md`](results/RESULT_2_TOKEN_EFFICIENCY.md) — the −63% contract-size lever
- [`docs/results/RESULT_4_FULL_STACK.md`](results/RESULT_4_FULL_STACK.md) — the 9×-cheaper full-stack headline
- [`docs/results/RESULT_5_SUBAGENT_VALIDATION.md`](results/RESULT_5_SUBAGENT_VALIDATION.md) — Claude subagents under STJP governance
- [`docs/results/RESULT_7_N100_SCALE.md`](results/RESULT_7_N100_SCALE.md) — n=100 confirmation
- [`experiments/reports/TABLES_v2.md`](../experiments/reports/TABLES_v2.md) — reliability (pass^k) + translation fidelity
- [`experiments/reports/n100/REPORT_N100.md`](../experiments/reports/n100/REPORT_N100.md) — full n=100 report incl. E6 roles sweep
- [`experiments/subagent_trials/reports/SUBAGENT_TRIALS_REPORT.md`](../experiments/subagent_trials/reports/SUBAGENT_TRIALS_REPORT.md) — method: agent interaction without Foundry
- [`pitch/STJP_pitch.html`](../pitch/STJP_pitch.html) — governance positioning ("enforced with code, not another AI")
