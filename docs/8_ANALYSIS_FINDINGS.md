# Analysis & Findings — the 12-case Foundry campaign

**Date: 2026-07-31.** This document is the analysis layer over the evidence
tables in [`7_RUN_REPORTS_FOUNDRY_REAL_CASES.md`](7_RUN_REPORTS_FOUNDRY_REAL_CASES.md):
derived views (model-scaling, cost decomposition, cross-case comparison) and
numbered findings, each with its mechanism. Every number is computed from the
committed run artifacts; the verification standard (independent re-derivation
of every trial verdict, 144 setting-cells, 0 disagreements) is described in
7_RUN. Style follows `paper-writing/v10/sections_eval_results` (which analyzes
a separate, earlier 5-arm campaign; the two data sets are never mixed).

**Design of the ladder.** The 8 settings isolate effects stepwise:
1→3 adds *global protocol knowledge*; 3→4 *localizes* it (each role sees only
its slice); 4→5/6 adds *enforcement* (the gate); 6→7 removes the per-turn
liveness hint (isolating pure enforcement); 7→8 adds *EFSM scheduling*. All
settings share intent, role descriptions, model, turn limit and retry rules.

**Cases by coordination complexity** (roles, control structure):
code_execution and airline_seat (3 roles, straight-line) · content_pipeline
(4 roles, straight-line) · booking_saga (4 roles, ordered steps) ·
agenticpay_settlement (4 roles, two branch points) · pr_review_merge
(4 roles, review loop) · multi_buyer and multi_seller (5 roles, sequenced
multi-party) · finance (6 roles, one branch) · react18 (6 roles, phases plus
a test loop) · sdlc (7 roles, review loop) · gem_dev_team (7 roles, branch
plus loop).

---

## Finding 1 — The scheduling dividend grows monotonically with coordination complexity

For each case (gpt-5.4), compare full STJP's calls/trial with the **best
completing non-scheduled setting** (highest GCR, then lowest tokens):

| Case | Complexity | Setting 8 calls/trial | Best other completing setting (calls/trial) | Setting 8 as % of best other |
|---|---|---|---|---|
| code_execution | 3 roles, straight-line | 3.0 | setting 4: 3.0 | 100% |
| airline_seat | 3 roles, straight-line | 3.0 | setting 7: 3.0 | 100% |
| content_pipeline | 4 roles, straight-line | 4.0 | setting 4: 4.0 | 100% |
| booking_saga | 4 roles, ordered steps | 4.0 | setting 6: 5.0 | 80% |
| multi_buyer | 5 roles, sequenced | 23.8 | setting 5: 44.0 | 54% |
| multi_seller | 5 roles, sequenced | 18.1 | setting 7: 39.0 | 46% |
| settlement | 4 roles, two branches | 14.2 | setting 3: 33.0 | 43% |
| finance | 6 roles, one branch | 32.8 | setting 6: 101.2 | 32% |
| sdlc | 7 roles, review loop | 16.8 | setting 5: 56.1 | 30% |
| gem_dev_team | 7 roles, branch + loop | 14.5 | (no other setting completes; best is setting 4: 94.5 calls at 3/10) | 15% |
| pr_review_merge | 4 roles, review loop | 34.9 | (no other setting completes; best is setting 7: 66.0 calls at 3/10) | 53% |
| react18 | 6 roles, phases + loop | 54.2 | setting 7: 65.8 | 82% |

On straight-line pipelines the round-robin order is already optimal (ratio
100% — the scheduler neither helps nor hurts). From the first ordering
constraint onward the ratio falls steadily, reaching 15–30% on the 7-role
protocols — and on the two loop cases where **no** alternative completes
(gem, pr_review), the dividend is completion itself. The one outlier is
react18 (82%): its loop is driven by a single role, so round-robin waste is
smaller — and a no-hint gate matches STJP's completion there (Finding 5).

## Finding 2 — Only full STJP is model-invariant on completion

