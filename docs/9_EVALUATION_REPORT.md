# Evaluation Report — Session-Typed Coordination on Azure AI Foundry

**Date: 2026-07-31.** Paper-style report over the 12-case campaign, in the
format of `paper-writing/v10/sections_eval_results` (which covers a separate,
earlier 5-configuration campaign; the two data sets are never mixed). Raw
evidence tables per case: [`7_RUN_REPORTS_FOUNDRY_REAL_CASES.md`](7_RUN_REPORTS_FOUNDRY_REAL_CASES.md).
All artifacts (per-message logs, summaries, prompts) are committed in
`experiments/cases/<case>/runs/`.

# 1. Evaluation Methodology

## 1.1 Conformance and goal achievement

**Protocol conformance (Set A).** Let T be a trial's message trace and M_r
the local state machine projected (by scribble-java) from the validated
global protocol for role r. A message event e = (sender, receiver, label,
payload) *conforms* iff it is accepted by the sender's machine M_sender
(structurally legal at the current state) and satisfies any refinement
predicate attached to its label. The **Violations** column counts events
rejected by the monitor. Conformance is deterministic, per-message, and uses
no LLM judge.

**Goal achievement (Set B).** Each case defines k goals, each anchored to a
message edge (sender, receiver, label) with a payload predicate. A trial
*succeeds* iff all k goals are satisfied within one of its allowed attempts.
Two grading rungs: **strict** requires the exact (sender, receiver, label)
plus the predicate; **role-pair** requires only (sender, receiver) plus the
predicate, under any label. Settings whose prompt contains the protocol
vocabulary are graded strictly; settings 1–2 (never shown the labels) are
graded on the role-pair rung — a fairness correction, marked **†** in all
tables. The audit finding that motivates the mark: many † successes never
emit the case's terminal message, so a † result is a weaker claim than a
strict one.

**Design principle.** Set A and Set B are reported separately because *type
safety and progress are distinct guarantees*: a team can hold zero
violations while failing its goals (rules followed, session ends before the
finish), or reach goals while violating ordering (right outcome, wrong
path). Both patterns occur in the data (§2.6, §2.4).

## 1.2 Consequence grading

Deviations are graded by consequence: duplicate/no-op messages (waste,
counted in the failure-anatomy re-send statistics); skipped obligations and
wrong ordering (monitor violations); non-termination (trial ends without the
terminal message); and **disasters** — the case's specific irreversible
catastrophe (charge-before-hold, unaudited filing, deploy-before-tests),
scored by declarative Critic policies (`protocols/v1.policy`) over the full
trace. Disasters are reported per trial; two cases (content_pipeline,
pr_review_merge) ship no policy file and are marked "—".

## 1.3 Experimental configurations

Eight configurations per case; each adds one mechanism. All share the same
intent, role descriptions, model, turn limit (`max_steps`) and retry rules.

| # | Setting | Protocol info in prompt | Enforcement | Scheduling |
|---|---|---|---|---|
| 1 | Intent only | none (task description) | none | round-robin |
| 2 | Real skills, no protocol | real published skill files, verbatim | none | round-robin |
| 3 | Global protocol (as text) | full validated global protocol | none | round-robin |
| 4 | Local contract (not enforced) | projected local contract per role | none (observe only) | round-robin |
| 5 | Local contract + gate (verbose) | projected local contract (full prose) | gate rejects violations | round-robin |
| 6 | Local contract + gate (lean) | projected local contract (SEND/RECV table) | gate rejects violations | round-robin |
| 7 | Local contract + gate, no turn hint | as 6, minus per-turn liveness nudge | gate rejects violations | round-robin |
| 8 | Full STJP | as 6 | gate rejects violations | **EFSM-driven** |

The ladder isolates: *knowledge* (1→3), *localization* (3→4), *enforcement*
(4→6), *the liveness hint* (6→7), and *scheduling* (7→8). Setting 2 tests
the industry practice of composing downloaded skills.

**What the scheduler is (and is not).** From the validated global protocol,
scribble-java projects one finite state machine per role: states = where that
role is in the conversation; transitions = the messages it may send or
receive next (*extended* — EFSM — because transitions also carry payload
conditions). These machines are data — maps, not programs. Two components
read the same maps: the **gate** checks each attempted send against the
sender's machine and blocks illegal ones (the machines advance only on
accepted messages); the **scheduler** is a dispatcher that, each turn, asks
"which role has a send enabled in the current state?" and gives the turn to
exactly that role instead of polling round-robin. The scheduler is therefore
NOT itself a state machine and adds no new intelligence and no LLM calls —
it is a lookup in a structure that already exists for enforcement, which is
why it requires the gate to be on (the machines' state must reflect what was
actually delivered) and why its entire cost advantage comes from never
spending a turn on a role that cannot act.

## 1.4 Statistical methodology

