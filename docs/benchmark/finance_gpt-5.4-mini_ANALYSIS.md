# Quarterly Finance Report — Benchmark Analysis

## Experiment Configuration

| Parameter | Value |
|---|---|
| **Case** | `finance` (Quarterly Finance Report with high-revenue audit branching) |
| **Model** | GPT-5.4 Mini (Azure AI Foundry) |
| **Trials** | 30 pooled across 2 independent runs (Run A: n=10, Run B: n=20) |
| **Max attempts/trial** | 3 |
| **Roles** | Fetcher, RevenueAnalyst, ExpenseAnalyst, Writer, TaxVerifier, TaxSpecialist |
| **Goals** | 6 (G1–G6, see below) |
| **Protocol** | LLM-drafted, Scribble-validated, deadlock-free (6 roles, branching choice) |
| **Execution mode** | Parallel (shared rate-limited deployment) |
| **Dates** | Run A: 2026-07-20, Run B: 2026-07-28 |
| **Code version** | Commit `f83a88d` (both runs) |
| **Branches** | `high` (revenue ≥ $50k, tax-specialist audit required) / `standard` |

## Protocol Complexity

This case is significantly more complex than `agenticpay_settlement` (4 roles, linear):

- **6 roles** with a value-dependent branching choice at RevenueAnalyst
- **Fan-out notifications** to TaxVerifier, TaxSpecialist, and Writer
- **Audit sub-protocol** (high branch only): TaxSpecialist produces audit,
  TaxVerifier approves, before the report can be written
- **Two independent analysis streams** (Revenue + Expense) that must converge

## Main Results

### Goal Achievement (Set B) — All-Goals-Pass Rate (Pooled)

A trial succeeds only if **all 6 goals** are achieved in at least one attempt.

| Arm | n | Strict % | 95% CI (Wilson) | Role-pair % | 95% CI |
|---|---:|---:|---|---:|---|
| bare | 19 | N/A | — | 42.1% | [23.1, 63.7] |
| maf_groupchat_llmvalid | 30 | 6.7% | [1.8, 21.3] | 6.7% | [1.8, 21.3] |
| global_decentralized | 10 | 100.0% | [72.2, 100] | 100.0% | [72.2, 100] |
| min_llmvalid | 30 | 90.0% | [74.4, 96.5] | 90.0% | [74.4, 96.5] |
| min_llmvalid_gate | 25 | 52.0% | [33.5, 70.0] | 52.0% | [33.5, 70.0] |
| **min_llmvalid_sched** | **30** | **100.0%** | **[88.6, 100]** | **100.0%** | **[88.6, 100]** |

> **Strict**: exact (sender, receiver, label) + predicate match.  
> **Role-pair**: (sender, receiver) + predicate (label may differ).  
> N/A = arm has no protocol vocabulary (intent-only).  
> `global_decentralized` available in Run A only (n=10).

### Replication Consistency

| Arm | Run A (n=10) | Run B (n=20) | Δ |
|---|---:|---:|---|
| bare (rp) | 40.0% | 44.4% | +4.4pp |
| maf_groupchat_llmvalid | 10.0% | 5.0% | −5.0pp |
| min_llmvalid | 90.0% | 90.0% | 0.0pp |
| min_llmvalid_gate | 62.5% (n=8) | 47.1% (n=17) | −15.4pp |
| min_llmvalid_sched | 100.0% | 100.0% | 0.0pp |

> The two runs produce consistent results. Gate variance is explained by
> small n (8 vs 17) plus the gate-retry budget exhaustion effect.

### Protocol Conformance (Set A) — Violations (Pooled)

| Arm | Total Events | Total Violations | Violation Rate |
|---|---:|---:|---:|
| bare | 1,241 | 1,207 | 97.3% |
| maf_groupchat_llmvalid | 341 | 98 | 28.7% |
| global_decentralized | 113 | 6 | 5.3% |
| min_llmvalid | 424 | 93 | 21.9% |
| min_llmvalid_gate | 424 | 0 | 0.0% |
| min_llmvalid_sched | 285 | 0 | 0.0% |

### Cost Efficiency (Pooled Weighted Averages)

| Arm | Avg Tokens/Trial | Avg Calls/Trial | Token Savings vs Bare |
|---|---:|---:|---:|
| bare | 135,879 | 88.5 | — |
| maf_groupchat_llmvalid | 31,519 | 22.0 | 76.8% |
| global_decentralized | 103,828 | 34.4 | 23.6% |
| min_llmvalid | 50,200 | 46.0 | 63.1% |
| min_llmvalid_gate | 54,633 | 54.9 | 59.8% |
| **min_llmvalid_sched** | **12,652** | **9.5** | **90.7%** |

