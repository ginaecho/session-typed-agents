# Ladder table — revenue_audit (no Foundry, cheap subagents)

**GCR** = goal-completion rate (% of trials that reached the goal). **CGC** =
critical-goal completion (reached the goal AND had zero critical-safety
violations). Cost unit = **LLM agent-calls** (tokens are not metered without
Foundry; calls are the model-independent coordination-cost proxy).
Cost-to-goal = total calls / GCR-fraction, the finance table's "true cost per
delivered result".

The **$** column is an estimate: cost-to-goal (calls) × ≈ **$0.00125** per lean haiku call (~1k in + ~50 out at $1/$5 per 1M). Method: [`COST_ESTIMATE.md`](../COST_ESTIMATE.md#per-arm-cost-to-goal-in-dollars-the--column-in-the-ladder-tables).

| arm | GCR | CGC | Disasters | Calls/trial | Cost-to-goal (calls) | Cost-to-goal ($, est.) | n (missing) |
|---|---|---|---|---|---|---|---|
| A: Intent only | 100.0% | 2.0% | 0 | 9.0 | 900.0 | $1.12 | 100 |
| B: Global text | 100.0% | 5.0% | 95 | 3.3 | 330.0 | $0.41 | 100 |
| C-min: Local contract | 32.0% | 2.0% | 0 | 23.3 | 7275.0 | $9.09 | 100 |
| C+spec: Local + gate | 98.0% | 98.0% | 0 | 9.1 | 927.6 | $1.16 | 100 |
| C+min: Local + gate | 100.0% | 100.0% | 0 | 9.0 | 900.0 | $1.12 | 100 |
| STJP: +scheduler | 100.0% | 100.0% | 0 | 3.0 | 300.0 | $0.38 | 100 |
