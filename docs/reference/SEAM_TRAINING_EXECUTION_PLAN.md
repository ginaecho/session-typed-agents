# Seam Training — execution plan (we are actually training this)

Companion to `SEAM_AUTOTRAINING_PLAN.md` (the strategy). This document is the
**executable** version: exact stacks, data formats, hyperparameters, judge
isolation mechanics, benchmarks, statistical gates, and ready-to-dispatch
worker briefs. Design goal throughout: **minimum implementation friction** —
every component is either already in the repo or a thin adapter over a
commodity tool.

Status: preregistered plan. Numbers in §8 are go/no-go commitments written
before any run, matching the house preregistration style (E9/E10 grading).

Four terms recur throughout and are defined here once: **SFT**
(supervised fine-tuning — training on labeled correct examples), **GRPO**
(Group Relative Policy Optimization — a reinforcement-learning method that
scores each sampled output against the average of a sampled group instead
of training a separate value model), **LoRA** (Low-Rank Adaptation — a
fine-tuning technique that trains a small add-on set of weights instead of
the whole model, so it is cheap enough to run on a single GPU), and
**gold** (a known-correct reference protocol or answer to score a
candidate against).

---

## 1. Operating model — who does what

| role | actor | does | does NOT |
|---|---|---|---|
| **Planner/advisor** | Fable 5 (main session) | owns this plan; reviews phase-gate reports; unblocks escalations; adjudicates design forks | write training code; run experiments; judge cases |
| **Architect worker** | Opus subagent | reward harness, connecting up GRPO training, grammar file, anything where a wrong abstraction is expensive | bulk data generation |
| **Implementation workers** | Sonnet subagents | data pipeline, eval harness, mining, report writing, experiment babysitting | architecture decisions (escalate) |
| **Judges** | stateless API calls (Sonnet default; Haiku where §6 calibration proves parity; one non-Anthropic family if available for decorrelation) | single-shot (payload → JSON verdict) | tools, files, conversation, memory of any kind |
| **Scouts** | Sonnet (judgment-heavy scouting: literature, stack verification, dataset/mining survey), Opus (adversarial plan red-team), Haiku (mechanical fact-sheets: versions, pricing, id verification) | read-only research; one report file each under `docs/reference/reports/seam/scouts/`; findings adjudicated by the planner in §11 | git operations; code edits; design decisions |
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
family for grammar-disciplined output; fits one A100-80GB with LoRA.
v2 ladder (R2-verified — Qwen3-Coder ships only as MoE, no dense 3–14B
successor exists): `-7B` primary → `Qwen2.5-Coder-14B-Instruct` if H3
misses → `Qwen3.6-27B` dense (Apache-2.0) if the 14B also misses.
License caveat (R5): the `-3B` twin is **Qwen-Research, not Apache** —
iteration/smoke only (smoke here and below means a quick end-to-end check,
not a full run), never in a released artifact. Fallback family:
`Llama-3.1-8B-Instruct` (only if Qwen shows tokenizer pathologies on
Scribble syntax — decide at T1 gate, not before).

**Version pins (R2-verified mutually compatible; do not float):**
`torch==2.11.0+cu128`, `vllm==0.23.0` (TRL hard-caps `<=0.23.0` — vLLM
0.24 exists and must NOT be taken), `xgrammar==0.2.3`,
`transformers==5.13.1`, `peft==0.19.1`, `trl==1.8.0`, `lark==1.2.2`
(repo) . Unsloth: optional later trial only, compat band unverified.
GPU: RunPod Secure Cloud primary (~$1.2–1.4/hr A100-80GB), Modal
fallback (~$2.50/hr, better phase-gate ergonomics). API budget note
(R5): current intro pricing expires 2026-08-31 (+~50% after) — run T0
and panel calibration before September or re-budget.

