# experiments/baselines/

Per-framework runners for the multi-baseline benchmark driven by
`experiments/scripts/case_runner.py`. Each runner drives one scenario — one
row ("arm") in the comparison table — for a given case.

`registry.py` is the single source of truth for which arms run and in what
order; this README mirrors it.

## Menu

- [The arm matrix (15 arms)](#the-arm-matrix-15-arms)
- [LLM-drafted-protocol dependency](#llm-drafted-protocol-dependency)
- [Orchestration — a deliberate variable, not a constant](#orchestration--a-deliberate-variable-not-a-constant)
- [Adding a new baseline](#adding-a-new-baseline)
- [Files](#files)
- [MAF SDK gotchas](#maf-sdk-gotchas)

## The arm matrix (15 arms)

An *arm* is one configuration being compared — like the treatment and control
groups of a medical trial. In registry order:

| key | name | runner | agent runtime | protocol info given to agents |
|---|---|---|---|---|
| `bare` | WITHOUT-skills | `FoundryRunner` | Azure AI Foundry Agent Service | none — intent + roles + goals only |
| `maf_native` | WITHOUT-maf-native | `MAFNativeRunner` | MAF Agent + Azure OpenAI direct | none |
| `maf_foundry` | WITHOUT-maf-foundry | `MAFFoundryRunner` | MAF Agent + Foundry chat client | none |
| `maf_groupchat` | WITHOUT-maf-groupchat | `MAFGroupChatRunner` | MAF GroupChat (LLM speaker selection) | none |
| `maf_groupchat_unsafe` | WITHOUT-maf-gc-unsafe | `MAFGroupChatRunner` | MAF GroupChat | LLM-drafted **unsafe** global type (Scribble rejected it) — observational, no monitor verdicts |
| `maf_groupchat_llmvalid` | WITHOUT-maf-gc-llmvalid | `MAFGroupChatRunner` | MAF GroupChat | LLM-drafted **valid** global type — raw text, no projection |
| `unchecked_skills` | WITHOUT-unchecked-skills | `FoundryRunner` | Azure AI Foundry Agent Service | hand-written per-role skills from `cases/<case>/unchecked_skills/`, never formally checked — the deadlock demo's no-checker arm |
| `global_decentralized` | WITH-global-decentralized | `FoundryRunner` | Azure AI Foundry Agent Service | LLM-drafted **valid** global type as text, on the decentralized round-robin runner (no LLM orchestrator) |
| `spec_llmvalid` | WITH-spec-llmvalid | `FoundryRunner` | Azure AI Foundry Agent Service | projected per-role local type — verbose EFSM markdown + refinement guards |
| `min_llmvalid` | WITH-min-llmvalid | `FoundryRunner` | Azure AI Foundry Agent Service | projected per-role local type — minimal SEND/RECV table + guards |
| `spec_llmvalid_gate` | WITH-spec-llmvalid-GATE | `FoundryRunner` | Azure AI Foundry Agent Service | verbose projected local type + **enforcement gate** (off-contract sends rejected before delivery, role re-prompted) |
| `min_llmvalid_gate` | WITH-min-llmvalid-GATE | `FoundryRunner` | Azure AI Foundry Agent Service | minimal projected local type + enforcement gate |
| `min_llmvalid_gate_nohint` | WITH-min-GATE-NOHINT | `FoundryRunner` | Azure AI Foundry Agent Service | same as `min_llmvalid_gate` but without the per-turn liveness nudge — isolates pure enforcement from per-turn guidance |
| `min_llmvalid_gate_lastrecv` | WITH-min-GATE-LASTRECV | `FoundryRunner` | Azure AI Foundry Agent Service | same prompt + gate, scheduled by the protocol-free "ask whoever just received a message" heuristic — the cheap-scheduling control |
| `min_llmvalid_sched` | WITH-min-llmvalid-SCHED | `FoundryRunner` | Azure AI Foundry Agent Service | minimal projected local type + gate + **EFSM enabled-sender scheduler** — the full STJP execution plane |

The variable that changes top-to-bottom is the **protocol information** the
agents receive, and then **how strongly the runtime uses it**: none →
unchecked skills → validated global type as text → projected per-role local
type → + enforcement gate → + protocol-derived scheduler. Everything else
(intent, goals, role descriptions, output schema) is held constant — see
`docs/archive/EXPERIMENT_DESIGN_v2.md` and, for the gate/scheduler arms,
`docs/archive/EXPERIMENT_DESIGN_V3_EXECUTION.md`.

### What the matrix isolates (pairwise)

Each comparison changes exactly one thing, so the difference in outcome can
be attributed to that one thing:

- **intent-only arms vs `maf_groupchat_llmvalid`** — does giving agents a
  *validated* global type beat intent-only?
- **`maf_groupchat_unsafe` vs `maf_groupchat_llmvalid`** — does Scribble
  *validation* matter? (an LLM-drafted protocol Scribble **rejected** vs one
  it **accepted**)
- **`maf_groupchat_llmvalid` vs `spec_llmvalid`/`min_llmvalid`** — does
  *projection + the monitor* earn its keep on top of a validated global type?
- **`global_decentralized` vs `spec_llmvalid`** — global text vs projected
  local contract on the *same* decentralized runner (removes the
  orchestration confound; see `docs/WHY_B_MATCHES_C_ANALYSIS.md`).
- **`min_llmvalid` vs `min_llmvalid_gate`** — identical prompts; only the
  gate differs. Isolates enforcement.
- **`min_llmvalid_gate` vs `min_llmvalid_gate_nohint`** — identical prompts
  and gate; only the per-turn hint differs. Isolates guidance.
- **`min_llmvalid_gate_lastrecv` vs `min_llmvalid_sched`** — identical
  prompts and gate; only the scheduler differs. Isolates what the
  protocol-derived scheduler adds beyond a trivial heuristic (see
  `docs/BENCHMARK_FAIRNESS_REVIEW.md`, Problem 4).

## LLM-drafted-protocol dependency

Ten arms — `maf_groupchat_unsafe`, `maf_groupchat_llmvalid`,
`global_decentralized`, `spec_llmvalid`, `min_llmvalid`,
`spec_llmvalid_gate`, `min_llmvalid_gate`, `min_llmvalid_gate_nohint`,
`min_llmvalid_gate_lastrecv`, `min_llmvalid_sched` — consume an
**LLM-drafted** protocol at
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
- `registry.py` — the `SCENARIOS` registry (the 15-arm matrix) + `make_runner(case, key)`
- `instructions.py` — prompt builders: `build_bare_instructions`,
  `build_global_spec_instructions`, `build_spec_instructions`,
  `build_spec_minimal_instructions`, `build_unchecked_skills_instructions`
- `_foundry_client.py` — lazy shared `AgentsClient` singleton
- `foundry_runner.py` — `FoundryRunner` (drives `bare`, `unchecked_skills`,
  `global_decentralized`, and the whole `spec`/`min` family, including the
  gate and scheduler variants)
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
