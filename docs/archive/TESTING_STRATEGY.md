# STJP Testing Strategy — a fair benchmark for what STJP actually claims

**2026-06-18.** A ground-up rethink of *how* to benchmark STJP fairly, written
after several rounds of muddy/confounded results taught us where the traps are.
This supersedes the framing in `BENCHMARK_DESIGN.md` (kept for history) on the one
point that matters most: **every comparison must change exactly one variable.**

---

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [1. What STJP actually claims (be precise, or the test is meaningless)](#1-what-stjp-actually-claims-be-precise-or-the-test-is-meaningless)
- [2. The fairness rules (lessons paid for in muddy runs)](#2-the-fairness-rules-lessons-paid-for-in-muddy-runs)
- [3. The design: two axes, four task shapes](#3-the-design-two-axes-four-task-shapes)
  - [Two axes (never cross them in one comparison)](#two-axes-never-cross-them-in-one-comparison)
  - [Four task shapes (each isolates one claim)](#four-task-shapes-each-isolates-one-claim)
- [4. Audit of the current arms — which comparisons are fair](#4-audit-of-the-current-arms--which-comparisons-are-fair)
- [5. How to make the two current demos stronger](#5-how-to-make-the-two-current-demos-stronger)
- [6. The headline table this strategy produces (per claim, per model)](#6-the-headline-table-this-strategy-produces-per-claim-per-model)
- [7. Priority to execute (smallest fair win first)](#7-priority-to-execute-smallest-fair-win-first)
<!-- MENU:END -->

## 1. What STJP actually claims (be precise, or the test is meaningless)

STJP takes a natural-language intent → an LLM drafts a global interaction protocol
→ **Scribble statically checks it** (well-formedness, projectability,
deadlock-freedom) → projects it into one **local contract per agent** → optional
runtime **monitor/gate**. Four distinct value claims, each needing its own test:

| # | Claim | The differentiator | A win looks like |
|---|---|---|---|
| **D** | **Deadlock-freedom by static check** | Only a global formal checker catches an interaction deadlock; per-agent review and runtime monitors cannot | unchecked specs deadlock at some rate; checked specs never do |
| **I** | **Static interaction correctness** (beyond deadlock: inconsistent choice, non-projectability, value-dependent branch) | Caught at *design time*, before any token is spent | checker rejects bad protocols; unchecked ones fail at runtime |
| **T** | **Token saving** | A compiled per-agent contract removes coordination deliberation + shrinks prompts | same task completed for fewer tokens |
| **W** | **Time / wall-clock saving** | Fewer rounds, less deliberation | same task completed faster |

These are *separate*. A benchmark that reports one number per arm and hopes it
speaks to all four is the original sin. Each claim gets its own task shape, its own
control, and its own metric.

## 2. The fairness rules (lessons paid for in muddy runs)

1. **One variable per comparison.** The big past mistake: comparing "global text"
   (arm B, run under a GroupChat *orchestrator*) against "local types" (arm C, run
   under a *decentralized round-robin*). That confounds *spec format* with
   *runtime*; B's wins were the orchestrator's doing, not the format's
   (`WHY_B_MATCHES_C_ANALYSIS.md`). **Fix:** hold the runtime constant when varying
   the spec, and hold the spec constant when varying the runtime.
2. **Separate "did it work" from "what did it cost."** Use *success-critical*
   tasks to test D and I (completion is the metric), and *completable* tasks to
   test T and W (everyone finishes; tokens/time is the metric). Never read
   efficiency off a task half the arms fail — that is cost-of-failure, not
   cost-of-coordination.
3. **Robust, structural goals — never magic words.** A goal coded as
   `"pass" in payload` failed agents who completed the task but wrote "approved
   for delivery." Use existence/numeric/role-pair predicates, or an LLM judge with
   a frozen prompt and a hand-audited sample. (Bug found 2026-06-17.)
4. **Correct, theory-faithful monitor.** The monitor must allow concurrent
   interleavings on different channels (asynchronous MPST); an over-strict monitor
   manufactures false violations (fixed 2026-06-17, `monitor_async_fix`).
5. **Report every model in scope.** STJP's value is *model-dependent* — larger on
   weaker models, smaller on frontier models. Show the trend (gpt-4o AND gpt-5.4),
   never a single model presented as universal.
6. **Don't rig the failure.** For the deadlock claim, do not only hand-write a
   spec that deadlocks (a skeptic calls it rigged). *Also* let an LLM author the
   per-agent specs from the intent and report the **rate** at which unchecked
   authoring produces a deadlock/unsafe protocol — that is the honest risk number.
7. **State the control explicitly.** Every result line should name: the task, the
   one variable, what is held constant, and the metric. If you can't, it isn't a
   clean comparison.

## 3. The design: two axes, four task shapes

### Two axes (never cross them in one comparison)
- **Axis SPEC** — what each agent is given: `intent-only` · `global-text` ·
  `local-verbose` · `local-lean` · `local+gate` · `unchecked-circular`.
- **Axis RUNTIME** — how agents are driven: `orchestrated` (group chat) ·
  `decentralized` (round-robin) · `efsm-scheduled` (projection drives who acts).

To test SPEC effects → fix RUNTIME = decentralized (the realistic "autonomous
agents talking to each other" setting). To test RUNTIME effects (the scheduler's
token saving) → fix SPEC = local-lean.

### Four task shapes (each isolates one claim)
- **Deadlock-prone** (a circular dependency hidden in plausible local rules) →
  Claim **D**. Metric: completion + cost-while-stuck. *(case: `trade_deadlock`)*
- **Coordination-heavy, completable** (a pipeline everyone can finish) → Claims
  **T/W**. Metric: tokens & time to goal. *(case: `report_pipeline`)*
- **Safety-critical** (an irreversible action that must be authorized first) →
  Claim **I** (value-dependent correctness, ordering, choice guards). Metric:
  disaster rate / critical-goal completion. *(cases: `finance`, `banking`)*
- **Scale** (many roles, deep nesting, a big protocol) → the projection/context
  benefit of **T** at scale, and where `global-text` should break down. Metric:
  tokens/call & completion vs protocol size. *(to build)*

## 4. Audit of the current arms — which comparisons are fair

| comparison | varies | holds constant | verdict |
|---|---|---|---|
| `unchecked_skills` vs `spec_llmvalid` (trade_deadlock) | checked vs not | intent, runtime (round-robin), model, format | **FAIR** — clean test of D |
| `bare` vs `spec_llmvalid` vs `min_llmvalid` (report_pipeline) | spec format | runtime (round-robin), model, task (all 100%) | **FAIR** — clean test of T/W |
| `spec_llmvalid` vs `min_llmvalid` | contract verbosity | everything else | **FAIR** — lean-contract saving |
| `spec_llmvalid` vs `spec_llmvalid_gate` | + enforcement | runtime, spec, model | **FAIR** — value of the gate |
| `maf_groupchat_llmvalid` (B) vs `spec_llmvalid` (C) | spec format **AND runtime** | model | **CONFOUNDED** — do not use for "global vs local" |
| `global_decentralized` vs `spec_llmvalid` | spec format only | runtime (both round-robin), model | **FAIR** — the *corrected* global-vs-local test |
| any arm vs `maf_groupchat` (intent) | spec **AND** vocabulary/scoring | — | use role-pair scoring; treat as floor only |

**Conclusion:** keep the decentralized (round-robin) family as the clean SPEC axis
(`bare`/`unchecked_skills` · `global_decentralized` · `spec` · `min` · `gate`). The
MAF-orchestrated arms belong to the RUNTIME axis and must only be compared to each
other or to a same-spec decentralized arm — never used to argue "global vs local."

## 5. How to make the two current demos stronger

**Deadlock (D) — make it un-rig-able and visceral.**
1. Add the **authoring-risk number**: run `draft_llm_protocols` on the deadlock
   intent N times; report how often the *unchecked* LLM-authored protocol contains
   a deadlock/unsafe structure (we already saw it happen), vs Scribble catching
   100%. This converts "I hand-wrote a deadlock" into "unchecked authoring produces
   deadlocks at rate X; the checker eliminates them."
2. Measure the **agentic cost-while-stuck over time** — tokens/calls accumulating
   during the deadlock (the "meter running" — not a cheap hang). Plot it.
3. Re-skin to a recognizable domain in the narrative (accounts-payable / supplier
   payment: a Payments agent and a Fulfilment agent, each with a sound control,
   composed without a global check). *(done in the doc story; optionally rename
   roles.)*

**Token/time (T/W) — make the saving provably scale and beat the real baseline.**
1. Add the **orchestrated baseline** (how teams build today) to the same task, so
   the compiled contract is shown to beat *both* intent-only-decentralized and the
   orchestrator — not just the weakest baseline.
2. **Scale the task** (5 → 8 → 12 roles, longer chains): show tokens-to-goal for
   `global-text` growing super-linearly (re-reads the whole protocol each turn)
   while `local-lean` stays flat — the projection's scale advantage, which the
   tiny cases cannot show.
3. **Wire the real LLM into the EFSM scheduler** (`delm_runner`, currently an
   oracle) and measure tokens/calls vs round-robin at equal completion — the
   second efficiency lever (−83% *calls* in the oracle smoke) quantified end-to-end.
4. Report **tokens and call-count** as the primary efficiency metrics; wall-clock
   only as secondary (API latency is noisy).

## 6. The headline table this strategy produces (per claim, per model)

Instead of one muddy matrix, four clean one-line claims:

- **D:** "Unchecked LLM-authored specs deadlocked in X/N drafts; every Scribble-
  checked spec was deadlock-free. When a deadlock occurs, agents burn ~Y tokens for
  zero output." (gpt-4o and gpt-5.4)
- **I:** "Scribble rejected Z classes of interaction bug at design time (deadlock,
  inconsistent choice, non-projectable, value-wrong branch); unchecked agents hit
  them at runtime, failing the goal."
- **T:** "On a task all settings complete, the projected lean contract reached the
  goal for 1/k the tokens of intent-only and global-text; the gap grows with
  protocol size." (both models)
- **W:** "...and in 1/m the wall-clock / LLM calls."

Each line names its task, its single variable, and its metric — which is the whole
point.

## 7. Priority to execute (smallest fair win first)

1. `global_decentralized` vs `spec`/`min` on a completable task, both models —
   the *corrected* global-vs-local comparison (fixes the historical confound).
2. Deadlock authoring-risk number (re-run drafting N×, report deadlock rate).
3. Scale task (8–12 roles) for the token-saving-scales claim.
4. Real-LLM EFSM scheduler vs round-robin for the runtime token saving.
5. Re-grade finance/banking with the fixed monitor + structural goals for the
   safety-critical (I) claim.

Everything here is additive and reversible; the cases and arms already exist except
the scale task and the real-LLM scheduler wiring.
