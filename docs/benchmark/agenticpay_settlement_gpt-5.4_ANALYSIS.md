# AgenticPay Settlement — Benchmark Analysis

## Experiment Configuration

| Parameter | Value |
|---|---|
| **Case** | `agenticpay_settlement` |
| **Model** | GPT-5.4 (Azure AI Foundry) |
| **Trials** | 10 per arm |
| **Max attempts/trial** | 3 |
| **Roles** | Buyer, Seller, Escrow, Carrier |
| **Goals** | 4 (G1: Deposit, G2: ShipGoods, G3: ReleasePayment, G4: SettlementComplete) |
| **Protocol** | LLM-drafted, Scribble-validated, deadlock-free |
| **Execution mode** | Parallel (shared rate-limited deployment) |
| **Date** | 2026-07-28 |

## Main Results

### Goal Achievement (Set B) — All-Goals-Pass Rate

A trial succeeds only if **all 4 goals** are achieved in at least one attempt.

| Arm | Category | n | Strict % | 95% CI | Role-pair % | 95% CI |
|---|---|---:|---:|---|---:|---|
| WITHOUT-skills | WITH | 10 | N/A | — | 0.0% | [0, 27.8] |
| WITHOUT-unchecked-skills | WITH | 10 | N/A | — | 0.0% | [0, 27.8] |
| WITHOUT-maf-gc-llmvalid | WITH | 10 | 100.0% | [72.2, 100] | 100.0% | [72.2, 100] |
| WITH-min-llmvalid | WITH | 10 | 100.0% | [72.2, 100] | 100.0% | [72.2, 100] |
| WITH-min-llmvalid-GATE | WITH | 10 | 100.0% | [72.2, 100] | 100.0% | [72.2, 100] |
| WITH-min-llmvalid-SCHED | WITH | 10 | 100.0% | [72.2, 100] | 100.0% | [72.2, 100] |

> **Strict**: exact (sender, receiver, label) + predicate match.  
> **Role-pair**: (sender, receiver) + predicate match (label may differ).  
> N/A = arm has no protocol vocabulary (intent-only).

### Protocol Conformance (Set A) — Violations

| Arm | Category | Total Events | Total Violations | Violation Rate |
|---|---|---:|---:|---:|
| WITHOUT-skills | WITH | 292 | 291 | 99.7% |
| WITHOUT-unchecked-skills | WITH | 0 | 0 | — |
| WITHOUT-maf-gc-llmvalid | WITH | 131 | 0 | 0.0% |
| WITH-min-llmvalid | WITH | 120 | 0 | 0.0% |
| WITH-min-llmvalid-GATE | WITH | 120 | 0 | 0.0% |
| WITH-min-llmvalid-SCHED | WITH | 120 | 0 | 0.0% |

### Cost Efficiency

| Arm | Avg Tokens/Trial | Avg Calls/Trial | Avg Seconds/Trial | Token Savings vs Bare |
|---|---:|---:|---:|---:|
| WITHOUT-skills | 82,544 | 59.7 | 242.8s | 0.0% |
| WITHOUT-unchecked-skills | 41,953 | 27.0 | 95.0s | 49.2% |
| WITHOUT-maf-gc-llmvalid | 22,965 | 16.8 | 66.2s | 72.2% |
| WITH-min-llmvalid | 46,408 | 35.0 | 114.4s | 43.8% |
| WITH-min-llmvalid-GATE | 48,497 | 35.0 | 125.5s | 41.2% |
| WITH-min-llmvalid-SCHED | 15,441 | 12.0 | 46.8s | 81.3% |

### Per-Goal Breakdown (Strict)

| Arm | G1 (Deposit) | G2 (ShipGoods) | G3 (ReleasePayment) | G4 (SettlementComplete) |
|---|---:|---:|---:|---:|
| WITHOUT-skills | 10%† | 100%† | 0%† | 60%† |
| WITHOUT-unchecked-skills | 0%† | 0%† | 0%† | 0%† |
| WITHOUT-maf-gc-llmvalid | 100% | 100% | 100% | 100% |
| WITH-min-llmvalid | 100% | 100% | 100% | 100% |
| WITH-min-llmvalid-GATE | 100% | 100% | 100% | 100% |
| WITH-min-llmvalid-SCHED | 100% | 100% | 100% | 100% |

> † Role-pair metric (no protocol vocabulary for strict comparison).

## Key Findings

1. **Session-type enforcement eliminates all violations.**  
   GATE and SCHED arms produce 0 protocol violations across all trials,
   compared to 291 violations (99.7% violation rate) for the unstructured baseline.

2. **All protocol-aware arms achieve 100% goal completion.**  
   GATE, SCHED, min_llmvalid, and maf_groupchat_llmvalid all achieve 100% strict
   goal completion [72.2, 100.0] CI. With GPT-5.4 (full), even the unguarded
   `min_llmvalid` arm achieves perfect results — a marked improvement over
   GPT-5.4-mini which only reached 55.6% strict on the same arm.

3. **SCHED is the most cost-efficient arm.**  
   At 15,441 tokens/trial, SCHED uses 81.3% fewer tokens than bare (82,544)
   while achieving perfect results. The EFSM scheduler avoids wasteful
   round-robin polling by only activating roles when the protocol enables them.

4. **Protocol knowledge alone is sufficient with a strong model.**  
   With GPT-5.4, `min_llmvalid` achieves 100% strict (vs 55.6% with 5.4-mini).
   The model's improved instruction-following means agents self-correct ordering
   from local type information alone — enforcement still eliminates violations
   but is no longer required for goal completion at this model capability level.

5. **Deadlock manifests as total communication failure.**  
   `unchecked_skills` (skill-based agents, no shared protocol) produces
   0 events across all trials — agents wait indefinitely for messages
   that never arrive, demonstrating the deadlock the session type prevents.

6. **MAF GroupChat with protocol spec matches Foundry projected-type arms.**  
   `maf_groupchat_llmvalid` (global spec text, MAF group chat, no projection)
   achieves 100% strict and 0 violations — the LLM speaker-selection in MAF
   combined with protocol text achieves the same safety as EFSM projection.

## Statistical Notes

- Confidence intervals are **Wilson score intervals** (95%, z=1.96),
  appropriate for small-sample binomial proportions.
- Timing data includes queueing contention (parallel execution mode);
  token counts are the reliable efficiency metric.
- All arms have n=10 trials (no transient failures in this run).
