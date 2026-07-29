# Run Reports V2 — Claims and Evidence (the reorganized benchmark)

**Date: 2026-07-27.** This document supersedes nothing and deletes nothing —
[`6_RUN_REPORTS_EXPLAINED.md`](6_RUN_REPORTS_EXPLAINED.md) (the 2026-07-02…08
campaigns) and [`7_RUN_REPORTS_FOUNDRY_REAL_CASES.md`](7_RUN_REPORTS_FOUNDRY_REAL_CASES.md)
(the 2026-07-24…27 Azure-Foundry campaign) remain the raw evidence records.
What V2 adds is the thing both were missing: **one structure that says what
claim each experiment exists to prove, and where the evidence for each claim
currently stands.**

## Why V2 exists (an honest diagnosis of the chaos)

Reading everything end-to-end, the problems are real:

1. **Nobody stated the claims.** Experiments accumulated run-by-run; a reader
   met tables before ever being told what question they answer.
2. **Three arm/setting vocabularies.** 6_RUN Part 1 uses A/B/C-min/C+spec/
   C+min/STJP; the skills_safety engine uses unchecked/bare/stjp; the Foundry
   registry uses 15 internal keys. Same ideas, three names each.
3. **Three metric vocabularies.** GCR/CGC/Disasters (6_RUN) vs
   strict/role_pair/semantic goal rates (evaluate_run) vs monitor violations
   vs Critic policy disasters — and one table briefly mislabeled violations as
   disasters before being corrected.
4. **Three runtimes and three trial counts** (subagent engine, Foundry Agent
   Service, MAF; n=1/10/100) presented side-by-side without saying which
   differences are the point and which are noise.
5. **Case sprawl without a map.** Purpose-built cases (finance, escrow_trade,
   trade_deadlock…), mined REAL-skills cases (6), a hybrid (agenticpay), and a
   methodological case (memory_race) all look alike in a directory listing but
   exist for different reasons.

V2 fixes this by inverting the structure: **claims first, then the canonical
experiment grammar, then a symmetric evidence matrix, then the case map.**

---

## 1. THE SEVEN CLAIMS — what this benchmark exists to prove

Each claim is stated with the question it answers, why it matters, and what
would falsify it. Every experiment in both campaigns tests exactly one or two
of these.

**CLAIM 1 — Composition failure is real.**
*Real, well-written, publicly published agent skills fail to coordinate when
composed without a protocol.*
Why it matters: this is the threat model — people are already composing
downloaded skills. Falsified if: unchecked real-skill teams reliably succeed.

**CLAIM 2 — The failure is detectable BEFORE runtime.**
*Static checking (Scribble/MPST validation of the composed protocol) rejects
the faulty compositions at design time, model-independently.*
Why it matters: a design-time verdict costs nothing per run and cannot be
"lucky." Falsified if: the checker accepts compositions that then fail, or
rejects ones that reliably work.

**CLAIM 3 — Enforcement eliminates the harm.**
*A projected local contract with a runtime gate reduces protocol violations
and safety disasters to zero, without hurting completion.*
Falsified if: any gated setting shows violations/disasters, or completion
drops below the unenforced settings.

**CLAIM 4 — The full stack is also the CHEAPEST way to succeed.**
*Contract + gate + EFSM scheduler delivers the lowest cost-to-goal (tokens
and calls) of any setting that succeeds.*
Falsified if: any equally-safe setting is consistently cheaper.

**CLAIM 5 — Benefits are MODEL-independent.**
*Claims 1–4 hold for weak and strong models; a stronger model does not
substitute for the contract (it just moves the failures).*
Falsified if: a strong model makes unchecked composition reliably safe.

**CLAIM 6 — Benefits are RUNTIME-independent.**
*The same pattern holds on different execution stacks (our engine, Azure
Foundry Agent Service, Microsoft Agent Framework) — the guarantee lives at
the message boundary, not in any framework.*
Falsified if: some runtime makes unchecked composition safe, or breaks the
contracted settings.

**CLAIM 7 — The MEASUREMENT itself is valid.**
*The instruments (monitor, grader, goals, policies, oracles) measure what
they claim: goals discriminate, mutations are caught, results cannot be
gamed or fabricated.*
Falsified if: goals pass on wrong behavior (gaming), instruments disagree
with hand-derived verdicts, or reported numbers don't recompute from raw
API-response logs.

---

## 2. THE CANONICAL EXPERIMENT GRAMMAR

Every run is a point in one grid:

```
  CASE  ×  SETTING (1–8)  ×  MODEL  ×  n  ×  RUNTIME
```