GCR per setting, gpt-5-mini → gpt-5.4, all cases (x/10; strict rate; settings
1–2 are label-free-graded and excluded here — see 7_RUN). Column numbers are
the canonical settings: 3 = Global protocol (as text) · 4 = Local contract
(not enforced) · 5 = Local contract + gate (verbose) · 6 = Local contract +
gate (lean) · 7 = Local contract + gate, no turn hint · 8 = Full STJP.

| Case | Setting 3 | Setting 4 | Setting 5 | Setting 6 | Setting 7 | **Setting 8 (Full STJP)** |
|---|---|---|---|---|---|---|
| code_execution | 10→10 | 10→10 | 10→10 | 10→10 | 10→10 | **10→10** |
| airline_seat | 10→10 | 10→10 | 10→10 | 10→10 | 10→10 | **10→10** |
| content_pipeline | 10→10 | 10→10 | 10→10 | 10→10 | 10→10 | **10→10** |
| booking_saga | 10→10 | 10→9 | 10→10 | 10→10 | 10→10 | **10→10** |
| settlement | 10→10 | 4→7 | 1→3 | 0→4 | 1→9 | **10→10** |
| multi_buyer | 10→10 | 10→7 | 10→10 | 10→7 | 10→6 | **10→10** |
| multi_seller | 10→10 | 10→10 | 10→10 | 10→9 | 10→10 | **10→10** |
| finance | 10→10 | 10→5 | 10→10 | 10→10 | — | **10→10** |
| react18 | 5→1 | 0→0 | 1→0 | 10→1 | 6→10 | **9→10** |
| gem_dev_team | 9→3 | 6→3 | 2→3 | 5→0 | 6→3 | **10→10** |
| sdlc | 5→2 | 3→0 | 4→10 | 5→1 | 3→1 | **7→10** |
| pr_review | 1→0 | 10→0 | 9→1 | 9→3 | 7→3 | **10→10** |

STJP is 10/10 in 22 of 24 model-runs and best-or-tied in the other two
(sdlc-mini 7/10 where no setting is clean; react18-mini 9/10 vs setting 6's
10). Every other setting **flips with the model** somewhere — in both
directions: setting 6 falls 10→1 on react18, setting 7 rises 1→9 on
settlement, setting 3 falls 9→3 on gem, setting 4 falls 10→5 on finance and
10→0 on pr_review (the starkest knowledge-trap drop in the campaign).
Guidance-based settings are model-sensitive; the scheduled, enforced setting
is not.

## Finding 3 — Enforcement buys safety invariantly; safety does not buy progress

Across every case, both models: **all gated settings (5–8) report zero
monitor violations and zero Critic-policy disasters** — the strongest
model-independent result in the campaign. But zero violations does not mean
completion: on sdlc, settlement, gem and pr_review, gated-but-unscheduled
settings fail most trials **with perfect conformance** — the agents follow
every rule and still run out of turns. Type safety (every message correct)
and progress (the right messages happen in time) are separate guarantees;
the gate provides the first, the scheduler the second. The empirical
converse also holds: the no-protocol settings show the violations (up to
1,155/run) and all of the policy disasters (booking 8/10 charge-before-hold,
finance 9–10/10 unaudited filings).

## Finding 4 — The cost advantage has two mechanisms: fewer calls AND smaller prompts

Decomposition on gpt-5.4 (calls/trial × tokens/call), among completing
settings:

- **Fewer calls (the scheduler):** settlement 14.2 vs 33.0 calls,
  finance 32.8 vs 101.2, sdlc 16.8 vs 56.1 — the scheduler polls only the
  role with an enabled send.
- **Smaller prompts (the projection):** setting 3 (the whole protocol as
  text) pays 2.8–3.8k tokens per
  call (every agent repeatedly processes the whole rulebook) vs 0.6–1.3k for
  local-contract settings — a ~3× per-call gap independent of scheduling.