All intervals are Wilson score intervals (95%, z = 1.96). n = 10 per cell
(cross-setting comparisons hold n constant); key deltas carry two-sided
Fisher exact p-values. Token counts are the efficiency metric; wall-clock is
not compared (settings run in parallel waves; timing requires sequential
runs). Verification standard: every trial verdict independently re-derived
from raw logs by a second goal-checker implementation — 144 setting-cells,
0 disagreements; per-trial token variance confirms live API calls.

# 2. Experiments and Results

## 2.1 Cases

Twelve cases ordered by coordination complexity: code_execution,
airline_seat (3 roles, straight-line); content_pipeline (4 roles,
straight-line); booking_saga (4 roles, ordered steps); agenticpay_settlement
(4 roles, two branch points); pr_review_merge (4 roles, review loop);
agenticpay_multi_buyer, agenticpay_multi_seller (5 roles, sequenced
multi-party settlement); finance (6 roles, one branch); react18_migration
(6 roles, phases plus a test loop); sdlc_release_gate (7 roles, review
loop); gem_dev_team (7 roles, branch plus loop). Nine compose **real
published skills** (AutoGen, OpenAI Agents SDK, LangGraph, CrewAI,
awesome-copilot, AgenticPay); finance is purpose-built; each case declares
its own catastrophe. Full stories and provenance: 7_RUN.

## 2.2 Models

**gpt-5-mini** (cost-efficient; coordination errors most visible) and
**gpt-5.4** (frontier-capability; tests whether enforcement remains
necessary as quality rises). Both run on the Azure AI Foundry **Agent
Service** — one classic service-side agent per role (visible with its
threads in the portal's previous/classic agents view; the portal's "Hosted"
agent type refers to the separately deployed per-case group agents, which
are NOT the benchmark execution path).

## 2.3 Main results: finance (6 roles, one branch; n = 10)

| # | Setting | GCR mini | GCR 5.4 | Viol. mini | Viol. 5.4 | Tokens/trial mini | Tokens/trial 5.4 |
|---|---|---|---|---|---|---|---|
| 1 | Intent only | 0/10 † | 0/10 † | 359 | 290 | 136,262 | 87,380 |
| 3 | Global protocol (as text) | 10/10 | 10/10 | 16 | 0 | 176,915 | 113,498 |
| 4 | Local contract (not enforced) | 10/10 | **5/10** | 1 | 0 | 160,211 | 120,807 |
| 5 | Local contract + gate (verbose) | 10/10 | 10/10 | 0 | 0 | 237,656 | 193,220 |
| 6 | Local contract + gate (lean) | 10/10 | 10/10 | 0 | 0 | 135,481 | 109,004 |
| 8 | Full STJP | **10/10** | **10/10** | 0 | 0 | **48,584** | **38,955** |

Wilson 95% CI at 10/10 is [72, 100]; at 5/10, [24, 76]. Settings 2 and 7
were not part of this purpose-built case's matrix.

**Findings.**

**(1) Setting 8 is model-invariant at the lowest cost.** 10/10 on both
models at 29–33 calls/trial versus 95–114 for the other local-contract
settings — a 3–4× total-token advantage over every completing alternative.

**(2) Knowledge-only regresses on the stronger model.** Setting 4 drops
10/10 → 5/10 (p = 0.033, Fisher exact) while producing **zero violations**:
gpt-5.4 follows the described contract perfectly but, unscheduled, consumes
114 calls/trial and exhausts the turn limit before the terminal message.
Type safety without progress, reproduced live.

**(3) Intent-only is a catastrophe generator here.** 0/10 with 290–359
violations and 9–10/10 unaudited-filing disaster trials — the case's
specific catastrophe concentrated entirely in the unenforced setting.

## 2.4 Branching case: agenticpay_settlement (4 roles, two branches; n = 10)

| # | Setting | GCR mini | GCR 5.4 | Tokens/trial mini | Tokens/trial 5.4 |
|---|---|---|---|---|---|
| 1 | Intent only | 0/10 † | 0/10 † | 97,733 | 72,252 |
| 2 | Real skills, no protocol | 0/10 † | 0/10 † | 51,222 | 50,156 |
| 3 | Global protocol (as text) | 10/10 | 10/10 | 147,402 | 126,084 |
| 4 | Local contract (not enforced) | 4/10 | 7/10 | 185,165 | 99,594 |
| 5 | Local contract + gate (verbose) | 1/10 | 3/10 | 58,825 | 75,460 |
| 6 | Local contract + gate (lean) | 0/10 | 4/10 | 30,220 | 42,638 |
| 7 | Local contract + gate, no turn hint | 1/10 | 9/10 | 32,480 | 33,384 |
| 8 | Full STJP | **10/10** | **10/10** | **18,461** | **15,683** |

On a branching protocol, only two settings complete on both models: the full
protocol text (setting 3) and full STJP (setting 8) — with setting 8 roughly
**8× cheaper** (14–16 calls at ~1.1k tokens/call versus 33–36 calls at
~3.8k). The per-turn hint hurts here: setting 7 (no hint) reaches 9/10 on
gpt-5.4 versus 3–4/10 for the hinted settings 5–6 (p = 0.0011).

