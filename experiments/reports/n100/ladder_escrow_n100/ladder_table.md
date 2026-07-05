# Ladder table — escrow_trade (no Foundry, cheap subagents)

Cost unit = **LLM agent-calls** (tokens are not metered without Foundry; calls are the model-independent coordination-cost proxy). Cost-to-goal = total calls / GCR-fraction, the finance table's "true cost per delivered result".

| arm | GCR | CGC | Disasters | Calls/trial | Cost-to-goal (calls) | n (missing) |
|---|---|---|---|---|---|---|
| A: Intent only | 83.0% | 70.0% | 26 | 27.8 | 3349.4 | 100 |
| B: Global text | 82.0% | 73.0% | 35 | 28.8 | 3512.2 | 100 |
| C-min: Local contract | 100.0% | 75.0% | 49 | 27.1 | 2708.0 | 100 |
| C+spec: Local + gate | 97.0% | 97.0% | 0 | 28.0 | 2882.5 | 100 |
| C+min: Local + gate | 83.0% | 83.0% | 0 | 24.7 | 2978.3 | 100 |
| STJP: +scheduler | 98.0% | 98.0% | 0 | 7.0 | 714.3 | 100 |
