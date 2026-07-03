# Experiment Design v2 — MPST vs. Intent-only Comparison

*Wrap-up of 2026-05-18. Supersedes `EXPERIMENT_DESIGN.md` (the v1 4-scenario
finance design from earlier sessions). v1 is archived in `docs/archive/` as historical
record; this doc is the working plan going forward.*

> **Status 2026-06-12** — this design is implemented and running; current
> scoring lives one level up in `docs/BENCHMARK_DESIGN.md` (gated layers,
> GCR / path adherence / cost-of-success) **plus the v2.1 addendum:
> consequence-graded violations S0–S4** (`experiments/scripts/severity_grader.py`,
> per-case `protocols/severity.yaml`), which supersedes raw violation counts
> for headline claims. `case_runner.py` now takes `--arms a,b,c`. The
> **banking** case is live (LLM-drafted protocol, run
> `20260611T183251-n2-dual`) and is the primary safety case; finance is the
> efficiency case. Latest results: `docs/RUN_REPORT_2026-06-11.md`.

This document has four parts:
1. The **success-metric framework** — three parallel metrics, each
   measuring a different question. Choosing one metric is choosing a
   research question.
2. What **non-MPST arms** (`bare`, `maf_native`, `maf_foundry`,
   `maf_groupchat`) actually receive as input — the matched-control
   prompt structure.
3. **Concrete worked examples** of the prompts and a sample trace,
   scored under each metric, so the framework is unambiguous.
4. **Three benchmark tasks** designed to exercise different MPST
   features and produce different separation patterns between arms.

---

## The evaluation in two sets, plus process cost — reconciled framing (2026-05-20)

The metric design, restated at the top level. Every benchmark run produces
**three groups of numbers**; a fair MPST-vs-intent-only comparison reports
all three and never collapses them.

### Set A — Global-type conformance