**The 8 canonical settings** (one vocabulary, used everywhere from now on;
historical names in parentheses):

| # | Setting | Historical names |
|---|---|---|
| 1 | Intent only | A / bare |
| 2 | Real skills, no protocol | R-orig / unchecked / unchecked_skills |
| 3 | Global protocol (as text) | B / global text / global_decentralized / maf_groupchat_llmvalid |
| 4 | Local contract (not enforced) | C-min / bare-contract / min_llmvalid |
| 5 | Local contract + gate (verbose) | C+spec / spec_llmvalid_gate |
| 6 | Local contract + gate (lean) | C+min / min_llmvalid_gate |
| 7 | Local contract + gate, no turn hint | min_llmvalid_gate_nohint |
| 8 | Full STJP (gate + scheduler) | STJP / min_llmvalid_sched |

**The canonical metric block** (every table reports these columns, in this
order; "—" where a runtime cannot honestly measure one):

| Metric | Definition | Instrument |
|---|---|---|
| GCR [95% CI] | trials finishing the task (Wilson interval) | goal verifier |
| CGC | trials finishing with zero safety findings | goals + policies |
| Violations | monitor-flagged off-protocol messages | runtime monitor |
| Disaster trials | trials where the case's specific catastrophe occurred | Critic policies |
| World-state OK | trials whose final environment state is correct | case oracle (where one exists) |
| Cost-to-goal | tokens (or calls) ÷ GCR | runner metering |
| Seconds/trial | wall clock (parallel-contention caveat) | runner |

---

## 3. THE EVIDENCE MATRIX — where each claim stands (2026-07-27)

Symmetric by construction: one row per claim × campaign.

| Claim | 6_RUN campaigns (engine/subagents, Claude models) | 7_RUN campaign (Azure Foundry API, GPT models) | Status |
|---|---|---|---|
| 1 Composition failure | R-orig 0% (n=10 Haiku); unchecked 75% GCR but 50% CGC + 100 disasters (n=100 Sonnet) | Setting 2 = 0/10 (code_execution), 0/10 (booking_saga), 0–1/10 (airline, rerun pending); worse than intent-only on code_execution | **PROVEN, both stacks** |
| 2 Design-time detection | compiler rejects all 4 composed real-skill protocols; E1 mutation 100/84/100% | pr_review_merge + loop cases validate True under BOTH backends (sound); but on circular_wait mutants BOTH catch 0 (comparable set) and nuscr can't analyse 19/30 — coinductive backend does NOT close the gap (Part 3c) | **Cross-validated sound for our cases; static detection INCOMPLETE for both backends → the gate is the guarantee** |
| 3 Enforcement → zero harm | STJP rows: 0 disasters at n=10, n=100, all cases | settings 5–8: 0 violations, 0 disaster trials in every completed n=10 table | **PROVEN, both stacks** |
| 4 Cheapest-safe | 13.3k vs 120k tokens (finance §2); 1.52–1.67k vs 2.75–4.9k (real skills) | booking_saga: STJP 3,839 tok vs 38k intent-only; MAF appendix: 5,092 vs 17–45k | **PROVEN at n=10; finance-on-Foundry n=10 RUNNING to close the loop** |
| 5 Model-independence | Haiku vs Sonnet: failures move, STJP flat 100%/0 (Part 3, 120 trials) | gpt-5-mini vs gpt-5.4: same shape (booking 0/10 both no-protocol settings on BOTH models); GPT curve = mini vs 5.4 (2 tiers; sol blocked from ladder) | **PROVEN on 2 Claude tiers + 2 GPT tiers (mini, 5.4)** |
| 6 Runtime-independence | engine + E7 portability 59/59 | Foundry Agent Service (hosted agents) + MAF appendix reproduce the pattern; E7 re-run 59/59 | **PROVEN across 3 runtimes** |
| 7 Measurement validity | instruments 40/40; E5 fidelity 300/300 | instruments re-run 40/40; goal-quality tooling (discrimination/mutation/gaming); world-state oracle caught a live race AND a goal false-negative; anti-fabrication: 92/92 recount + verbatim server-thread matches | **PROVEN, and stronger than in 6_RUN** |

**Open gaps** (the honest to-do list): finance-on-Foundry (running); airline
re-runs (running); E3 GPT-tier curve; E5 live-drafting; agenticpay root cause;
pr_review_merge round budget; memory_race delta-semantics fix; content_pipeline
(blocked on an unlicensed upstream — user decision); n=100 on Foundry (cost
decision); a non-OpenAI/non-Claude vendor point.

---

## 3c. Coinductive nuscr re-validation (2026-07-28)