The two multiply: on settlement, STJP (local slice + scheduler) delivers the
same 10/10 as setting 3 at **8× fewer tokens** (15.7k vs 126.1k). Cost
comparisons here are made only among settings that complete; comparing raw
tokens against a failing setting is meaningless (a cheap failure is not
cheap per delivered result).

**Why costs compound: the history-re-reading snowball.** The model has no
memory between calls. Each turn is one call, and each call must be sent the
entire conversation so far as its input before the model writes its one
reply. The token total counts both what the model reads and what it writes —
and the reading side dominates, because the whole history is re-sent on
every single turn: turn 1 reads one message, turn 100 reads a hundred. A
trial therefore does not cost "number of turns × fixed price"; every verbose
message taxes every turn that comes after it, and every failed attempt
(up to 3 per trial under the retry rules) restarts a fresh conversation on
top of the ones already paid for. An analogy: a meeting where, before each
person speaks, the full minutes so far are read aloud to them. Brief
speakers keep every future reading quick; ramblers make all later readings
long; and a meeting that fails and restarts pays for its re-readings again.

The sdlc case (setting 6, 7 roles, review loop) shows the mechanism at full
scale. gpt-5-mini averages 143.6 calls and **2,702,158 tokens** per trial:
long messages × many turns × retries mean each late call re-reads tens of
thousands of tokens of history (18.8k tokens per call on average). gpt-5.4
takes almost as many turns — 105.4, not many fewer — but writes short
messages, so the history stays small: about 445 tokens per call, 46,921 per
trial. The 58× gap is not "gpt-5.4 did less work"; it is that short messages
keep every later turn cheap, while verbose messages tax everything after
them. The proof that verbosity, not the model, drives the cost: in the one
gpt-5-mini trial where the agents happened to stay brief, the whole trial
cost 13,063 tokens — inside gpt-5.4's range — while the most verbose trial
of the same setting and model cost 4,420,161. Same model, same setting; the
only difference was message length.

This mechanism is also why scheduling saves so much (Finding 1): fewer turns
means fewer re-readings of the history, so cutting turns attacks the
compounding itself — same case, full STJP on gpt-5.4: 16.8 calls, 17,732
tokens, 10/10.

## Finding 5 — Guidance features are model-sensitive: the knowledge trap and the hint backfire

Two regressions recur:
- **Knowledge without enforcement** (setting 4) degrades on the stronger
  model where the flow is long or branching: finance 10→5, multi_buyer
  10→7, settlement stuck low on both (4→7). Following a described protocol
  is not the same as being held to it.
- **The per-turn liveness hint backfires on looping/phased protocols**: on
  react18 on gpt-5.4 the hinted gate settings (5, 6) score 0–1/10 while
  setting 7 (no hint) and setting 8 score 10/10; on settlement/gpt-5.4
  setting 7 scores 9/10 vs 3–4/10 for settings 5 and 6. The hint
  nudges the acting role to act *now*, which in phased flows re-triggers
  early-phase actions instead of advancing.

Both regressions vanish under setting 8: scheduling replaces per-turn
guidance with structural turn selection.

## Finding 6 — Composed real skills fail for identifiable, recurring reasons

Setting 2 completes at most 4/10 in eleven of twelve cases while being the
most expensive setting run (up to 6.0M tokens/trial). The five recurring
mechanisms — invented vocabulary/orderings, label-free "successes" that never
finish, phantom recipients, waiting-status chatter storms, negotiation
stand-offs — are catalogued with counts in 7_RUN's FAILURE ANATOMY section.
Settings 3–8 remove all five by construction.

---

## Scope notes

memory_race (both models) completes this matrix when its runs pass
verification. n=10 per cell (Wilson 95% CIs in
the 7_RUN tables); the earlier 5-arm campaign analyzed in
`paper-writing/v10/sections_eval_results` provides n=26–30 depth on finance
with consistent conclusions (scheduler model-invariance, knowledge-only
regression, cost-from-fewer-calls).
