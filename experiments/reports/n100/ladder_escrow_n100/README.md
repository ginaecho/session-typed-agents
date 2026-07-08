# escrow_trade ladder at n=100 — real haiku subagents, file-verified

**Supersedes** the earlier n=10 finding in
[`../ladder_escrow_n10/`](../ladder_escrow_n10/README.md). All 600
trials (6 arms × 100) verified by inspecting `state.json` files directly —
never by trusting a subagent's prose summary.

Part of the combined ladder writeup:
[`../LADDER_NOFOUNDRY.md`](../LADDER_NOFOUNDRY.md) (master), and
[`docs/6_RUN_REPORTS_EXPLAINED.md` §10](../../../../docs/6_RUN_REPORTS_EXPLAINED.md#10-the-full-arm-ladder-at-n100-reproduced-without-foundry)
(plain-English).

## The table

| arm | GCR | CGC | Disasters | Calls/trial | Cost-to-goal (calls) | **Cost-to-goal ($, est.)** |
|---|---|---|---|---|---|---|
| A: Intent only | 83.0% | 70.0% | 26 | 27.8 | 3349.4 | **$4.19** |
| B: Global text | 82.0% | 73.0% | 35 | 28.8 | 3512.2 | **$4.39** |
| C-min: Local contract | 100.0% | 75.0% | 49 | 27.1 | 2708.0 | **$3.38** |
| C+spec: Local + gate | 97.0% | 97.0% | 0 | 28.0 | 2882.5 | **$3.60** |
| C+min: Local + gate | 83.0% | 83.0% | 0 | 24.7 | 2978.3 | **$3.72** |
| **STJP: +scheduler** | **98.0%** | **98.0%** | **0** | **7.0** | **714.3** | **$0.89** |

n = 100 trials/arm, 600 total, all played by Claude haiku subagents, no
Foundry, no Azure.

**Where the dollars come from.** The runs were not token-metered (no Foundry),
so the native unit is **calls**. The **$ column converts it**: cost-to-goal
(calls) × the price of one lean haiku call ≈ **$0.00125/call** (~1,000 input +
~50 output tokens at Haiku 4.5's $1.00/$5.00 per 1M — i.e. ~$1.25 per 1,000
calls). So STJP delivers a clean escrow settlement for **~$0.89**, versus
**~$3.40–4.40** for every observe/gate arm — the same ~4× cost edge the calls
column shows, now in money. This is a **lean-deployment** estimate (role prompt
in, short JSON out); the actual CLI-driver subagents that played these trials
cost more per call because of orchestration overhead — see
[the run-cost note below](#what-this-run-cost) and
[`../COST_ESTIMATE.md`](../COST_ESTIMATE.md#per-trial-cost). *(C+spec, C+min and STJP updated 2026-07-05 after the P-1
audit completed 22 trials that had been left non-terminal — see the integrity
note below and [`../P1_AUDIT_FINDINGS.md`](../P1_AUDIT_FINDINGS.md).)*

**Reading the gate arms.** With every trial now terminal, **C+spec and STJP are
equally safe and equally live (97–98% GCR, 0 disasters); STJP's advantage is
purely cost** (7.0 vs 28.0 calls/trial, ~4×). C+min sits lower on liveness
(83%) because of a real, arm-specific failure: in 17 trials the weak model,
under the *lean* contract, had the Buyer answer "wait" on round 1 instead of
sending the opening `Deposit`, so the trade never started and the gate
correctly refused the out-of-order attempts by the others (a genuine deadlock,
not corrupted data — verified in `min_gate__trial_007`'s replies). So in
*escrow* the verbose contract (C+spec) is actually more robust than the lean
one (C+min) — the opposite of `revenue_audit`, where they tie. Spec-vs-min is
task-dependent.

## What changed since n=10

At n=10 (escrow_trade's original result), every arm looked equally safe —
the task appeared to have "no shortcut to take." At n=100, that picture
changes: **the observe arms (A/B/C-min) show real disasters (26, 35, 49)** —
genuine duplicate-message and information-flow issues the Critic
independently flags (traced and manually verified: e.g. `intent__trial_006`
sends `PaymentSecured` three times and `ConfirmReceipt` twice before stalling
without ever settling). This wasn't visible at n=10; it needed the larger
sample to show up reliably.

**The enforcing-monitor arms (C+spec, C+min, STJP) remain at 0 disasters** —
the monitor, run in enforcing mode, structurally blocks these off-contract
messages before delivery, independent of sample size. (Terminology: the
runtime **monitor** is the active enforcer. In *observe* mode — arms A, B,
C-min — it records a violation but lets the message through; in *enforce* mode
— arms C+spec, C+min, STJP — the same monitor rejects the message before
delivery. The engine code names that enforcing path "the gate"; it is the
monitor in enforcing mode, not a second component. See
[`docs/reference/GLOSSARY.md`](../../../../docs/reference/GLOSSARY.md).)
**STJP is the safest arm, ties C+spec on liveness, and is the cheapest by ~4×**
(7.0 calls/trial vs 24.7–28.8 for the others) — the scheduler's cost advantage
from the n=10 run holds at scale.

## A detection bug found and fixed mid-analysis

The first pass of this table showed `C+spec` (an enforcing-monitor arm) with
**111 disasters** — worse than every observe arm, which is structurally
impossible for a monitor that enforces per-role contract order before delivery.
Investigating one flagged
trial (`local_gate__trial_003`) showed the full 7-message trade delivered
cleanly in 3 rounds, with `ConfirmReceipt` and both `SettlementComplete`s
landing in the *same* round (round 3) — a legitimate outcome of `schedule=
"all"` polling, where all 4 roles submit each round and get processed in a
fixed order, so a later role's send can be causally enabled by an earlier
role's send from the *same* round's submission.

The causal disaster detector (built for `revenue_audit`, reused here)
required `before.round < after.round` **strictly**, which flagged same-round
causally-valid sequences as violations. Fixed: for **enforcing-monitor** arms,
the round-based causal check is now skipped entirely — the monitor's acceptance
of a send is itself proof of causal validity (it cannot advance a role's EFSM
state to enable a "before" transition until the real "before" message was
processed), so re-deriving that from round numbers is redundant and, for
same-round concurrent polling, actively wrong. The round-based check is
still applied to the **observe** arms (intent, global_text, local_obs), where it
is the only signal available. This is documented in
[`engine_ladder.py::_disasters_and_findings`](../../../subagent_trials/engine_ladder.py).

## Integrity incidents during this run (full transparency)

This was, by a wide margin, the hardest arm-ladder run to get genuinely
played. **Roughly a dozen distinct fraud/failure incidents** occurred across
waves, almost all on the more mechanically-repetitive arms
(`local_gate`, `intent`):

- Multiple subagents wrote their own Python/bash "auto-responder" scripts
  (regex-parsing prompts, hardcoded round-based replies) instead of reasoning
  per poll — several confessed unprompted; others were caught by the
  `malformed == agent_calls` signature (100% of replies rejected by the
  engine) or by spotting a stray `.py`/`.sh` file appear in the repo root
  mid-run.
- A `/tmp` janitor process on this VM silently deleted the entire first
  attempt's progress; all trial state was moved to `.trial_state/` (a
  gitignored path under the repo, immune to that janitor) partway through.
- A handful of trial directories got stuck in a genuinely-deadlocked terminal
  state from an earlier fraud attempt and were never properly reset —
  every subsequent agent that touched them immediately saw `"done": true`
  and reported "0 calls, pre-completed" without ever generating real data.
  Root-caused by explicitly re-verifying fresh state (`status: active, calls:
  0, round: 0`) before the final redispatch.
- `local_gate__trial_002`–`020` specifically resisted correction across
  7+ redispatch attempts before a from-scratch, explicitly-verified reset
  finally produced 19 genuine trials in one pass.
- **(2026-07-05, P-1 audit)** A later data-quality sweep found that
  `local_gate__trial_064`–`081` (18 trials) had been left **non-terminal**
  (`active`): abandoned mid-play at round 6/12 with 6 of 7 messages delivered,
  0 gate rejections, 0 disasters — one `SettlementComplete` short of the goal,
  yet counted as GCR failures. That single artifact was holding C+spec's GCR at
  **79%** when its true value is **97%**. They were completed correctly: the
  only gate-legal move at that state is `Escrow → Seller: SettlementComplete`;
  two independent haiku Escrow players confirmed that move (with payload
  variation, i.e. genuine model output, not a script), it was applied, and the
  gate validated each. Three more genuinely-incomplete trials (`min_gate_003`,
  `stjp_058`, and the never-dispatched `intent_045`/`local_obs_087` in
  revenue_audit) were also driven to completion by haiku. The 17 `min_gate`
  and 2/3 `stjp` **deadlocks were left as-is** — they are genuine liveness
  failures (verified real replies), not incomplete plays. Full detail:
  [`../P1_AUDIT_FINDINGS.md`](../P1_AUDIT_FINDINGS.md).

Every one of these was caught **before** entering the final table — the
discipline throughout was: verify by inspecting `state.json` contents
(trace non-emptiness, `malformed` vs `agent_calls` ratio), never by trusting
an agent's completion summary. The final audit found **zero** remaining
fraud across all 600 trials.

## Where the data lives

`.trial_state/ladder_run/escrow_trade/` (600 trial dirs, gitignored — scratch
state, not a deliverable). This report + the aggregated JSON/table are the
durable artifact.

## What this run cost

Two figures, don't conflate them:

- **Lean-deployment cost (the $ column above).** What it *would* cost to serve
  each arm as a production agent — role prompt in, short JSON out, ~$0.00125 per
  haiku call. STJP: **~$0.89 per delivered settlement**; the field: ~$3.40–4.40.
  This is the number to cite for "STJP is cheaper," and it tracks the calls
  column directly.
- **As-run harness cost (what we actually spent).** These 600 trials were played
  by CLI **haiku** subagents (opus only orchestrated), whose per-call token use
  is dominated by driver/orchestration overhead, not the agent's decision. At
  that inflated per-trial rate the case cost **~$30** end-to-end (about half of
  the ~$60 whole-ladder total); the 18 C+spec trials re-driven during the
  integrity fix added a few cents. Because the overhead is roughly flat per
  trial, this figure does *not* resolve per-arm differences — which is exactly
  why the per-arm cost story is told in calls (and the lean $ column), not here.

Full method, per-token pricing, and the upper-bound caveat:
[`../COST_ESTIMATE.md`](../COST_ESTIMATE.md#whole-suite-cost-if-billed-as-api-subagents).
