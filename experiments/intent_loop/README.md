# intent_loop — interrogation, faithful drafting, and prompt-level training

The seam (paper §"contribution 5"): translating a natural-language intent
into a formal Scribble protocol passes through an LLM, so a protocol can be
perfectly **valid** yet not what the user **meant**. This app closes the
loop around that seam:

```
intent document ──> INTERROGATE ──> distilled requirements (typed, atomic)
      (stakeholder answers /            │
       explicit assumptions)            v
                                     DRAFT ──> real Scribble validate
                                        ^          │ counterexample
                                        └── REPAIR ┘   (≤ 3 rounds, t0 loop)
                                               │ valid protocol
                                               v
                                     FAITHFULNESS SUITE
                                     (coverage / back-translation / E5)
                                               │
                                               v
                                     CORPUS (every episode, failures too)
                                               │
                                               v
                                     PROMPT PACK (few-shot + rulebook)
                                     — fed back into DRAFT, no weights touched
```

## Why interrogation instead of one-shot distillation

`BENCHMARK_PLAN_V3` §10.3 models an "interrogation step" but implements a
single-pass distillation. This app is the real multi-turn loop, and its
value is measurable, not cosmetic:

1. **Facts outside the document.** `StakeholderSim` takes `hidden_notes` —
   requirements the stakeholder knows but the document omits. Only asking
   surfaces them; a one-shot distiller cannot. Training episodes plant
   hidden notes and check whether the distilled requirements recovered
   them.
2. **Ambiguity becomes explicit.** With `improvise=False` (default) the
   stakeholder answers `NOT SPECIFIED.` for anything uncovered; the
   interrogator must then log an `open_question` or a requirement with
   `source: assumption` — never a silently invented fact.
3. **Requirements are atomic and typed** (`ordering` / `authorization` /
   `value` / `branch` / `termination` / `role`), because the faithfulness
   suite checks them one by one against the drafted protocol. A prose blob
   can't be checked item-wise; a checklist can.

## The faithfulness metric (what "reflects the user intent" means here)

Three instruments, cheapest first; no single LLM opinion is ever the whole
verdict:

| # | Instrument | Mechanism | Catches |
|---|---|---|---|
| 1 | **Requirement coverage** (primary) | checker LLM must find each requirement in the protocol and cite evidence; must also list `ungrounded` interactions | omissions (per item), hallucinated structure |
| 2 | **Back-translation** (the round-trip idea) | one call sees ONLY the protocol and reconstructs the intent (`back_translate()` has no intent parameter — that signature is the isolation mechanism); a separate comparator scores the reconstruction 0–100 with missing/added lists | global drift, mis-emphasis |
| 3 | **Gold E5 equivalence** (exact, optional) | `eval/validity.bisim_equivalent` against a known-correct reference | everything, mechanically — but only for benchmark cases that have a gold protocol |

Verdict rule (stated inside every report): *faithful iff all requirements
covered "yes" AND no ungrounded interactions AND back-translation score ≥
70.* `partial` counts as a miss — conservative on purpose; the per-item
evidence is kept so a human can overrule.

An external similarity scorer (e.g. `azure-ai-evaluation`'s
`SimilarityEvaluator`) can replace the comparator seat via the `compare_fn`
parameter without touching anything else. For **calibrated headline
numbers**, use the seam_bench judge panel (J-fwd / J-back / J-probe with
human-audit calibration) — `faithfulness.run_seam_panel` is the bridge;
this in-loop suite is the fast per-episode training signal.

## Prompt-level training (no weight updates)

`optimize.build_prompt_pack` mines the corpus into a versioned
`PromptPack`:

- **Few-shot exemplars** — (intent, protocol) pairs from episodes that were
  both valid **and** faithful, retrieved per-intent by BM25
  (`t0/exemplars.ExemplarIndex`). Valid-but-unfaithful episodes are
  excluded by default: they would teach exactly the failure mode this app
  exists to prevent.
- **Rulebook** — validator counterexamples grouped into error families;
  recurring families become standing lesson lines in the drafter's system
  prompt. A failure the validator caught twice should not need catching a
  third time.

Compare packs by re-running the same eval set and diffing
validity-first-try rate, mean repair rounds, and faithfulness rate — the
corpus records all three. When prompt-level gains plateau, the same corpus
is the SFT dataset; weight tuning (SEAM_TRAINING_EXECUTION_PLAN.md) is the
escalation path, not the starting point.

## Usage

```bash
# offline demo/smoke — zero network, zero cost, scripted end to end
python -m experiments.intent_loop run --mock

# real episode (Foundry-first LLM calls, real Scribble validator; az login first)
python -m experiments.intent_loop run --intent-file docs/handbook_markdown.md \
    --out experiments/intent_loop/sessions/handbook_01

# with a known-correct reference protocol (adds the E5 check)
python -m experiments.intent_loop run --intent-file intent.md \
    --gold experiments/cases/finance/protocols/v1.scr

# mine the corpus into a prompt pack, then draft with it
python -m experiments.intent_loop optimize --version v2
python -m experiments.intent_loop run --intent-file intent.md \
    --pack experiments/intent_loop/packs/pack_v2.json

python -m experiments.intent_loop show-corpus
```

Every episode persists a full audit trail under `sessions/<ts>/`:
`document.md`, `transcript.json`, `intent_distilled.md`, `drafts/attempt_*`
with per-attempt validator verdicts, `protocol.scr`, `faithfulness.json`,
`record.json`. Mock runs are labeled `validator: mock` in every artifact
and are never evidence.

## What is reused, not rebuilt

| piece | reused from |
|---|---|
| Drafter interface + validate/repair production loop | `seam_bench/t0/drafter.py`, `t0/repair_loop.py` |
| Real Scribble validation + E5 equivalence | `seam_bench/eval/validity.py` |
| BM25 few-shot retrieval | `seam_bench/t0/exemplars.py` |
| Calibrated faithfulness panel (optional bridge) | `seam_bench/judge/` |
| Foundry-first LLM transport | `stjp_core/foundry/llm_client.py` |

Relationship to `experiments/scripts/intent_pipeline.py`: that script
produces the *benchmark* intent artifacts (one-shot distillation, label-leak
guard, human `approve` gate) and stays the source of truth for benchmark
runs. This app is the *research loop* on the interrogation/drafting seam;
if its distilled artifacts are ever fed into benchmark arms, they must
first pass `intent_pipeline.py check` (label-leak + goal-coverage).