*Only meaningful for arms that were given a global type* (`spec_llmvalid`,
`min_llmvalid`, `maf_groupchat_llmvalid`; `maf_groupchat_unsafe` runs
**observational** because Scribble refuses to project it). The runtime
monitor (`stjp_core/monitor.py`, walking each role's projected EFSM) checks
whether every observed message conforms to the protocol — right label,
right state, payload refinement holds. Output: the **violation count and
violation types** in `summary.json` (`off_protocol`, `refinement_failed`,
`unexpected_peer`, `premature_termination`, …). Intent-only arms (`bare`,
`maf_native`, `maf_foundry`, `maf_groupchat`) have no global type, so Set A
is **N/A** for them — they cannot deviate from a contract they were never
given. Set A answers: *how faithfully does local agent behaviour follow the
global type?*

### Set B — Goal achievement

*For every arm.* Goals are the externally-observable outcomes the run must
achieve. There is always **more than one**: an **ultimate goal** (e.g. "a
final report is delivered to the user") and one or more **intermediate
goals** — required checkpoints such as "a tax-verifier approval interaction
occurred" or "the audit step happened". Intermediate goals are how a
required security / policy check becomes something checkable. A run
succeeds on Set B only if **all** its applicable goals pass.

Set B is judged through **three lenses** of increasing leniency — and these
are exactly the three metrics detailed in §1 below:

| Set B lens | check | who it applies to |
|---|---|---|
| **strict** | goal anchor matched on exact `(sender, receiver, label)` + predicate | with-vocabulary arms only — N/A otherwise |
| **role-pair** | `(sender, receiver)` + predicate, label dropped | all arms |
| **semantic** | LLM-judged against the goal's NL description | all arms |

So the v2 "three-metric framework" (§1) **is** Set B. Set A (conformance)
is a separate axis the original v2 doc surfaced only as the "total
violations" row — read it as a co-equal result, not a footnote.

### Process cost — for every arm

Independent of pass/fail: **tokens** (prompt + completion, cumulative to
success), **LLM calls**, **wall-clock seconds**, **turns / interactions**
(trace event count), **attempts** (retries to success), and a derived
**tokens/second**. Two arms can both reach 100% on Set B at very different
cost; that gap is itself a headline finding.

### Where the three groups land in the code (2026-05-20)

| Group | Field(s) | File | When |
|---|---|---|---|
| Set A — conformance | `violations`, `violation_types` | `summary.json` (monitor, via `LiveEventEmitter`) | live, every run |
| Set B — strict | `success_rate_pct` (retry-to-success is strict-goal-gated); `strict_pct`, `strict_per_goal` | `summary.json`; `summary_eval.json` | live; end of run |
| Set B — role-pair | `role_pair_pct`, `role_pair_per_goal` | `summary_eval.json` | end of every run (deterministic, free) |
| Set B — semantic | `semantic_pct`, `semantic_per_goal` | `summary_eval.json` | end of run **only with `--semantic`** (~5 LLM calls/trial/arm) |
| Process cost | `avg_tokens_*`, `avg_calls_*`, `avg_seconds_*`, `tokens_per_second`, `events`, `avg_attempts_*` | `summary.json` | live, every run |

`case_runner.py` runs the Set B evaluation (`evaluate_run.evaluate`)
automatically at the end of **every** run — it is no longer a separate
manual `evaluate_run.py` step. The deterministic lenses (strict, role-pair)
always run; the LLM-judged `semantic` lens runs only when `--semantic` is
passed, so a routine run spends no LLM budget on evaluation.
`evaluate_run.py` is still runnable standalone (semantic on by default
there; `--no-semantic` to skip it).

### Branch-conditional goals

A goal in `case.yaml` may declare `branch: <hint>`. It is then enforced only
on trials whose branch hint matches; on any other branch it is **vacuously
satisfied** instead of failed for a missing anchor. This fixes the
branch-asymmetric bug (open issue #1): finance `G1` (high-revenue) and `G2`
(audit) anchor on messages that exist *only on the high branch*, so on
standard-branch trials they are skipped, not failed. Goals with **no**
`branch` stay mandatory on every branch — a missing anchor is a real
failure (e.g. `G6`, the terminal report, must never be vacuously passed).
Implemented in `goal_elicitor.verify_goals_against_trace` and in both
deterministic verifiers of `evaluate_run.py`.

---

## 1. What "fair" depends on the question

Multi-agent success is not a single number. Three legitimate questions, each
with its own metric:

| metric | what it measures | who can pass | implementation status |
|---|---|---|---|
| **strict** | "did agents use the exact protocol vocabulary?" | **only arms with vocabulary** (spec/min/MAF arms told the global type); intent-only arms get **N/A** | LIVE in `case_runner.py` (the `success_rate_pct` column) |
| **role-pair** | "did the right agents exchange the right *kind* of payload, regardless of label?" | any arm whose role-pair semantics align with the goal anchors | built in `experiments/scripts/evaluate_run.py`; post-hoc |
| **semantic** | "did the conversation, judged by an LLM against the goal's NL description, achieve the goal?" | any arm that did the right work in any vocabulary or role pairing | built in `evaluate_run.py`; LLM-judged per (goal, trace); cached |

### Why three metrics, not one

- **strict**: "Did the agents follow the protocol's contract?" — the
  natural question for arms that were told the protocol. Asking it of
  arms that were NOT told the protocol is unfair — they can't match
  labels they were never given. Hence **N/A** for intent-only arms.
- **role-pair**: "Even if agents invented vocabulary, did the right
  pair of roles exchange a payload satisfying the predicate?" — a
  middle ground. Tests structural coordination without testing
  vocabulary memory.
- **semantic**: "Did the conversation, in spirit, achieve what the
  goal asks for?" — fair to all arms. Costs an LLM judge call per
  (goal, trial) and introduces a small amount of judgment variance.

**The gap between metrics is itself a finding:**

- **strict 100%, semantic 100%** — agents both followed the contract
  and achieved the intent. Both vocabulary and outcome correct.
- **strict 0%, role-pair 60%, semantic 80%** — agents did the right
  work but invented their own vocabulary. The protocol's contribution
  is *common ground*, not *capability*.
- **strict 0%, role-pair 0%, semantic 0%** — agents failed to
  coordinate at all. Independent of vocabulary.

### How to read a result responsibly

- Report all three columns side by side, never just one in isolation.
- For arms without vocabulary, show `N/A` in the strict column —
  not `0%` — so the reader doesn't conflate "fails strict by design"
  with "actually achieves nothing."
- The semantic metric is the most charitable; if even it shows 0%,
  the arm genuinely failed.

---

## 2. What non-MPST arms receive as input

The **matched-control prompt structure** for arms that DO NOT get a global
type drafted (`bare`, `maf_native`, `maf_foundry`, `maf_groupchat`). This
is the design as of 2026-05-18 (after applying the five fairness fixes
from this session).

Every non-MPST arm receives the same five blocks, in this order:

1. **Identity** — "You are the **{role}** in a small multi-agent
   {case_id} pipeline."
2. **Intent** — the natural-language description of the user's task
   (paragraph from `case.yaml:intent`).
3. **Goals** — the list of `G1..GN` with their NL descriptions.
4. **Role descriptions** — *(new, 2026-05-18 fairness fix)* prose
   description of what every role does. Held constant across all
   arms (MPST arms also see this). Without it, MPST arms get role
   descriptions implicitly through the projected local type while
   non-MPST arms get only role names — a confound that unfairly
   punished non-MPST arms in earlier rounds.
5. **Termination instruction** — *(new, 2026-05-18 fairness fix)*
   "Stop participating (reply WAIT) once the final report has been
   delivered to the user". Without it, non-MPST arms had no
   termination signal whereas MPST arms knew via their projected
   local type's accepting state.
6. **Output schema** — the JSON format every agent must emit per turn:
   `{"send_to": "<RoleName>", "label": "<MessageLabel>", "payload":
   "<value>", "rationale": "<one sentence>"}` (or
   `{"send_to": null, "label": "WAIT", "payload": "", "rationale":
   "..."}` if nothing to send).

Critically, the non-MPST prompt **never contains**:
- Any message labels (no `HighRevenue`, `FetchData`, etc.)
- Any sender → receiver routing ("X sends to Y")
- Any ordering ("first do A, then B")
- Any structural protocol (no graph, no branches, no state machine)
- Any refinement predicates

The MPST arms get one additional block ON TOP of these six, varying by arm:

| arm class | extra block on top |
|---|---|
| `maf_groupchat_unsafe` / `_llmvalid` | full **global protocol** (raw Scribble + NL paraphrase, same to every role) |
| `spec_llmvalid` | **projected local type** for this role (verbose Claude markdown — state machine + transitions + refinement guards) |
| `min_llmvalid` | **projected local type** for this role (minimal SEND/RECV state table + refinement guards) |

So the variable being measured is purely the protocol-info layer. Everything
else — intent, goals, role descriptions, termination instruction, output
schema — is held identical across all arms.

---

## 3. Concrete worked examples

### 3.1 The bare Fetcher prompt, byte-for-byte (finance case, 2026-05-18)

```
You are the **Fetcher** in a small multi-agent finance pipeline.

User intent:
We need a Quarterly Finance Report pipeline that takes raw revenue data
and produces a written report. The pipeline distinguishes 'high' revenue
(above $50k, requires a tax-specialist audit) from 'standard' revenue.
Every revenue analysis must be approved by a tax verifier before it lands
in the report.

Goals:
  - G1: High-path revenue must exceed $50,000
  - G2: Audit result must be non-empty
  - G3: Tax verifier must approve the audit explicitly
  - G4: Revenue analysis must be substantive (>10 chars)
  - G5: Expense analysis must be substantive (>10 chars)
  - G6: A final quarterly report is produced and delivered to the user,
    terminating the pipeline

Role descriptions (what each agent does):
  - Fetcher: retrieves raw revenue data on request
  - RevenueAnalyst: analyzes revenue, classifying it as high (>$50k)
    or standard
  - ExpenseAnalyst: analyzes expense data
  - Writer: composes the final quarterly report from approved analyses
    and delivers it back to the user (the Fetcher)
  - TaxVerifier: verifies the tax audit is correct before approved
    figures land in the report
  - TaxSpecialist: audits high-revenue items when an audit is requested

You communicate with the other agents (RevenueAnalyst, ExpenseAnalyst,
Writer, TaxVerifier, TaxSpecialist).

Stop participating (reply WAIT) once the final report has been delivered
to the user (i.e. once a message labelled 'GenerateReport' or semantically
equivalent has been sent and no further action is needed of you).

Output rules:
- Reply with a SINGLE JSON object, no prose, no fences.
- Schema: {"send_to": "<RoleName or null>", "label": "<MessageLabel>",
  "payload": "<value or empty>", "rationale": "<one sentence>"}
- If nothing to send, reply: {"send_to": null, "label": "WAIT",
  "payload": "", "rationale": "..."}
```

That is the **complete** prompt. There is no protocol structure, no
label vocabulary, no ordering. The only structural information is what's
implicit in the goal descriptions ("audit", "approval", "report") and the
role descriptions ("audits high-revenue items").

### 3.2 A bare trial trace (representative, from 2026-05-18 runs)

Bare agents on a high-branch trial typically produce something like this
(condensed; real traces are 5–12 events per attempt × up to 3 attempts):

```
Fetcher        → RevenueAnalyst : REQUEST_REVENUE_ANALYSIS()
RevenueAnalyst → TaxSpecialist  : REQUEST_HIGH_REVENUE_AUDIT(75000)
TaxSpecialist  → TaxVerifier    : REQUEST_AUDIT_APPROVAL("audit complete for $75K")
TaxVerifier    → TaxSpecialist  : AUDIT_APPROVAL("APPROVED")
TaxSpecialist  → Writer         : SEND_HIGH_REVENUE_ANALYSIS("High revenue audit completed at $75K, approved")
ExpenseAnalyst → Writer         : EXPENSE_ANALYSIS("Q3 expenses totalled $42K across operations")
Writer         → Fetcher        : DELIVER_REPORT("Quarterly report: revenue $75K, expenses $42K, all audited")
```

Notice:
- Labels are entirely invented: `REQUEST_REVENUE_ANALYSIS`, `AUDIT_APPROVAL`,
  `SEND_HIGH_REVENUE_ANALYSIS`, `DELIVER_REPORT`.
- Role pairs differ from the canonical protocol — e.g., TaxVerifier's
  approval goes back to TaxSpecialist, not directly to RevenueAnalyst as
  G3's anchor would expect.
- The conversation reaches a terminal-like state but does not use the
  exact label `GenerateReport`.

### 3.3 How each metric scores this trace

Using the goal set from `case.yaml` (anchored on canonical labels):

| goal | what it needs | strict | role-pair | semantic |
|---|---|:---:|:---:|:---:|
| G1: high revenue > $50K | event `RevenueAnalyst → TaxSpecialist : HighRevenue` with `float(x) > 50000` | ✗ (label is `REQUEST_HIGH_REVENUE_AUDIT`) | ✓ (RA→TS event exists, `float(75000) > 50000`) | ✓ (LLM judges "the high-revenue figure is communicated to TaxSpecialist") |
| G2: audit result non-empty | event `TaxSpecialist → RevenueAnalyst : AuditedRevenue`, `len(x) > 0` | ✗ (no event between these roles with this label) | ✗ (no event from TS to RA in this trace) | ✓ (LLM judges "the audit was performed and communicated") |
| G3: tax verifier explicit approval | event `TaxVerifier → RevenueAnalyst : RevenueAuditApproval`, contains `"approved"` or `"ok"` | ✗ | ✗ (TV → TS, not TV → RA) | ✓ (LLM judges "the audit was explicitly approved by TaxVerifier") |
| G4: revenue analysis substantive | event `RevenueAnalyst → Writer : RevenueAnalysis`, `len(x) > 10` | ✗ | ✗ (no RA → Writer event) | ✗/✓ (depends on whether LLM accepts TS→Writer "High revenue audit completed..." as a substantive revenue analysis) |
| G5: expense analysis substantive | event `ExpenseAnalyst → Writer : ExpenseAnalysis`, `len(x) > 10` | ✗ | ✓ (EA → Writer event, payload "Q3 expenses..." is >10 chars) | ✓ |
| G6: terminal report delivered | event `Writer → Fetcher : GenerateReport` | ✗ (label is `DELIVER_REPORT`) | ✓ (Writer → Fetcher event exists, predicate is True) | ✓ (LLM judges "the report was produced and delivered") |

Trial-success requires **all** goals to pass:

| metric | goals passed | trial succeeds? |
|---|:---:|:---:|
| strict | 0 / 6 | ✗ |
| role-pair | 3 / 6 | ✗ |
| semantic | 5 / 6 (with G4 likely passing) | ✗ |

The **gap from 0/6 strict to ~5/6 semantic** is exactly the cost of *not
having shared vocabulary*. The bare agents did the work; they could not
prove they did it in the protocol's terms. With the same trace, an MPST
arm using the canonical labels would score 6/6 on all three metrics.

If this trace gave us 5/6 semantic, the natural question becomes: is the
1/6 gap "shared vocabulary lets agents prove correctness with less
effort," or "the missing goal was genuinely missed"? That's what the
adversarial test cases (§4) probe.

### 3.4 How to read the per-goal table in a writeup

Don't just report a single percentage per arm. Show per-goal breakdown
per metric:

```
                    strict (A)              role-pair                semantic
arm              G1 G2 G3 G4 G5 G6      G1 G2 G3 G4 G5 G6      G1 G2 G3 G4 G5 G6
bare             N  N  N  N  N  N       50 20  0 30 80 60       80 70 60 60 90 70
spec_llmvalid    100 100 100 100 100 100  100 100 100 100 100 100  100 100 100 100 100 100
min_llmvalid     100 100 100 100 100 100  100 100 100 100 100 100  100 100 100 100 100 100
```

(Illustrative numbers; `N` = N/A. Per-goal breakdown lets a reader see
*which* goals each arm achieves and where it breaks down — which is the
diagnostic story, not the headline number.)

---

## 4. Three benchmark tasks

Each task is designed to exercise a different MPST feature and produce
a different separation pattern. Together they cover the main coordination
problems where session types are claimed to help.

### Principle

Every success metric below is defined as an **external observable on the
message trace**. Nothing references the protocol's structure. The
MPST-equipped arms get the protocol as a coordination aid; the
intent-only arms must achieve the same observables by other means.
**Fair comparison requires that a developer who has never heard of
session types could read the metric and agree it matters.**

| task | MPST feature stressed | why intent-only struggles |
|---|---|---|
| Banking transaction | Choice (amount-dependent path) + safety invariants | Money conservation under partial-failure paths; correct routing to Approver for large amounts |
| Travel booking with rollback | Transactional integrity + exception propagation | Partial-booking states; rollback coordination across roles |
| Multi-source RAG with verification | Recursion + content correctness | Synthesis-before-retrieval; unverified claims; unbounded retry |

---

### Task 1 — Banking Transaction

#### Description
Initiator requests a transfer of amount X from account A to account B.
SourceBank debits A; DestBank credits B; AuditLog records the operation.
For amounts above a threshold (e.g., $10,000), an Approver must authorize
before any debit/credit occurs. If SourceBank rejects (insufficient funds,
frozen account), nothing moves and AuditLog records the rejection.

#### Why this task
Tests safety invariants under a value-dependent choice and an exception
path. Conservation-of-money is a clean, protocol-agnostic invariant.
The large/small branching exposes the *knowledge-of-choice* failure mode
(Approver and DestBank behave differently across branches).

#### Roles
`Initiator`, `SourceBank`, `DestBank`, `AuditLog`, `Approver`.

#### Natural-language intent (given to every arm)
> Transfer amount X from account A to account B. If X exceeds $10,000,
> the transfer requires Approver authorization before any money moves.
> SourceBank debits A; DestBank credits B; AuditLog records the final
> outcome. If SourceBank cannot complete the debit (insufficient funds,
> frozen account), the transfer fails, no money moves, and AuditLog
> records the rejection.

#### Goals (given to every arm)
- **G1**: The final balance of A decreases by exactly X (success) or is
  unchanged (rejection).
- **G2**: The final balance of B increases by exactly X (success) or is
  unchanged (rejection).
- **G3**: AuditLog contains exactly one terminal record (success or
  rejection), not both, not neither.
- **G4**: For X > $10,000, Approver issued explicit authorization before
  any balance changed.

#### Protocol sketch (only spec/min arms see this)
```scribble
global protocol Transfer(role I, role S, role D, role A, role Audit) {
    Request(Amount) from I to S;
    choice at S {
        // Large amount path
        ApprovalNeeded(Amount) from S to A;
        choice at A {
            Authorize(Amount) from A to S;
            Authorize(Amount) from A to D;
            Debit(Amount) from S to D;
            Credit(Amount) from D to Audit;
            Success(Amount) from Audit to I;
        } or {
            Deny() from A to S;
            Deny() from A to D;
            Rejected("approver_denied") from S to Audit;
            Failure(String) from Audit to I;
        }
    } or {
        // Small amount path
        Debit(Amount) from S to D;
        Credit(Amount) from D to Audit;
        Success(Amount) from Audit to I;
    } or {
        // SourceBank rejection
        Rejected(String) from S to D;
        Rejected(String) from S to Audit;
        Failure(String) from Audit to I;
    }
}
```

#### Metrics

**Safety invariants** (computed by trace checker; fail if ever violated):
- `INV1_conservation`: At every point in the trace, total balance across
  A and B (plus any escrow) equals the initial total. Never positive,
  never negative.
- `INV2_no_unauthorized_large`: For X > $10,000, no message tagged as a
  balance change occurs in the trace before an Approver authorization
  event.
- `INV3_no_credit_without_debit`: DestBank never updates B's balance
  unless SourceBank has already confirmed A's debit.
- `INV4_terminal_audit`: AuditLog produces exactly one terminal record
  per transaction. Not zero, not two.

**Terminal outcomes** (binary scoring at end of trace):
- `OUT_correct_state`: Final balances match either the success state
  (A−X, B+X) or the rejection state (A, B unchanged), with a matching
  audit record.
- `OUT_initiator_informed`: Initiator received a terminal status
  message (success or failure).

**Milestone observables** (count occurrences; semantic equivalence allowed):
- `MS_debit_confirmed`: SourceBank emitted any message semantically
  expressing debit confirmation.
- `MS_credit_confirmed`: DestBank emitted any message semantically
  expressing credit confirmation.
- `MS_approver_decision`: For X > $10,000, Approver issued any
  authorize/deny message.
- `MS_audit_received_outcome`: AuditLog received any message
  communicating the terminal state.

**Process cost**: tokens, LLM calls, wall-clock, distinct labels
invented across the trace.

**Negative trace properties**:
- `NEG_orphan_credit`: A credit event with no preceding debit event in
  the trace.
- `NEG_double_debit`: Two debit events for the same transaction.
- `NEG_post_terminal_activity`: Any message sent after the audit
  terminal record.
- `NEG_stuck_steps`: ≥ K turns with no new information added to the trace.

#### One adversarial test case
X = $9,999.99 (just under the threshold). SourceBank account A has
$9,000. **Expected**: SourceBank rejects on insufficient funds, audit
records rejection, no money moves, Approver is never invoked. The
intent-only arm often fails `INV2` in adjacent variants (X = $10,000.01
with sufficient funds) by skipping the Approver step.

---

### Task 2 — Travel Booking with Rollback

#### Description
User requests a trip: flight (dates D1–D2), hotel (D1–D2), and rental
car (D1–D2), total cost ≤ B. Three booking agents (Flight, Hotel, Car)
operate in parallel under a Coordinator. PaymentAgent charges only after
all three confirm available within budget. If any leg fails or the total
exceeds budget, the Coordinator must trigger a clean rollback: any
provisional bookings released, no payment charged.

#### Why this task
Tests transactional integrity ("all-or-nothing") with exception
propagation across roles. The rollback path is structurally a non-local
choice — every booking agent's behavior differs between success and
failure paths, and all must be informed. Partial-booking outcomes are
catastrophic in production and very common in intent-only systems.

#### Roles
`User`, `Coordinator`, `Flight`, `Hotel`, `Car`, `Payment`.

#### Natural-language intent (given to every arm)
> Book a flight, hotel, and rental car for the requested date range.
> Total cost must not exceed the user's budget. If all three are
> available within budget, charge payment and confirm to the user. If
> any one is unavailable or the total exceeds budget, release any
> provisional bookings, do not charge payment, and inform the user that
> the trip could not be booked.

#### Goals
- **G1**: Either all three legs are confirmed and payment is charged,
  OR no payment is charged and no leg remains in a "booked" state.
- **G2**: Total amount charged to payment, if any, equals sum of
  confirmed leg prices.
- **G3**: User receives exactly one terminal message: trip confirmed
  (with itinerary) or trip cancelled (with reason).
- **G4**: All booked dates fall within the requested range D1–D2.

#### Metrics

**Safety invariants**:
- `INV1_atomicity`: At termination, the set of legs in "confirmed"
  state is either {flight, hotel, car} or {}. Never a strict subset.
- `INV2_payment_only_after_all_quoted`: Payment is never charged unless
  Flight, Hotel, and Car have all issued explicit quotes within budget.
- `INV3_no_charge_on_rollback`: If any leg failed or budget exceeded,
  payment was not charged.
- `INV4_dates_within_range`: Every confirmed booking has dates in [D1, D2].
- `INV5_budget_respected`: Total charged ≤ B.

**Terminal outcomes**:
- `OUT_atomic_state`: Final state is fully booked + charged, or fully
  unbooked + uncharged.
- `OUT_user_informed`: User received a terminal confirmation or
  cancellation message.
- `OUT_itinerary_correct`: If confirmed, itinerary matches the
  confirmed legs.

**Milestone observables**:
- `MS_each_agent_quoted`: Each of Flight/Hotel/Car emitted any message
  semantically expressing a quote with price and dates.
- `MS_coordinator_aggregated`: Coordinator emitted any message
  indicating it had received all three quotes.
- `MS_payment_authorized`: Payment received any authorization message
  from the Coordinator.
- `MS_rollback_initiated`: On failure, Coordinator emitted any
  rollback/cancel message to each booking agent.

**Negative properties**:
- `NEG_partial_confirmation`: Final state has 1 or 2 confirmed legs
  (not 0, not 3).
- `NEG_orphan_charge`: Payment charged with at least one leg
  unconfirmed.
- `NEG_double_book`: Same agent emits two confirmation messages for
  the same trip.
- `NEG_dangling_booking`: After "cancel" terminal, any agent still
  reports a booked state.

#### One adversarial test case
Budget = $1,000. Flight quotes $400, Hotel quotes $400, Car quotes $250
(total $1,050 — over budget by $50). **Expected**: clean rollback, no
payment, user informed. Intent-only arms frequently fail `INV1` by
confirming two legs and "forgetting" to cancel them, or by charging the
partial total.

---

### Task 3 — Multi-source RAG with Verification

#### Description
User asks a factual question. QueryPlanner decomposes it. Two
Retrievers fetch documents in parallel from different sources.
Synthesizer drafts an answer with citations. FactChecker verifies each
cited claim against the retrieved documents. If verification fails,
Synthesizer revises and resubmits (up to K rounds); if still failing,
the system emits "cannot answer" with an explanation.

#### Why this task
Tests recursion (the verification loop) and content correctness.
Without protocol, Synthesizer often emits answers before retrieval
completes; FactChecker often doesn't receive the synthesis; the loop
either runs unbounded or terminates without verification. Citation
validity is a clean, protocol-agnostic correctness criterion.

#### Roles
`User`, `QueryPlanner`, `Retriever1`, `Retriever2`, `Synthesizer`,
`FactChecker`.

#### Natural-language intent
> Answer the user's question using retrieved documents. Two retrievers
> fetch in parallel. The synthesizer drafts an answer with citations.
> Every citation must point to a retrieved document. A fact-checker
> verifies each cited claim against the source. If verification fails,
> the synthesizer revises. After at most K verification rounds, either
> emit a verified answer or emit "cannot answer" with a reason.

#### Goals
- **G1**: Final user-facing answer either passes fact-check or is
  "cannot answer" with a documented reason.
- **G2**: Every citation in the final answer resolves to a document
  actually retrieved during the run.
- **G3**: The number of synthesis-verification cycles is at most K.
- **G4**: The user receives exactly one terminal answer.

#### Metrics

**Safety invariants**:
- `INV1_no_synthesis_before_retrieval`: No Synthesizer message
  contains content unless both Retrievers have emitted
  retrieved-content messages.
- `INV2_no_answer_without_factcheck`: User never receives a terminal
  answer unless FactChecker has issued a verdict on the synthesis
  being emitted.
- `INV3_citation_validity`: Every citation in the final answer
  matches some retrieved document by ID or content hash.
- `INV4_loop_bounded`: The synthesis-verification cycle count never
  exceeds K.

**Terminal outcomes**:
- `OUT_user_received_terminal`: Exactly one terminal message reaches
  the user.
- `OUT_factcheck_passed_or_documented_failure`: Terminal is either
  fact-checked-success or explicit "cannot answer."
- `OUT_citation_coverage`: For factual claims in the answer, ≥ Y%
  have a citation that survives validation.

**Milestone observables**:
- `MS_both_retrievers_responded`: Both retrievers emitted any message
  containing retrieved content (or explicit "no results").
- `MS_synthesis_drafted`: Synthesizer emitted any draft answer message.
- `MS_factcheck_verdict`: FactChecker emitted any pass/fail verdict
  on a draft.
- `MS_loop_iterations`: Count of synthesis-verification cycles
  (should be ≤ K).

**Negative properties**:
- `NEG_hallucinated_citation`: A citation that does not match any
  retrieved document.
- `NEG_unbounded_loop`: Cycle count > K.
- `NEG_orphan_draft`: A synthesis emitted but never reaching
  FactChecker.
- `NEG_premature_answer`: User-facing answer emitted before
  fact-check verdict.

#### One adversarial test case
Question requires synthesis across both retrievers' documents.
Retriever1 returns a fact that contradicts Retriever2. The correct
behavior is either: (a) synthesizer reconciles and cites both with
explanation, fact-checker passes; or (b) fact-checker flags the
contradiction, system emits "cannot answer" with the contradiction as
reason. Intent-only arms often emit one side's answer without
acknowledging the conflict, failing `INV2` or `INV3`.

---

## Implementation notes

### Semantic equivalence for milestones

Milestones must be checkable across arms that use different
vocabularies. Define each milestone as an equivalence class of messages,
scored by an LLM judge with a rubric:

```
Milestone: MS_debit_confirmed
Rubric: A message from SourceBank to DestBank or AuditLog that
        communicates that account A has been debited by amount X,
        regardless of label. Examples that count:
          - Debit(X)
          - DEBIT_CONFIRMED { amount: X }
          - "Account A debited by $X"
          - "Funds released: X"
        Examples that do not count:
          - A quote ("can debit X")
          - A request ("please debit X")
          - An ack of the request without confirming the debit happened
```

A separate small LLM (not the agent under test) judges each message in
the trace against each milestone rubric. **Cache the judgments and audit
a sample manually to validate the judge's calibration.**

### Safety invariants as trace properties

Express each invariant as a function `(trace, params) -> bool`. Run it
over every prefix of the trace, not just the final state — a violation
that gets later "fixed" still counts. This catches transient unsafe
states (briefly double-charging then refunding) that an end-state check
would miss.

```python
def INV3_no_credit_without_debit(trace, txn_id):
    for i, msg in enumerate(trace):
        if is_credit_event(msg, txn_id):
            prefix = trace[:i]
            if not any(is_debit_confirmed(m, txn_id) for m in prefix):
                return False  # violation
    return True
```

### Scoring across arms

Each trial yields a vector:
```
(success: bool, safety_violations: int, milestones_hit: int/total,
 tokens: int, calls: int, neg_properties_hit: int)
```

Report **distributions across trials**, not single values. The summary
table should have at least mean + std (or median + IQR) over **n ≥ 20
trials per arm per task**. n=1 is fine for smoke; it cannot support a
claim of separation.

### Adversarial variants per task

For each task, build a battery of inputs that probe specific failure
surfaces:

| variant | what it probes |
|---|---|
| Boundary case (e.g., X = $10,000 exact) | Choice-point disambiguation |
| Exception trigger (insufficient funds, no availability, contradicting sources) | Exception path propagation |
| Adversarial input (e.g., total slightly over budget) | Atomicity under near-success |
| Ambiguous input (e.g., dates that span midnight) | Implicit assumption handling |

Run every arm on the full battery. The interesting finding is not the
average separation but **where each arm specifically breaks down** —
that's what diagnoses the failure mode and lets you claim MPST addresses
*which* class of problems.

### What "fair comparison" looks like

A reviewer should be able to read your metric definitions and not be able
to tell which arm you expect to win. If reading `INV2_no_unauthorized_large`
makes the reviewer think *"obviously the MPST arm wins"*, the metric is
fine — that's the whole point of MPST. If reading it makes the reviewer
think *"obviously the protocol structure is being measured directly,"*
rewrite the metric.

---

## Open issues from 2026-05-18 (to address before the n=10 / n=20 runs)

1. **Branch-asymmetric goals** — **RESOLVED 2026-05-20.** Goals now carry an
   optional `branch:` field; a branch-tagged goal is vacuously satisfied on
   trials of any other branch instead of failing for a missing anchor.
   `finance` `G1` and `G2` are tagged `branch: high`. Implemented in
   `goal_elicitor.verify_goals_against_trace` and both deterministic
   verifiers in `evaluate_run.py`. A blanket "no anchor → vacuously true"
   was rejected: it would let mandatory goals like `G6` (terminal report)
   pass when the report was never produced. Still open: report per-branch
   metrics separately in the writeup.
2. **MAF 400 errors**: the 2026-05-18 n=2 run had all 5 MAF arms fail
   with `Error code: 400 - {'error': {'code'...}` (full body truncated
   by the line-based log capture). Need to dump the full error and
   diagnose — likely an oversized prompt (role descriptions + global
   type + termination might push past a per-call limit for the
   `gpt-4o` deployment) or an MAF SDK regression. Investigate before
   the next MAF-arm run.
3. **Three-metric verifier integration** — **RESOLVED 2026-05-20.**
   `case_runner.py` now runs `evaluate_run.evaluate` automatically at the
   end of every run (strict + role-pair always; `semantic` with
   `--semantic`). Set B is emitted in `summary_eval.json` for every run;
   `evaluate_run.py` is no longer a required manual step.

---

## Pointers

- v1 design (4-scenario finance, historical): `docs/EXPERIMENT_DESIGN.md`
- Today's diary entry (full session log): `docs/DIARY.md` (2026-05-18 entry)
- The 8-arm matrix code: `experiments/baselines/`
- The harnesses: `experiments/scripts/{draft_llm_protocols,re_anchor_goals,case_runner,evaluate_run}.py`
- Memory: [[baselines-architecture]], [[llm-validator-experiment]],
  [[maf-sdk-gotchas]] in the auto-memory store
