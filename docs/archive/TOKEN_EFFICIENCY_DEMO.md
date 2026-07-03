# Token-efficiency demo — STJP reaches the same goal for ~1/3 the tokens

**2026-06-17.** Companion to `DEADLOCK_DEMO.md`. The deadlock demo proved STJP
prevents *catastrophic* waste (an unchecked spec can deadlock → infinite
cost-of-success). This demo proves the *steady-state* claim: even when the task
finishes fine, a validated + projected per-agent contract reaches the goal with
far fewer tokens than no contract — and a lean contract is best of all.

## Why this happens in the real world (the story)

Anyone who has run a multi-agent framework (AutoGen / CrewAI / a group-chat
orchestrator) has watched it: you give each agent a role and a shared goal and let
them coordinate, and a large fraction of the spend goes not to *doing the work* but
to *figuring out the coordination*. Every turn, each agent re-reads the whole
conversation and reasons out loud: "has the research happened yet? is it my turn?
what should I produce? should I wait for the analyst?" The orchestrator adds its
own "who should speak next?" deliberation. Agents take wrong turns — the Publisher
tries to publish before the Reviewer has approved — that then have to be undone.

This coordination overhead is the *dominant* cost of real agentic pipelines, and it
grows with the number of agents and steps, because every idle agent still gets
asked "anything to do?" and still spends tokens answering. It is the same money the
deadlock burns, just slower and without ever failing outright — so it hides on the
invoice instead of in an incident.

STJP replaces open-ended coordination with a **projected per-agent contract**: each
agent is told exactly what it receives, what it sends, and to whom. There is
nothing to deliberate — the agent either has its trigger (act) or it doesn't
(wait). The coordination tokens collapse. And because that contract was *projected
from a validated global protocol*, the coordination it encodes is provably correct
and deadlock-free: you are not just cheaper, you are cheaper **and** safe. In one
line: **STJP turns probabilistic, re-derived-every-turn coordination into a
compiled contract — same work, a fraction of the bill.**

## Design — a fair efficiency test

`experiments/cases/report_pipeline`: a 6-role strictly-linear production pipeline
(Requester → Researcher → Analyst → Drafter → Reviewer → Publisher). No deadlock,
no trap — **every arm completes 100%** — so this is purely about *how many tokens
it takes*. Same model (gpt-5.4), same round-robin runner, same n=6; the **only**
variable is what each agent is given:

- **intent-only (`bare`)** — the task description + role list, no contract. Each
  agent must work out, every turn, whether it's its turn and what to send.
- **projected `spec`** — each agent's own verbose local contract (the full EFSM
  markdown + guards).
- **lean `min`** — each agent's own contract compressed to one line per step.

## Result (n=6, gpt-5.4)

| metric | intent-only | projected `spec` | lean `min` |
|---|---|---|---|
| completion | 100% | 100% | 100% |
| **total tokens / trial** | **24.1k** | 18.4k | **8.8k** |
| &nbsp;&nbsp;prompt tokens / trial | 13.4k | 12.0k | 5.5k |
| &nbsp;&nbsp;completion (deliberation) / trial | 10.7k | 6.4k | 3.3k |
| LLM calls / trial | 7.0 | 6.0 | 6.0 |
| **deliberation tokens / call** | **1,534** | 1,061 | **552** |
| seconds / trial | 148 | 91 | 66 |

**The lean projected contract reaches the same finished report at 8.8k tokens vs
the no-contract 24.1k — a 63% reduction** (and 52% below the verbose contract).

## Why — the mechanism (this is the "wasted tokens" you predicted)

The savings split cleanly into two parts, both caused by giving each agent a
clear, small contract:

1. **Less deliberation (output tokens).** Without a contract, an agent spends
   ~1,534 tokens *per turn* reasoning "given the intent, is it my turn, what
   should I send, to whom?" With the lean contract it spends ~552 — it already
   knows: "at this state, send `Findings` to Drafter." Deliberation drops 69%.
   This is exactly the "agents keep thinking and investigating how to proceed"
   waste.
2. **Smaller prompt (input tokens).** The lean per-agent contract is a fraction
   of the size of the intent+goals prose or the verbose EFSM markdown, so every
   call carries fewer input tokens. Prompt drops 59%.

The no-contract arm also took one extra round (7 calls vs 6) — a small amount of
wrong-route/coordination overhead on top of the per-turn deliberation.

## The two efficiency levers, and the bigger one still on the table

- **Lean projected contract** (shown here): −63% tokens vs no contract, same
  completion. A clear, minimal per-agent contract makes every turn decisive.
- **EFSM-driven scheduling** (shown in `delm_runner.py`'s offline smoke, −83%
  *calls* vs round-robin): the round-robin runner polls *every* agent each round,
  so idle agents burn a call just to say WAIT. The projected EFSM tells the runtime
  exactly which agents can act, so only they are polled. On this case the
  round-robin still cost 6–7 calls for 6 messages (near-minimal because the chain
  is short); on wider protocols with many idle roles per step the scheduler's
  saving compounds. Wiring the real LLM agent into the scheduler (vs the current
  oracle) is the remaining online step to quantify this end-to-end.

## Together with the deadlock demo

- `DEADLOCK_DEMO.md`: unchecked spec → deadlock → **∞** cost-of-success; the
  static checker prevents it for free.
- this demo: validated + projected contract → same goal for **~1/3** the tokens.

STJP is a guard that both **removes the catastrophic tail** (deadlock) **and
lowers the steady-state bill** (deliberation + prompt size + scheduling).
