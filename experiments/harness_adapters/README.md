# Harness adapters — LangGraph

`langgraph_ladder.py` runs an STJP arm-ladder case (`revenue_audit`,
`escrow_trade`) as a **LangGraph `StateGraph`** instead of the native
`engine_ladder.py`. It exists for two reasons, and it answers a question that
had been marked "blocked": *can you install LangGraph and use it to trace token
usage and agent behaviour?*

## 1. E7 third harness (portability) — **done, 14/14 agreement**

The plan's E7 was "in-process vs standalone monitor agreement only." This adds a
genuinely different runtime. LangGraph executes the protocol (roles = graph
nodes, rounds = a self-looping `poll` node, the gate/scheduler as node logic);
the resulting message trace is then judged by the **native STJP
`SessionMonitor`**. Agreement means:

- every clean structural run → **0 monitor violations**, and
- an injected off-protocol send (Analyst emits an illegal `Filed`) → **caught**.

Result across both cases × all six arms + a fault case per case:
**14 / 14 agree** (`experiments/reports/n100/e7/langgraph_agreement.json`).
The STJP monitor's verdicts are runtime-independent.

```
python experiments/harness_adapters/langgraph_ladder.py --case revenue_audit --arm min_gate
python experiments/harness_adapters/langgraph_ladder.py --case revenue_audit --arm intent --fault
```

## 2. Token metering — **wired and ready, needs an LLM key**

Each role node calls a pluggable `decide(view)`. If `ANTHROPIC_API_KEY` is set
it uses `langchain_anthropic.ChatAnthropic` and **real per-call token usage is
captured** via `langchain_core.callbacks.get_usage_metadata_callback()` — the
run prints `tokens: input=… output=…`. Without a key it falls back to a
deterministic contract-follower (0 tokens) so the harness still runs and the
wiring is provable.

**Why tokens read 0 here:** this environment has **no usable LLM API key**.
`ANTHROPIC_BASE_URL` is the public `api.anthropic.com` (needs an `x-api-key` we
don't have); there is no local model (ollama/vllm/lmstudio all unreachable); and
the CLI's own session credential must not be repurposed for separately-billed
API calls. So LangGraph installs and runs, but it cannot call a live metered
model *in this environment*. **Give the process an `ANTHROPIC_API_KEY` (or point
`ANTHROPIC_BASE_URL` at a keyed gateway / a local model) and `--llm` produces
real token numbers and real per-agent LLM behaviour** — that is exactly the
metered-E6 / live-token unblock.

## 3. Behaviour tracing

Every run prints the full ordered message trace (round, sender, receiver, label,
payload) and gate rejections — the LangGraph execution *is* the behaviour trace.
With `--llm` each node's decision is a real model call, so the same trace becomes
a live per-agent behaviour log.

## Status vs the plan

- **E7 "three-harness":** was blocked; now LangGraph is a working third harness,
  14/14 agreement. (LangGraph + langchain-anthropic are installed.)
- **Token-metered E6 / live token numbers:** the framework is done and wired;
  the only remaining dependency is an LLM key, which is an environment/access
  matter, not a code one.