### Per-Goal Breakdown — Strict (Run B, n=20)

| Arm | G1 (Revenue) | G2 (Audit) | G3 (Approval) | G4 (Analysis) | G5 (Expense) | G6 (Report) |
|---|---:|---:|---:|---:|---:|---:|
| bare | N/A | N/A | N/A | N/A | N/A | N/A |
| maf_groupchat_llmvalid | 100% | 80% | 55% | 25% | 45% | 25% |
| min_llmvalid | 100% | 100% | 100% | 90% | 100% | 95% |
| min_llmvalid_gate | 100% | 47% | 100% | 100% | 100% | 82% |
| min_llmvalid_sched | 100% | 100% | 100% | 100% | 100% | 100% |

> G1–G2 are branch-conditional (high only, vacuously satisfied on standard).  
> bare uses role-pair metric: G1=44%, G2=89%, G3=78%, G4=67%, G5=89%, G6=100%.

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

1. **SCHED achieves perfect safety AND 90.7% token savings on a 6-role protocol.**  
   At 12,652 tokens/trial (vs 135,879 bare), the EFSM scheduler is 10.7×
   cheaper while achieving 100% strict goal completion [88.6, 100] across
   30 pooled trials. This is the strongest cost-efficiency result — the protocol
   pays for itself with each LLM call it avoids.

2. **Protocol knowledge alone achieves 90% without enforcement.**  
   `min_llmvalid` (projected local types, no gate/scheduler) reaches 90% strict
   [74.4, 96.5] — the same rate as on `agenticpay_settlement` (55.6%) but
   higher, suggesting GPT-5.4-mini handles 6-role coordination with
   projected types surprisingly well. The remaining 10% failures are ordering
   errors (G4 or G6 missed).

3. **Gate enforcement WITHOUT scheduling HURTS on complex protocols.**  
   `min_llmvalid_gate` at 52.0% [33.5, 70.0] is *worse* than unguarded
   `min_llmvalid` (90.0%). Root cause: with round-robin scheduling, the gate
   blocks messages from roles polled out-of-turn, consuming retry budget
   until `max_steps` is exhausted. The scheduler resolves this by only
   polling roles with enabled SEND transitions — gate + scheduler together
   yield 100%.

4. **MAF GroupChat fails catastrophically on multi-role coordination.**  
   `maf_groupchat_llmvalid` (6.7%) is barely above chance despite receiving
   the full protocol text. The LLM-based speaker-selection in GroupChat
   cannot maintain ordering across 6 concurrent roles — it achieves G1
   (100%, simple send) but collapses on later sequencing goals (G6: 25%).

5. **Bare agents produce 97.3% protocol violations.**  
   Without any protocol knowledge, agents produce almost exclusively
   non-conforming messages — confirming that protocol-shaped coordination
   does not emerge from intent alone, even with descriptive role prompts.

6. **Results replicate across independent runs.**  
   Run A (2026-07-20) and Run B (2026-07-28) agree within expected
   binomial variance on all arms, confirming experimental stability.

## Comparison with AgenticPay Settlement (Same Model)

| Metric | AgenticPay (4 roles) | Finance (6 roles) |
|---|---|---|
| SCHED strict | 100% (n=10) | 100% (n=30) |
| SCHED tokens/trial | 44,022 | 12,652 |
| min_llmvalid strict | 55.6% (n=9) | 90.0% (n=30) |
| Gate strict | 100% (n=10) | 52.0% (n=25) |
| Bare violation rate | 98.3% | 97.3% |

> Finance's SCHED uses fewer tokens because the EFSM scheduler precisely
> sequences 6 roles (9.5 calls/trial = close to the protocol's minimum 9
> message events), whereas AgenticPay's 4-role linear protocol still involves
> more round-trips. Gate is dramatically worse on finance because
> round-robin on 6 roles means more out-of-turn polls → more rejections
> → faster budget exhaustion.

## Statistical Notes

- Results are **pooled across 2 independent runs** (same code, same model,
  different dates). Per-arm n varies due to transient Azure API failures
  (bare: 10+9=19, gate: 8+17=25, others: 10+20=30).
- Confidence intervals are **Wilson score intervals** (95%, z=1.96).
- Token counts are the reliable efficiency metric; wall-clock times are
  unreliable due to parallel execution and rate-limit contention.
- `global_decentralized` was only run in Run A (n=10); its CI is wider.
- All trials use `max_attempts=3` with retry on goal failure.
