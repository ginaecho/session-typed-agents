# Quarterly Finance Report — Benchmark Analysis (GPT-5.4)

## Experiment Configuration

| Parameter | Value |
|---|---|
| **Case** | `finance` (Quarterly Finance Report with high-revenue audit branching) |
| **Model** | GPT-5.4 (Azure AI Foundry) |
| **Trials** | 30 per arm |
| **Max attempts/trial** | 3 |
| **Roles** | Fetcher, RevenueAnalyst, ExpenseAnalyst, Writer, TaxVerifier, TaxSpecialist |
| **Goals** | 6 (G1–G6, see below) |
| **Protocol** | LLM-drafted, Scribble-validated, deadlock-free (6 roles, branching choice) |
| **Execution mode** | Parallel (shared rate-limited deployment) |
| **Date** | 2026-07-29 |
| **Run ID** | `20260729T080229-n30-dual` |
| **Arms run** | bare, maf_groupchat_llmvalid, min_llmvalid, min_llmvalid_gate, min_llmvalid_sched |
| **Branches** | `high` (revenue ≥ $50k, tax-specialist audit required) / `standard` |

## Protocol Complexity

This case is significantly more complex than `agenticpay_settlement` (4 roles, linear):

- **6 roles** with a value-dependent branching choice at RevenueAnalyst
- **Fan-out notifications** to TaxVerifier, TaxSpecialist, and Writer
- **Audit sub-protocol** (high branch only): TaxSpecialist produces audit,
  TaxVerifier approves, before the report can be written
- **Two independent analysis streams** (Revenue + Expense) that must converge

## Main Results

### Goal Achievement (Set B) — All-Goals-Pass Rate

A trial succeeds only if **all 6 goals** are achieved in at least one attempt.

| Arm | n | Strict % | 95% CI (Wilson) | Role-pair % | 95% CI |
|---|---:|---:|---|---:|---|
| bare | 30 | N/A | — | 0.0% | [0.0, 11.4] |
| maf_groupchat_llmvalid | 30 | 100.0% | [88.6, 100] | 100.0% | [88.6, 100] |
| min_llmvalid | 26 | 50.0% | [32.1, 67.9] | 50.0% | [32.1, 67.9] |
| min_llmvalid_gate | 30 | 100.0% | [88.6, 100] | 100.0% | [88.6, 100] |
| **min_llmvalid_sched** | **30** | **100.0%** | **[88.6, 100]** | **100.0%** | **[88.6, 100]** |

> **Strict**: exact (sender, receiver, label) + predicate match.  
> **Role-pair**: (sender, receiver) + predicate (label may differ).  
> N/A = arm has no protocol vocabulary (intent-only).

### Protocol Conformance (Set A) — Violations

| Arm | Total Events | Total Violations | Violation Rate |
|---|---:|---:|---:|
| bare | 992 | 795 | 80.1% |
| maf_groupchat_llmvalid | 310 | 0 | 0.0% |
| min_llmvalid | 403 | 0 | 0.0% |
| min_llmvalid_gate | 285 | 0 | 0.0% |
| min_llmvalid_sched | 285 | 0 | 0.0% |

### Cost Efficiency

| Arm | Avg Tokens/Trial | Avg Calls/Trial | Avg Sec/Trial | Token Savings vs Bare |
|---|---:|---:|---:|---:|
| bare | 58,007 | 45.2 | 180.3s | — |
| maf_groupchat_llmvalid | 25,083 | 13.7 | 53.7s | 56.8% |
| min_llmvalid | 87,613 | 79.0 | 270.7s | −51.0% |
| min_llmvalid_gate | 37,915 | 34.0 | 120.5s | 34.6% |
| **min_llmvalid_sched** | **12,729** | **9.5** | **36.1s** | **78.1%** |

### Per-Goal Breakdown — Strict

