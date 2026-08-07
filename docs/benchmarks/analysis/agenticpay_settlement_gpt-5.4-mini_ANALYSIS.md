# AgenticPay Settlement — Benchmark Analysis

## Experiment Configuration

| Parameter | Value |
|---|---|
| **Case** | `agenticpay_settlement` |
| **Model** | GPT-5.4 Mini (Azure AI Foundry) |
| **Trials** | 10 per arm (9 for min_llmvalid due to transient failure) |
| **Max attempts/trial** | 3 |
| **Roles** | Buyer, Seller, Escrow, Carrier |
| **Goals** | 4 (G1: Deposit, G2: ShipGoods, G3: ReleasePayment, G4: SettlementComplete) |
| **Protocol** | LLM-drafted, Scribble-validated, deadlock-free |
| **Execution mode** | Parallel (shared rate-limited deployment) |
| **Date** | 2026-07-27 |

## Main Results

### Goal Achievement (Set B) — All-Goals-Pass Rate

A trial succeeds only if **all 4 goals** are achieved in at least one attempt.

| Arm | Category | n | Strict % | 95% CI | Role-pair % | 95% CI |
|---|---|---:|---:|---|---:|---|
| WITHOUT-skills | WITH | 10 | N/A | — | 0.0% | [0, 27.8] |
| WITHOUT-unchecked-skills | WITH | 10 | N/A | — | 0.0% | [0, 27.8] |
| WITHOUT-maf-gc-llmvalid | WITH | 10 | 0.0% | [0, 27.8] | 100.0% | [72.2, 100] |
| WITH-min-llmvalid | WITH | 9 | 55.6% | [26.7, 81.1] | 100.0% | [70.1, 100] |
| WITH-min-llmvalid-GATE | WITH | 10 | 100.0% | [72.2, 100] | 100.0% | [72.2, 100] |
| WITH-min-llmvalid-SCHED | WITH | 10 | 100.0% | [72.2, 100] | 100.0% | [72.2, 100] |

> **Strict**: exact (sender, receiver, label) + predicate match.  
> **Role-pair**: (sender, receiver) + predicate match (label may differ).  
> N/A = arm has no protocol vocabulary (intent-only).

### Protocol Conformance (Set A) — Violations

| Arm | Category | Total Events | Total Violations | Violation Rate |
|---|---|---:|---:|---:|
| WITHOUT-skills | WITH | 477 | 469 | 98.3% |
| WITHOUT-unchecked-skills | WITH | 0 | 0 | — |
| WITHOUT-maf-gc-llmvalid | WITH | 248 | 84 | 33.9% |
| WITH-min-llmvalid | WITH | 347 | 71 | 20.5% |
| WITH-min-llmvalid-GATE | WITH | 358 | 0 | 0.0% |
| WITH-min-llmvalid-SCHED | WITH | 360 | 0 | 0.0% |

### Cost Efficiency

| Arm | Avg Tokens/Trial | Avg Calls/Trial | Avg Seconds/Trial | Token Savings vs Bare |
|---|---:|---:|---:|---:|
| WITHOUT-skills | 98,260 | 61.3 | 198.7s | 0.0% |
| WITHOUT-unchecked-skills | 41,876 | 27.0 | 73.8s | 57.4% |
| WITHOUT-maf-gc-llmvalid | 49,307 | 39.9 | 102.1s | 49.8% |
| WITH-min-llmvalid | 97,552 | 83.4 | 219.1s | 0.7% |
| WITH-min-llmvalid-GATE | 102,630 | 84.2 | 226.7s | -4.4% |
| WITH-min-llmvalid-SCHED | 44,022 | 36.0 | 97.2s | 55.2% |

### Per-Goal Breakdown (Strict)

| Arm | G1 (Deposit) | G2 (ShipGoods) | G3 (ReleasePayment) | G4 (SettlementComplete) |
|---|---:|---:|---:|---:|
| WITHOUT-skills | 0%† | 100%† | 0%† | 100%† |
| WITHOUT-unchecked-skills | 0%† | 0%† | 0%† | 0%† |
| WITHOUT-maf-gc-llmvalid | 100% | 100% | 0% | 0% |
| WITH-min-llmvalid | 100% | 100% | 89% | 56% |
| WITH-min-llmvalid-GATE | 100% | 100% | 100% | 100% |
| WITH-min-llmvalid-SCHED | 100% | 100% | 100% | 100% |

> † Role-pair metric (no protocol vocabulary for strict comparison).

## Key Findings

1. **Session-type enforcement eliminates all violations.**  
   GATE and SCHED arms produce 0 protocol violations across all trials,
   compared to 469 violations (98.3% violation rate) for the unstructured baseline.

2. **Enforcement achieves 100% goal completion.**  
   Both GATE (monitor-rejects + re-prompts) and SCHED (EFSM-guided scheduling)
   achieve 100% strict goal completion [72.2, 100.0] CI, while the bare baseline
   achieves 0% [0.0, 27.8].

3. **SCHED is the most cost-efficient arm.**  
   At 44,022 tokens/trial, SCHED uses 55.2% fewer tokens than bare (98,261)
   while achieving perfect results. The EFSM scheduler avoids wasteful
   round-robin polling by only activating roles when the protocol enables them.

4. **Protocol knowledge without enforcement is necessary but insufficient.**  
   `min_llmvalid` (projected local types, no gate) achieves 100% role-pair
   but only 55.6% strict — agents know the vocabulary but still mis-order
   messages. `maf_groupchat_llmvalid` (global spec, group chat) achieves 100%
   role-pair but 0% strict — correct participants and goals, wrong ordering.

5. **Deadlock manifests as total communication failure.**  
   `unchecked_skills` (skill-based agents, no shared protocol) produces
   0 events across all trials — agents wait indefinitely for messages
   that never arrive, demonstrating the deadlock the session type prevents.

## Statistical Notes

- Confidence intervals are **Wilson score intervals** (95%, z=1.96),
  appropriate for small-sample binomial proportions.
- Timing data includes queueing contention (parallel execution mode);
  token counts are the reliable efficiency metric.
- `min_llmvalid` has n=9 (one trial lost to a transient Azure API failure).
