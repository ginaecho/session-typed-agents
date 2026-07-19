# Result 2 — Same task, one-third the tokens

**Measured 2026-06-17. Case: `report_pipeline`. Model: gpt-5.4. 6 trials per setting.**

> **At a glance:** A six-agent report pipeline finishes 100% of the time in every setting — so this test is purely about cost. With no contract, a finished report costs 24,100 tokens. With a lean per-agent contract projected from the validated protocol, the same finished report costs **8,800 tokens — a 63% reduction**. The saving comes from agents no longer having to *figure out* the coordination every turn: it's already written down.

Companion to [`RESULT_1_DEADLOCK.md`](RESULT_1_DEADLOCK.md): that result showed an unchecked spec can fail *catastrophically* (deadlock → infinite cost). This one shows the *everyday* saving: even when everything works, a contract makes it much cheaper.

---

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [The story at a glance (STAR)](#the-story-at-a-glance-star)
- [How this experiment is set](#how-this-experiment-is-set)
- [1. The story — where the money actually goes in multi-agent systems](#1-the-story--where-the-money-actually-goes-in-multi-agent-systems)
- [2. How the test was set up (a fair efficiency test)](#2-how-the-test-was-set-up-a-fair-efficiency-test)
- [3. The numbers](#3-the-numbers)
- [4. Why — the mechanism, in two parts](#4-why--the-mechanism-in-two-parts)
- [5. The second lever: scheduling (measured later, in Result 4)](#5-the-second-lever-scheduling-measured-later-in-result-4)
- [6. Honest caveats](#6-honest-caveats)
- [7. Where the raw data is](#7-where-the-raw-data-is)
- [Run it on Azure AI Foundry (later)](#run-it-on-azure-ai-foundry-later)
<!-- MENU:END -->

## The story at a glance (STAR)

- **Situation** — In multi-agent frameworks, a large share of the spend goes not to doing the work but to agents re-figuring out the coordination every single turn — "has the research happened yet? is it my turn?" — even on tasks that never fail.
- **Task** — On a task where every setting completes 100% of the time (so it is a pure cost test), measure how much a per-agent contract actually saves versus giving agents only the task description.
- **Action** — 3 settings x 6 trials on the `report_pipeline` case (a six-role linear pipeline), gpt-5.4, same runner: no contract, full contract (`spec`), and lean contract (`min`).
- **Result** — No-contract cost **24,100 tokens/trial**; the lean contract reaches the same finished report at **8,800 tokens — a 63% reduction** — driven by thinking tokens per call dropping from **1,534 to 552**.

## How this experiment is set

- **Case(s):** [`report_pipeline`](../../experiments/cases/report_pipeline/)
- **Arms/settings:** no contract (intent only); full per-agent contract (`spec`); lean per-agent contract (`min`)
- **Trials:** 6 per arm
- **Who plays the roles:** gpt-5.4, one Azure AI Foundry hosted agent per role per arm (`case_runner.py` / `FoundryRunner`)
- **Isolation:** each role is a separate Foundry agent with its own thread; sees only its own thread's history and its own contract, never another role's prompt
- **Harness & budgets:** `case_runner.py`, round-robin polling (every role asked every round — this run isolates cost, not scheduling, so the scheduler is deliberately not in play here); up to 3 attempts per trial, each capped at `max_steps: 30` (`case.yaml`)
- **Where the raw data is:** `experiments/cases/report_pipeline/runs/` (run directory — not committed; per-trial numbers preserved in the report tables and `summary*.json` copies referenced in this document)

## 1. The story — where the money actually goes in multi-agent systems

Anyone who has run a multi-agent framework (AutoGen, CrewAI, a group-chat orchestrator) has watched this: you give each agent a role and a shared goal, and a large share of the spend goes not to *doing the work* but to *figuring out the coordination*. Every turn, each agent re-reads the whole conversation and reasons out loud:

> "Has the research happened yet? Is it my turn? What should I produce? Should I wait for the analyst?"

The orchestrator adds its own "who should speak next?" deliberation. Agents take wrong turns — the Publisher tries to publish before the Reviewer approved — which then have to be undone.

This coordination overhead grows with the number of agents, because every *idle* agent still gets asked "anything to do?" and still spends tokens answering. It is the same money the deadlock burns, just slower and without ever failing outright — so it hides on the invoice instead of showing up as an incident.

The fix: give each agent a **projected contract** — its own slice of the validated protocol, saying exactly what it receives, what it sends, and to whom. There is nothing left to deliberate: the agent either has its trigger (act) or it doesn't (wait). And because the contract was projected from a checker-validated protocol, the coordination it encodes is provably correct. **You are not just cheaper — you are cheaper *and* safe.**

---

## 2. How the test was set up (a fair efficiency test)

The case is a six-role, strictly linear pipeline: Requester → Researcher → Analyst → Drafter → Reviewer → Publisher. There is no trap and no deadlock — **every setting completes 100% of its trials** — which is exactly what makes it a fair *cost* test. (Rule of fair benchmarking: never read cost off a task some settings fail; that measures cost-of-failure, not cost-of-coordination.)

Same model, same runner, same 6 trials. The **only** variable is what each agent is given:

- **No contract (intent only)** — the task description and the role list. Each agent must work out, every single turn, whether it's its turn and what to send.
- **Full contract (`spec`)** — each agent's own complete projected contract (every state and allowed step, with value guards).
- **Lean contract (`min`)** — the same contract compressed to one line per step.

---

## 3. The numbers

| Measure | No contract | Full contract (`spec`) | Lean contract (`min`) |
|---|---|---|---|
| Completion | 100% | 100% | 100% |
| **Total tokens per trial** | **24,100** | 18,400 | **8,800** |
| — prompt (input) tokens per trial | 13,400 | 12,000 | 5,500 |
| — thinking (output) tokens per trial | 10,700 | 6,400 | 3,300 |
| Model calls per trial | 7.0 | 6.0 | 6.0 |
| **Thinking tokens per call** | **1,534** | 1,061 | **552** |
| Seconds per trial | 148 | 91 | 66 |

**The lean contract reaches the same finished report at 8,800 tokens vs 24,100 without a contract — a 63% reduction** (and 52% below the full-length contract). It is also more than twice as fast (66s vs 148s).

---

## 4. Why — the mechanism, in two parts

The saving splits cleanly into two causes, both from giving each agent a clear, small contract:

1. **Less thinking per turn (output tokens).** Without a contract, an agent spends about **1,534 tokens per turn** reasoning "given the task, is it my turn? what should I send? to whom?" With the lean contract it spends about **552** — it already knows: *"at this step, send `Findings` to Drafter."* That's a 69% drop in deliberation. This is the "agents keep thinking about how to proceed" waste, measured.

2. **A smaller prompt every call (input tokens).** The lean per-agent contract is a fraction of the size of the full task prose or the verbose contract, so every single call carries fewer input tokens. Prompt cost drops 59%.

The no-contract setting also needed one extra round (7 calls vs 6) — a bit of wrong-turn overhead on top of the per-turn deliberation.

---

## 5. The second lever: scheduling (measured later, in Result 4)

This test still used a "round-robin" runner that polls **every** agent each round — so idle agents burn a call just to say "WAIT." The projected contract enables a better runtime: the protocol's state machine says exactly which agents *can* act at each moment, so only they get polled.

- In an offline simulation this cut **83% of agent calls** versus round-robin.
- Connected to real agents on the finance case, it produced the headline in [`RESULT_4_FULL_STACK.md`](RESULT_4_FULL_STACK.md): 13,300 tokens per delivered report — 9× cheaper than the same protocol pasted as text.

On this short pipeline the scheduler has little to save (6–7 calls for 6 messages is already near-minimal); its saving compounds on wider protocols where many agents are idle at each step.

---

## 6. Honest caveats

- This case is small (6 roles, one straight line). The *contract-size* saving shown here should grow with protocol size — the bigger the whole protocol, the bigger the win from each agent seeing only its slice — but that scale test has not been run yet.
- The 63% number is for gpt-5.4 on this case. The mechanism (less deliberation + smaller prompts) is general, but the exact percentage will vary by model and task.

## 7. Where the raw data is

- Case: `experiments/cases/report_pipeline/` (protocol, contracts, goals)
- Run outputs: `experiments/cases/report_pipeline/runs/` (per-message logs, `summary.json` with token counts)
- Offline scheduler simulation: `stjp_core/runtime/delm_runner.py` + `experiments/scripts/smoke_delm_runtime.py`

## Run it on Azure AI Foundry (later)

This run's harness was already Azure AI Foundry-hosted agents (`experiments/scripts/case_runner.py` / `FoundryRunner`), gpt-5.4. To reproduce or extend it, follow the standard recipe in [`1_TECH_SETUP.md` section 5](../1_TECH_SETUP.md#5-running-stjp-with-azure-ai-foundry-hosted-agents) plus the four registration points listed in [`experiments/CLAUDE.md`](../../experiments/CLAUDE.md) (`registry.py` SCENARIOS, `case_runner.py` `_FOUNDRY_INSTALL_KEYS` and `FOUNDRY_KEYS`, `evaluate_run.py` `VOCABULARY_ARMS`).
