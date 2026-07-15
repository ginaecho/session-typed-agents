# Run Report — 2026-06-17

Two smoke tests (quick end-to-end checks, not full statistical runs) run this
session, both on real infrastructure. Purpose: verify
the new design changes *compute and behave* on real data — not to draw final
conclusions (those need the larger runs noted as future work).

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [The story at a glance (STAR)](#the-story-at-a-glance-star)
- [How this experiment is set](#how-this-experiment-is-set)
- [1. Drafting prompt — v1 vs v2 A/B (real gpt-5.4)](#1-drafting-prompt--v1-vs-v2-ab-real-gpt-54)
- [2. Criticality gates — smoke on the grand n=10 traces](#2-criticality-gates--smoke-on-the-grand-n10-traces)
- [3. Fresh n=10 stability run + cost/time-to-goal](#3-fresh-n10-stability-run--costtime-to-goal)
- [4. v3 roadmap built this session (steps 1, 2, 4, 5)](#4-v3-roadmap-built-this-session-steps-1-2-4-5)
- [5. Artifacts written this session](#5-artifacts-written-this-session)
- [Run it on Azure AI Foundry (later)](#run-it-on-azure-ai-foundry-later)
<!-- MENU:END -->

## The story at a glance (STAR)

- **Situation** — Several new design changes (a v2 drafting prompt, criticality gates, four v3 roadmap steps) had just been built and needed a real-infrastructure check before any larger claim was made about them.
- **Task** — Run quick smoke tests (not full statistical runs) to verify each change actually computes and behaves correctly on real data, not to draw final conclusions.
- **Action** — A 3-trial-per-arm A/B of the drafting prompt (v1 vs v2) on real gpt-5.4; a post-hoc criticality-gate smoke over existing n=10 finance traces (no new LLM calls); a fresh n=10 stability run across 5 arms; four v3 roadmap steps built and offline-smoke-tested.
- **Result** — v2 cut re-draft loops **2.33 → 1.00** and reached **3/3** eventual validity vs. v1's 2/3; the fresh n=10 run found B (global text) and C+ (gate) tie on outcome — both **100%** complete, 0 disasters — but B cheaper (**27k** vs **79k** cost-to-goal); the offline v3 EFSM scheduler cut **−83% agent calls** vs. round-robin.

## How this experiment is set

- **Case(s):** [`finance`](../../experiments/cases/finance/) (fresh n=10 stability run and the criticality-gate smoke over an earlier finance run); a fresh, unseen 5-role Incident-Response scenario, not a committed case folder, used only for the drafting-prompt A/B
- **Arms/settings:** drafting-prompt v1 vs. v2 (3 trials/arm); criticality-gate smoke over 5 existing finance arms (A/B/C/C-min/C+ gate, post-hoc, no new calls); fresh n=10 stability run over the same 5 arms
- **Trials:** 3 per arm (drafting A/B); 10 per arm (fresh stability run); the criticality smoke re-uses the existing `runs/20260612T162803-n10-dual` traces — no new trials
- **Who plays the roles:** gpt-5.4, real Azure AI Foundry hosted agents for the drafting-prompt and stability-run trials; the criticality-gate smoke runs no new LLM calls at all
- **Isolation:** each role is a separate Foundry agent with its own thread; sees only its own thread's history and its own contract
- **Harness & budgets:** `experiments/scripts/smoke_draft_prompt.py` (drafting A/B, up to 4 Scribble fix-rounds per draft); `experiments/scripts/criticality_gate.py` (post-hoc, no budget — reads existing traces); `case_runner.py` / `FoundryRunner` (fresh stability run, up to 3 attempts per trial, each capped at `max_steps: 24`, `finance/case.yaml`)
- **Where the raw data is:** `experiments/cases/finance/runs/20260617T081755-n10-dual/` (fresh stability run), `experiments/cases/finance/runs/20260612T162803-n10-dual/` (criticality-smoke source)

## 1. Drafting prompt — v1 vs v2 A/B (real gpt-5.4)

Harness: `experiments/scripts/smoke_draft_prompt.py`. A fresh, unseen scenario
(5-role Incident-Response triage with a severity branch + ack-before-resolve
dependency — exactly the shape that trips Scribble's external-choice/wait-for
checks). Each arm drafts, validates with the real Scribble compiler, and fixes up
to 4 rounds. 3 trials/arm.

| prompt | first-pass valid | eventually valid | avg fix-rounds | avg time |
|---|---|---|---|---|
| v1 (one-shot "code only") | 0/3 | 2/3 | 2.33 | 20.6s |
| **v2 (reason-then-code + notify template)** | 0/3 | **3/3** | **1.00** | **15.9s** |

**Read:** v2 cut re-draft loops 2.33 → 1.00 (−57%), reached 100% eventual
validity (v1 left one draft unfixable in budget), and ran ~23% faster. First-pass
validity stayed 0/3 — this scenario is genuinely hard (chained ack dependency +
branch), and even v2 needed one fix — but v2 *always converged in exactly one
fix and never failed*. Honest conclusion: v2 is a clear improvement on
loop-count and reliability; it does not make hard protocols first-pass-perfect.

The change is reversible: `ArchitectAgent(use_v2_prompt=False)` restores v1.
What v2 adds: (a) a short PLAN step before code (gpt-5.4 is a reasoning model;
the old "return ONLY code" suppressed it), and (b) one canonical
choice-notification fan-out template that structurally prevents the two dominant
errors. Details: `prompts.py` `SCRIBBLE_SYSTEM_PROMPT_V2`.

## 2. Criticality gates — smoke on the grand n=10 traces

Harness: `experiments/scripts/criticality_gate.py` over
`runs/20260612T162803-n10-dual` with `finance/protocols/criticality.yaml`.
Post-hoc, no new LLM calls. Tests the *critical property directly*
(BENCHMARK_DESIGN_V3_CRITICALITY.md), not order-conformance.

| arm | C1 provenance | C2 struct | C2 coverage | C3 authz | **CGC** | (GCR ref) |
|---|---|---|---|---|---|---|
| A intent | n/a* | n/a* | n/a* | 0% | 0% | n/a |
| B global | 100% | 100% | 100% | 100% | **100%** | 100% |
| C local | 100% | 100% | 100% | 100% | 60% | 60% |
| C-min | 80% | 100% | 80% | 100% | 40% | 50% |
| C+ gate | 100% | 100% | 60%† | 100% | 60% | 100% |

\* A invents its own labels, so provenance/context can't anchor without semantic
label-alignment first (same gap the severity grader solves with alignment — a
to-do for the criticality grader). A's C3=0% (22 S4 disasters) and CGC=0% still
land the safety point.

† **The instructive finding.** C+ shows coverage 60% < C's 100% even though C+ had
100% GCR. Diagnosed: the 4 "failures" are trials where `ExpenseData=0.0` (or the
analyst summarized without restating the expense number) — the numeric
**coverage proxy is noisy on zero/edge values**. This is *exactly* the
limitation the design doc flagged (§6: "coverage proxies are imperfect; length
is weaker still; the strong form is a semantic faithfulness judge"). The smoke
did its job: the metric computes, **discriminates** (C-min's real 80%/80% dip vs
C's 100% is genuine — the slim contract let one provenance + one coverage slip),
and surfaced its own proxy weakness honestly.

**What this smoke does and does not show.** It shows the v3 gates run on real
traces and separate arms. It does **not** yet show the headline v3 claim
(protocol help is criticality-specific) — that needs the purpose-built
neutral/critical case *variants* with planted provenance tokens
(BENCHMARK_DESIGN_V3_CRITICALITY.md §8), which is the next build. On the
*existing* (criticality-critical-by-accident) finance case, B matched C on CGC —
consistent with the v2 finding that gpt-5.4 follows a good protocol anyway, and
precisely why the two-variant design is needed to make the claim fair.

## 3. Fresh n=10 stability run + cost/time-to-goal

`runs/20260617T081755-n10-dual`, finance, gpt-5.4, 5 arms. Reproduces the grand
run (`20260612T162803`) closely — the pattern is stable across runs. **Cost-to-goal**
= tokens ÷ GCR (tokens per *delivered* report, amortizing failed-attempt waste);
**time-to-goal** = seconds ÷ GCR.

| arm | GCR | S4 disasters | tokens/trial | **cost-to-goal** | sec/trial | **time-to-goal** |
|---|---|---|---|---|---|---|
| A intent | 0% | **15** | 19.8k | ∞ | 110 | ∞ |
| B global | 100% | 0 | 26.5k | **27k** | 59 | **59s** |
| C local (observer) | 50% | 0 | 166.0k | 332k | 259 | 518s |
| C-min | 50% | 0 | 83.4k | 167k | 245 | 491s |
| **C+ gate** | **100%** | **0** | 79.5k | **79k** | 126 | **126s** |

Reading it (consistent with `STJP_RESEARCH_REPORT.md` §4.8):

- **B (global protocol as text) and C+ (gate) tie on outcome — both 100%-complete
  with zero disasters — and B is cheaper** (27k / 59s vs 79k / 126s per delivered
  report). This benchmark does **not** show the gate beating B; on this model and
  case, just giving the agents the validated protocol was enough.
- **A (intent-only) again filed 15 reports before audit** (a disaster: an
  irreversible step before its authorization) — 0% complete, unbounded
  cost-to-goal. Stronger model, same unsafe behaviour. The contrast A→B (same
  orchestration, only difference is having the validated protocol) is where the
  value shows up: the **protocol** is doing the work, and it is present in both B
  and C+.
- **What distinguishes B from C+ is guarantee, not outcome.** B's success is the
  model *choosing* to follow pasted text — on a weaker model (gpt-4o) the same
  arm scored 40%, and in earlier runs 0–50%. C+ blocks wrong messages regardless
  of the model, and produces the compliance audit trail B cannot. Whether that
  guarantee is *worth the extra cost* is not decided by this case — it needs the
  criticality variants (`BENCHMARK_DESIGN_V3_CRITICALITY.md`), where the task is
  built so a model would *not* reliably self-comply.
- **The observer arms (C / C-min) are the expensive ones per goal** (332k / 167k)
  — not because they misbehave (0 disasters) but because their **50% stall rate**
  (S3, the liveness problem) doubles the amortized cost. This is exactly the
  problem the new v3 DeLM-style runtime targets (DeLM: a decentralized,
  shared-context execution design from related work, adapted here — not an
  STJP invention; see `../reference/STJP_V3_PLAN.md`): its EFSM (extended
  finite-state machine — the step-by-step map of a role's allowed
  transitions) scheduler polls only
  enabled senders (**−83% agent calls** in the offline smoke) and never stalls a
  role that should act. **C's inflated cost-to-goal is the measured motivation for
  the v3 execution plane built this session.**

Graded with `severity_grader.py` (S4 above) and `criticality_gate.py`
(CGC: A 0, B 100, C 50, C-min 50, C+ 70 — the C+ 70 vs GCR 100 gap is the
documented zero-value coverage-proxy noise, §2). `criticality.json` /
`severity.json` written to the run dir.

## 4. v3 roadmap built this session (steps 1, 2, 4, 5)

While the n=10 ran, four v3 roadmap steps were implemented and verified offline
(`STJP_V3_PLAN.md` for the full design):

- **Step 1 — `stjp_core/governance/policy_export.py`**: STJP → toolkit
  `PolicyDocument` (finance 30 rules / banking 44, with ordering + stateful
  choice-guard + refinement conditions, default deny).
- **Step 2 — `stjp_core/governance/audit_export.py`**: run verdicts → toolkit
  audit-entry schema with OWASP/NIST tags (intent arm 180 deny, gate 100 allow /
  5 deny on real traces).
- **Steps 4+5 — `stjp_core/runtime/delm_runner.py`** + `smoke_delm_runtime.py`:
  DeLM-style runtime with STJP monitor as write-verifier and EFSM enabled-set as
  claim predicate. Offline smoke: deadlock-free both branches, **−83% agent
  calls** vs round-robin, verifier blocks the value-wrong branch (enforce) /
  flags it (observe), order-jumping structurally impossible.

## 5. Artifacts written this session

Code: `prompts.py` (v2 prompts), `architect.py` (toggle),
`smoke_draft_prompt.py`, `criticality_gate.py`, `finance/protocols/criticality.yaml`.
Docs: see the 2026-06-17 entry in `../diary/DIARY.md`.

## Run it on Azure AI Foundry (later)

This session's live smoke tests already used Azure AI Foundry-hosted agents (gpt-5.4, via `experiments/scripts/case_runner.py` / `FoundryRunner`); the v3 roadmap steps were verified offline. To reproduce or extend the live parts, follow the standard recipe in [`1_TECH_SETUP.md` section 5](../1_TECH_SETUP.md#5-running-stjp-with-azure-ai-foundry-hosted-agents) plus the four registration points listed in [`experiments/CLAUDE.md`](../../experiments/CLAUDE.md) (`registry.py` SCENARIOS, `case_runner.py` `_FOUNDRY_INSTALL_KEYS` and `FOUNDRY_KEYS`, `evaluate_run.py` `VOCABULARY_ARMS`).
