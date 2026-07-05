# Ladder table — revenue_audit (no Foundry, cheap subagents)

Cost unit = **LLM agent-calls** (tokens are not metered without Foundry; calls are the model-independent coordination-cost proxy). Cost-to-goal = total calls / GCR-fraction, the finance table's "true cost per delivered result".

| arm | GCR | CGC | Disasters | Calls/trial | Cost-to-goal (calls) | n (missing) |
|---|---|---|---|---|---|---|
| A: Intent only | 100.0% | 2.0% | 0 | 9.0 | 900.0 | 100 |
| B: Global text | 100.0% | 5.0% | 95 | 3.3 | 330.0 | 100 |
| C-min: Local contract | 32.0% | 2.0% | 0 | 23.3 | 7275.0 | 100 |
| C+spec: Local + gate | 98.0% | 98.0% | 0 | 9.1 | 927.6 | 100 |
| C+min: Local + gate | 100.0% | 100.0% | 0 | 9.0 | 900.0 | 100 |
| STJP: +scheduler | 100.0% | 100.0% | 0 | 3.0 | 300.0 | 100 |
