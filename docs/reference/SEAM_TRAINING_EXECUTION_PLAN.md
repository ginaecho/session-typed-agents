# Seam Training — execution plan (we are actually training this)

Companion to `SEAM_AUTOTRAINING_PLAN.md` (the strategy). This document is the
**executable** version: exact stacks, data formats, hyperparameters, judge
isolation mechanics, benchmarks, statistical gates, and ready-to-dispatch
worker briefs. Design goal throughout: **minimum implementation friction** —
every component is either already in the repo or a thin adapter over a
commodity tool.

Status: preregistered plan. Numbers in §8 are go/no-go commitments written
before any run, matching the house preregistration style (E9/E10 grading).

---

## 1. Operating model — who does what

| role | actor | does | does NOT |
|---|---|---|---|
| **Planner/advisor** | Fable 5 (main session) | owns this plan; reviews phase-gate reports; unblocks escalations; adjudicates design forks | write training code; run experiments; judge cases |
| **Architect worker** | Opus subagent | reward harness, GRPO wiring, grammar file, anything where a wrong abstraction is expensive | bulk data generation |
| **Implementation workers** | Sonnet subagents | data pipeline, eval harness, mining, report writing, experiment babysitting | architecture decisions (escalate) |
| **Judges** | stateless API calls (Sonnet default; Haiku where §6 calibration proves parity; one non-Anthropic family if available for decorrelation) | single-shot (payload → JSON verdict) | tools, files, conversation, memory of any kind |
| **Trainee** | open-weights model (§4) | intent→protocol translation; repair | judging its own outputs, ever |

**Two different isolation regimes — do not conflate them:**

- *Workers* are Claude Code subagents launched in **separate git worktrees**;
  they share the repo (that is the point) but never a conversation. Handoffs
  happen only through committed artifacts (code, reports, JSONL).
- *Judges* are **not** interactive agents at all. Lowest-friction and
  strongest-isolation implementation is a plain SDK call: no tool loop, no
  session, no filesystem. A judge is a pure function
  `verdict = judge(class, model, temperature, payload)`. §5 specifies the
  mechanism that keeps panels from converging on "the same judgment."

**Escalation protocol (workers → planner).** A blocked worker commits
`reports/blocked/<task-id>.md` containing: goal, what was tried (≥2
approaches), exact errors, smallest failing repro, and its best-guess fork
(A vs B). The planner answers in the same file. No worker idles waiting; it
moves to its next task card.

**Phase gates.** A phase ends when its worker report exists, its
deterministic checks pass in CI-style scripts (not narrative claims), and
the planner has reviewed the report. Test sets are touched **only** at phase
gates (§7 cadence).

---

## 2. System under training

Two artifacts, one base model:

1. **Translator** T: intent (NL) → global protocol G (Scribble `.scr` +
   `.refn` guard sidecar when the intent implies value constraints).
2. **Repairer** R: (intent, broken G, validator counterexample) → fixed G.
   At inference the pair runs the production loop: T drafts → validate → on
   reject, R patches, ≤ 3 rounds (mirrors the live 4-reject→pass trace).

**Base model (T and R share it; LoRA heads differ):**
`Qwen2.5-Coder-7B-Instruct` (Apache-2.0). Rationale: strongest small coder
family for grammar-disciplined output; fits one A100-80GB with LoRA; a
`-3B` twin exists for fast iteration and a `-14B` upgrade path if H4 (§8)
misses narrowly. Fallback family: `Llama-3.1-8B-Instruct` (only if Qwen
shows tokenizer pathologies on Scribble syntax — decide at T1 gate, not
before).

**Grammar-constrained decoding (GCD).** Write the Scribble surface grammar
once as Lark/EBNF (`stjp_core/compiler/nuscr_syntax.py` is the source of
truth; the grammar file is generated from it or hand-derived and round-trip
tested against the corpus: every corpus protocol must parse under the
grammar, and 1k grammar-sampled strings must parse under `protocol_parser`).
Serve with **vLLM guided decoding** (xgrammar backend, `guided_grammar=`).
That gives GCD in *both* eval and GRPO rollouts with zero custom decoding
code. API-model baselines (Sonnet/Opus) cannot be grammar-constrained; they
get parse-reject-retry instead, and we report that asymmetry explicitly.

