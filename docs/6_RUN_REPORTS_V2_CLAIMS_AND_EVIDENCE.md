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
| 2 Design-time detection | compiler rejects all 4 composed real-skill protocols; E1 mutation 100/84/100% | pr_review_merge + loop cases validate True under BOTH backends; on circular_wait mutants BOTH catch 0 (3c). NEW (2026-07-30/31): TWO Scribble-VALID protocols I authored (multi_buyer, agenticpay_settlement) had unenforced-ordering holes — a role acts before a prerequisite it was never messaged about; deadlock-free so Scribble AND the runtime gate both accept the reordered run. Caught by the suspicion audit (STJP-fails red flag) + trace, fixed by one notification message each; spawned `protocol_entry_audit.py` (catches the first-action subclass) | **Static detection INCOMPLETE (both backends); the deadlock-free guarantee does NOT imply intended-ordering — needs realizability lint + suspicion auditing on top** |
| 3 Enforcement → zero harm | STJP rows: 0 disasters at n=10, n=100, all cases; E2 hostile-agent gate 0→42→92→100% blocked as layers add | settings 5–8: 0 violations, 0 disaster trials in every completed n=10 table | **PROVEN, both stacks** |
| 4 Cheapest-safe | 13.3k vs 120k tokens (finance §2); 1.52–1.67k vs 2.75–4.9k (real skills); E6 scaling: savings grow 9×→17× from 2→10 roles | finance FINAL both models; 5 complex cases FINAL both models (CASES 6–10). STJP cheapest where coordination is non-trivial: gem (7r branch+loop) ONLY STJP completes 10/10 both models; multi_seller/multi_buyer STJP 12–24 calls vs 44–73. HONEST limits (3d/3e): at 3–4 roles/linear STJP ties within noise; react18 STJP NOT uniquely best (a no-hint gate matches/beats it — CASE 9) | **PROVEN where coordination cost is real; complexity-dependent (ties at ≤4 roles/linear), documented honestly** |
| 5 Model-independence | Haiku vs Sonnet: failures move, STJP flat 100%/0 (Part 3, 120 trials) | SAFETY is model-independent — 0 violations/disasters on every gated setting, mini AND 5.4, all cases. But COMPLETION of the HARDEST coordination is model-DEPENDENT: sdlc's clean 5.4 result (STJP+verbose-gate 10/10) does NOT reproduce on mini (noisy 7/10, CASE 6); react18's winning settings differ by model (CASE 9). Reported honestly, not smoothed | **Safety+cost model-independent; hardest-case completion is model-dependent — stated openly** |
| 6 Runtime-independence | engine + E7 portability 59/59 | Foundry Agent Service (hosted agents) + MAF appendix reproduce the pattern; E7 re-run 59/59 | **PROVEN across 3 runtimes** |
| 7 Measurement validity | instruments 40/40; E5 fidelity 300/300; E4 reliability math: n=100 lifts worst-case pass-ten confidence 17.6× vs n=10 | instruments re-run 40/40; goal-quality tooling (discrimination/mutation/gaming); world-state oracle caught a live race AND a goal false-negative; anti-fabrication: 92/92 recount + verbatim server-thread matches; 2026-07-29 suspicion audit (3e): 0 recount mismatches, all cases goal-audited | **PROVEN, and stronger than in 6_RUN** |

**Open gaps** (updated 2026-07-31 — RESOLVED since last update: all 5 complex/
N-party cases DONE both models + written as CASES 6–10 (gem, sdlc,
react18, multi_seller, multi_buyer); content_pipeline mini DONE (CASE 4);
multi_buyer protocol bug found+fixed+re-run; agenticpay_settlement protocol bug
found+fixed, re-run IN PROGRESS both models). **STILL OPEN:**
agenticpay_settlement re-run to complete + write as a CASE; pr_review_merge
round-budget rework (its 07-28 run failed the suspicion audit); memory_race
delta-semantics fix; E3 GPT-tier curve; E5 live-drafting; n=100 on Foundry
(cost decision); a non-OpenAI/non-Claude vendor point; sync these docs to the
`session-typed-agents` repo.

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

## 3d. The complex real-skills cases: three honest shapes (2026-07-31, all 5 FINAL both models)

First case where the EFSM scheduler's completion value (beyond Claim 4's cost
edge) becomes visible: the smaller cases (1–4 roles) finish for every contract
setting, so nothing separates them there. sdlc_release_gate (7 agents, real
awesome-copilot review skills, gpt-5.4, n=10 FINAL) separates them.

> **Corrected from a provisional posting.** An earlier version of this section
> (from a 65/80 partial run) said "setting 8 is the ONLY setting that
> finishes; all others 0–2/10." The FINAL 80/80 run REFUTES that — the verbose
> gate (setting 5) also reaches 10/10. Kept as a live example of the suspicion
> rule (§5 rule 8): a partial run is never citable.

