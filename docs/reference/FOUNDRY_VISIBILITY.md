# Making agents / threads / traces visible in Azure AI Foundry portal

The Foundry portal has **three independent visibility surfaces**. Each has its
own requirement; missing any one means that surface stays empty even though
the underlying data is in the project.

| Portal surface | Where in portal | What controls visibility |
|---|---|---|
| **Agents** | "Create and debug your agents" → My agents | `AgentsClient.create_agent()` with `model=` pointing to a deployment registered in the project |
| **Threads** | same page → My threads tab | A **successful** run on a registered agent. Failed runs DO NOT make the thread visible. |
| **Tracing** | Tracing tab (left nav, project scope) | OpenTelemetry spans exported to the project's connected Application Insights resource |

Below: the exact code for each, all connected in this repo.

## Deep links for this project (verified 2026-06-11)

Project `firstProject` on resource `foundary-tzuc06` (rg `rg-tzuc06`). The
`wsid` query parameter is the full ARM id:

```
wsid=/subscriptions/ef669702-542a-4abc-95a6-edf9f972cd3c/resourceGroups/rg-tzuc06/providers/Microsoft.CognitiveServices/accounts/foundary-tzuc06/projects/firstProject
```

- Agents list: `https://ai.azure.com/resource/agentsList?wsid=<wsid>`
- Tracing:     `https://ai.azure.com/resource/tracing?wsid=<wsid>`

The Foundry-stack arms (`bare`/`spec_llmvalid`/`min_llmvalid`) appear under
Agents/Threads; the MAF (Microsoft Agent Framework) arms bypass Agent Service and appear **only** in
Tracing (OTel spans, `service.name = stjp-case-runner`, full message content
captured via `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true`).

---

## 1. Agents — visible in My agents

```python
from azure.ai.agents import AgentsClient
from az_credential import AzCliCredential
import os

client = AgentsClient(
    endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"],
    credential=AzCliCredential(),
)
agent = client.create_agent(
    model="gpt-4o",                    # MUST be a project deployment (Models + endpoints tab)
    name="stjp-fetcher",
    description="...",                 # appears in the agent list
    instructions="You are ...",        # appears in the agent's instructions panel
)
print(agent.id)                        # asst_xxxxx
```

Reference impl: `register_agent_service.py`. The agents must use a model that
shows up under **Project → Models + endpoints**, not just any OpenAI deployment.
This project's deployments are listed by `probe_foundry_setup.py`.

## 2. Threads — visible in My threads (after successful runs)

```python
thread = client.threads.create(metadata={"role": "Fetcher"})
client.messages.create(thread_id=thread.id, role="user", content="...")
run = client.runs.create_and_process(thread_id=thread.id, agent_id=agent.id)
# run.status MUST be COMPLETED for the thread to appear in My threads
assert str(run.status).split(".")[-1].lower() == "completed"
```

Gotchas observed in this project:

- **Failed runs hide the thread.** If `run.status` is `failed` or `incomplete`,
  the thread is API-listable but does NOT appear in the portal "My threads"
  tab. Don't trust the absence of a thread in the UI as proof it doesn't
  exist; check via `client.threads.list()`.
- **Filters can hide threads.** Click the `Filter` button at top right and
  clear any agent / date filters.
- **Refresh isn't automatic.** Click `Refresh` after running.
- **Initial sync delay can be 30-60s.** App Insights ingestion is best-effort.

Reference impl: `experiment_via_agent_service.py` (each trial creates 6 threads
— one per role — and runs them to completion).

## 3. Traces — visible in Tracing tab

This is the one that requires explicit setup. The Foundry Agent Service does
NOT auto-emit OpenTelemetry spans to the project's App Insights — your code
must connect OpenTelemetry → App Insights manually.

```python
import os
from azure.ai.projects import AIProjectClient
from azure.monitor.opentelemetry import configure_azure_monitor
from az_credential import AzCliCredential

# Required env var so genai prompts/responses are recorded in spans
os.environ["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] = "true"
os.environ["AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED"] = "true"

# Pull the project's connected App Insights string
project = AIProjectClient(
    endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"],
    credential=AzCliCredential(),
)
conn_str = project.telemetry.get_application_insights_connection_string()

# Connect OTel exporter
configure_azure_monitor(
    connection_string=conn_str,
    resource_attributes={"service.name": "stjp-experiment"},
)

# Tell azure-core to use OTel for SDK calls
from azure.core.settings import settings
from azure.core.tracing.ext.opentelemetry_span import OpenTelemetrySpan
settings.tracing_implementation = OpenTelemetrySpan

# Instrument OpenAI SDK so chat/agent calls emit gen_ai.* spans
from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor
OpenAIInstrumentor().instrument()
```

Reference impl: `foundry_tracing.py:enable_foundry_tracing()` — call once at
startup. It is idempotent and safely no-ops if `AZURE_AI_PROJECT_ENDPOINT` is
unset.

After enabling, look for the line `[trace] tracing enabled -> IngestionEndpoint=...`
in stdout — that confirms the exporter is configured.

### Required packages

```
pip install azure-monitor-opentelemetry opentelemetry-instrumentation-openai-v2
```

### Required project resource

The project must have an **Application Insights connection** under Project
Settings → Connections. Verify with:

```python
for c in project.connections.list():
    print(c.name, c.type)
# Should include: ConnectionType.APPLICATION_INSIGHTS
```

If it doesn't, add an App Insights connection in the portal (Project Settings
→ Connections → + → Application Insights).

## 4. Connected Agents — visible in agent detail's "Connected agents" panel

Optional handoff orchestration: each agent can call other agents as tools.

```python
from azure.ai.agents.models import ConnectedAgentTool

tool = ConnectedAgentTool(
    id=peer_agent.id,
    name="taxspecialist",                 # tool name the model sees
    description="Send revenue figures for audit ...",
)
client.update_agent(agent_id=parent.id, tools=tool.definitions)
```

Reference impl: `wire_connected_agents.py`. Note: when this is set, the agent
will sometimes try to invoke tools instead of returning JSON. If your
orchestration is Python-driven (as this project's experiment is), keep
`Connected agents` configured for portal visibility but tell the agent in its
instructions NOT to call tools (see `restore_strict_instructions.py`).

---

## One-shot setup

A single script that connects everything for a fresh project:

```bash
# 1. Set up agents in the Agent Service (visible in My agents)
python register_agent_service.py

# 2. Connect Connected Agents per the protocol topology
python wire_connected_agents.py

# 3. Run an experiment with tracing enabled (creates threads + spans)
python experiment_via_agent_service.py 2

# 4. Verify everything via API
python diagnose_threads_fast.py
python probe_foundry_setup.py
```

After step 3 finishes, check the portal:

- **My agents** shows 12 agents (6 spec + 6 bare).
- **My threads** shows 24 threads (after Refresh + clear Filter).
- **Tracing** shows ~50+ spans (after Refresh; ~30-60s ingestion delay).

## Verifying without the portal

If the portal is misbehaving, the API is the source of truth. Use:

```bash
python dump_conversations.py        # writes every thread to readable .md
python diagnose_threads_fast.py     # lists agents + threads + runs
python probe_foundry_setup.py       # lists deployments + connections
```

Outputs land under `generated_agents/conversations/` and the project's stdout.
