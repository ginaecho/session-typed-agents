# Azure AI Foundry — deployment reference (project `firstProject`)

Verified 2026-07-06 via `az cognitiveservices account deployment list`.

## Account / project

| Item | Value |
|---|---|
| AI Services account | `foundary-tzuc06` (kind `AIServices`) |
| Resource group | `rg-tzuc06` |
| Tenant | `16b3c013-d300-468d-ac64-7eda0820b6d3` |
| Account owner | tzuchunchen@microsoft.com |
| Project endpoint | `https://foundary-tzuc06.services.ai.azure.com/api/projects/firstProject` |
| OpenAI endpoint | `https://foundary-tzuc06.openai.azure.com/openai/v1` |

## Model deployments

| Deployment name | Model | Version | SKU | Notes |
|---|---|---|---|---|
| `gpt-4o` | gpt-4o | 2024-11-20 | GlobalStandard | **cheap model** for A/B trials (100k TPM / 600 RPM); lifecycle: deprecating, retires 2026-10-01 |
| `gpt-5.1-chat` | gpt-chat-latest | 2026-05-05 | GlobalStandard | |
| `gpt-5.4` | gpt-5.4 | 2026-03-05 | GlobalStandard | default in `.env` |
| `gpt-5.4-2` | gpt-5.4 | 2026-03-05 | GlobalStandard | |

## How STJP selects the deployment

- `.env` (`stjp_core/.env`) keys: `AZURE_OPENAI_DEPLOYMENT`,
  `AZURE_AI_MODEL_DEPLOYMENT_NAME` (both currently `gpt-5.4`).
- To run on the **cheap** model without editing `.env`, set the deployment env
  var for that process, e.g. (PowerShell):

  ```powershell
  $env:AZURE_AI_MODEL_DEPLOYMENT_NAME = "gpt-4o"
  $env:AZURE_OPENAI_DEPLOYMENT = "gpt-4o"
  ```

- All Foundry calls route through the Agent Service (hosted agents) so runs are
  visible in the portal under Agents -> Threads -> Tracing
  (see `docs/reference/FOUNDRY_VISIBILITY.md`).

## Auth

`az login` as tzuchunchen@microsoft.com; ensure the active tenant is
`16b3c013-...` (the credential wrapper pins `STJP_AZURE_TENANT_ID` from `.env`).