**Training stack.** TRL (`SFTTrainer`, `GRPOTrainer`) + PEFT LoRA + vLLM
rollouts. Single-node, rented GPU (Modal or RunPod; image pinned by a
`pyproject`/lockfile committed to the repo). No custom trainer code — the
only bespoke pieces are the **reward function** (a Python callable that
shells into `compiler/validator.py` and the E5 bisimulation scorer) and the
**data builders**. This is deliberate: everything nonstandard in this
project lives in *rewards and data*, where our verifiers are the moat, not
in training infrastructure, where custom code is pure friction.

Hyperparameter starting points (tune on dev only):
- SFT: LoRA r=32 α=64 dropout=0.05 on attn+MLP; lr 1e-4 cosine; eff. batch
  64; 2–3 epochs; max seq 4k (covers corpus max + intent).
- GRPO: group size 8; lr 2e-6; KL β 0.02 vs SFT checkpoint; rollout ≤1024
  new tokens; temperature 0.8 under GCD; 1–2k prompts/epoch.
- Reward (per sample): parse is guaranteed by GCD → not rewarded;
  `+1.0` validator pass; `+2.0` bisimulation-equivalent to gold;
  `−0.1·(len_tokens/1024)` brevity term; guard co-emission `+0.5` when the
  gold has `.refn` and the draft's guards check. Faithfulness term stays
  **0.0 until the §6 calibration gate passes**, then `+1.0·panel_score` on
  the no-gold (mined) prompts only, with J-probe veto ⇒ reward 0.

Compute/cost envelope (approved before spend, per house frugality):
SFT ≈ 2–6 A100-hours (~$10–30); GRPO ≈ 24–72 A100-hours (~$100–350);
data generation ≈ $150–400 API; panel calibration ≈ $50–150 API;
E5 best-of-n fill ≈ $50–100 API. Total well under $1k for the full program.

---

## 3. Data pipeline

**Ground truth inventory (verified on disk today):** 30 corpus skeletons
(`experiments/cases/_corpus/corpus_*.scr`) + 19 named cases + mutation
operators (`integration_stress.py::s2_mutation`) + incremental composition
(`compiler/incremental.py`) + EFSM tooling (`efsm_parser`, E5 equivalence).

**D1 — Expand the protocol set.** From 30+19 seeds to ≥5,000 unique valid
protocols by (a) parameter sweeps (role count 2–6, branch width, recursion
on/off, guard density), (b) compositional insertion of child sub-protocols
via `incremental.py`, (c) validated crossover of corpus fragments. Every
candidate must pass the validator; **uniqueness is by EFSM-equivalence
class**, not text: compute a canonical bisimulation-quotient signature and
dedupe on it. This same signature later enforces split hygiene.

**D2 — Back-translate to intents.** Sonnet verbalizes each protocol into
3–5 intents at controlled registers (terse ticket / conversational ask /
spec-ish paragraph), *without seeing role-name hints stripped?* — no: role
names stay (they carry meaning), but the prompt forbids Scribble vocabulary
in the intent so the pair is a real translation task, not transliteration.
Every (intent, G) pair is accepted only if a **round-trip probe** passes:
an independent Sonnet call translates the intent back to a protocol under
best-of-5 + validator, and the E5 checker finds it equivalent to G. Pairs
that fail round-trip are quarantined as `hard/` (kept — they are exactly
the interesting tail) but excluded from T1 SFT.

**D3 — Repair pairs.** For each protocol: apply each applicable mutation
operator → run validator → keep (intent, mutant, counterexample, gold) with
the *machine* counterexample verbatim in the prompt. Target ≥20k repair
tuples. Mutants that still validate (semantic near-misses) go to the judge
calibration set (§6), not to repair training.

**D4 — Splits (leakage rules are the whole game):**

| split | contents | size target | used for |
|---|---|---|---|
| `train` | D1/D2/D3 synthetic | ~80% of families | SFT, GRPO prompts |
| `dev` | synthetic | ~10% | all tuning, checkpoint picking |
| `test-syn` | synthetic | ~10% | phase gates only |
| `test-real` | mined (D5), human-written intents only | 150–300 items | phase gates only; never trained on |

Split by **structural family** (the EFSM signature of the *seed* before
paraphrase/mutation): all paraphrases and mutants of one skeleton live on
one side of the line. A paraphrase straddling the split is silent leakage;
the signature makes it mechanically impossible.

