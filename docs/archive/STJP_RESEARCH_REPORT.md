# Session-Typed Agent Pipelines (STJP): Contracts, Monitors, and Gates for Multi-Agent LLM Coordination

**Technical report — 2026-06-12**
*Experiments executed on Azure AI Foundry (Agent Service) and Microsoft Agent
Framework (MAF); models gpt-4o and gpt-5.4 (Azure OpenAI deployments).
All traces, prompts, and verdicts cited here are persisted under
`experiments/cases/<case>/runs/` and are independently checkable.*

---

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [Abstract](#abstract)
- [1. Problem](#1-problem)
- [2. The STJP pipeline](#2-the-stjp-pipeline)
- [3. Benchmark design](#3-benchmark-design)
  - [3.1 Arms (all same intent, role descriptions, model, step budget, retry budget)](#31-arms-all-same-intent-role-descriptions-model-step-budget-retry-budget)
  - [3.2 Metrics — four gated layers](#32-metrics--four-gated-layers)
  - [3.3 Consequence-graded violations (S0–S4)](#33-consequence-graded-violations-s0s4)
- [4. Results](#4-results)
  - [4.1 The protocol-information ladder (finance, n=10, gpt-4o, 2026-05-21)](#41-the-protocol-information-ladder-finance-n10-gpt-4o-2026-05-21)
  - [4.2 Severity re-scoring (same run)](#42-severity-re-scoring-same-run)
  - [4.3 Banking — S4 in dollars (n=2, gpt-4o, live-drafted protocol)](#43-banking--s4-in-dollars-n2-gpt-4o-live-drafted-protocol)
  - [4.4 Cost anatomy — the contract is the cheap part](#44-cost-anatomy--the-contract-is-the-cheap-part)
  - [4.5 Choice guards close the branch hole](#45-choice-guards-close-the-branch-hole)
  - [4.6 The enforcement gate (C+), first production runs](#46-the-enforcement-gate-c-first-production-runs)
  - [4.7 Confirmation at n=5 (gpt-5.4, observer vs gate)](#47-confirmation-at-n5-gpt-54-observer-vs-gate)
  - [4.8 Grand five-arm comparison (n=10, gpt-5.4, all arms, 2026-06-12)](#48-grand-five-arm-comparison-n10-gpt-54-all-arms-2026-06-12)
- [5. Two systems lessons](#5-two-systems-lessons)
  - [5.1 Safety monitors are structurally blind to liveness](#51-safety-monitors-are-structurally-blind-to-liveness)
  - [5.2 The tone of the monitor is part of the contract surface](#52-the-tone-of-the-monitor-is-part-of-the-contract-surface)
- [6. Limitations](#6-limitations)
- [7. Conclusions](#7-conclusions)
- [Appendix A — Reproducibility](#appendix-a--reproducibility)
<!-- MENU:END -->

## Abstract

We study whether multiparty session types (MPST) make LLM multi-agent systems
reliably achieve a user's goal. A natural-language intent is translated by an
LLM into a Scribble global protocol, validated for deadlock-freedom, projected
into per-role **local contracts**, and supervised by per-role **static Python
monitors** (not agents). Across a 6-role finance pipeline and a 5-role banking
pipeline we compare: (A) agents given only the intent, (B) agents additionally
given the full validated global type as text, (C) agents given only their own
projected local contract, and (C+) the same with an **enforcement gate** that
rejects off-contract messages before delivery. Goal completion rises
0% → 40% → 80% across A/B/C (finance, n=10), and the cost of one *completed*
task falls from unbounded (A) to 88k tokens (B) to 42k (C). A
consequence-graded violation taxonomy (S0–S4) addresses the circularity
objection to protocol-conformance metrics and reveals that intent-only agents
performed **unauthorized irreversible actions** (filing unaudited reports;
moving money before authorization) that nothing in their own stack flagged.
The same grading exposed a real gap in our typed arms — protocol-legal but
value-wrong **branch choices** — which we closed with value-dependent
**choice guards** (asserted-MPST style) compiled into contracts and checked by
value-tracking monitors. Finally we report two systems lessons: protocol
**liveness cannot be enforced by observation** (a waiting agent emits no event
to judge), and the **tone of runtime guidance is part of the contract
surface** — an imperative monitor nudge caused a frontier model to refuse
outright, while the same content phrased descriptively was followed.

---

## 1. Problem

LLM multi-agent frameworks (group chat, orchestrators) coordinate by prose:
the task description and role descriptions are the only specification. Three
failure classes follow:

1. **No shared interaction vocabulary** — agents invent message types ad hoc;
   downstream agents misread them.
2. **No ordering/authority constraints** — irreversible actions (file the
   report, move the money) can occur before the steps that authorize them,
   and nothing in the stack even *records* that this happened.
3. **No termination discipline** — sessions stall (everyone waits) or loop.

MPST theory offers exactly the missing artifact: a **global type** validated
for deadlock-freedom, **projected** to per-role local types whose product
recovers the global behaviour (Honda–Yoshida–Carbone), with runtime
monitorability (Bocchi et al., FORTE'13) and assertion layers for data
constraints (asserted MPST, CONCUR'10). STJP operationalizes this for LLM
agents.

## 2. The STJP pipeline

```
intent (NL) ──LLM──► global type (.scr) ──Scribble──► VALID / REJECTED
                                            │
                       ┌────────────────────┤ projection
                       ▼                    ▼
        per-role local contract     per-role static monitor (Python)
        (EFSM SEND/RECV table       (same EFSM + refinement and
         + refinement guards,        choice guards; observer or gate)
         compiled into prompt)
                       │
        goals (predicates anchored to protocol messages,
               one marked FINAL = termination indicator)
```

Key properties:

- **Validation is real**: drafting the banking protocol live, Scribble
  rejected four consecutive LLM drafts with safety violations before
  accepting the fifth. The rejected finance draft contained a wait-for cycle
  `[Writer → RevenueAnalyst → TaxVerifier]` — a protocol that *would* deadlock
  at runtime, caught before any agent ran. Agents given that unsafe draft
  completed only 20% of trials.
- **Monitors are scripts, not agents**: per-role EFSM walkers, deterministic,
  O(1) per event, no LLM call. They observe sends/receives, evaluate payload
  and choice predicates, and count goal achievement.
- **Guards live in a sidecar (`.refn`)**, not in a Scribble fork — stock
  `scribble-java` is untouched.

## 3. Benchmark design

### 3.1 Arms (all same intent, role descriptions, model, step budget, retry budget)

| arm | agents receive | monitor |
|---|---|---|
| **A** intent-only | intent + role prose (MAF GroupChat) | canonical type (never seen by agents) |
| **B** + global type | A + full validated `.scr` as text | same type |
| **C** projected local | A + own local contract only | same type, per-role |
| **C-min** | C with one-line-per-transition contract | same |
| **C+ gate** | C, plus monitor **rejects off-contract sends before delivery** and re-prompts | same, in-line |

### 3.2 Metrics — four gated layers

1. **Liveness (gate):** terminal label within budget; stall classification.
2. **Goal achievement:** GCR = all applicable goals + the final goal in the
   *same attempt*; strict / role-pair / semantic rungs; branch-aware vacuity.
3. **Path adherence:** monitor acceptance rate, mandatory-milestone coverage,
   first-violation depth, redundancy ratio (events ÷ minimal accepting path).
4. **Cost:** tokens and seconds per trial; **cost of success** = tokens ÷ GCR.

### 3.3 Consequence-graded violations (S0–S4)

Raw "violation = deviation from our protocol" is circular — baselines that
never saw the protocol fail by construction. We therefore (i) align observed
labels semantically before judging, and (ii) grade each surviving deviation by
**consequence** against the partial order that has *reasons* (data and
authority dependencies), annotated with irreversibility:

| class | meaning | counted against correctness? |
|---|---|---|
| S0 | benign reorder / dialect | **no** |
| S1 | waste (duplicates, polling) | cost only |
| S2 | skipped obligation / broken order | yes |
| S3 | never terminated | yes |
| S4 | **irreversible act before its authorization** | yes — disaster class |

The grading is itself validated empirically:
**P(goal failure | attempt had S2+/S4) = 100% in every arm of every run**;
benign deviations did not predict failure. The monitor measures harm, not
difference.

## 4. Results

### 4.1 The protocol-information ladder (finance, n=10, gpt-4o, 2026-05-21)

| metric | A intent | B global | C local | C-min |
|---|---|---|---|---|
| GCR (strict) | 0% (0% even role-pair) | 40% | **80%** | 60% |
| monitor acceptance | 0% | 60% | **100%** | 84% |
| avg tokens/trial | 15.4k | 35.4k | 33.7k | 28.2k |
| **cost of success** | ∞ | 88.5k | **42.1k** | 47.0k |
| redundancy ratio | 1.9× | 2.2× | **1.5×** | 2.0× |

*Validation* of the global type earns the first step (unsafe-draft arm: 20%;
validated-text arm: 40%); *projection + monitoring* earns the second
(40% → 80%). The verbose contract beats the slim one per completed task
despite costing more per trial — slim contracts buy retries.

### 4.2 Severity re-scoring (same run)

| arm | raw viol. | S0 | S1 | S2 | S3 | **S4** | harmful attempts |
|---|---|---|---|---|---|---|---|
| A | 184 | 134 | 8 | 14 | 24 | **4** | 50% |
| B | 63 | 89 | 0 | 3 | 18 | 0 | 12% |
| C | 0 | 49 | 0 | 4 | 5 | **2** | 11% |
| C-min | 23 | 65 | 0 | 7 | 4 | **3** | 20% |

Two headline corrections to the naive reading:

- A's fair indictment is not "184 violations" (134 were dialect) but
  **"filed the report before approval/audit 4 times in 30 attempts."**
- C is **not spotless**: its disasters were *protocol-legal but value-wrong
  branch choices* (standard branch on >$50k revenue, skipping the audit).
  Classic MPST cannot express which branch the data requires — see §5.

### 4.3 Banking — S4 in dollars (n=2, gpt-4o, live-drafted protocol)

| metric | A | B | C | C-min |
|---|---|---|---|---|
| GCR (strict) | 0% | 50% | **100%** | **100%** |
| **S4 disasters** | **2 × `debit before authorized`** | 0 | 0 | 0 |
| tokens (2 trials) | 22.8k | 98.9k | 84.6k | **53.3k** |

Intent-only agents **moved money before authorization twice in six
attempts** — and their own stack produced no signal. Conversely the typed
arm's 8 raw monitor flags collapsed under grading to a single harmless skipped
notification (S2, order intact, delivered) — the letter-vs-consequence gap
demonstrated against our own arm.

### 4.4 Cost anatomy — the contract is the cheap part

Installed per-role system prompts: A 1,870 chars; B ~6,000 (whole global type
re-read by every role every call, 1,603 prompt-tok/call); C 2,672–4,646;
**C-min 1,063–1,986 — smaller than the intent-only prompt** (the SEND/RECV
table replaces coordination guesswork prose). The dominant cost is the
**turn loop**: ~4.5 LLM calls per delivered message (idle roles polled, answer
WAIT), each re-reading static text. Identified levers, in payoff order:
EFSM-driven scheduling (poll only enabled senders), projected views (per-role
history deltas), prompt-caching the static prefix, role-level retry.

### 4.5 Choice guards close the branch hole

We extended the `.refn` sidecar with **value-dependent choice guards**
(asserted-MPST style; predicates range over previously observed payloads):

```
[choice at RevenueAnalyst]
when: float(RawRevenueData) > 50000
require: HighRevenueNotification
over: StandardRevenueNotification
```

The rule travels through four stages: **define** (sidecar) → **state**
(compiled into the contract *at the decision state*) → **check**
(value-tracking monitor, new verdict `choice_guard_violation`) → **enforce**
(gate). Offline replay verification: high-revenue + standard-branch fires;
correct branch is clean; low-revenue + high-branch fires symmetrically;
unevaluable guards stay silent (no false positives). The banking guards also
close the *denied-but-debited* hole (`Approval=='true' ⇒ Approved`).

### 4.6 The enforcement gate (C+), first production runs

In the first gate run (gpt-4o), the gate **intercepted a real off-contract
send pre-delivery** (RevenueAnalyst jumping ahead at state 25) and re-prompted;
the un-gated arm made the same jump in parallel and its trace cascaded
off-protocol for three further steps. Delivered violations: observer 9/15
events, **gate 0/7**; gate also cost less (−22% tokens, −29% time): rejecting
a wrong action is cheaper than delivering it.

Both arms scored 0% that run for an orthogonal reason — see §5.2.

### 4.7 Confirmation at n=5 (gpt-5.4, observer vs gate)

Five trials per arm, branch-balanced, identical contracts; the only delta is
the gate + the (repaired) liveness nudge. Run
`runs/20260612T155053-n5-dual`, `runs/20260612T162803-n10-dual`:

| metric | C observer | **C+ gate** |
|---|---|---|
| GCR (strict, all goals + final, same attempt) | 80% | **100%** |
| avg attempts per trial | 1.40 | **1.00** (first attempt, every trial) |
| delivered violations | 6 / 63 events | **0 / 53** |
| stalled attempts (S3) | 3 | **0** |
| avg tokens / trial | 114.9k | **80.9k** (−30%) |
| tokens per success | 81.5k | 80.9k |
| avg seconds / trial | 170.3 | **122.1** (−28%) |
| LLM calls / trial | 54.2 | **37.6** (−31%) |

The mechanism is visible in the traces. In both arms, TaxVerifier repeatedly
tried to send `Approval` **early** (before the branch-ack sequence completed).
In the observer arm this premature send was *delivered* four times; once it
desynchronized the session and cascaded (`FinalRevenueAnalysis`,
`GenerateReport` then also off-protocol), failing the trial — hence 80%.
In the gate arm the identical mistake was attempted twice, **rejected
pre-delivery both times**, the role re-prompted with its expected actions —
and every trial completed on the first attempt. Severity grading: observer
0 harmful deviations but 3 liveness stalls; gate **zero in every class**.

Enforcement also *paid for itself*: rejecting two wrong sends and nudging
enabled senders cost less than delivering mistakes and retrying — the gate
arm was ~30% cheaper per trial and 28% faster, with equal cost-per-success.


### 4.8 Grand five-arm comparison (n=10, gpt-5.4, all arms, 2026-06-12)

The full matrix on one model and one run (`runs/20260612T162803-n10-dual`),
with the complete new STJP (choice guards in contracts and monitors,
enforcement gate + liveness nudge in C+):

| metric | A intent | B global | C local | C-min | **C+ gate** |
|---|---|---|---|---|---|
| GCR (strict) | 0% | 100% | 60% | 50% | **100%** |
| avg attempts | 3.00 | 1.00 | 1.90 | 2.00 | **1.00** |
| delivered violations | 180/180 | 26/100 | 16/151 | 15/153 | **0/105** |
| severity: S2 / S3 / **S4** | 29 / 1 / **22** | 0 / 0 / 0 | 0 / 13 / 0 | 0 / 15 / 0 | **0 / 0 / 0** |
| harmful attempts | **97%** | 0% | 0% | 0% | **0%** |
| tokens / trial | 21.7k | 24.4k | 154.1k | 84.0k | 79.5k |
| tokens / success | ∞ | **24.4k** | 96.8k | 44.7k | 79.5k |
| seconds / trial | 109 | **51** | 230 | 245 | 121 |

Five findings, in order of importance:

1. **B (global protocol as text) and C+ (gate) TIE on outcome — both reach
   100% goal completion with zero harm, and B does it cheaper** (24.4k vs 79.5k
   tokens/success). They differ only in *how*: B relies on the model *choosing*
   to follow the pasted protocol (no enforcement); C+ blocks wrong messages
   mechanically (it intercepted five premature `Approval` sends and recovered).
   On this model and this case, enforcement was **not needed** for the outcome.
   C+'s measured advantage is over the *observer projection* arms (C / C-min,
   which stalled at 50–60%), **not over B**. Whether enforcement is *necessary*
   — rather than merely sufficient — depends on the model and the task's
   criticality, which is exactly what the two-variant redesign
   (`BENCHMARK_DESIGN_V3_CRITICALITY.md`) is built to test. **This benchmark does
   not show C+ beating B; it shows the validated protocol (present in both)
   doing the work.**
2. **A stronger model makes intent-only agents MORE dangerous, not safer.**
   gpt-5.4's A-arm acts confidently and fast — and committed **22
   unauthorized irreversible acts in 30 attempts** (report filed before
   audit/approval), with 97% of attempts harmful and 0% goal completion.
   Capability amplifies the coordination gap; it does not close it.
3. **B's 100% is real but unguaranteed.** On gpt-5.4 the global-text arm
   completed everything cheaply (24.4k/success), and its 26 raw violations
   all graded benign (S0/S1 — consequence-free reordering such as early
   `Approval` after the audit milestone). But the same arm scored 40% (gpt-4o,
   n=10), 0% (gpt-4o live), and 50% with stalls (banking): its good behaviour
   is a property of the model and the protocol's shape, not of the system.
   It carries no mechanism that *prevents* the A-arm failure mode — and the
   contrast with A (same orchestration, no validated type: 22 disasters)
   shows the validated global type is doing the safety work even here.
4. **Observer-mode C/C-min underperformed B on this model — and the cause is
   liveness, not contracts.** All 13/15 of their harmful-free failures were
   S3 stalls (the ExpenseAnalyst/role-passivity problem §5.1); retries then
   inflated their token bills (154k/84k per trial). C+ uses the *identical
   contracts* plus the projection-driven nudge and gate: 60% → **100%**.
   This isolates the runtime drive as the binding constraint — the cleanest
   evidence in the study that the projection must schedule, not just judge.
5. **Guarantees cost ~3× tokens-per-success over B** (79.5k vs 24.4k) on this
   protocol and model. That is the honest price of "cannot misbehave" vs
   "happened not to misbehave" — and §4.4's levers (scheduling, projected
   views, caching) all reduce it.

## 5. Two systems lessons

### 5.1 Safety monitors are structurally blind to liveness

The dominant failure of the gpt-4o gate run was not any wrong action but
**inaction**: ExpenseAnalyst — whose entire contract is one line, `state 41
(start): SEND ExpenseData → 42` — replied WAIT repeatedly. Its view showed
"(no messages yet)", its role prose ("analyzes expense data") is passive, and
the output rules offer a legitimate-looking WAIT escape. A monitor judges
*events*; a WAIT emits none. A contract can make every action that happens
correct; it cannot, by observation alone, make an action happen. The fix is
to let the projection **drive** the runtime, not just judge it: the harness
knows exactly which roles sit at SEND-only states and can say so at the point
of decision (first slice of EFSM-driven scheduling, shipped in the gate arm).

### 5.2 The tone of the monitor is part of the contract surface

Our first liveness nudge — *"You are an enabled sender — WAIT is OFF-CONTRACT
here; act now"* (with an em-dash that mojibaked in transit) — made gpt-5.4
**refuse outright** ("I'm sorry, but I cannot assist with that request") in
both nudged roles, stalling the entire arm at 0 events, while the same model
followed the identical contract flawlessly in the un-nudged observer arm
(8/8 clean steps). Rephrased descriptively — *"Protocol status: per your role
contract you are at state 41; the available action at this state is SEND
ExpenseData to RevenueAnalyst; there is no incoming message to wait for"* —
the same model complied immediately: the gate arm completed 5/5 trials first-attempt with zero stalls (§4.7). Runtime governance text must be neutral, ASCII-safe, and
informative rather than imperative; stronger models police the difference.

## 6. Limitations

- **Sample sizes**: n=10 (finance ladder), n=2–5 elsewhere; percentages carry
  wide intervals. Branch seeds are balanced but trials are not paired.
- **Severity grader is payload-blind at milestones** (`Approval(False)`
  currently counts as the authorization milestone); choice guards close this
  at the monitor level but the post-hoc grader needs the same upgrade.
- **Choice-guard authoring is manual**; the LLM step that drafts a protocol
  should co-emit its `.refn` (we observed the same drift class three times:
  goals.yaml twice, refn once).
- **No behavioural subtyping yet**: protocol evolution currently proves
  non-impact by contract hash-equality, which is sound but coarse.
  Composition (`// @use` child protocols) is implemented; subtyping is
  roadmap.
- **One model family** (Azure OpenAI gpt-4o / gpt-5.4); the refusal finding
  in §5.2 in particular needs cross-model replication.

## 7. Conclusions

Each layer of STJP buys a different, measurable thing:

| layer | buys | evidence |
|---|---|---|
| Scribble validation | deadlock-freedom for all runs | 4 unsafe drafts rejected pre-runtime; unsafe arm 20% |
| projection → local contract | compliance becomes likely, cheaply | 0% → 80–100% GCR; contract smaller than the prose it replaces |
| monitor (observer) | harm becomes visible | unauthorized debits/filings — flagged by nothing else |
| choice guards | value-wrong branches become visible | typed-arm disasters 2/18 → detectable, then preventable |
| monitor (gate) | harm becomes non-completable | 0 delivered violations; cheaper than delivering mistakes |

Prompts move probabilities; only checks move guarantees. The remaining
frontier is liveness — and the projection already contains the schedule.

---

## Appendix A — Reproducibility

| artifact | location |
|---|---|
| 8-arm registry / runners | `experiments/baselines/` |
| case specs, protocols, goals, guards | `experiments/cases/{finance,banking}/` |
| runs cited (events, prompts, verdicts) | `runs/20260521T111637-n10-dual`, `runs/20260611T175113-n1-dual`, `runs/20260611T183251-n2-dual` (banking), `runs/20260612T151309-n2-dual`, `runs/20260612T155053-n5-dual`, `runs/20260612T162803-n10-dual` |
| severity grader | `experiments/scripts/severity_grader.py` + per-case `protocols/severity.yaml` |
| choice guards + gate implementation | `docs/CHOICE_GUARDS_AND_GATE.md` |
| benchmark design (layers, S0–S4) | `docs/BENCHMARK_DESIGN.md` |
| interactive demo (replayable traces) | `pitch/STJP_Benchmark_Demo.html` |
| run reports | `docs/RUN_REPORT_2026-06-11.md` |

Runner: `python experiments/scripts/case_runner.py <case> <n> --arms <keys>`
(venv: `stjp_core/.venv`). Foundry portal: project `firstProject` on
`foundary-tzuc06` — Agents/Threads for Foundry-stack arms, Tracing
(Application Insights) for all arms.
