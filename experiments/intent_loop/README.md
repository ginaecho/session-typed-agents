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

Verdict rule (stated inside every report): *faithful iff all
protocol-expressible requirements covered "yes" AND no ungrounded
interactions AND back-translation score ≥ 70.* `partial` counts as a miss —
conservative on purpose; the per-item evidence is kept so a human can
overrule.

### Policy requirements are reported, never scored

Some real requirements **cannot be expressed as a session type at all**: a
protocol constrains *roles* and the messages between them, but says nothing
about which *principal* inhabits a role. The first live episode produced the
canonical example — "the FinanceApprover and the PaymentProcessor must be
distinct people." Grading a protocol on that is a category error, and left
uncorrected it makes `faithful=True` unreachable for any realistic intent
and teaches the drafter to fake compliance.

So the interrogator tags these `kind: policy` **at distill time, before any
protocol exists** (it therefore cannot be used afterwards to excuse a weak
draft). They are excluded from the coverage checker's input, from recall,
and from the back-translation reference, and are reported separately as
obligations handed to the deployment/identity layer.

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

## The app (humans + agents, one API)

```bash
python -m experiments.intent_loop web          # http://127.0.0.1:8765
```

In VS Code: `Ctrl+Shift+P` → **Simple Browser: Show** → paste the URL.

The browser UI is a thin client over exactly the endpoints an agent calls —
there are no private routes, so anything a person can do here an agent can
do headlessly. Agents discover the surface with `GET /api/manifest`.

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | readiness: is an LLM configured, is the real Scribble toolchain wired |
| `GET /api/manifest` | self-describing endpoint catalog (agent entry point) |
| `GET /api/episodes` · `/api/episodes/<session>` | episode summaries · one episode in full |
| `POST /api/runs` → `{job_id}` | start an episode (async — a live one is 8–15 LLM calls) |
| `GET /api/runs/<job_id>` | job state + stage events: `start → interrogated → drafted → evaluated → done` |
| `GET /api/corpus` | corpus statistics |
| `POST /api/packs` | mine a prompt pack — **prompt-level training** |
| `GET /api/training/stats` | how many fine-tuning examples exist, and what was dropped |
| `POST /api/training/export` | write train/validation JSONL — **weight-level training** |

Runs are asynchronous because a live episode takes minutes; poll the job
rather than holding a request open. **Security:** the API binds to
127.0.0.1, has no authentication, and can spend LLM budget — do not expose
it. `--host` exists for devcontainers; put an authenticating proxy in front.

## Fine-tuning the target model

Two levels, same corpus, in the order you should try them:

1. **Prompt level** (`POST /api/packs`, or `optimize`) — few-shot exemplars
   + validator-error rulebook. Zero GPU cost, auditable, transferable
   across models. Start here.
2. **Weight level** (`POST /api/training/export`, or `export-sft`) — emits
   chat-format JSONL that Azure OpenAI / OpenAI fine-tuning accepts as-is:
   - *drafting* examples: distilled spec → a protocol that was **both
     valid and faithful** (a valid-but-unfaithful protocol is exactly the
     failure this project exists to prevent — training on it teaches the
     model to produce more);
   - *repair* examples: (spec, broken draft, the validator's verbatim
     error) → the draft that validated next, mined from consecutive real
     attempts rather than synthetic corruption.

   Splitting is **by intent hash, never by row**, so two episodes on the
   same document cannot straddle train/validation — the leak that makes a
   fine-tune look better than it is. The training prompts are the
   *zero-shot* forms: a fine-tune should internalize what the prompt pack
   carries, so the served model needs a shorter prompt than the baseline.

Measure a pack or a checkpoint the same way: re-run the same intents and
diff validity-first-try, mean repair rounds, and faithfulness rate — the
corpus records all three.

## Usage

```bash
# offline demo/smoke — zero network, zero cost, scripted end to end
python -m experiments.intent_loop run --mock

# real episode (Foundry-first LLM calls, real Scribble validator; az login first)
python -m experiments.intent_loop run --intent-file docs/handbook_markdown.md \
    --out experiments/intent_loop/sessions/handbook_01

# live LLM on a machine without the Scribble toolchain (development only —
# every artifact is stamped `validator: mock` and is never evidence)
python -m experiments.intent_loop run --intent-file intent.md --validator mock

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
