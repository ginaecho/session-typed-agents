# stjp_core / AI_ST_verf — project policy

## Package layout

`stjp_core/` is a Python package: `compiler/`, `authoring/`, `generation/`,
`monitor/`, `evaluation/`, `foundry/`, `apps/`, `tests/` (+ `config.py` at the
top). Imports are `from stjp_core.<package>.<module> import …`. See `README.md`
for what each package holds.

**As of 2026-05-29 this package is library-only.** Protocols, skills, and run
outputs all live under `experiments/cases/<case>/` — the legacy `protocols/`,
`skills/`, and `version_history.json` were deleted, and `config.py` no longer
exports `PROTOCOLS_DIR` / `SKILLS_DIR` / `VERSION_HISTORY_FILE`. Authoring
flows (`apps/orchestrator.py` + `authoring/evolution_loop.py`) now take a
`case_dir` parameter and write into that case's `protocols/` and `skills/`.

## Foundry portal visibility (3 surfaces)

For details + code: `../docs/reference/FOUNDRY_VISIBILITY.md`. The three surfaces are independent:

1. **My agents** — `AgentsClient.create_agent(model=<project-deployed-name>)`
2. **My threads** — at least one COMPLETED run per thread; FAILED runs do NOT
   make threads visible. Click Refresh + clear Filter in the portal.
3. **Tracing** — call `enable_foundry_tracing()` once at startup. Requires
   Application Insights connection on the project.

`experiments/scripts/case_runner.py` calls `enable_foundry_tracing()` once
at module import (line 50-51) and the `foundry/foundry_client.py` utility
client does the same — every script that uses either produces portal-visible
traces by default.

## Foundry-first: all LLM calls go through Azure AI Foundry Agent Service

**Rule:** every script in this directory that hits an LLM routes the call
through the Foundry Agent Service so the interaction is visible in the portal.

**Why:** auditability. The user wants to see *every* agent-system interaction
in the Foundry portal under Agents → Threads. Direct chat-completion calls
are invisible there.

### How it's wired

- `foundry/foundry_client.py` `FoundryLLMClient` — single-shot calls go through
  `stjp-utility` agent (auto-created on first use). Each call creates one
  thread with `metadata.caller="FoundryLLMClient.<method>"`.
- `foundry/llm_client.py` `LLMClient` — public name; resolves to
  `FoundryLLMClient` by default. Override via env var `STJP_LLM_BACKEND=chat`
  for the legacy direct path (cost/latency-sensitive batch runs).
- `foundry/session_helpers.py` — three small helpers (build_view,
  parse_action, latest_assistant_text) imported by the experiments harness
  to drive a per-role turn. Replaced the older
  `experiment_via_agent_service.py` driver (removed 2026-05-29).
- `apps/stjp_dual_demo.py` — live 2-arm visual demo. Picks any 2 of the
  8 benchmark arms and runs them through `experiments/scripts/case_runner.py`
  with output mirrored to fixed filenames that `stjp_comparison.html` polls.
- `apps/orchestrator.py` — LLM-powered protocol-authoring CLI. Generates
  protocols + skills into `experiments/cases/<case_id>/{protocols,skills}/`;
  invoke with `--case <case_id>`. The legacy `stjp_core/protocols/` and
  `stjp_core/skills/` dirs were retired 2026-05-29.
- `../experiments/scripts/case_runner.py` — case-agnostic benchmark runner;
  reuses this folder as a library, importing `stjp_core.<package>.<module>`.
  **All protocols + outputs live under `experiments/cases/<case>/`**; this
  package is library code only.

### Adding new LLM-using code

```python
from stjp_core.foundry.llm_client import LLMClient  # resolves to FoundryLLMClient by default
client = LLMClient()
text = client.generate(system_prompt, user_prompt)
# ^ this call now appears in Foundry portal under Agents -> stjp-utility -> Threads
```

For multi-agent protocols (one agent per role), follow the pattern in
`experiments/baselines/foundry_runner.py`:
- One registered Agent Service agent per role
  (`stjp-<case_id>-<scenario_key>-<role.lower()>`).
- One thread per `(role, attempt)` (fresh threads each retry).
- `AgentsClient.runs.create_and_process(thread_id, agent_id)` per turn.
- `SessionMonitor` walks the captured TraceEvents independently of the
  Agent Service for protocol-conformance verdicts.

The three turn-loop primitives (`build_view`, `parse_action`,
`latest_assistant_text`) live in `foundry/session_helpers.py` and are
imported by `foundry_runner.py` as `ex`.

### Cleanup

- `python -m stjp_core.foundry.foundry_client --gc-utility-threads` (from the
  repo root) — deletes utility-agent threads older than 24h.
- Delete agents manually via portal or
  `AgentsClient.delete_agent(agent_id)` if you want to start fresh.

### Env vars (in `.env`)

| key | purpose |
|---|---|
| `AZURE_AI_PROJECT_ENDPOINT` | required for default Foundry path |
| `AZURE_OPENAI_DEPLOYMENT` | model deployment name (gpt-5.4) |
| `AZURE_OPENAI_ENDPOINT` | required only for `STJP_LLM_BACKEND=chat` |
| `STJP_LLM_BACKEND` | `foundry` (default) or `chat` |

### Auth

`az login` once. `foundry/az_credential.py`'s `AzCliCredential` is used
everywhere because the official `azure-identity.AzureCliCredential` can't find
`az.cmd` on Windows without `shell=True`.