## 2.5 Hard shapes: loops and 7-role teams (gpt-5.4, n = 10)

| Case | Setting 8 | Best other completing setting | Setting 8 calls vs best other |
|---|---|---|---|
| gem_dev_team (7 roles, branch + loop) | **10/10**, 14.5 calls | none ≥ 4/10 (best: setting 4, 3/10; p = 0.003) | — (sole finisher) |
| pr_review_merge (4 roles, review loop) | **10/10**, 34.9 calls | none ≥ 4/10 (best: setting 7, 3/10) | — (sole finisher) |
| sdlc_release_gate (7 roles, review loop) | **10/10**, 16.8 calls | setting 5: 10/10, 56.1 calls | 30% |
| react18_migration (6 roles, phases + loop) | **10/10**, 54.2 calls | setting 7: 10/10, 65.8 calls | 82% |

On looping protocols, scheduling separates from enforcement decisively: on
gem and pr_review **no setting without the scheduler completes** (rules
followed, turn limit exhausted); on sdlc only the verbose gate also
finishes, at 3.3× the calls and 5.8× the tokens. react18 is the honest
boundary: a no-hint gate matches setting 8's completion (the loop is driven
by a single role, so round-robin waste is small), and on gpt-5-mini
setting 6 edges setting 8 there (10/10 vs 9/10).

## 2.6 Model-scaling analysis

GCR mini → 5.4 for every case (settings 3–8; full matrix in
`8_ANALYSIS_FINDINGS.md`). Classification of each setting across the 12
cases:

1. **Invariant** — setting 8: 10/10 in 21 of 23 model-runs, best-or-tied in
   the other two; never regresses.
2. **Positively scaling** — setting 7 on settlement (1→9), setting 5 on
   sdlc (4→10): improve with capability, but require the stronger model.
3. **Negatively scaling** — setting 4 on finance (10→5) and multi_buyer
   (10→7); setting 6 on react18 (10→1, p = 0.0001); setting 3 on gem
   (9→3); even setting 1 on content (9→0 †). "Use a bigger model" makes
   these *worse*.

The same mechanism underlies every negative cell: the stronger model's
longer, individually-valid outputs consume the turn limit faster when
nothing schedules the turns. Model scaling is not a substitute for
structural enforcement.

## 2.7 Cost analysis: the scheduling dividend

Cost decomposes as calls/trial × tokens/call. Two independent mechanisms:

- **Fewer calls (scheduling):** the EFSM scheduler polls only the role with
  an enabled send: finance 32.8 vs 101.2 calls (setting 6), sdlc 16.8 vs
  56.1 (setting 5), settlement 14.2 vs 33.0 (setting 3).
- **Smaller prompts (projection):** setting 3 pays 2.8–3.8k tokens per call
  (each agent repeatedly processes the whole protocol text) versus 0.6–1.3k
  for local-contract settings — a ~3× per-call gap independent of
  scheduling.

Cross-case, setting 8's calls as a share of the best completing alternative
fall monotonically with coordination complexity: 100% (3–4 roles,
straight-line — nothing to save) → 80% (ordered steps) → 43–54% (branching,
sequenced multi-party) → 30–32% (6–7 roles) → sole-finisher on the
branch+loop shapes. Cost comparisons are made only among settings that
complete; a cheap failure is not cheap per delivered result.

## 2.8 Discussion: design principles

**Principle 1 — Type safety does not imply progress.** Perfect conformance
with failed completion occurs in every hard case (finance setting 4,
settlement settings 5–6, sdlc settings 6–7, gem all gated non-scheduled
settings). A monitor verifies that whatever happens is correct; only the
scheduler makes the right things happen in time.

**Principle 2 — Model scaling is not a substitute for enforcement.** Five
settings regress on the stronger model somewhere in the matrix; the
regressions concentrate exactly where guidance (described contracts, turn
hints) substitutes for structure.

**Principle 3 — The cheapest correct system is the most constrained.** The
savings come from not making calls whose answers cannot advance the
protocol, and from each agent reading one slice instead of the whole
rulebook. The protocol's own state machine is the scheduling oracle.

**Boundary conditions, stated plainly.** On short straight-line pipelines
every contract setting completes and setting 8 ties rather than wins; on
one loop shape (react18) a no-hint gate equals its completion. The
scheduler's value is a function of coordination complexity — visible from
zero on trivial pipelines to decisive (sole finisher) on branch+loop shapes.

## Scope

memory_race (both models) joins the matrix when its runs pass
verification. pr_review_merge is complete on both models: full STJP is the
only setting at 10/10 on both (the other settings flip — gpt-5-mini
completes 7–10/10 on the contract settings where gpt-5.4 completes 0–3/10),
reinforcing the model-invariance finding. Settings 1–2 grading (†), the
verification standard, and per-case evidence tables: 7_RUN. Failure
taxonomy of the no-protocol settings: 7_RUN, FAILURE ANATOMY.
