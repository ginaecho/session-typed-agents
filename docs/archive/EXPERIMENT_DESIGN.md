# 4-scenario experiment: live MS Agent Framework + Azure AI Foundry

End-to-end experiment that drives 6 LLM agents (one per protocol role) and measures
how often the runtime monitor catches deviations from the projected MPST local
type. Compares **spec-driven** (skills.md given to each agent) vs. **spec-free**
(only intent + goals given) under identical orchestration.

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [Wiring](#wiring)
- [What plays the user's role](#what-plays-the-users-role)
- [The 4 scenarios](#the-4-scenarios)
  - [Scenario 1 -- generate skills/agents markdown](#scenario-1----generate-skillsagents-markdown)
  - [Scenario 2 -- single illustrative trial WITH spec markdown](#scenario-2----single-illustrative-trial-with-spec-markdown)
  - [Scenario 3 -- 10 trials WITH spec markdown](#scenario-3----10-trials-with-spec-markdown)
  - [Scenario 4 -- 10 trials WITHOUT spec markdown](#scenario-4----10-trials-without-spec-markdown)
- [Coordinator (the agent driver)](#coordinator-the-agent-driver)
- [What the monitor catches](#what-the-monitor-catches)
- [Why this is the right experiment](#why-this-is-the-right-experiment)
- [Files written](#files-written)
<!-- MENU:END -->

## Wiring

```
.env
  ├─ AZURE_OPENAI_ENDPOINT         (https://foundary-tzuc06.cognitiveservices.azure.com/)
  ├─ AZURE_OPENAI_DEPLOYMENT       (gpt-5.4)
  ├─ AZURE_OPENAI_API_VERSION      (2024-12-01-preview)
  └─ AZURE_AI_PROJECT_ENDPOINT     (https://foundary-tzuc06.services.ai.azure.com/api/projects/firstProject)

Auth:
  az login        ->     az_credential.AzCliCredential       ->     Bearer token
                         (shells out to `az account get-access-token`,
                          works around the Windows azure-identity issue
                          where AzureCliCredential can't find az.cmd
                          when not invoked via shell=True)

Inference:
  Azure OpenAI Chat Completions
    azure_endpoint=AZURE_OPENAI_ENDPOINT
    azure_ad_token_provider=make_token_provider(...)
    api_version="2024-12-01-preview"
    model="gpt-5.4"

Foundry portal visibility:
  AIProjectClient(endpoint=AZURE_AI_PROJECT_ENDPOINT, credential=AzCliCredential())
    .agents.create_version(
      agent_name="stjp-<role>",
      definition=PromptAgentDefinition(model="gpt-5.4", instructions=<skills.md>),
      description="AI_ST_verf <role> for QuarterlyFinanceReport")
  -- registers a PromptAgent in the Foundry project; visible in portal.
  -- inference still uses the chat-completions client (one round-trip per turn).
```

## What plays the user's role

`USER_INTENT` and `USER_GOALS` (5 anchored goals: G1..G5) are baked into
`experiment_4_scenarios.py`. Claude Code role-plays the user supplying:

1. The natural-language intent describing the Quarterly Finance Report pipeline.
2. Five math-checkable goals, each anchored to a real protocol message
   (sender / receiver / label tuple). These match the `Goal` schema defined
   by `goal_elicitor.py`.

The goal_elicitor pipeline converts goals to a `.refn` (anchored predicate)
file consumed by the SessionMonitor.

## The 4 scenarios

### Scenario 1 -- generate skills/agents markdown
Confirms skills.md present for all 6 roles. Writes `goals -> .refn` predicates
at `generated_agents/Generated.refn`. No LLM calls.

### Scenario 2 -- single illustrative trial WITH spec markdown
Per role:
- Builds system prompt = `intent + goals + skills.md + JSON output rules`.
- Registers a PromptAgent in Foundry (visible in portal under Agents).
- Coordinator drives the protocol round-robin, parsing JSON actions, emitting
  TraceEvents until the protocol terminates (Writer -> Fetcher : GenerateReport)
  or MAX_STEPS=12 elapses.

### Scenario 3 -- 10 trials WITH spec markdown
Same prompts as scenario 2. For each trial:
- branch hint alternates high/standard
- session monitor runs against the projected EFSMs of P1_v2.scr
- aggregated: global conformance, goals-pass rate, violations by type/role/step

### Scenario 4 -- 10 trials WITHOUT spec markdown
System prompts strip the skills.md block entirely; agents get only the intent
and goals. Same orchestration. Same monitor. Side-by-side comparison.

## Coordinator (the agent driver)

Round-robin across the 6 roles:

```
for step in 0..MAX_STEPS:
  actor = next role from queue
  view = filtered session history (only messages this role sent or received)
  reply = chat_client.chat(system_prompt[actor], view)
  action = json.parse(reply)  # {"send_to":..., "label":..., "payload":...}
  if action.label == WAIT or action.send_to is None:
    continue
  emit TraceEvent(actor -> action.send_to : action.label(action.payload))
  if action.label == "GenerateReport":
    break  # protocol terminal
```

The agent only ever sees its own past messages, never the global history.
This is the intended MPST property: **local conformance only**. The session
monitor is the only thing that has the global view, and even that is a per-role
EFSM walk, not a central observer (FORTE'13).

## What the monitor catches

For each TraceEvent, each role's monitor (one per role) checks:

| Violation class                | What triggers it                                      |
|--------------------------------|-------------------------------------------------------|
| `off_protocol`                 | label not in current state's transitions             |
| `unexpected_peer`              | label correct but wrong peer                          |
| `refinement_failed`            | `.refn` predicate evaluates false on payload         |
| `premature_termination`        | role ended in non-accepting state                     |

Cost per check: O(1) state-machine step + sandboxed predicate eval. Three
orders of magnitude cheaper than LLM-as-judge per check; no LLM in the hot path.

## Why this is the right experiment

The interesting result is **the contrast** between spec-driven and spec-free
runs under an identical orchestrator and identical monitor. If the spec is
load-bearing, conformance and goals-pass rate are higher in scenario 3 than
scenario 4. If the LLM "just figures it out from the goals," the difference
should be small. The session monitor's per-event detection is the audit trail
for either claim.

## Files written

- `generated_agents/Generated.refn`     -- goals as anchored predicates
- `generated_agents/experiment_results.json`  -- full aggregated stats
- `generated_agents/experiment_run.log`       -- per-trial console log
- 6 PromptAgent definitions in Foundry (visible at the portal under Agents,
  named `stjp-fetcher`, `stjp-revenueanalyst`, ...)