We built the coinductive nuscr fork (Docker image `nuscr-coind`) and re-validated
with BOTH backends. (A first attempt had a test bug — mutants written to files
whose name didn't match the `module` declaration, so scribble-java rejected them
on a NAME error, not a deadlock verdict; corrected below by naming each file
after its module.)

1. **Our real cases are cross-validated sound.** pr_review_merge (the real-skills
   LOOP case) and the purpose-built loop cases (retry_loop, nested_retry,
   iterative_polling) all validate **True under both scribble-java AND nuscr**.
   pr_review_merge is genuinely deadlock-free — two independent MPST checkers agree.
2. **nuscr does NOT close the circular_wait gap (hypothesis REFUTED, cleanly).**
   After fixing TWO harness bugs (scribble module-name errors AND nuscr
   "not implemented" tool-errors both miscounted as deadlock catches) and
   verifying a clean 0/30 false-positive baseline for both backends: on the 11
   corpus protocols BOTH can judge, **scribble caught 0 and nuscr caught 0**;
   nuscr additionally **cannot analyse 19/30 protocols** (non-tail-recursive not
   implemented). Full detail + the two-bug story: `reference/NUSCR_BACKEND_COMPARISON.md`.
3. **Consequence for Claim 2:** static MPST detection is INCOMPLETE for BOTH
   backends (neither catches these mutants; nuscr is practically weaker via
   coverage gaps). Two backends do agree our composed real-skill protocols are
   sound (pr_review_merge validates True under both). The incompleteness is the
   whole reason STJP does not rely on the static check alone — **the runtime gate
   is the guarantee.**

Reproduce: `docker build -t nuscr-coind -f tools/nuscr/Dockerfile <nuscr-fork>`,
then `NuscrCompiler().validate(path)`; write mutants to `<module>.scr`.

## 3d. The scheduler becomes NECESSARY at 7 roles (2026-07-29, PROVISIONAL — run in progress)

First evidence that the EFSM scheduler is not merely the cheapest way to
succeed (Claim 4) but, at larger team sizes, the difference between finishing
and not finishing at all. From the sdlc_release_gate case (7 agents, real
awesome-copilot review skills, gpt-5.4, 65/80 trials done):

7 agents must review and deploy code in at most 48 turns. Only one agent can
act at any moment. Settings 1–7 hand out turns in a fixed circle, so most
turns go to agents with nothing to send, and the 48 run out before deployment.
Setting 8's scheduler gives every turn to the one agent the protocol is
waiting on, and finishes 10/10.

Provisional numbers: setting 8 is 10/10; every other setting is 0–2/10 —
including the gate settings, which fail with ZERO violations (the agents
follow every rule and still run out of turns). The fragile-goal audit is CLEAN
on the partial run, and the same 48-turn budget applies to every setting, so
the comparison is fair. If the final numbers hold, this sharpens Claim 3/4:
enforcement eliminates the harm, but at 7 roles only the scheduler delivers
completion — coordination overhead, not rule-breaking, becomes the dominant
failure mode. Full case section: `7_RUN_REPORTS_FOUNDRY_REAL_CASES.md` CASE 6
(FINAL numbers land there when the run completes and passes the audit gate).

## 3b. MODEL-FAMILY COVERAGE — where each model has actually been tested

A reader of the matrix above could miss that the two campaigns used DIFFERENT
model families. Stated explicitly:

| Evidence source | Models actually used | Settings covered |
|---|---|---|
| 6_RUN campaigns | Claude: Haiku 4.5, Sonnet (+GPT-5.4 in the §2 finance run) | full ladder |
| 7_RUN campaign | GPT: gpt-5-mini, gpt-5.4 | full ladder (1–8) |
| 7_RUN campaign | **gpt-5.6-sol** | ONLY the MAF-runtime setups and the hosted group agents |

**Why gpt-5.6-sol cannot run settings 1–8:** the classic Foundry Agent
Service force-injects a `top_p` parameter that reasoning-family models reject
(verified live; even a REST PATCH to null it returns 400 — RESULT_13). This is
a platform limitation, not a design choice. Where sol CAN run, it is tested:
MAF on TWO cases — code_execution and booking_saga (both: no-protocol 0/10,
global-protocol 10/10) — and all six hosted group agents.

**Extra-work register opened by this observation (in flight as of 2026-07-27):**
1. finance §2 ladder on the GPT pair — RUNNING (mini leg live, 5.4 queued).
2. E3 capability curve on GPT tiers — the project's models are gpt-5-mini
   (weak) and gpt-5.6-sol (advanced), with gpt-5.4 as the working advanced
   classic-path model (sol is platform-blocked from settings 1–8). The GPT
   curve is therefore the 2-tier mini vs 5.4 comparison already collected;
   gpt-5-nano is NOT part of this project and is not used.