FINAL result: **two** settings finish all 10 — setting 5 (verbose gate) and
setting 8 (full STJP) — but at very different cost. Setting 8 finishes at 17
calls / 18k tokens per trial; setting 5 finishes at 56 calls / 103k tokens
(3.3× / 5.8× more). The lean gate without the scheduler (6, 7) and the
unenforced contract (4) mostly run out of the turn budget (0–1/10); raw real
skills (2) melt down at ~2M tokens/trial. All gated settings hold violations
to zero. So: enforcement handles SAFETY at every team size (Claim 3 intact),
but at 7 roles COMPLETION becomes a turn-budget problem and the scheduler is
the only setting that solves it cheaply — sharpening Claim 4 from "cheapest"
to "the only reliable-and-cheap option once coordination dominates." Full
table + mechanism: `7_RUN_REPORTS_FOUNDRY_REAL_CASES.md` CASE 6.

**All 5 complex cases are now FINAL on BOTH models (2026-07-31, CASES 6–10) —
and the honest picture has three shapes, not one:**
- **Scheduler is NECESSARY (hardest cases): gem_dev_team (7r, branch+LOOP) —
  the strongest result.** On BOTH models, setting 8 is the ONLY setting that
  completes 10/10; even the verbose gate fails (unlike sdlc). Radically cheapest
  (14.5–34 calls vs 80–431) — never enters the replan-loop that burns up to
  3.18M tok/trial. sdlc is similar on gpt-5.4 (STJP + verbose-gate 10/10) but
  **does NOT reproduce on mini** (noisy 7/10 for all) — completion is
  model-dependent for the very hardest coordination.
- **Scheduler is CHEAPEST-safe (mid cases): multi_seller + multi_buyer (5r
  escrow).** Most contract settings complete; STJP wins decisively on cost
  (12–24 calls vs 44–73) with 0 violations. multi_buyer is also the worked
  example of the suspicion rule: its first STJP-0/10 was a protocol bug I
  authored, caught, fixed (one `BeginB` message), re-run clean.
- **Scheduler is NOT uniquely best (honest counter-shape): react18 (6r,
  phased+loop).** STJP is robust (9–10/10 both models) and cheapest among
  reliable settings, but a **no-hint gate matches or beats it** — the per-turn
  liveness hint *backfires* in this loop. Reported as a genuine limit, not
  smoothed over (CASE 9).

Honest caveat across all: disaster counts are near-zero because failing
settings mostly never reach the dangerous step, and intent-only's 10/10 on
weak-model gem is a brute-force fluke (418 violations, 2.1M tok, 1 real
disaster). Separation on these hard cases is COMPLETION + COST + violations,
not disaster frequency. (agenticpay_settlement — a 6th complex case — is
re-running after a second authoring-bug fix; see 7_RUN register.)

## 3e. SUSPICION AUDIT of the Foundry tables (2026-07-29)

Standing rule (after the G3 and nuscr measurement bugs): **a result is not
citable until someone has tried to break it.** Two symmetric suspicions were
tested against raw logs for every FINAL 7_RUN table:

- **"STJP is 100% — too good?"** Recount of every GCR/violation/token/call
  from raw `events_*.jsonl` vs `summary.json`: 0 mismatches (9 runs × 8
  settings). Fragile-goal audit now CLEAN on ALL finalized cases (the three
  never-audited ones — code_execution, airline_seat, booking_saga — audited
  2026-07-29). Finance's re-grade verified independently, including a payload
  spot-check showing the fixed predicate accepts genuine approvals only.
- **"Settings 4/7 sometimes BEAT STJP on tokens — why?"** Explained from
  calls/trial: in short linear pipelines every contract setting uses the
  identical 3.0–4.0 calls (round-robin is already optimal), so the scheduler
  has nothing to save and the gate's ~100–150-token prompt overhead makes
  setting 4/7 the token winner. The scheduler's edge grows with coordination
  complexity: booking (fewer calls, cheapest), finance (3–4× cheaper), sdlc
  (only setting that finishes). Full mechanism + numbers:
  `7_RUN_REPORTS_FOUNDRY_REAL_CASES.md` → "SUSPICION AUDIT".

Consequence for the claims: Claim 4 (cheapest-safe) is now stated honestly as
**complexity-dependent** — at 3–4 roles/linear, STJP ties within noise and the
unenforced contract can be marginally cheaper; from ~5 roles or any branch/
loop upward, STJP is strictly cheapest, and at 7 roles it is the only setting
that completes (3d). Claim 7 (measurement validity) gains the recount +
audit-all-cases evidence.

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
8. **The suspicion rule (added 2026-07-29).** Every result section answers,
   with log evidence: if STJP wins or is 100%, prove it is not a measurement
   artifact (recount + fragile-goal audit + a real payload spot-check); if
   any NON-STJP setting beats STJP on any column, never present it silently —
   find the mechanism in the logs and write it into the doc. An anomaly
   without an explanation means the number is not citable yet. And every
   result is written story-first: the scenario in plain English, then what
   the numbers show, then the verified insight.

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
