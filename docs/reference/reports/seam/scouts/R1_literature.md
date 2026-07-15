# Scout R1: Literature Sweep — Seam Training Program

**Retrieved 2026-07-11.** Scope: does anything in the 2024–2026 literature CHANGE the
design in `SEAM_TRAINING_EXECUTION_PLAN.md` / `SEAM_AUTOTRAINING_PLAN.md`, or its
grounding table (execution plan §10)? Findings are ranked by impact. Each entry gives
a full citation, 2–3 sentence relevance, and a concrete design implication tagged
**CHANGE** / **CONFIRM** / **EXTEND** against a specific plan section.

---

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [Ranked findings](#ranked-findings)
  - [1. [CHANGE — plan §8 H1, §7 ablations] Grammar-constrained decoding can suppress semantic quality, not just syntax](#1-change--plan-8-h1-7-ablations-grammar-constrained-decoding-can-suppress-semantic-quality-not-just-syntax)
  - [2. [CONFIRM, with caveat — plan §10 novelty claim, §7 benchmark rationale] No direct NL→MPST/Scribble prior work found; nearest neighbors are MSC-based coordination and network-protocol autoformalization, both off-target](#2-confirm-with-caveat--plan-10-novelty-claim-7-benchmark-rationale-no-direct-nlmpstscribble-prior-work-found-nearest-neighbors-are-msc-based-coordination-and-network-protocol-autoformalization-both-off-target)
  - [3. [EXTEND — plan §5, §6] Judge-panel independence is worse than assumed at any panel size; robust aggregation and family-diversity have concrete new evidence](#3-extend--plan-5-6-judge-panel-independence-is-worse-than-assumed-at-any-panel-size-robust-aggregation-and-family-diversity-have-concrete-new-evidence)
  - [4. [EXTEND — plan §2 GRPO hyperparameters, §8 H4] Post-R1 GRPO successors target failure modes the plan's hyperparameters only partially cover](#4-extend--plan-2-grpo-hyperparameters-8-h4-post-r1-grpo-successors-target-failure-modes-the-plans-hyperparameters-only-partially-cover)
  - [5. [EXTEND — plan §5.5 reward-hacking guards, §4 T2 divergence guard] Reward-hacking detection has moved past "watch the aggregate metric"](#5-extend--plan-55-reward-hacking-guards-4-t2-divergence-guard-reward-hacking-detection-has-moved-past-watch-the-aggregate-metric)
  - [6. [CONFIRM — plan §3/A3, D2] Autoformalization back-translation precedent has matured toward "quality/cycle-consistency over volume," matching the plan's round-trip design](#6-confirm--plan-3a3-d2-autoformalization-back-translation-precedent-has-matured-toward-qualitycycle-consistency-over-volume-matching-the-plans-round-trip-design)
  - [7. [CONFIRM — plan §2 GCD tool choice] xgrammar remains the right default backend; llguidance is the credible fallback](#7-confirm--plan-2-gcd-tool-choice-xgrammar-remains-the-right-default-backend-llguidance-is-the-credible-fallback)
- [Empty searches (recorded as evidence, not just absence of results)](#empty-searches-recorded-as-evidence-not-just-absence-of-results)
- [Sources consulted (full list, deduplicated)](#sources-consulted-full-list-deduplicated)
<!-- MENU:END -->

## Ranked findings

### 1. [CHANGE — plan §8 H1, §7 ablations] Grammar-constrained decoding can suppress semantic quality, not just syntax

- **Lee, I. Y., D'Antoni, L., & Berg-Kirkpatrick, T. "The Format Tax." arXiv:2604.03616 (2026-04-04).**
  Shows structured-output requirements (JSON/XML/LaTeX/Markdown) substantially degrade
  reasoning and writing quality across open-weight models, and — the load-bearing
  detail — most of the loss comes from the *prompt-level format instruction itself*,
  before any decoder-level constraint is even applied; constrained-decoding sampling
  bias explains only a fraction of the degradation. Their fix: decouple reasoning from
  formatting (freeform-then-reformat, or extended thinking inside one generation)
  recovers most of the lost accuracy.
- **Banerjee, D., Suresh, T., Ugare, S., Misailovic, S., & Singh, G. "CRANE: Reasoning
  with Constrained LLM Generation." ICML 2025, arXiv:2502.09061.**
  Proves theoretically that constraining outputs to restrictive grammars reduces
  reasoning capability (grammars without reasoning tokens collapse expressivity), then
  shows augmenting the grammar with reasoning-preserving rules recovers up to ~10 pts
  on symbolic reasoning benchmarks vs. naive constrained decoding.
- **"Thinking Before Constraining: A Unified Decoding Framework for LLMs."
  arXiv:2601.07525 (2026-01).** Proposes unconstrained reasoning up to a trigger token,
  then constrained decoding only for the final structured answer — the same
  decouple-then-constrain pattern as Format Tax, independently arrived at.

**Design implication.** The plan's H1 ("semantic validity@1 within ±2 pts of
unconstrained; GCD must not distort content," execution plan §8) is currently a
one-line assumption backed only by the syntax-guarantee argument. This is now a
credible research risk, not a formality: three independent 2025–2026 papers, one
theoretical, document GCD (or format constraints generally) suppressing quality when
applied over the *entire* generation, especially when there's no room for the model to
reason before emitting structured tokens. Two concrete changes to make:
(a) the GCD ablation already listed in execution plan §7 ("Ablations at T2 gate: −GCD")
should be promoted from an afterthought to a **primary, pre-registered H1 sub-test**,
run at T1 as well as T2, not just T2 — measure semantic-validity@1 with GCD on vs. off
at the *same* checkpoint; (b) consider a CRANE/Format-Tax-style decode shape for the
translator: let the model reason freely (or emit a short unconstrained rationale) before
the grammar clamps down on the Scribble body, rather than constraining from token 1 —
this is a training-stack change (a two-segment decode: free preamble + `guided_grammar`
for the protocol body) worth prototyping at W2 rather than assuming vanilla
`guided_grammar=` end-to-end is safe by construction.

### 2. [CONFIRM, with caveat — plan §10 novelty claim, §7 benchmark rationale] No direct NL→MPST/Scribble prior work found; nearest neighbors are MSC-based coordination and network-protocol autoformalization, both off-target

Searches run (all empty of a direct hit): `multiparty session types LLM`,
`Scribble natural language`, `choreography synthesis LLM`, `natural language to session
types arxiv`, `autoformalization multiparty session types choreographic programming
LLM`, `"multiparty session type" "natural language" translation generate protocol
intent`, `"Scribble" "LLM" generate .scr file protocol paper`. None returned a paper
that translates natural-language intent into MPST/Scribble/choreography artifacts.
Two adjacent-but-distinct papers surfaced and are worth citing explicitly as
near-misses in the grounding table, because a careless reader might mistake either for
prior art:

- **"Provable Coordination for LLM Agents via Message Sequence Charts" (ZipperGen),
  arXiv:2604.17612 (2026-04).** Defines a DSL over message sequence charts for LLM
  agent coordination, with syntax-directed projection to deadlock-free local agent
  programs — structurally close to MPST global-type projection and explicitly invokes
  "choreographic programming" philosophy. But it is a *programmer-authored* coordination
  DSL (plus a runtime-planning mode where an LLM emits a workflow at runtime), not an
  NL→formal-protocol *translation* task, and it targets LLM-agent orchestration, not
  Scribble/MPST specifically. It is the closest thing to a competing formalism in the
  agent-coordination space and should be cited in §10 as "related but orthogonal:
  agent-coordination DSL, not autoformalization."
- **Liu, K., Chakraborty, D., Liggesmeyer, A., & Zeller, A. "Synthesizing Precise
  Protocol Specs from Natural Language for Effective Test Generation." arXiv:2511.17977
  (2025-11-22).** A two-stage NL→formal-protocol-spec pipeline (extract protocol
  elements from NL spec text, then synthesize/refine a formal spec), demonstrated on
  POP3 → I/O grammar for test generation. This is architecturally the closest sibling
  to the plan's T (translator) stage — same shape (NL spec → formal artifact, iterative
  refinement) — but the target formalism is network-protocol I/O grammars for
  differential test generation, not MPST/session types, and there is no multiparty
  global-type / projection / well-formedness dimension at all. Cite in §10 as
  methodological precedent for the two-stage NL→formal-spec pipeline shape, distinct
  from the nl2spec/NL2TL/Lang2LTL lineage already listed.

**Design implication.** This strengthens, not just confirms, the plan's claim ("there
is no public NL→MPST/Scribble benchmark," execution plan §7). Recommend adding one
sentence to execution plan §7 or §10 naming ZipperGen and the Liu et al. paper as the
two nearest neighbors and stating explicitly why neither anticipates the novelty claim
— reviewers who know the MSC/choreography literature will independently find ZipperGen,
and pre-empting the comparison is cheaper than being asked for it later.

### 3. [EXTEND — plan §5, §6] Judge-panel independence is worse than assumed at any panel size; robust aggregation and family-diversity have concrete new evidence

- **Kohli, G. (Apple). "Nine Judges, Two Effective Votes: Correlated Errors Undermine
  LLM Evaluation Panels." arXiv:2605.29800 (2026-05).** Tests a 9-judge, 7-model-family
  panel on 3 NLI datasets with 100 human annotations/item; finds the panel carries only
  ~2 independent votes' worth of information (¾ of nominal independence lost to
  correlated errors), panel accuracy trails independent-voting accuracy by 8–22 pts,
  the single best judge matches or beats the full panel, and neither more judges nor
  smarter aggregation closes more than ~11% of the gap even with ground truth available.
  Root cause: judges are correlated, not badly aggregated.
- **"RoPoLL: Robust Panel of LLM Judges." arXiv:2606.30931 (2026-06).** Formalizes PoLL
  under a Huber contamination model and proves arithmetic-mean vote share (the plan's
  current §5.5 aggregator) has *unbounded* bias whenever any one judge fails in a biased
  way, regardless of panel size. Proposes swapping in a geometric-median (a
robust way to combine scores so one extreme judge cannot drag the result)
robust mean
  estimator (tuning-free, optimal 1/2 breakdown point) as a drop-in aggregator fix.
- **"Quantifying and Mitigating Self-Preference Bias of LLM Judges." arXiv:2604.22891
  (2026-05)** and **"Judging the Judges: A Systematic Evaluation of Bias Mitigation
  Strategies in LLM-as-a-Judge Pipelines." arXiv:2604.23178 (2026-04).** Both converge
  on: cross-*family* judge diversity (not just cross-model, cross-temperature, or
  cross-prompt) is the dominant lever for reducing self-preference bias; 4+ independent
  provider families materially outperform same-family multi-seat panels.

**Design implication.** This is genuinely double-edged for the plan and should be
written into §6/§7 explicitly rather than left implicit:
(a) The Apple paper's finding — that scaling panel size or aggregation cleverness
cannot substitute for genuinely decorrelated judges — is actually a *validation* of the
plan's §5.3 view-decorrelation design (J-fwd/J-back/J-probe are different classes with
structurally different failure surfaces, not just re-samples of one judge), which is
exactly the axis the paper says matters. Frame this as confirming evidence for the
"decorrelate views, not just seeds" principle already in the plan (§3.1 of the
autotraining plan).
(b) But it should lower the plan's confidence that adding vote-count alone (k=5–7,
execution plan §5.3) buys much beyond the 3-judge-class minimum; the plan's §6
human-audited-100 gate becomes even more load-bearing given panels may carry
effectively 2–3 "real" votes no matter how k is set — this is a reason *not* to relax
the §6 gate thresholds even under budget pressure.
(c) **Concrete, cheap change**: swap the plan's §5.5 "calibration-weighted vote share"
aggregator for a geometric-median-style robust estimator per RoPoLL — same panel,
tuning-free, and directly addresses the arithmetic-mean unbounded-bias failure mode
RoPoLL proves. Low implementation cost (it's an aggregation function change in
`judge_panel.py`, W6's deliverable), worth adopting before W7 calibration runs.
(d) Elevate non-Anthropic family diversity in §5.3's model mix from "where available"
to a stated priority, given 2026 evidence it's the dominant bias lever, not one option
among several.

### 4. [EXTEND — plan §2 GRPO hyperparameters, §8 H4] Post-R1 GRPO successors target failure modes the plan's hyperparameters only partially cover

- **Yu, Q. et al. (ByteDance Seed). "DAPO: An Open-Source LLM Reinforcement Learning
  System at Scale." arXiv:2503.14476 (2025-03).** Documents and fixes entropy collapse
  and zero-gradient prompts in vanilla GRPO via Clip-Higher (asymmetric clip bounds),
  dynamic sampling (drop prompts with accuracy 0 or 1 — no learning signal), token-level
  policy-gradient loss, and overlong-reward shaping.
- **Zheng, C. et al. (Qwen team). "Group Sequence Policy Optimization." arXiv:2507.18071
  (2025-07).** Identifies that GRPO's token-level importance ratios are a fundamental
  misapplication of importance sampling that introduces noise growing with response
  length, and fixes it with sequence-level importance ratios/clipping; reported as
  necessary for stabilizing MoE RL training in Qwen3.
- **Liu, Z. et al. "Understanding R1-Zero-Like Training: A Critical Perspective."
  arXiv:2503.20783 (2025-03) → Dr. GRPO.** Shows vanilla GRPO's length/std
  normalization terms create a systematic bias toward longer responses (especially
  wrong ones); removing those normalization terms (Dr. GRPO) fixes token efficiency
  without hurting accuracy.

**Design implication.** The plan's GRPO block (execution plan §2: group size 8, lr
2e-6, KL β 0.02, brevity term `−0.1·(len_tokens/1024)`) already has an explicit
brevity penalty, which is a *symptom-level* patch for the same length-bias failure Dr.
GRPO fixes at the *normalization* level — worth checking whether TRL's `GRPOTrainer`
default advantage normalization has the Dr. GRPO-documented bias, because if so the
plan may be fighting the same bias twice (once via reward shaping, once implicitly via
whatever normalization TRL ships) with unclear net effect. Recommend: (a) at W10 (GRPO
run), log response-length trajectories per epoch as a diagnostic regardless of outcome,
since this is now a known, named failure mode with a known fix; (b) if TRL exposes a
Dr.-GRPO-style normalization flag, prefer it over compounding with the brevity term;
(c) DAPO's dynamic-sampling (drop prompts the model always/never solves) is directly
applicable to the plan's curriculum design in T2 and is a cheap, well-evidenced
addition — the plan's "epoch 1 restricted to ≤4-role non-recursive families" curriculum
(execution plan §4) could adopt DAPO-style dynamic filtering *within* each curriculum
stage, not just across stages.

### 5. [EXTEND — plan §5.5 reward-hacking guards, §4 T2 divergence guard] Reward-hacking detection has moved past "watch the aggregate metric"

- **Deng, W. et al. "Directional Alignment Mitigates Reward Hacking in Reinforcement
  Learning for Language Models." arXiv:2605.25189 (2026-05).** Shows reward-hacking
  runs exhibit measurably larger drift in the dominant singular directions of parameter
  updates than clean runs, and that constraining gradients to a trusted reference
  subspace ("trusted-direction projection") delays shortcut exploitation.
- **Deshpande, D., Kannappan, A., & Qian, R. "Benchmarking Reward Hack Detection in
  Code Environments via Contrastive Analysis" (TRACE benchmark). arXiv:2601.20103
  (2026-01).** 517 human-verified trajectories, 54-category exploit taxonomy; shows
  models (used as hack-detectors) do much worse on *semantically* contextualized reward
  hacks than syntactically obvious ones (63% vs. much lower without reasoning mode) —
  relevant analog: a translator emitting a validator-passing but semantically-empty
  protocol is exactly a "semantically contextualized" hack, the harder class to catch.

**Design implication.** The plan's existing divergence guard (execution plan §4 T2:
"dev validity may rise only if dev panel score... does not fall >2 pts, checked every
200 steps") is an aggregate-metric-level guard, which is the right instinct but coarse
relative to what's now available. This is an EXTEND, not a CHANGE: the aggregate
validity/faithfulness divergence check should stay as the primary automatic halt
(it's cheap, already scoped, doesn't require new tooling), but the TRACE finding
motivates explicitly weighting a *subset* of the calibration set (§6) toward
semantically-plausible-but-wrong mutants (which the plan's D3 near-miss mutants already
produce) when computing the divergence-guard's panel-score probe set, rather than a
random probe sample — cheap change, reuses existing assets, addresses a named blind
spot (aggregate detectors are worse at exactly this hack class).

### 6. [CONFIRM — plan §3/A3, D2] Autoformalization back-translation precedent has matured toward "quality/cycle-consistency over volume," matching the plan's round-trip design

- **"Lean-ing on Quality: How High-Quality Data Beats Diverse Multilingual Data in
  AutoFormalization." arXiv:2502.15795 (2025-02).** High-fidelity, curated
  informalize-then-backtranslate corpora outperform larger, more heterogeneous ones for
  Lean4 autoformalization — a direct precedent for prioritizing round-trip-verified
  pairs over raw volume.
- **"Improving Lean4 Autoformalization via Cycle Consistency Fine-tuning."
  arXiv:2603.24372 (2026-03).** Adds a compiler-feedback + critic-model loop that
  optimizes for semantic round-trip fidelity rather than compilation success alone —
  i.e., trains *toward* the round-trip metric, not just filters by it.

**Design implication.** This confirms the plan's D2 round-trip-probe design (back-
translate → independent re-translation → E5-equivalence check → accept/quarantine to
`hard/`) is aligned with where the field has converged (execution plan §3, autotraining
plan §4.1). One extension worth flagging for T3/A5: the cycle-consistency-fine-tuning
paper trains the model to directly optimize round-trip fidelity via RL, which is a
natural, low-effort *additional* reward term for T2/T3 beyond "filter SFT data by
round-trip" — i.e., the plan could add a round-trip-fidelity term to the RLVR reward
in §2, not just use it as a D2 data filter. Flag as a candidate reward term for the
planner to consider alongside the existing validity/bisim/faithfulness terms; not
urgent enough to require it before T2.

### 7. [CONFIRM — plan §2 GCD tool choice] xgrammar remains the right default backend; llguidance is the credible fallback

Community benchmarking through 2026-03 (vLLM/SGLang/TensorRT-LLM ecosystem posts,
JSONSchemaBench-style comparisons) confirms **xgrammar** is the default structured-
generation backend across all three major serving frameworks as of March 2026, with
sub-40-microsecond per-token overhead; **llguidance** (Rust, memory-optimized tokenizer
trie + lazy lexer + Earley parser) is competitive and sometimes wins on repeated-schema
caching scenarios; **Outlines**' FSM-compilation approach struggles with complex
schemas (compile times from 40s to 10+ minutes) and has the lowest compliance rate in
JSONSchemaBench-style tests; **SynCode** remains a research-grade PDA-based
alternative. No new tool has displaced xgrammar as of this sweep.

**Design implication.** No change to execution plan §2's choice of "vLLM guided
decoding (xgrammar backend)." Worth adding one line to §10's grounding table noting
llguidance as the documented fallback if xgrammar shows Scribble-grammar-specific
pathologies at W2 (corpus round-trip / 1k-sample grammar test), since llguidance's
lazy-lexer design may handle recursive/nested Scribble grammar constructs differently
than xgrammar's vocabulary-partitioning approach — worth a quick compile-time/coverage
comparison at W2 if xgrammar shows any friction, rather than assuming xgrammar is
uniquely correct.

---

## Empty searches (recorded as evidence, not just absence of results)

The following queries were run specifically to stress-test the plan's novelty claim
(execution plan §7: "there is no public NL→MPST/Scribble benchmark") and turned up
**no direct hit** — no paper that translates natural-language intent into multiparty
session types, Scribble protocols, or choreography specifications via LLM:

- `multiparty session types LLM natural language generation`
- `Scribble protocol natural language synthesis LLM`
- `choreography synthesis LLM` (returned only dance-choreography false positives —
  music/motion generation, unrelated field entirely)
- `natural language to session types arxiv`
- `autoformalization multiparty session types choreographic programming LLM`
- `"session types" "large language model" natural language protocol generation`
- `"multiparty session type" "natural language" translation generate protocol intent`
- `"Scribble" "LLM" OR "large language model" generate .scr file protocol paper`
- `Scribble global protocol synthesis natural language description "choreography" 2026
  paper`

The two closest results in any of these searches (ZipperGen, arXiv:2604.17612, and
Liu et al., arXiv:2511.17977 — both discussed in finding #2 above) are each one
dimension short of the plan's task: one has the right formalism family (MSC, adjacent
to MPST) but no NL-translation step; the other has the right task shape (two-stage
NL→formal-protocol pipeline) but the wrong formalism (network I/O grammars, not
multiparty session types). Neither anticipates a global-type-with-projection target.
This is meaningful absence, not a failure to search hard enough — the queries covered
the term-of-art vocabulary (MPST, Scribble, choreography, session types) crossed with
every plausible LLM/NL-generation phrasing, spanning venues and preprint servers
through 2026-07.

---

## Sources consulted (full list, deduplicated)

- Lee, D'Antoni, Berg-Kirkpatrick. "The Format Tax." arXiv:2604.03616.
- Banerjee, Suresh, Ugare, Misailovic, Singh. "CRANE: Reasoning with Constrained LLM
  Generation." ICML 2025, arXiv:2502.09061.
- "Thinking Before Constraining: A Unified Decoding Framework for LLMs."
  arXiv:2601.07525.
- "Provable Coordination for LLM Agents via Message Sequence Charts" (ZipperGen).
  arXiv:2604.17612.
- Liu, Chakraborty, Liggesmeyer, Zeller. "Synthesizing Precise Protocol Specs from
  Natural Language for Effective Test Generation." arXiv:2511.17977.
- Kohli, G. "Nine Judges, Two Effective Votes: Correlated Errors Undermine LLM
  Evaluation Panels." arXiv:2605.29800 (Apple).
- "RoPoLL: Robust Panel of LLM Judges." arXiv:2606.30931 (Amazon Science).
- "Quantifying and Mitigating Self-Preference Bias of LLM Judges." arXiv:2604.22891.
- "Judging the Judges: A Systematic Evaluation of Bias Mitigation Strategies in
  LLM-as-a-Judge Pipelines." arXiv:2604.23178.
- "A Finite-Calibration Regime Map for LLM Judge Panels." arXiv:2606.01034 (Zhu & Rao,
  Sun Yat-sen University) — cross-checked as background on judge-panel calibration
  methodology; scalar/reliability aggregation wins most real-dataset regime cells,
  consistent with keeping the plan's calibration-weighted vote share simple rather than
  building a joint interaction table, except where the calibration set later shows
  strong judge-class interactions.
- Yu et al. (ByteDance Seed). "DAPO: An Open-Source LLM Reinforcement Learning System
  at Scale." arXiv:2503.14476.
- Zheng et al. (Qwen team). "Group Sequence Policy Optimization." arXiv:2507.18071.
- Liu, Z. et al. "Understanding R1-Zero-Like Training: A Critical Perspective"
  (Dr. GRPO). arXiv:2503.20783.
- Deng et al. "Directional Alignment Mitigates Reward Hacking in Reinforcement
  Learning for Language Models." arXiv:2605.25189.
- Deshpande, Kannappan, Qian. "Benchmarking Reward Hack Detection in Code Environments
  via Contrastive Analysis" (TRACE). arXiv:2601.20103.
- "Lean-ing on Quality: How High-Quality Data Beats Diverse Multilingual Data in
  AutoFormalization." arXiv:2502.15795.
- "Improving Lean4 Autoformalization via Cycle Consistency Fine-tuning."
  arXiv:2603.24372.
- "Beyond Surface-Level Similarity: Hierarchical Contamination Detection for Synthetic
  Training Data in Foundation Models." arXiv:2511.17602 — cross-checked as precedent
  for the plan's D4 EFSM-bisimulation-signature split hygiene; confirms structural/
  semantic-level dedup (what the plan already does) is the right response to
  surface-level contamination detection being insufficient for synthetic corpora.
- xgrammar / llguidance / Outlines / SynCode comparison: vLLM/SGLang guided-decoding
  benchmarking posts and XGrammar paper, arXiv:2411.15100, current as of 2026-03.
