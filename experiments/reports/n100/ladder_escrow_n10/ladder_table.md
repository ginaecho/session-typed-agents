# Ladder table — escrow_trade (no Foundry, cheap subagents)

`escrow_trade` is a goods-for-payment case whose Escrow role holds funds until
both sides deliver, like a real-world escrow. **GCR** = goal-completion rate
(% of trials that reached the goal). **CGC** = critical-goal completion
(reached the goal AND had zero critical-safety violations). Cost unit = **LLM
agent-calls** (tokens are not metered without Foundry; calls are the
model-independent coordination-cost proxy). Cost-to-goal = total calls /
GCR-fraction, the finance table's "true cost per delivered result".

| arm | GCR | CGC | Disasters | Calls/trial | Cost-to-goal (calls) | n (missing) |
|---|---|---|---|---|---|---|
| A: Intent only | 100.0% | 100.0% | 0 | 27.6 | 276.0 | 10 |
| B: Global text | 100.0% | 100.0% | 0 | 28.0 | 280.0 | 10 |
| C-min: Local contract | 100.0% | 100.0% | 0 | 28.0 | 280.0 | 10 |
| C+spec: Local + gate | 100.0% | 100.0% | 0 | 28.0 | 280.0 | 10 |
| C+min: Local + gate | 100.0% | 100.0% | 0 | 28.0 | 280.0 | 10 |
| STJP: +scheduler | 100.0% | 100.0% | 0 | 7.0 | 70.0 | 10 |
