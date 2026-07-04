# Ladder table — revenue_audit (no Foundry, cheap subagents)

Cost unit = **LLM agent-calls** (tokens are not metered without Foundry; calls are the model-independent coordination-cost proxy). Cost-to-goal = total calls / GCR-fraction, the finance table's "true cost per delivered result".

| arm | GCR | CGC | Disasters | Calls/trial | Cost-to-goal (calls) | n (missing) |
|---|---|---|---|---|---|---|
| A: Intent only | 100.0% | 0.0% | 10 | 3.0 | 30.0 | 10 |
| B: Global text | 100.0% | 0.0% | 10 | 3.0 | 30.0 | 10 |
| C-min: Local contract | 100.0% | 100.0% | 0 | 9.0 | 90.0 | 10 |
| C+spec: Local + gate | 100.0% | 100.0% | 0 | 9.0 | 90.0 | 10 |
| STJP: +scheduler | 100.0% | 100.0% | 0 | 3.0 | 30.0 | 10 |
