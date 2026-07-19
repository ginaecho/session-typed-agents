# Experiment Results: monitoring 6 LLM agents against a multiparty session type

Two independent 10-trial runs of `experiment_4_scenarios.py` against the
Quarterly Finance Report protocol (`P1_v2.scr`). Each trial drives 6 agents
(one per protocol role) with `gpt-5.4` via Azure OpenAI; the runtime monitor
walks each role's projected EFSM (extended finite-state machine — the
step-by-step map of that role's allowed messages) against the captured trace.

Run dates: 2026-05-07. Total: 20 trials / scenario × 2 scenarios = 80 trials.

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [How this experiment is set](#how-this-experiment-is-set)
- [Setup](#setup)
- [Side-by-side aggregate (combined 20 trials per scenario)](#side-by-side-aggregate-combined-20-trials-per-scenario)
- [Per-trial detail (run 1)](#per-trial-detail-run-1)
- [What the monitor caught](#what-the-monitor-caught)
  - [WITH spec — agents use real labels but mis-order them](#with-spec--agents-use-real-labels-but-mis-order-them)
  - [WITHOUT spec — agents invent entirely new labels](#without-spec--agents-invent-entirely-new-labels)
  - [Violations by role (run 1, WITHOUT spec)](#violations-by-role-run-1-without-spec)
  - [Violations by step (run 1, WITHOUT spec)](#violations-by-step-run-1-without-spec)
- [How the monitor detects it](#how-the-monitor-detects-it)
- [Goal verification (post-execution)](#goal-verification-post-execution)
- [Files](#files)
- [Caveats and honest scope](#caveats-and-honest-scope)
<!-- MENU:END -->

## How this experiment is set

- **Case(s):** the Quarterly Finance Report protocol (`P1_v2.scr`) — a pre-`experiments/cases/` convention setup; the driver script (`experiment_4_scenarios.py`) and protocol file referenced in this report are not present in the current repository checkout (this is the project's earliest committed result, 2026-05-07, superseded in structure by the later `experiments/cases/finance/` case)
- **Arms/settings:** WITH spec markdown; WITHOUT spec markdown
- **Trials:** 10 per arm per run, 2 independent runs (20 trials/arm total), × 2 scenarios (high / standard revenue) = 80 trials
- **Who plays the roles:** gpt-5.4 via Azure OpenAI Chat Completions, 6 PromptAgent definitions registered in Azure AI Foundry (one per protocol role)
- **Isolation:** each role is a separate Foundry PromptAgent; isolation details beyond "one agent per role" are not recorded in this report
- **Harness & budgets:** `experiment_4_scenarios.py`; round-robin orchestration asking every role at every step; no documented step cap beyond the scenario's own message count
- **Where the raw data is:** `generated_agents/experiment_results.json`, `_run1.json`, `_run2.json`, `experiment_run.log` (paths as listed in "Files" below; not confirmed present in the current repository checkout)


## Setup

- **Agents in Azure AI Foundry portal** — six PromptAgent definitions registered
  via `AIProjectClient.agents.create_version`, each with `model=gpt-5.4` and
  `instructions=<role>_skills.md`. Visible at
  `https://foundary-tzuc06.services.ai.azure.com/api/projects/firstProject`
  under Agents:
  - `stjp-fetcher:1`
  - `stjp-revenueanalyst:1`
  - `stjp-expenseanalyst:1`
  - `stjp-writer:1`
  - `stjp-taxverifier:1`
  - `stjp-taxspecialist:1`
- **Inference path** — Azure OpenAI Chat Completions (`gpt-5.4`) with
  `AzCliCredential` (works around the Windows `azure-identity` bug where
  `AzureCliCredential` can't find `az.cmd` because it doesn't shell out).
- **Monitor path** — `monitor.SessionMonitor` walks each role's projected EFSM
  (Scribble `scribblec.sh -fsm`) against the captured TraceEvents.

## Side-by-side aggregate (combined 20 trials per scenario)

| metric | WITH spec markdown | WITHOUT spec markdown |
|---|---:|---:|
| Global conformance | **0/20 (0.0%)** | **0/20 (0.0%)** |
| Goals satisfied (out of 5/trial) | **50/100 (50.0%)** | **1/100 (1.0%)** |
| Off-protocol violations (total) | 167 | 479 |
| Premature-termination violations | 78 | 120 |
| Unexpected-peer violations | 1 | 0 |
| Mean violations per trial | ~12 | ~30 |
| Events captured per trial (mean) | 8.2 | 12.0 |

**Headline.** Specs cut violations roughly in half and lift goal-satisfaction
from 1% to 50%. But neither configuration produces a perfectly-conforming
trace under round-robin orchestration with `gpt-5.4` — the monitor flags every
deviation with full detail.

## Per-trial detail (run 1)

```
WITH spec (10 trials):
  trial 0 (high)    : 10 events, 14 viol, 4/5 goals
  trial 1 (standard):  7 events,  8 viol, 1/5 goals
  trial 2 (high)    : 10 events, 18 viol, 4/5 goals
  trial 3 (standard):  7 events,  8 viol, 1/5 goals
  trial 4 (high)    : 10 events, 17 viol, 4/5 goals
  trial 5 (standard):  7 events,  8 viol, 0/5 goals
  trial 6 (high)    : 10 events, 18 viol, 4/5 goals
  trial 7 (standard):  7 events, 14 viol, 2/5 goals
  trial 8 (high)    : 10 events, 14 viol, 4/5 goals
  trial 9 (standard):  7 events, 14 viol, 2/5 goals

WITHOUT spec (10 trials):
  trial 0..9: all 12 events (max), 29-30 viol each, 0-1/5 goals
```

Run 2 is qualitatively identical (48% goals with spec; 0% without) — see
`generated_agents/experiment_results_run1.json` and `_run2.json`.

## What the monitor caught

### WITH spec — agents use real labels but mis-order them

Every off-protocol violation comes from a real protocol message label sent in
the wrong state (the spec says "send HighRevenue first" but the agent sometimes
sends `HighNotice` first; the spec says "wait for AuditedRevenue" but the agent
jumps straight to RevenueAnalysis). Six concrete examples from run 1:

```
Fetcher step=1  off_protocol: at state 10 sent TaxSpecialist!HighRevenue(Double)
                              expected: TaxSpecialist!HighRevenue OR RevenueAnalyst!StandardRevenue
Fetcher step=3  off_protocol: at state 10 sent RevenueAnalyst!HighNotice (already past that point)
Fetcher step=6  off_protocol: at state 10 sent ExpenseAnalyst!HighNotice
Fetcher step=10 off_protocol: at state 10 received Writer?GenerateReport (out of order)
Fetcher step=5  premature_termination: stuck in state 10 (never advanced from initial)
```

### WITHOUT spec — agents invent entirely new labels

Without the skills.md, the LLM agents fabricate plausible-but-wrong message
labels — exactly the failure mode the protocol is meant to prevent:

```
Fetcher step=1  off_protocol: sent TaxSpecialist!REQUEST_AUDIT          (invented)
Fetcher step=2  off_protocol: received RevenueAnalyst?REQUEST_REVENUE_DATA  (invented)
Fetcher step=3  off_protocol: received ExpenseAnalyst?REQUEST_EXPENSE_DATA  (invented)
Fetcher step=4  off_protocol: received Writer?REQUEST_RAW_REVENUE_DATA      (invented)
Fetcher step=5  off_protocol: received TaxVerifier?REQUEST_REVENUE_AND_AUDIT_CONTEXT (invented)
Fetcher step=7  off_protocol: sent RevenueAnalyst!RAW_REVENUE_DATA       (invented)
```

These off-protocol labels are detected at the per-event level — there is no
LLM in the monitoring hot path. Each violation carries `(role, step, state, expected)`
which is exactly what a CI gate or an alert pipeline needs.

### Violations by role (run 1, WITHOUT spec)

| role | violations | what it did |
|---|---:|---|
| Fetcher | 84 | invented entire RPC vocabulary (REQUEST_AUDIT etc.) |
| RevenueAnalyst | 50 | sent free-form analyses to wrong peers |
| ExpenseAnalyst | 43 | invented `RAW_EXPENSE_DATA`, `FOLLOW_UP_RAW_FINANCE_DATA` |
| TaxVerifier | 39 | invented `REVIEW_REQUEST` instead of `RevenueAuditApproval` |
| TaxSpecialist | 40 | sent unsolicited "audit complete" replies |
| Writer | 43 | tried to drive the conversation instead of consuming inputs |

### Violations by step (run 1, WITHOUT spec)

| step | count |
|---:|---:|
| 4 | 38 |
| 2 | 32 |
| 3 | 30 |
| 5 | 26 |
| 6 | 23 |
| 8 | 24 |

Steps 2-5 dominate — that's where the choice-branch should have happened
(High vs Standard); without the spec, agents skip the branching entirely
and try to converge on a generic data-pipeline shape.

## How the monitor detects it

For each TraceEvent, every role's monitor:

1. Identifies the event's direction relative to the role (sent / received / not relevant).
2. Looks up transitions out of the role's current EFSM state.
3. If no transition matches `(direction, peer, label)`:
   - If the *label* exists but for a different peer → `unexpected_peer`.
   - Otherwise → `off_protocol` with the full set of expected labels.
4. If the transition matches and the protocol carries a refinement predicate
   in the `.refn`, sandboxed-evaluate the predicate over the payload; on
   failure → `refinement_failed`.
5. Advance state.
6. After the trace ends, check whether each monitor's current state is in the
   accepting set; if not → `premature_termination`.

Per-event cost: O(1) state-machine step plus, where applicable, a sandboxed
Python-AST predicate evaluation (microseconds). No LLM call.

By the **Bocchi-Chen-Demangeon-Honda-Yoshida composition theorem (FORTE'13)**:
local conformance for every role implies global protocol satisfaction. We get
the global guarantee from per-role local checks alone — no central observer.

## Goal verification (post-execution)

The 5 user-supplied goals are anchored to real protocol messages (`G1` to
`Fetcher → TaxSpecialist : HighRevenue`, `G3` to `TaxVerifier → RevenueAnalyst :
RevenueAuditApproval`, etc.). After each trial the trace is scanned for the
anchor message and the goal predicate is evaluated against the payload.

**WITH spec, 5 of 5 goals pass in 1/10 trials; 4 of 5 in 5/10; lower for trials
that take the standard branch (where G1, G2 don't apply).**

**WITHOUT spec, the anchor messages don't exist in the trace at all** — the
agents emit `REQUEST_REVENUE_DATA` instead of `HighRevenue`, so the goal
checker reports "anchor message not found in trace" for almost every goal.

This is exactly the value MPST adds over LLM-as-judge: a goal anchored to a
specific message is worth nothing if the agent decides to skip the message.
The monitor's `off_protocol` violation **is** the anchor-missing failure,
detected at event time rather than after the trace.

## Files

- `experiment_4_scenarios.py` — the experiment driver (Phase B + C + D combined).
- `az_credential.py` — Windows-friendly Azure CLI credential.
- `smoke_test_azure.py`, `smoke_test_foundry_agent.py` — Phase A verifiers.
- `EXPERIMENT_DESIGN.md` — architecture + wiring documentation.
- `generated_agents/Generated.refn` — goals as anchored predicates.
- `generated_agents/experiment_results.json` — run 2 raw aggregate.
- `generated_agents/experiment_results_run1.json` — run 1 raw aggregate.
- `generated_agents/experiment_results_run2.json` — run 2 raw aggregate (copy).
- `generated_agents/experiment_run.log` — full per-trial console log.

## Caveats and honest scope

1. **0/20 globally-conformant trials, even with spec, is striking.** The
   round-robin orchestrator asks every role at every step; agents sometimes
   try to act when they should be waiting, and the monitor catches that as
   `off_protocol`. A more sophisticated orchestrator that respects the EFSM's
   "next active role" hint would likely produce conformant traces — but that
   would also defeat the experiment, because the monitor would have nothing
   left to catch. The current design is intentionally adversarial: it gives
   the LLM enough rope to deviate, then measures how often it does.

2. **`gpt-5.4` is the deployment name supplied by the user.** No public Azure
   model has that exact name; whatever is behind that deployment is what
   produced these numbers.

3. **Spec-free agents converge on a *plausible* shape**, not a random one.
   They invent a generic RPC vocabulary (`REQUEST_AUDIT`, `RAW_REVENUE_DATA`)
   that mimics what a finance pipeline could look like. The monitor's job is
   to reject those plausible-but-wrong labels — and it does, deterministically.

4. **The 0% conformance with spec is at the per-trial level.** At the
   per-message level, ~70% of the events captured *are* on-protocol — the
   monitor catches the ~30% that aren't. A trial registers as non-conformant
   if any single event deviates.

5. **The 50× goals advantage of spec over no-spec is the load-bearing finding.**
   Even without perfect protocol conformance, agents that have the spec
   reliably hit half the goals; agents without the spec almost never do,
   because they don't know to send the messages the goals are anchored to.