**D5 — Mined real-world set.** Precedent already in-repo: the
`skills_safety/pr_merge` case adapted from `github/awesome-copilot` (MIT),
RESULT_9 ran real Anthropic+Copilot skills. Scale that recipe:
harvest `.claude/skills/**`, `SKILL.md`, agent-role sections of
CLAUDE.md/AGENTS.md, CrewAI/AutoGen/LangGraph role+handoff configs from
permissively-licensed public repos (dev-workflow first: review, triage,
release, CI). For each team of skills:
`skill_compactor.py` → LocalTypes → `global_synthesizer.py` → validator →
G. The **intent** is the human-written description/when-to-use/README text
— gold because no model wrote it. Provenance (repo, license, SHA) recorded
per item. Yield expectation is honestly unknown; the compactor's
compatibility check measures it cheaply, and a low yield is itself a paper
finding (hand-written skills under-determine coordination).

---

## 4. Training phases

**T0 — prompt-era baselines + E5 fill (no weights; run first, ~days).**
Best-of-n with validator filter for n∈{1,5,10,25} over Haiku/Sonnet/Opus,
plus few-shot retrieval (BM25 over train-split intents, 3 exemplars), plus
the repair loop with the same API model. This (a) fills the pending E5
cells with measured numbers **before any training**, (b) freezes the
baseline row of every table, (c) shakes out the eval harness on cheap
tokens. Deliverable: `reports/seam/T0_baselines.md` + JSONL of every run.

**T1 — SFT.** Train T on D2-accepted pairs; train R on D3. Checkpoint
selection on dev validity@1 (T) and fix-rate@1 (R). Deliverable: LoRA
adapters + `T1_sft_report.md` with the §7 metric block.

