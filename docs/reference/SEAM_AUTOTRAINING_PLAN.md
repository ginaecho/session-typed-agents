# Auto-Training the Translation Seam — plan & strategy proposal

**Scope.** The S1→S2 seam (natural-language intent → Scribble-validated global
protocol G) is today an LLM-drafts / validator-rejects / human-endorses loop.
This document proposes how to make that seam **self-improving**: (A) a
verifiable-reward training program for *validity* (does Scribble accept G?),
(B) an automated instrument for *faithfulness* (does G describe what the user
actually wants?), and (C) a corpus-generation design — synthetic and mined
from real-world repositories — that feeds both.

Status: proposal. Companion to paper v8 §7 ("The seam is trainable, not
merely open") and to the pending E5 cells. The executable version — stacks,
hyperparameters, judge-isolation mechanics, preregistered go/no-go gates,
and worker task cards — is `SEAM_TRAINING_EXECUTION_PLAN.md`.

---

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [0. The improved paragraph (drop-in)](#0-the-improved-paragraph-drop-in)
- [1. Problem statement: two axes, only one currently instrumented](#1-problem-statement-two-axes-only-one-currently-instrumented)
- [2. Part A — the validity ladder (verifiable rewards, ascending effort)](#2-part-a--the-validity-ladder-verifiable-rewards-ascending-effort)
- [3. Part B — faithfulness: memoryless judge panels, voting](#3-part-b--faithfulness-memoryless-judge-panels-voting)
  - [3.1 Design principle: independence is the whole point](#31-design-principle-independence-is-the-whole-point)
  - [3.2 Three judge classes (vote in one panel)](#32-three-judge-classes-vote-in-one-panel)
  - [3.3 Aggregation and thresholds](#33-aggregation-and-thresholds)
  - [3.4 Calibrating the panel itself (meta-eval, fully automatic)](#34-calibrating-the-panel-itself-meta-eval-fully-automatic)
- [4. Part C — corpus generation](#4-part-c--corpus-generation)
  - [4.1 Synthetic split (generator-owned; training)](#41-synthetic-split-generator-owned-training)
  - [4.2 Real-world split (mined; evaluation-first)](#42-real-world-split-mined-evaluation-first)
- [5. The auto-training loop, assembled](#5-the-auto-training-loop-assembled)
- [6. Phasing](#6-phasing)
- [7. Risks / open questions](#7-risks--open-questions)
<!-- MENU:END -->

## 0. The improved paragraph (drop-in)

Replacement for the "missing on-ramp" sentence in the review notes / §7
discussion:

> STJP's S1→S2 loop (LLM drafts Scribble from intent; the validator rejects
> with counterexamples until a draft passes; the human endorses G) is the
> missing on-ramp — and it is not merely open but *trainable*, because the
> target side of the seam is already fully mechanized. The Scribble grammar,
> the well-formedness validator, and the E5 EFSM-bisimulation scorer
> (validated 300/300) stack into a three-level verifier hierarchy — parses /
> is safe / is behaviorally equivalent to gold (a known-correct reference
> protocol) — each level deterministic,
> counterexample-producing, and free at training time. That is precisely the
> setup the ML community is currently converging on (verifier-guided
> generation; RL from verifiable rewards), with one advantage over the usual
> code-and-math targets: our reward is not a unit test that samples behavior
> but a total checker over *all* paths. The live evidence is already in the
> repo — four consecutive rejected drafts before the fifth passed on the
> banking case — which is exactly one trajectory of the repair curriculum
> below. What the verifier stack cannot see is *faithfulness*: a protocol can
> be perfectly valid and perfectly wrong about what the user meant. §3 of
> this plan proposes the missing instrument — panels of memoryless,
> non-communicating judge agents voting on intent–protocol fit, hardened by
> compiling intent fragments into machine-checkable probes over G's EFSM.

---

## 1. Problem statement: two axes, only one currently instrumented

| axis | question | verifier | status |
|---|---|---|---|
| **Validity** | does G parse, project, avoid deadlock, merge cleanly? | Scribble (`compiler/validator.py`) + refinement checker | total, deterministic, counterexample-producing — DONE |
| **Equivalence** | is G behaviorally identical to a known-gold G*? | E5 EFSM-bisimulation scorer | total, deterministic — DONE (300/300), but requires a gold |
| **Faithfulness** | does G mean what the *user* meant? | human endorsement only | the gap this plan closes |

Speed and token-efficiency of intent→G matter (fewer repair rounds, fewer
tokens per accepted protocol), and Part A addresses them. But the harder and
more novel problem is the third row: **when no gold protocol exists — i.e.,
in every real deployment — nothing currently checks that the validated G is
the *right* G.** Validity is a property of G alone; faithfulness is a
property of the (intent, G) pair. A trained translator that maximizes
validity rewards without a faithfulness instrument would learn to emit
*easy* protocols, not *intended* ones — the classic reward-hacking failure.
Both axes therefore have to enter the reward, and only one of them is free.

---

## 2. Part A — the validity ladder (verifiable rewards, ascending effort)

The target side is fixed and mechanized (MPST — multiparty session types,
the type-theory rules Scribble is built on — plus Scribble's grammar,
validator, and bisimulation scorer). Everything below is training-side only.

**A1. Grammar-constrained decoding (zero training).**
Scribble's surface grammar is small (`compiler/nuscr_syntax.py` already
encodes it). Constrained decoding guarantees every sampled draft *parses*,
deleting the syntactic half of repair rounds outright. Side benefit for the
paper: first-draft validity then measures **semantic** well-formedness only —
a cleaner number than the current syntax-and-semantics blend.

**A2. Best-of-n with the validator as filter (zero training; run before
submission).**
Sample k drafts, keep the first that validates. Embarrassingly cheap, and it
directly fills the three pending E5 cells (first-draft validity, repair
rounds, guard co-emission) with measured numbers. **This is the single
highest-leverage experiment left: it converts a declared limitation into a
result.** Report validity@1 and validity@k with k ∈ {1, 5, 10, 25}.

**A3. Back-translation for training data (SFT — supervised fine-tuning:
training on labeled correct examples, as opposed to reinforcement learning).**
We already own the data generator: the protocol corpus (30 skeletons in
`experiments/cases/_corpus` + 19 named-case protocols) plus the mutation
operators (`integration_stress.py`, `s2_mutation`) produce unlimited
*valid* protocols; an LLM back-translates
each into a natural-language intent; that yields (intent, gold-protocol)
pairs for free, scored end-to-end by the E5 equivalence checker. Fine-tune a
small translator; the scorer *is* the eval. This is the standard
autoformalization recipe (NL2LTL / NL2Spec lineage) transplanted to a target
whose checker is total and counterexample-producing rather than sampled.

**A4. Repair training from mutants (SFT on the loop we already observed).**
The mutation operators define the validator's error space. Training pairs
(broken protocol + validator counterexample → fixed protocol) teach exactly
the repair loop live drafting exhibited (four rejections → pass, banking).
The counterexample goes *in the prompt*: the model learns to read the
validator, not to guess.

**A5. RLVR (the ceiling).**
Policy = the translator (with A1 decoding); reward per sample =
`w_v·validates + w_e·bisim-to-gold (synthetic split) + w_f·faithfulness
(Part B, real split) − w_t·token-cost`. GRPO (Group Relative Policy
Optimization, a reinforcement-learning method that scores each sample
against the average of a sampled group instead of a separate value model)
-style group sampling reuses the
A2 harness unchanged — best-of-n *is* the rollout collector. A3/A4 checkpoints
are the initialization. Reward-hacking guards in §5.

---

## 3. Part B — faithfulness: memoryless judge panels, voting

### 3.1 Design principle: independence is the whole point

Faithfulness has no deterministic checker, so we approximate one with a
panel of LLM judges — under strict isolation:

- **No shared memory.** Judges never see each other's outputs, the drafting
  trace, the repair history, or prior verdicts. Vote aggregation only helps
  when errors are (approximately) independent — a Condorcet argument; shared
  context correlates errors and silently converts a 7-judge panel into one
  judge with seven rubber stamps.
- **No memory at all.** Each judgment is a fresh, stateless call: fixed
  prompt template + (view of the case) + sampled temperature. Statelessness
  buys reproducibility, cacheability, and immunity to drift across a corpus
  run — and it removes the anchoring channel by construction.
- **Decorrelate views, not just seeds.** Same-model same-prompt sampling
  gives weak independence. Stronger: different judge *classes* (below),
  different model families where available, and paraphrase-perturbed intents.

### 3.2 Three judge classes (vote in one panel)

**J-fwd — forward checklist judges.** Input: (intent, pretty-printed G).
Output: structured verdict — roles covered / orderings honored / prohibited
interactions absent / branches meaningful — plus a binary fit vote. Cheap;
catches gross mistranslation; weakest against confirmation bias.

**J-back — blind back-translation judges (round-trip).** Input: **G only** —
the judge never sees the original intent, so it cannot be led. It writes the
intent G actually encodes; a separate stateless comparator (or an entailment
model) scores reconstructed-intent vs original-intent. Mirrors the A3 data
recipe, which means every training pair doubles as a panel-calibration pair.
This is the strongest decorrelator in the panel.

**J-probe — compiled behavioral probes (the mechanizable fraction).** An LLM
translates intent fragments into concrete checkable queries — "can Auditor
receive the report before Approver signs?", "does every rejected loan end in
a notification to Customer?" — and those queries are answered *not by an
LLM* but by reachability/trace checks over G's EFSM, i.e., exactly the
machinery the Critic already runs over `.policy` sidecars
(`critic/critic.py`, static-over-every-path mode). The LLM is only the
front-end translator of probes; the verdict is deterministic. Every probe
that compiles moves a piece of faithfulness from the fuzzy column into the
verifiable column — and failed probes come with counterexample traces, which
feed the repair curriculum (A4) with *faithfulness* counterexamples, not
just validity ones.

### 3.3 Aggregation and thresholds

- Panel of k = 5–7 (odd), class-mixed. Faithfulness score = weighted vote
  share; J-probe failures are veto-strength (a deterministic counterexample
  outranks any vote).
- **Two operating points.** Training reward: fractional vote share (dense
  signal). Deployment / endorsement gate: strict — e.g., ≥ 6/7 votes AND
  zero probe failures; anything between goes to the human, with the
  dissenting judges' verdicts attached (the panel's disagreement *is* the
  explanation).
- Judges may abstain ("intent underspecified here"); abstentions route to
  the human as ambiguity findings, not as noise.

### 3.4 Calibrating the panel itself (meta-eval, fully automatic)

The mutation operators give a free discrimination test: a faithful panel
must score (intent, gold G) above (intent, mutated-G) for
behavior-changing mutations. Run the panel over corpus golds vs. their
single-mutation variants → ROC/AUC per judge class and for the ensemble;
pick vote thresholds from the curve. Then validate against the human
endorsements already collected in live drafting. A panel that cannot
separate golds from near-miss mutants is not entitled to be a reward signal
— this gate comes *before* any RLVR run that uses `w_f > 0`.

---

## 4. Part C — corpus generation

### 4.1 Synthetic split (generator-owned; training)

- Base: protocol corpus (30 skeletons + 19 case protocols) × mutation
  operators → unlimited valid
  protocols; grow structural diversity along measured axes (roles, branch
  depth, recursion, guards) and by composition via `compiler/incremental.py`
  (child sub-protocol insertion) — compositional cases exceed what anyone
  hand-writes.
- Back-translate each to intent (A3); score round-trips with the E5 checker;
  keep paraphrase clusters (3–5 intents per protocol) so the translator
  learns intent variance, not one verbalization style.
- Mutants provide: repair pairs (A4), panel calibration pairs (§3.4), and
  hard negatives for J-fwd (near-miss decoys that punish leniency bias).

### 4.2 Real-world split (mined; evaluation-first)

This is the distribution-shift test the synthetic split cannot give, and the
pipeline is mostly *already implemented* as the bottom-up entry point:

1. **Mine.** Harvest real agent skills from public repos — `.claude/skills/
   **`, `SKILL.md`, CLAUDE.md/AGENTS.md role sections, multi-agent framework
   configs (CrewAI/AutoGen/LangGraph role+handoff definitions), CI/release/
   review pipelines — with permissive-license filtering and dedup.
   Development-workflow cases (code review, triage, release) are the
   priority, matching the existing `code_review` case.
2. **Recover the intent.** Most skill artifacts *ship with their intent
   already written by a human* — description frontmatter, "when to use"
   sections, READMEs. Where present, that text is a gold intent (human-
   authored, zero LLM involvement). Where absent, an LLM reverse-engineers
   the intent from the skill body — marked silver, evaluation-only.
3. **Formalize.** Skills → per-role LocalTypes via the existing
   `generation/skill_compactor.py`, → deterministic global synthesis via
   `compiler/global_synthesizer.py` (LLM fallback for out-of-fragment
   shapes), → Scribble validation. Note what this buys: G is derived from
   the *skill bodies* while the intent came from the *skill descriptions* —
   two independent human artifacts.
4. **Compare.** Run the §3 panel on (recovered intent, validated G). Three
   outcomes, all valuable: *agree* → a gold real-world (intent, G) pair for
   the benchmark; *disagree with probe counterexample* → either a hard
   training example or a real skills-vs-docs inconsistency in the wild (the
   trade_deadlock story found in nature — publishable in its own right);
   *underspecified* → measured evidence of how ambiguous real intents are,
   which motivates the endorsement step in the paper.
5. **Split discipline.** Train on synthetic back-translations (4.1);
   evaluate on mined real intents. Never the reverse — the mined split's
   entire value is that no model in the loop generated it.

---

## 5. The auto-training loop, assembled

```
                     ┌────────────── corpus (4.1 synthetic ∪ 4.2 mined) ─────────────┐
                     ▼                                                               │
 intent ──► translator (A1 grammar-constrained) ──► k drafts                         │
                     │                                                               │
                     ├─ Scribble validate ──► reject+counterexample ─► repair model ─┤ (A4 pairs)
                     │                                                               │
                     ├─ gold exists?  ── yes ──► E5 bisimulation score               │
                     │                └─ no ───► §3 panel (J-fwd, J-back, J-probe)   │
                     ▼                                                               │
        keep winning trajectories ──► SFT (expert iteration)  ──►  RLVR (A5) ───────┘
```

- **Cadence.** Expert-iteration first (STaR-style: sample → filter by
  verifier stack → SFT on survivors, including repair trajectories); RLVR
  only after A3/A4 checkpoints plateau.
- **Reward-hacking guards.** (i) The panel is the only stochastic reward
  term — freeze judge prompts and judge model per epoch; (ii) monitor the
  validity/faithfulness divergence — a rising validity score with flat panel
  score is the hacking signature (emitting easy protocols); (iii) hold out a
  human-endorsed set that no reward term ever touches; (iv) J-probe vetoes
  are non-negotiable in the gate even when vote share is high.
- **Metrics (standing).** First-draft validity (semantic-only, post-A1);
  repair rounds to validity; tokens-to-accepted-protocol; equivalence-to-gold
  (synthetic); panel score + human-agreement rate (real); probe compile rate
  (how much of faithfulness got mechanized); mined-split transfer gap.

## 6. Phasing

| phase | deliverable | cost | blocks |
|---|---|---|---|
| **P0** (pre-submission) | A1 + A2: fill the three pending E5 cells | hours of API sampling | nothing — run now |
| **P1** | 4.1 corpus build-out + §3 panel implemented + §3.4 calibration report | days | P0 harness |
| **P2** | mined real-world split (4.2), first intent-vs-G comparison report | days–weeks (mining + license filter) | skill_compactor hardening |
| **P3** | A3 + A4 SFT translator/repair checkpoints, eval on mined split | GPU-days (small model) | P1 |
| **P4** | A5 RLVR with composite reward; benchmark + panel released | weeks | P1 calibration gate passed |

## 7. Risks / open questions

- **Panel validity ceiling.** If §3.4 AUC is mediocre, faithfulness reward
  stays advisory (`w_f` small) and the human gate stays; the plan degrades
  gracefully to A1–A4, which are verifier-only.
- **Probe coverage.** Unknown fraction of real intents compiles to EFSM
  probes; measure probe-compile rate early (P1) — it is itself a finding.
- **Mining yield.** Real skills may under-specify interaction structure
  (prose about *what*, silent on *who-talks-to-whom*); the skill compactor's
  compatibility check tells us the yield fast, and low yield is evidence for
  the paper's thesis (hand-written skills under-determine coordination).
- **Judge-family monoculture.** If all judges share one model family with
  the translator, self-preference inflates votes; mitigation is class
  diversity (J-back and J-probe are structurally immune: one never sees the
  intent, the other's verdict is deterministic).
