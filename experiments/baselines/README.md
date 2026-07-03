# experiments/baselines/

Per-framework runners for the multi-baseline benchmark driven by
`experiments/scripts/case_runner.py`. Each runner drives one scenario — one
row ("arm") in the comparison table — for a given case.

`registry.py` is the single source of truth for which arms run and in what
order; this README mirrors it.

## The 8-arm matrix

| key | name | runner | agent runtime | protocol info given to agents |
|---|---|---|---|---|
| `bare` | WITHOUT-skills | `FoundryRunner` | Azure AI Foundry Agent Service | none — intent + roles + goals only |
| `maf_native` | WITHOUT-maf-native | `MAFNativeRunner` | MAF Agent + Azure OpenAI direct | none |
| `maf_foundry` | WITHOUT-maf-foundry | `MAFFoundryRunner` | MAF Agent + Foundry chat client | none |
| `maf_groupchat` | WITHOUT-maf-groupchat | `MAFGroupChatRunner` | MAF GroupChat (LLM speaker selection) | none |
| `maf_groupchat_unsafe` | WITHOUT-maf-gc-unsafe | `MAFGroupChatRunner` | MAF GroupChat | LLM-drafted **unsafe** global type (Scribble rejected it) — observational, no monitor verdicts |
| `maf_groupchat_llmvalid` | WITHOUT-maf-gc-llmvalid | `MAFGroupChatRunner` | MAF GroupChat | LLM-drafted **valid** global type — raw text, no projection |
| `spec_llmvalid` | WITH-spec-llmvalid | `FoundryRunner` | Azure AI Foundry Agent Service | projected per-role local type — verbose EFSM markdown + refinement guards |
| `min_llmvalid` | WITH-min-llmvalid | `FoundryRunner` | Azure AI Foundry Agent Service | projected per-role local type — minimal SEND/RECV table + guards |

The variable that changes left-to-right is the **protocol information** the
agents receive: none → validated global type as text → projected per-role
local type. Everything else (intent, goals, role descriptions, output
schema) is held constant — see `docs/archive/EXPERIMENT_DESIGN_v2.md`.

### What the matrix isolates (pairwise)

- **arms 1–4 vs 6** — does giving agents a *validated* global type beat
  intent-only?
- **arm 5 vs 6** — does Scribble *validation* matter? (an LLM-drafted
  protocol that Scribble **rejected** vs one it **accepted**)
- **arm 6 vs 7–8** — does *projection + the monitor* earn its keep on top of
  a validated global type?

## LLM-drafted-protocol dependency

Five arms — `maf_groupchat_unsafe`, `maf_groupchat_llmvalid`,
`spec_llmvalid`, `min_llmvalid` — consume an **LLM-drafted** protocol at
`cases/<case>/protocols/llm_drafts/{valid,unsafe}/v1.scr` (+ re-anchored
`goals.yaml`). These are produced per-case by:

```
python experiments/scripts/draft_llm_protocols.py <case>
python experiments/scripts/re_anchor_goals.py <case> valid
python experiments/scripts/re_anchor_goals.py <case> unsafe
```

Their `registry.py` factories **fail-fast** at `setup()` with a clear
remediation message if those files are missing. The intent-only arms
(`bare`, `maf_native`, `maf_foundry`, `maf_groupchat`) need no such setup.

## Orchestration — a deliberate variable, not a constant

Two orchestration styles are in the matrix on purpose:

- **Recipient-addressed dispatch** (`bare`, `maf_native`, `maf_foundry`):
  each agent emits a JSON action with `send_to`; the next speaker is whoever
  was addressed. The agents decide who talks next; the loop just enforces it.
- **MAF GroupChat** (`maf_groupchat*`): an LLM orchestrator
  (`GroupChatBuilder`) selects the next speaker — emergent orchestration with
  no addressed-recipient channel.

So "agent runtime" and "orchestration pattern" both vary across the matrix;
read pairwise comparisons (above) accordingly rather than treating any one
arm as the sole control.

## Adding a new baseline

1. Implement a `BaselineRunner` subclass (see `base.py`) in a new module.
2. Import it in `registry.py` and add a `(scenario_key, scenario_name,
   factory)` tuple to `SCENARIOS` (order = display order).
3. Done — retry-to-success, goal checking, JSONL emission, Set A/Set B
   metrics, and summary aggregation in `case_runner.py` are
   framework-agnostic and apply to any new runner automatically.

## Files

- `__init__.py` — re-exports `SCENARIOS`, `make_runner`, `BaselineRunner`, `AttemptResult`
- `base.py` — `BaselineRunner` ABC + `AttemptResult` dataclass
- `registry.py` — the `SCENARIOS` registry (8-arm matrix) + `make_runner(case, key)`
- `instructions.py` — prompt builders: `build_bare_instructions`,
  `build_global_spec_instructions`, `build_spec_instructions`,
  `build_spec_minimal_instructions`
- `_foundry_client.py` — lazy shared `AgentsClient` singleton
- `foundry_runner.py` — `FoundryRunner` (drives `bare`, `spec_llmvalid`, `min_llmvalid`)
- `_maf_common.py` — `MAFRunnerBase` (shared loop logic for the MAF arms)
- `maf_native.py` — `MAFNativeRunner` (MAF Agent + Azure OpenAI direct)
- `maf_foundry.py` — `MAFFoundryRunner` (MAF Agent + Foundry chat client)
- `maf_groupchat.py` — `MAFGroupChatRunner` (drives `maf_groupchat`,
  `maf_groupchat_unsafe`, `maf_groupchat_llmvalid` — parameterised by the
  instructions builder + optional protocol override)

The runners import the STJP library as `stjp_core.<package>.<module>` (the
monitor, projection, refinements, agent generation).

## MAF SDK gotchas

For non-obvious MAF v1.2.2 API choices (why `OpenAIChatCompletionClient` not
`OpenAIChatClient`; why `FoundryChatClient.as_agent()` not `FoundryAgent()`;
custom usage-key normalisation), see the comments at the top of each MAF
runner module. A MAF `400` with empty traces is usually a stale `az` CLI
token — run `az account show`, re-`az login` if it's the wrong tenant.