**Grammar-constrained decoding (GCD) — v2, per R2/R1 scouting.** The
grammar exists (W2: `scribble_grammar.lark` + GBNF emitter; 100% corpus
round-trip; 1000/1000 samples parse; zero parse-level rejections under
real Scribble on probe). v2 corrections: (i) the **GBNF form is the
primary artifact**, not a mirror — xgrammar's native dialect is
GBNF-style EBNF and vLLM's Lark auto-detection has a confirmed open bug;
(ii) vLLM's `guided_grammar=` param was removed in v0.12 — current API is
`structured_outputs={"grammar": ...}` / `StructuredOutputsParams`;
(iii) **inside TRL GRPO rollouts** grammar constraints are reachable only
via the undocumented `generation_kwargs` pass-through (confirmed in both
TRL rollout code paths, server and colocate) — so a one-train()-step
plumbing smoke test (W13) gates T2, source-verified but undocumented
APIs being exactly where runs die. (iv) **Format-tax caveat (R1):**
multiple lines of evidence show constrained/structured decoding can
suppress semantic quality. The −GCD arm is therefore promoted from
ablation to a PRIMARY preregistered comparison at both T1 and T2 (H1
rewritten accordingly), and W13 also prototypes reason-then-clamp
decoding (free reasoning prefix, grammar clamps only the emitted
protocol body). If GCD costs >2 pts semantic validity, it is demoted to
data-generation filtering and inference falls back to parse-reject-retry.
API-model baselines (Sonnet/Opus) cannot be grammar-constrained; they get
parse-reject-retry, and we report that asymmetry explicitly.

**Real toolchain mandate (hard rule).** "Validates" in this program means
the REAL Scribble-java CLI (`org.scribble.cli.CommandLine` via
`stjp_core/compiler/validator.py::ScribbleValidator`), never a Python-only
approximation. One-command install for any checkout/worktree:
`bash tools/setup_scribble_cloud.sh` (builds the ginaecho/scribble-java fork
with Maven once under /workspace, wires the checkout, installs the nuscr
coinductive-fork binary, and smoke-tests gold-pass + corrupt-reject).
Verified 2026-07-11: 30/30 `_corpus` protocols pass real validation; a
corrupted control is rejected with a genuine parser error. Every harness
entry point must fail loudly if the toolchain is absent — a silent fallback
to a weaker checker would poison every reward and every reported number.
nuscr remains the opt-in second backend (`STJP_NUSCR_BIN=/workspace/bin/
nuscr`); it accepts only a fragment (11/30 corpus; non-tail-recursive
protocols rejected by design — a tool limitation, not protocol invalidity),
so it is a cross-check and projection engine, not the validity oracle.
Throughput note for bulk data building: each validation is a JVM spawn
(~0.5–1s); D1-scale runs must parallelize with a worker pool and cache
verdicts by protocol-text hash.

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
  new tokens; temperature 0.8 under GCD; 1–2k prompts/epoch. Before
  adding bespoke normalization, adopt TRL's current defaults against the
  Dr. GRPO/DAPO/GSPO fixes for length bias and entropy collapse (R1) —
  don't double-patch what the trainer already corrects.
- **Reward (v2 — redesigned after red-team B2, which showed the v1 reward's
  within-group variance collapses post-SFT, leaving only the length term
  and driving shortest-valid mode collapse):**
  parse guaranteed by GCD → not rewarded; `+1.0` validator pass;
  **graded equivalence** `+2.0·equiv_score` where `equiv_score ∈ [0,1]` is
  a CHEAP structural proxy (canonical-EFSM feature overlap: roles matched,
  transition-label multiset F1, branch/rec skeleton match — computable in
  ms), with FULL bisimulation reserved for eval only (W1 measured bisim at
  10–40× a validation, up to ~20s — it cannot sit in a rollout loop);
  brevity flipped **one-sided**: penalty only for `len > 1.25× gold_len`,
  zero below (no reward for degenerate brevity); guard co-emission `+0.5`
  as before. **Gradient-starvation guard:** if within-group reward std
  < 0.05 on >50% of groups for 200 steps, halt and escalate — that is B2
  manifesting. Faithfulness term stays **0.0 until the §6 calibration
  gate passes**, then `+1.0·panel_score` on the no-gold (mined) prompts
  only, with J-probe veto ⇒ reward 0.

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

**D1 — Expand the protocol set (v2, after red-team B1).** From 30+19 seeds
toward ≥5,000 unique valid protocols by (a) parameter sweeps (role count
2–6, branch width, recursion on/off, guard density), (b) compositional
insertion of child sub-protocols via `incremental.py`, (c) validated
crossover of corpus fragments. Every candidate must pass the validator.
B1 corrections: (i) the repo has NO canonical quotient signature — only
pairwise `efsm_equiv.py::protocols_equivalent` — so uniqueness is
**bucket-then-verify**: a cheap canonical hash (per-role minimized
automata, BFS-relabelled, sorted transitions) buckets candidates, and the
pairwise checker verifies only within-bucket collisions (never O(N²));
signature-vs-checker agreement measured on ≥200 pairs, escalate if
<100%. (ii) **Non-bisimilarity is not diversity** — a 3-role and a 5-role
pipeline are non-bisimilar but the same shape. D1 therefore reports a
structural-diversity profile (topology class × role count × branch/rec
depth histograms) with a preregistered floor: **≥8 distinct topology
classes, none exceeding 30% of families; every (topology, role-count)
cell in train has a counterpart in dev and test-syn**. 5k near-clones of
five shapes fails the floor regardless of the count. If operators
saturate below the floor, the honest deliverable is the saturation curve
plus new operator proposals — not a padded count.

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