| Arm | G1 (Revenue) | G2 (Audit) | G3 (Approval) | G4 (Analysis) | G5 (Expense) | G6 (Report) |
|---|---:|---:|---:|---:|---:|---:|
| bare (rp) | 50% | 53% | 0% | 83% | 100% | 100% |
| maf_groupchat_llmvalid | 100% | 100% | 100% | 100% | 100% | 100% |
| min_llmvalid | 100% | 100% | 100% | 50% | 100% | 50% |
| min_llmvalid_gate | 100% | 100% | 100% | 100% | 100% | 100% |
| min_llmvalid_sched | 100% | 100% | 100% | 100% | 100% | 100% |

> bare uses role-pair metric (no protocol vocabulary for strict).  
> min_llmvalid fails on G4 (strict only; role-pair G4=100%) and G6 (both).
> G6 failures = session exhausts max_steps before Writer produces the final report.

### Per-Branch Cost Comparison

| Arm | High (tok) | High (calls) | Standard (tok) | Standard (calls) |
|---|---:|---:|---:|---:|
| min_llmvalid_sched | 15,660 | 11.0 | 9,798 | 8.0 |
| min_llmvalid_gate | 46,614 | 40.0 | 29,217 | 28.0 |

> SCHED calls/trial (11 high, 8 standard) closely matches the protocol's
> theoretical minimum message count — confirming the scheduler only polls
> roles that have enabled SEND transitions.

### Goal Definitions

| Goal | Description | Anchor | Predicate |
|---|---|---|---|
| G1 | High-path revenue > $50k | Fetcher→TaxSpecialist:HighRevenue | `float(x) > 50000` |
| G2 | Audit result non-empty | TaxSpecialist→RevenueAnalyst:AuditedRevenue | `len(x) > 0` |
| G3 | Tax verifier approves explicitly | TaxVerifier→RevenueAnalyst:RevenueAuditApproval | `"approved" in x.lower()` |
| G4 | Revenue analysis substantive | RevenueAnalyst→Writer:RevenueAnalysis | `len(x) > 10` |
| G5 | Expense analysis substantive | ExpenseAnalyst→Writer:ExpenseAnalysis | `len(x) > 10` |
| G6 | Final report produced (terminal) | Writer→Fetcher:GenerateReport | `True` |

## Key Findings

1. **Enforcement is necessary even on GPT-5.4 — knowledge alone regresses.**  
   `min_llmvalid` (projected local types, no enforcement) drops from 90% on
   mini to **50%** [32.1, 67.9] on the full model. Meanwhile, enforced arms
   (gate, sched) and MAF all achieve 100%. This is a **counter-intuitive
   model-scaling regression**: GPT-5.4's verbosity and longer responses
   exhaust the step budget before completing the protocol (G6=50%), while
   the smaller model's terser outputs complete within budget. Enforcement
   (gate/sched) or orchestration (MAF) is required to prevent this.

2. **SCHED achieves 100% correctness at 78% lower cost — 6.9× cheaper than min_llmvalid.**  
   SCHED: 12,729 tok/trial vs min_llmvalid: 87,613 tok/trial. Without
   scheduling, the model wastes 79 calls/trial (vs 9.5) polling roles
   out of turn — each producing valid but unneeded tokens. The scheduler
   eliminates this entirely by only polling roles with enabled transitions.

3. **Gate's overhead penalty persists at 100% success.**  
   `min_llmvalid_gate` uses 37,915 tokens/trial — 3× more than SCHED (12,729)
   and 1.5× more than MAF (25,083). The gate validates every message attempt
   against the EFSM, so with round-robin polling it probes all 6 roles
   each turn even when only one has an enabled transition. This overhead
   is purely computational (no correctness benefit on GPT-5.4).

4. **MAF GroupChat is rescued by model capability.**  
   The jump from 6.7% (mini) to 100% (full) is the largest positive
   model-scaling effect. MAF's LLM-based speaker selection succeeds when
   the underlying model is strong enough to maintain 6-role ordering from
   protocol text alone. However, it remains 2× costlier than SCHED.

5. **Bare agents achieve 0% despite a capable model.**  
   Without protocol knowledge, GPT-5.4 cannot solve G3 (explicit approval
   = 0%) — it produces natural conversational turns that happen to satisfy
   some goals (G5, G6 = 100%) but cannot reliably reproduce the structured
   multi-role handoff pattern. The 80.1% violation rate (down from 97.3%
   on mini) shows the model is better at *sounding* like coordination, but
   still fails the structured requirements.