**T2 — GRPO.** Initialize from T1. Rewards as §2. Curriculum: epoch 1
restricted to ≤4-role non-recursive families, then unrestricted (anneal,
don't shock). Divergence guard runs every 200 steps: dev validity may rise
only if dev *panel score on a fixed probe set* does not fall >2 pts —
the reward-hacking signature is validity↑ faithfulness→flat/↓, and it
halts the run automatically.

**T3 — faithfulness-in-the-loop (conditional).** Only if the §6 calibration
gate passed: add the panel term on mined-style prompts (no gold available),
J-probe veto semantics. This is the only phase where judge calls enter the
reward path; they are cached by payload hash so a repeated rollout never
re-rolls a verdict (§5 reproducibility).

---

## 5. Judge panel — the no-shared-memory mechanism, concretely

The requirement: judges must not share memory, must not *have* memory, and
must not end up "saying the same judgment" through any hidden channel. The
mechanism has five layers; all five are enforced by the orchestrator
(deterministic Python, `experiments/scripts/judge_panel.py`), not by
convention:

**5.1 Process isolation.** A verdict is one stateless SDK call: fresh
context, no tools, no files, no session id, `max_tokens` bounded, JSON
schema forced. There is no judge "agent" that could accumulate state; there
is nothing to share because nothing persists. Verdicts are cached keyed by
`(class, model, temp, prompt_hash, payload_hash)` — reproducible reruns,
and a cache hit is by construction identical isolation.

**5.2 Payload sanitization (starve the channel).** Judges receive ONLY
their class-specific view. The orchestrator strips: drafting/repair traces,
validator logs, case names/ids, file paths, provenance, and **all comments
in G** (a trained translator could otherwise learn to smuggle persuasion
into comments — the pretty-printer emits canonical, comment-free,
whitespace-normalized Scribble). No judge ever sees another verdict, the
vote count, or even that other judges exist.

**5.3 View decorrelation (make honest agreement the only correlation).**
- **J-fwd** (forward checklist): sees (intent′, G) where intent′ is one of
  k paraphrase variants — each fwd judge gets a *different* paraphrase, so
  surface-cue anchoring decorrelates; a verdict that flips across
  paraphrases is measured noise, not signal.
- **J-back** (blind round-trip): sees **G only**, writes the intent G
  encodes; a *separate* stateless comparator call scores reconstructed vs
  original intent. Structurally immune to confirmation — it cannot parrot
  an intent it never saw.
- **J-probe**: an LLM call compiles the intent into probe queries; the
  *verdict* is `critic`-style deterministic reachability/trace checking on
  G's EFSM. Immune to correlation entirely (no sampling in the verdict).
- Model mix: default panel = 2×J-fwd (Sonnet, distinct paraphrases) +
  2×J-back (Sonnet, Haiku) + J-probe. Where a non-Anthropic family is
  available, swap one J-back seat for it. Temperatures drawn per-seat from
  {0.3, 0.7}; rubric emphasis rotated per-seat (roles / ordering /
  prohibitions / termination) so even same-model seats attend differently.
- **Order randomization** for any comparative payload (A/B position bias).

**5.4 Structured verdicts with evidence pointers.** Schema:
`{vote: yes|no|abstain, confidence: 0–1, evidence: [{quote, source:
intent|protocol}...], missing: [...]}`. The aggregator **verifies every
evidence quote actually occurs** in the payload (string match after
normalization); verdicts with fabricated evidence are discarded and
resampled at a different temperature. This is the lie-detector that keeps
votes anchored to the artifact instead of to plausible-sounding prose.

**5.5 Collusion/degeneration audits (continuous, automatic).**
- *Rationale-overlap alarm:* pairwise 5-gram Jaccard across the panel's
  free-text fields; overlap above threshold (identical phrasing, not
  merely identical votes — honest judges may agree; they should not agree
  *verbatim*) fails the panel run and pages the planner. This is the
  direct guard against "they all say the same judgment."
- *Canaries interleaved in every batch:* (i) swapped pairs — intent_A with
  G_B must be rejected; a seat that accepts mismatches is leniency-broken;
  (ii) mutant decoys — gold vs behavior-changing mutant must separate;
  (iii) duplicate probes — same payload, different seed, measures per-seat
  self-consistency. Per-seat calibration curves are recomputed nightly
  from canaries alone; a drifting seat is removed from aggregation weight
  without touching any real verdict.
- *Aggregation is code:* calibration-weighted vote share; J-probe failures
  veto regardless of votes; abstentions route to the human queue with the
  dissent attached. No LLM anywhere in aggregation.

---

## 6. Judge calibration gate (before the panel may reward or gate anything)

Build the calibration set from assets we already trust:
gold (intent, G) pairs from D2 round-trip winners; hard negatives from
semantic near-miss mutants (validator-passing mutants of D3); swapped
pairs; plus a **100-item human-audited subset** (the only human labor in
the program: Gina labels fit/no-fit; ~2–3 hours).

Gate (all must hold, per judge class and for the ensemble):
- AUC ≥ 0.85 separating gold vs behavior-changing mutant (ensemble ≥ 0.90);
- ≥ 95% rejection of swapped pairs;
- ≥ 85% agreement with the human-audited 100 (ensemble);
- per-seat self-consistency ≥ 0.8 on duplicate canaries.

Below gate → the panel remains **advisory** (logged, never a reward, never
a deployment gate), and T3 is cancelled while T0–T2 proceed unchanged. The
plan degrades gracefully because A-side rewards are verifier-only.

---

## 7. Evaluation design — benchmarks, baselines, statistics

**Why we must build the benchmark:** there is no public NL→MPST/Scribble
benchmark. Nearest lineage is NL→temporal-logic (nl2spec, NL2TL,
Lang2LTL) and verifier-checked autoformalization (miniF2F-style pass@k);
we adopt their *methodology* (verifier-scored pass@k, held-out human-
written eval) and release ours as the reference benchmark. Working name:
**Seam-Bench** = `train/dev/test-syn` (synthetic, §3) + `test-real`
(mined, human intents). Releasing it is a paper deliverable, and RESULT_9's
mined-skills precedent shows the release pipeline (provenance + license).

**Standing metric block (every system reports all of it):**

| metric | definition | axis |
|---|---|---|
| validity@1 / @k | validator pass rate, first draft / best-of-k | validity |
| semantic-validity@1 | validity under GCD (syntax impossible) | validity |
| bisim@1 / @k | E5 equivalence to gold | equivalence |
| repair-rounds | mean rounds to valid under T+R loop (cap 3) | validity |
| tokens-to-accepted | total tokens (draft+repairs) per accepted G | cost |
| $-to-accepted | ditto in dollars at posted prices | cost |
| panel-score | calibrated vote share (only if §6 gate passed) | faithfulness |
| probe pass-rate | deterministic probe checks passed | faithfulness |
| probe compile-rate | fraction of intent clauses that compiled to probes | coverage |
| transfer gap | metric(test-syn) − metric(test-real) | generalization |

**Systems matrix (rows measured at every phase gate):**
S0 zero-shot {Haiku, Sonnet, Opus} · S1 +few-shot retrieval ·
S2 +best-of-10 · S3 +repair loop ·
S4 SFT-7B+GCD · S5 S4+best-of-10 · S6 GRPO · S7 GRPO+R (full loop).
Ablations at T2 gate: −GCD, −repair-curriculum, −paraphrase-clusters,
−round-trip filter on SFT data; judge-class ablations (fwd-only vs full).

**Statistics (house rules):** paired bootstrap (10k resamples) for all
deltas on the same test items; McNemar for validity@1 flips; report 95%
CIs, never bare means; n per cell stated in-table. Dev may be consulted
freely; `test-syn`/`test-real` are opened **only at phase gates** and every
opening is logged in the report (the E9/E10 preregistration discipline).

## 8. Preregistered go/no-go (written before any run)

- **H1 (GCD):** syntactic invalidity → 0 by construction; semantic
  validity@1 within ±2 pts of unconstrained (GCD must not distort content).
- **H2 (best-of-n, fills E5):** Sonnet validity@10 ≥ validity@1 + 25 pts on
  test-syn. *Go for T1 regardless — H2 is a measurement, not a gate.*
- **H3 (SFT):** S4 validity@1 ≥ S0-Sonnet validity@1 − 10 pts at ≤ 1/20 the
  $-to-accepted; bisim@1 ≥ S1-Sonnet − 5 pts. Miss → try 14B once; miss
  again → program stops at the (still-publishable) T0+panel results.
- **H4 (GRPO):** S6 ≥ S4 + 10 pts validity@1 on test-syn AND repair-rounds
  strictly down AND divergence guard never tripped at the accepted
  checkpoint. Miss → ship S4/S5 and report GRPO honestly as negative.
- **H5 (panel):** §6 gate numbers. Miss → panel advisory-only forever.
- **H6 (transfer):** trained systems' transfer gap ≤ prompt-baseline
  transfer gap (training must not overfit synthetic register). Miss →
  augment D2 with mined-register paraphrases, one retry.

## 9. Worker task cards (dispatch order)

| id | worker | deliverable | done when |
|---|---|---|---|
| W1 | Sonnet | eval harness: metric block + splits + JSONL schema + report generator | metrics reproduce on the 30-corpus smoke set; opened-test log exists |
| W2 | Opus | Lark grammar + vLLM guided-decoding adapter | corpus round-trip 100%; 1k samples parse |
| W3 | Sonnet | D1–D3 builders + EFSM-signature dedupe/splitter | ≥5k families; leakage checker green |
| W4 | Sonnet | T0 baselines + E5 cell fill | `T0_baselines.md` + JSONL |
| W5 | Opus | reward fn (validator+bisim callable, subprocess-safe, <200ms cached) | 1k-call fuzz, zero hangs |
| W6 | Sonnet | `judge_panel.py` per §5 + canary battery | §5.5 audits run in CI mode |
| W7 | Sonnet | calibration set + human-audit packet (100 items) | §6 report with per-class curves |
| W8 | Sonnet | miner (D5) with provenance/license ledger | ≥150 `test-real` items or a measured-yield report |
| W9 | Opus | T1 SFT run + report | H3 evaluated |
| W10 | Opus | T2 GRPO run + divergence guard + report | H4 evaluated |
| W11 | Sonnet | Seam-Bench packaging + card | external repro instructions pass a clean-room run |

Dependencies: W1→W4; W2→{W4,W9,W10}; W3→{W4,W9}; W5→W10; W6→W7→(T3
decision); W8→H6. W1–W3 dispatch in parallel, day one.

## 10. Grounding — design choice → precedent (why this shape, not another)

| choice | precedent |
|---|---|
| verifier-filtered sampling → SFT (expert iteration) | STaR (Zelikman et al. '22); ReST |
| RL from verifiable rewards, group-relative | DeepSeekMath/R1 GRPO; Tülu-3 RLVR |
| grammar-constrained decoding | Outlines (Willard & Louf '23); xgrammar; SynCode |
| back-translation from a generator we own | Sennrich et al. '16; OSS-Instruct/Magicoder (real artifacts → instructions) |
| NL→formal-spec task shape + verifier-scored eval | nl2spec (Cosler et al. '23); NL2TL (Chen et al. '23); Lang2LTL; miniF2F pass@k methodology |
| independent juries over one big judge | PoLL "juries" (Verga et al. '24); known LLM-judge biases — position, verbosity, self-preference (Zheng et al. '23) — each mapped to a §5 control |
| counterexample-conditioned repair | self-debug/self-repair lines; our validator's counterexamples are total, unlike test-based feedback |

Our edge over every cited line: the checker is **total and
counterexample-producing** (all paths, not sampled tests), and the
faithfulness instrument is partially **mechanized** (J-probe compiles to
EFSM checks) rather than purely rubric-based.