**5.0 Seat transports (v2.3).** Two interchangeable transports behind one
seat interface: (a) **subscription-subagent transport** — seats are
session subagents with schema-forced structured output; fresh context
per spawn, payload-only prompt, no inter-seat visibility; billed to the
session subscription, no API key. Validated live 2026-07-11
(PANEL_SMOKE report: 14 seats, canary rejected at 0.99, J-back caught a
forward-seat confirmation bias on trade_deadlock). Default for all
interactive/phase-gate judging: calibration sweeps, mined-item judging,
escalation seats, and T0 drafting baselines. Instruction-level no-tools
rule plus transcript tool-use audit (tool_uses must be 0 per verdict).
(b) **API-key transport** (the SDK path below) — REQUIRED only where
judging runs headless off-session: the T2/T3 GPU reward path and any
external harness. The key is therefore a T2-gate prerequisite, not a
day-one blocker.

**5.1 Process isolation.** A verdict is one stateless call (either
transport): fresh context, no tools, no files, no session id,
`max_tokens` bounded, JSON schema forced. There is no judge "agent" that could accumulate state; there
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
- Model mix (v2.1, owner directive: judges use top-tier models): default
  panel = 2×J-fwd (Opus 4.8 + Sonnet 5, distinct paraphrases) + 2×J-back
  (Sonnet 5 + Opus 4.6) + J-probe (deterministic). Where a non-Anthropic
  family is available, swap one seat for it. Monoculture caveat (R1
  effective-votes finding): mixed Anthropic versions buy ACCURACY, not
  independence — the class structure (fwd/back/probe) carries
  decorrelation; the effective-votes ≥3 gate still binds. **Escalation
  tier** for borderline cases (aggregate in [0.4, 0.6], or probe-vote
  conflict, or any abstention): a stateless Fable-5 seat (fresh context,
  sanitized payload — the model, never the planner session) plus a
  planner-written analysis routed WITH the case to the human gate; the
  planner's analysis is advisory and never a counted vote, because the
  planner holds exactly the contaminating context (drafting traces,
  reward design) that §5.2 strips from every judge. **Planner load cap
  (owner directive, v2.2):** the planner personally reviews at most 25
  escalations per phase gate, stratified-sampled (worst disagreements +
  random draws), and reviews for PATTERNS, not verdicts — the deliverable
  is a one-page rubric-improvement memo per gate. Escalations beyond the
  cap flow stateless-Fable-seat → human gate without planner involvement.
  Rationale: planner context is the program's scarcest resource; spending
  it on case-by-case judging displaces the planning/adjudication role
  that nothing else can fill. Cost control: strong panel for gate
  decisions, mined items, and escalations; §6-calibrated cheaper seats
  only for bulk screening where per-seat AUC proves parity.
  Temperatures drawn per-seat from {0.3, 0.7}; rubric emphasis rotated
  per-seat (roles / ordering / prohibitions / termination) so even
  same-model seats attend differently.
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
- *Aggregation is code:* v2 (R1): **geometric-median aggregation** over
  per-seat calibrated scores (arithmetic vote-share has unbounded bias
  under a single biased judge; the geometric median is the tuning-free
  robust fix), J-probe failures veto regardless of votes; abstentions
  route to the human queue with the dissent attached. No LLM anywhere in
  aggregation. Additionally report **effective independent votes**
  (estimated from canary inter-seat correlation): scouting found a
  9-judge panel can carry ~2 effective votes — a panel whose effective
  count drops below 3 must diversify seats, not add more of the same.

---

## 6. Judge calibration gate (before the panel may reward or gate anything)