6. **Zero violations, 50% goal achievement — protocol conformance ≠ task completion.**  
   `min_llmvalid` achieves 0 protocol violations (agents follow message ordering
   correctly) but only 50% goal completion. The protocol is followed but
   the session runs out of steps. This demonstrates that **type safety and
   progress are distinct guarantees** — you need scheduling for both.

## Model-Scaling Comparison: GPT-5.4-mini vs GPT-5.4

| Arm | Mini (Strict %) | Full (Strict %) | Δ | Mini Tok | Full Tok | Tok Δ |
|---|---:|---:|---|---:|---:|---|
| bare | N/A (42% rp) | N/A (0% rp) | — | 135,879 | 58,007 | −57% |
| maf_groupchat_llmvalid | 6.7% | 100.0% | +93.3pp | 31,519 | 25,083 | −20% |
| min_llmvalid | 90.0% | 50.0% | **−40.0pp** | 50,200 | 87,613 | +75% |
| min_llmvalid_gate | 52.0% | 100.0% | +48.0pp | 54,633 | 37,915 | −31% |
| **min_llmvalid_sched** | **100.0%** | **100.0%** | **0pp** | **12,652** | **12,729** | **+0.6%** |

> Key observations:
> - **SCHED is model-invariant**: 100% on both models at identical cost (~12.7k tok).
>   This is the only arm whose correctness guarantee does NOT depend on model capability.
> - **min_llmvalid REGRESSES on the stronger model** (90%→50%, +75% token cost).
>   GPT-5.4's verbosity causes step-budget exhaustion — the model follows protocol
>   ordering (0 violations) but produces longer outputs that consume more turns
>   before reaching the terminal goal. This is a capability-without-efficiency trap.
> - **Gate and MAF scale positively**: they require GPT-5.4 (full) to reach 100%.
>   On weaker models, they degrade significantly (gate: 52%, MAF: 7%).
> - **Bare cost drops 57%** on the full model (fewer retries, shorter exchanges)
>   but still achieves 0% goal completion — cheaper failure, not better coordination.

## Implications for Paper

1. **The enforcement gradient is non-monotonic with model capability.**  
   On GPT-5.4-mini: bare (0%) < maf (7%) < gate (52%) < min_llmvalid (90%) < sched (100%).  
   On GPT-5.4: bare (0%) < min_llmvalid (50%) < {maf, gate, sched} (100%).  
   Knowledge-only (`min_llmvalid`) *regresses* on the stronger model — a surprising
   result that strengthens the argument for enforcement.

2. **SCHED is the only arm that provides model-independent correctness guarantees.**
   All other arms' success rates are non-monotone functions of model capability.
   SCHED's deterministic scheduling makes it the only arm suitable for
   safety-critical deployments where model quality cannot be guaranteed.

3. **"More capable" ≠ "more reliable" without structural enforcement.**  
   The min_llmvalid regression demonstrates that scaling model capability
   can *hurt* protocol completion when verbosity exhausts step budgets.
   This is a cautionary result for the "just use a bigger model" approach
   to multi-agent coordination.

4. **The cost argument for SCHED is strongest on capable models**: when everything
   works, SCHED is 4.6× cheaper than bare, 6.9× cheaper than min_llmvalid,
   3.0× cheaper than gate, and 2.0× cheaper than MAF.

## Statistical Notes

- All arms ran n=30 with balanced branch allocation (15 high, 15 standard).
- Confidence intervals are **Wilson score intervals** (95%, z=1.96).
- Token counts are the reliable efficiency metric; wall-clock times are
  unreliable due to parallel execution and rate-limit contention.
- `min_llmvalid` ran n=26 (4 trials lost to transient API failures).
  Mean attempts = 2.0 (vs 1.0 for enforced arms), confirming retry pressure.
- All trials use `max_attempts=3` with retry on goal failure.
- MAF had 1/30 trials requiring a second attempt (all others: first attempt only).
