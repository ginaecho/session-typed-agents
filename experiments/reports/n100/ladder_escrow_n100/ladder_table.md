# Ladder table — escrow_trade (no Foundry, cheap subagents)

Cost unit = **LLM agent-calls** (tokens are not metered without Foundry; calls are the model-independent coordination-cost proxy). Cost-to-goal = total calls / GCR-fraction, the finance table's "true cost per delivered result".

| arm | GCR | CGC | Disasters | Calls/trial | Cost-to-goal (calls) | n (missing) |
|---|---|---|---|---|---|---|
| A: Intent only | 83.0% | 70.0% | 26 | 27.8 | 3349.4 | 100 |
| B: Global text | 82.0% | 73.0% | 35 | 28.8 | 3512.2 | 100 |
| C-min: Local contract | 100.0% | 75.0% | 49 | 27.1 | 2708.0 | 100 |
| C+spec: Local + gate | 79.0% | 79.0% | 0 | 27.2 | 3448.1 | 100 |
| C+min: Local + gate | 82.0% | 82.0% | 0 | 24.5 | 2990.2 | 100 |
| STJP: +scheduler | 97.0% | 97.0% | 0 | 7.0 | 720.6 | 100 |