Build the calibration set from assets we already trust — with two v2
corrections from the red-team:
(i) **Circularity (M2):** D2 round-trip winners are model-selected by the
same family that judges, inflating AUC. The calibration set must mix
strata: D2 winners AND mined human-written (intent, G) items AND the
human-audited set; report AUC per stratum, and the gate binds on the
non-D2 strata. Where available, judge seats from a different model
family than the back-translator.
(ii) **Audit power (M3):** 85/100 agreement has a Wilson 95% lower bound
of ~76% — a 100-item audit cannot certify an 85% gate. v2 gate: audit
**n ≥ 200** (Gina labels fit/no-fit, ~4–6 hours, split across two
sittings with an intra-rater consistency check on 20 repeats), and the
criterion is the **Wilson 95% lower bound ≥ 0.80**, not the point
estimate. Certifying ≥85% honestly needs ~370 items — grow to that only
if the panel is later promoted into a training reward at scale.

Gate (all must hold, per judge class and for the ensemble):
- AUC ≥ 0.85 separating gold vs behavior-changing mutant on the
  non-D2 strata (ensemble ≥ 0.90);
- ≥ 95% rejection of swapped pairs;
- human-agreement Wilson 95% lower bound ≥ 0.80 (ensemble, n ≥ 200);
- per-seat self-consistency ≥ 0.8 on duplicate canaries;
- effective independent votes ≥ 3 (per §5.5 correlation estimate).

Below gate → the panel remains **advisory** (logged, never a reward, never
a deployment gate), and T3 is cancelled while T0–T2 proceed unchanged. The
plan degrades gracefully because A-side rewards are verifier-only.
v2 (M1): if the gate fails, the T2 divergence guard must NOT silently
lose its faithfulness leg — it switches to a **deterministic substitute**:
probe pass-rate on a fixed dev probe set (J-probe compiles once, verdicts
are EFSM checks, no panel involved). The guard is never defeasible.

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

- **H1 (GCD, v2 — now a primary two-sided test, not an assumption):**
  syntactic invalidity → 0 by construction. The GCD-on vs GCD-off arms run
  as preregistered comparisons at BOTH T1 and T2 on dev: if GCD-on costs
  >2 pts semantic validity or >2 pts graded equivalence (format-tax
  effect, R1), GCD is demoted to data-generation filtering and inference
  uses parse-reject-retry; reason-then-clamp (W13) is the middle option
  if it recovers the gap.
- **H2 (best-of-n, fills E5):** Sonnet validity@10 ≥ validity@1 + 25 pts on
  test-syn. *Go for T1 regardless — H2 is a measurement, not a gate.*
- **H3 (SFT):** S4 validity@1 ≥ S0-Sonnet validity@1 − 10 pts at ≤ 1/20 the
  $-to-accepted; bisim@1 ≥ S1-Sonnet − 5 pts. Miss → try 14B once; miss
  again → program stops at the (still-publishable) T0+panel results.
- **H4 (GRPO, v2 — headroom-aware):** if S4 validity@1 < 85%: S6 ≥ S4 +
  10 pts validity@1 on test-syn. If S4 validity@1 ≥ 85% (ceiling — a
  successful H3 makes +10 arithmetically impossible): the primary H4
  metric switches to graded equivalence@1 (+5 pts) with validity@1
  non-decreasing. Either branch also requires repair-rounds strictly
  down AND the divergence guard never tripped at the accepted
  checkpoint. Miss → ship S4/S5 and report GRPO honestly as negative.