3. sol second-case coverage — RUNNING (booking_saga MAF setups on sol).
4. Part-3 team equivalents on the GPT pair — pr_review_merge pending its
   budget re-run; doc_coauthor_ship not yet run on Foundry.
5. Claude-tier rows in the matrix stay labeled as Claude evidence; claims are
   only marked model-independent where BOTH families show the effect.

## 4. THE CASE MAP — why each case exists

**Tier 1 — mined REAL skills (the threat model itself):** each composes real
published skill files; each encodes ONE canonical catastrophe:

| Case | Real source | The catastrophe | Unique role in the benchmark |
|---|---|---|---|
| code_execution | microsoft/autogen | code runs without review | security-critical; the "skills worse than no skills" result |
| airline_seat | openai/openai-agents-python | seat written before flight assigned | precondition-in-code-not-in-prompt pattern |
| booking_saga | langchain-ai/langgraph | charge before hold | cleanest full separation (0/10 vs 10/10) |
| pr_review_merge | github/awesome-copilot | merge before both reviews | LOOPING protocol (rec/continue) — stresses liveness budgets |
| doc_coauthor_ship / doc_pipeline | anthropics/skills | ship before styling/review | subagent-engine evidence (6_RUN Part 3) |
| agenticpay_settlement | SafeRL-Lab/AgenticPay (hybrid) | pay-vs-ship deadlock | the only real-repo DEADLOCK case; best provenance |

**Tier 2 — purpose-built (controlled difficulty):** finance (branch + audit
obligation — the flagship §2 ladder), escrow_trade / trade_deadlock
(deadlock), banking/travel/etc. (breadth corpus for the compiler suite).

**Tier 3 — methodological (tests the MEASUREMENT, claim 7):** memory_race —
a lost-update race that deadlock-checking cannot catch, with a world-state
oracle that cannot be gamed by hallucinated payloads. It exists to prove the
benchmark's own limits and the fix for them.

---

## 5. WHAT "MORE SENSIBLE BENCHMARKING" LOOKS LIKE (V3 proposal)

Adopting these rules going forward — several are already implemented:

1. **Claims-first registration.** No experiment without a stated claim number
   and a falsification condition (this document is the registry).
2. **One grammar.** Every run = case × setting(1–8) × model × n × runtime;
   run dirs are self-attributing (`timestamp-model-pid` — implemented
   2026-07-27 after the collision incident).
3. **Equal n or say so.** Cross-setting tables must hold n constant; anything
   else is marked provisional.
4. **Four measurement layers on every case, always:** goal verifier +
   monitor + Critic policies (`v1.policy` now mandatory per case) +
   world-state oracle where state exists (memory_race pattern).
5. **Goal-quality gates as CI:** discrimination score, trace-mutation kill
   rate, gaming red-team (implemented: `goal_quality.py`, `goal_mutation.py`,
   `goal_gaming.py`) — a case whose goals are naive/impossible fails CI
   before anyone cites its numbers.
6. **Provenance chain on every campaign:** raw server-side artifacts
   (threads/traces) → per-message logs → summaries → tables, each link
   mechanically re-checkable (the 92/92 recount + verbatim thread matching
   from RESULT_13).
7. **Incidents are data.** Stalls, collisions, misattributions, impossible
   goals get documented in the report, never silently fixed (see 7_RUN
   Honest limitations).

## 6. READING GUIDE

- **This document** — what is claimed and where evidence stands. Start here.
- [`7_RUN_REPORTS_FOUNDRY_REAL_CASES.md`](7_RUN_REPORTS_FOUNDRY_REAL_CASES.md) —
  the Foundry campaign's symmetric tables (GPT models, live API).
- [`6_RUN_REPORTS_EXPLAINED.md`](6_RUN_REPORTS_EXPLAINED.md) — the original
  campaigns (Claude models, engine + n=100 suite + two-model teams).
  Unchanged, per the do-not-rewrite-history rule.
- [`results/RESULT_13_FOUNDRY_REAL_CASES_TWO_MODELS.md`](results/RESULT_13_FOUNDRY_REAL_CASES_TWO_MODELS.md)
  — Foundry campaign record + authenticity proofs. RESULT_01…12: per-campaign
  records feeding 6_RUN.
- [`reference/GOAL_QUALITY_AUDIT.md`](reference/GOAL_QUALITY_AUDIT.md) — why
  claim 7 needed new instruments, and what was built.
