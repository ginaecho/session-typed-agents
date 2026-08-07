# experiments/baselines/

Per-framework runners for the multi-baseline benchmark driven by
`experiments/scripts/case_runner.py`. Each runner drives one scenario — one
row ("arm") in the comparison table — for a given case.

`registry.py` is the single source of truth for which arms run and in what
order; this README mirrors it.

## Menu

- [The arm matrix (10 core arms)](#the-arm-matrix-10-core-arms)
- [LLM-drafted-protocol dependency](#llm-drafted-protocol-dependency)
- [Orchestration — a deliberate variable, not a constant](#orchestration--a-deliberate-variable-not-a-constant)
- [Adding a new baseline](#adding-a-new-baseline)
- [Files](#files)
- [MAF SDK gotchas](#maf-sdk-gotchas)

## The arm matrix (10 core arms)

An *arm* is one configuration being compared — like the treatment and control
groups of a medical trial. In registry order:

| key | name | runner | agent runtime | protocol info given to agents |
|---|---|---|---|---|
| `skills` | WITHOUT-skills | `FoundryRunner` | round-robin | real published per-role skills; no protocol |
| `maf_skills` | WITHOUT-maf-skills | `MAFGroupChatRunner` | MAF LLM orchestrator | same skills; no protocol |
| `globalvalid` | WITH-globalvalid | `FoundryRunner` | round-robin | whole validated protocol as text |
| `maf_globalvalid` | WITHOUT-maf-globalvalid | `MAFGroupChatRunner` | MAF LLM orchestrator | same whole protocol text |
| `localvalid` | WITH-localvalid | `FoundryRunner` | round-robin | projected local contract; observe-only |
| `maf_localvalid` | WITHOUT-maf-localvalid-ORCH | `MAFGroupChatRunner` | MAF LLM orchestrator | same local contracts; orchestrator holds global plan |
| `localvalid_gate` | WITH-localvalid-GATE | `FoundryRunner` | round-robin | local contracts + pre-delivery gate |
| `maf_localvalid_gate` | WITH-maf-localvalid-GATE | `MAFGroupChatRunner` | MAF LLM orchestrator | same local contracts + pre-broadcast gate |
| `localvalid_sched` | WITH-localvalid-SCHED | `FoundryRunner` | EFSM scheduler | local contracts + gate + scheduler (full STJP) |
| `maf_localvalid_sched` | WITHOUT-maf-localvalid-SCHED | `MAFGroupChatRunner` | MAF EFSM selection function | local contracts + deterministic speaker selection; no gate |

`SCENARIOS` contains these 10 core arms. `ABLATION_SCENARIOS` contains
three opt-in mechanism checks, and `LEGACY_SCENARIOS` retains 17 historical
keys so old run directories remain reproducible and gradable.

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

- **`skills` vs `maf_skills`** — same skill prompts, different runtime.
- **`globalvalid` vs `localvalid`** and **`maf_globalvalid` vs
  `maf_localvalid`** — global text versus projected local contracts on each
  runtime.
- **`localvalid` vs `localvalid_gate`** and **`maf_localvalid` vs
  `maf_localvalid_gate`** — byte-identical role prompts; only enforcement
  differs.
- **`localvalid_gate` vs `maf_localvalid_gate`** — same contracts and
  deterministic gate, different runtime/speaker selection.
- **`localvalid_gate` vs `localvalid_sched`** — enforcement held constant;
  only the EFSM scheduler is added.
- **`maf_localvalid` vs `maf_localvalid_sched`** — local contracts held
  constant; LLM versus deterministic speaker selection.
- **`min_llmvalid_gate` vs `min_llmvalid_gate_nohint`** — identical prompts
  and gate; only the per-turn hint differs. Isolates guidance.
- **`min_llmvalid_gate_lastrecv` vs `min_llmvalid_sched`** — identical
  prompts and gate; only the scheduler differs. Isolates what the
  protocol-derived scheduler adds beyond a trivial heuristic (see
  `docs/benchmarks/BENCHMARK_FAIRNESS_REVIEW.md`, Problem 4).

## LLM-drafted-protocol dependency

Eight core arms — every arm except `skills` and `maf_skills` — consume an
**LLM-drafted** protocol at
`cases/<case>/protocols/llm_drafts/{valid,unsafe}/v1.scr` (+ re-anchored
`goals.yaml`). These are produced per-case by:

```
python experiments/scripts/draft_llm_protocols.py <case>
python experiments/scripts/re_anchor_goals.py <case> valid
python experiments/scripts/re_anchor_goals.py <case> unsafe
```

Their `registry.py` factories **fail-fast** at `setup()` with a clear
remediation message if those files are missing. The skills arms need no
protocol draft.

## Orchestration — a deliberate variable, not a constant

Two orchestration styles are in the matrix on purpose:

- **Round-robin / EFSM dispatch** (`skills`, `globalvalid`, `localvalid*`):
  the benchmark runtime selects roles in fixed order or from enabled EFSM
  SEND transitions.
- **MAF GroupChat** (`maf_*`): either an LLM orchestrator selects speakers,
  or `maf_localvalid_sched` uses MAF's deterministic `selection_func`.
  `maf_localvalid_gate` installs a custom MAF orchestrator that validates
  before the framework's transcript append/broadcast path.

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
- `registry.py` — 10 core + 3 ablation + 17 legacy arms + `make_runner(case, key)`
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