- **H5 (panel):** §6 gate numbers. Miss → panel advisory-only forever.
- **H6 (transfer, v2 — estimation, not a binary test):** at test-real
  n = 150–300 the gap-of-gaps is underpowered as a hypothesis test (M6),
  so H6 is reported as a bootstrap point estimate with 95% CI on
  (trained gap − baseline gap), decision rule: proceed if the point
  estimate is ≤ 0 OR the CI includes 0; a CI strictly above 0 (trained
  system reliably overfits synthetic register) → augment D2 with
  mined-register paraphrases, one retry. CI width is itself reported —
  no pretending the sample is bigger than it is.

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
| W12 | Opus | persistent validator service (long-lived JVM, batch mode) + throughput bench — M4 fix; GRPO needs ~16k validations/epoch and process-per-call won't hold | ≥50 validations/sec sustained; drop-in for W1's validity adapters |
| W13 | Sonnet | GRPO plumbing smoke: ONE GRPOTrainer.train() step on a small model with grammar via the `generation_kwargs` structured-outputs pass-through (R2's source-verified but undocumented path) + reason-then-clamp prototype | train step completes with constrained rollouts on RunPod; gates T2 |
| W14 | Sonnet | artifact persistence (M5): push adapters/checkpoints/verdict-caches to HF Hub or release storage; phase-gate artifact manifests committed to git | a fresh container reconstructs any phase gate from git + manifest |

Status: W1 DONE (86/86 tests; real-Scribble smoke 30/30 pass, 60/60
corrupt rejected). W2 DONE (100% corpus round-trip; 1000/1000 samples;
0 parse-level rejections under real Scribble on independent probe).
W3 in progress. Dependencies: W2→{W4,W9,W10}; W3→{W4,W9}; W5→W10;
W6→W7→(T3 decision); W8→H6; W12→W10; W13→T2 gate; W14→T1 gate.

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

Novelty verification (v2, was red-team M7): R1 ran nine query variants
across MPST/Scribble/choreography/session-type × LLM/NL-generation
vocabulary — no NL→MPST prior found. Two nearest misses, named to
pre-empt reviewer comparison: ZipperGen (arXiv:2604.17612, MSC-based
coordination DSL, no NL-translation step — already cited by paper v8)
and arXiv:2511.17977 (NL→formal-protocol, but network I/O grammars, not
MPST). R3 independently confirmed no reusable NL→choreography dataset
exists; VLTL-Bench and FLOW-BENCH are methodology donors only.

---

## 11. v2 revision log — scout & red-team adjudication (2026-07-11)

Sources: R1 (literature), R2 (training stack), R3 (datasets/mining),
R4 (red-team), R5 (fact-sheet), W1/W2 (implementation findings). Every
R4 finding adjudicated; plan sections edited in place above.

| finding | verdict | plan change |
|---|---|---|
| R4-B1 signature doesn't exist; non-bisimilarity ≠ diversity | ACCEPT | §3 D1: bucket-then-verify dedup; preregistered diversity floor (≥8 topology classes, ≤30% each, cell coverage across splits) |
| R4-B2 GRPO reward variance collapse post-SFT → shortest-valid drift | ACCEPT | §2 reward: graded equivalence proxy (ms-cheap), one-sided bloat-only length cap, gradient-starvation halt |
| R4-M1 defeasible divergence guard | ACCEPT | §6: deterministic probe-based substitute; guard never defeasible |
| R4-M2 circular judge calibration | ACCEPT | §6: stratified calibration set, gate binds on non-D2 strata, cross-family seats |
| R4-M3 100-item audit underpowered | ACCEPT | §6: n≥200, Wilson lower-bound ≥0.80 criterion; ~370 documented for an honest 85% |
| R4-M4 JVM throughput at rollout scale | ACCEPT | W12 card: persistent validator service, ≥50/s; W1's measured bisim cost (10–40× validation) reserves full bisim for eval |
| R4-M5 ephemeral-host state loss | ACCEPT | W14 card: artifact persistence + manifests |
| R4-M6 test-real underpowered for gap-of-gaps | ACCEPT | H6 reframed as estimation with CI |
| R4-M7 novelty unverified | RESOLVED | verified empty by R1 (this section) |
| R4-minor stale "100-protocol corpus" | ACCEPT | corrected here and in SEAM_AUTOTRAINING_PLAN.md: 30 corpus skeletons + 19 case protocols on disk |
| R4-minor H4 ceiling collision | ACCEPT | H4 headroom-aware branch |
| R1 format-tax (GCD may hurt semantics) | ACCEPT | H1 promoted to primary two-sided test at T1+T2; reason-then-clamp prototype (W13) |
| R1 effective-votes + aggregator bias | ACCEPT | §5.5: geometric-median aggregation; effective-votes ≥3 gate |
| R1 GRPO successors (DAPO/GSPO/Dr. GRPO) | ACCEPT | §2: adopt TRL-default fixes, no double-patching |
| R2 vLLM API rename + version ceiling + GBNF dialect | ACCEPT | §2 GCD block + pins: `structured_outputs` API, `vllm==0.23.0`, GBNF primary artifact |
| R2 guided decoding inside GRPO = undocumented pass-through | ACCEPT | W13 smoke gates T2 |
| R3 mining shortlist + killed targets | ACCEPT | D5 executes the ranked shortlist (awesome-copilot, VoltAgent, anthropics/skills first); GH-Actions/blind-crawl targets dropped |
| R5 pricing cliff 2026-08-31; Qwen-3B license | ACCEPT | §2 budget note; 3B = iteration only |
