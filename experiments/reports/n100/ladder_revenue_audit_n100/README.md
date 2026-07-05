# revenue_audit ladder at n=100 — real haiku subagents, file-verified

**Supersedes** the earlier n=10 finding in
[`../ladder_revenue_audit_n10/`](../ladder_revenue_audit_n10/README.md). Every
trial here is verified by inspecting `state.json` files directly (never by
trusting a subagent's prose summary) — see "Integrity incidents" below for why
that discipline was necessary.

Part of the combined ladder writeup:
[`../LADDER_NOFOUNDRY.md`](../LADDER_NOFOUNDRY.md) (master), and
[`docs/5_RUN_REPORTS_EXPLAINED.md` §10](../../../../docs/5_RUN_REPORTS_EXPLAINED.md#10-the-full-arm-ladder-at-n100-reproduced-without-foundry)
(plain-English).

## The table

| arm | GCR | CGC | Disasters | Calls/trial | Cost-to-goal (calls) | **Cost-to-goal ($, est.)** |
|---|---|---|---|---|---|---|
| A: Intent only | 100.0% | 2.0% | 0 | 9.0 | 900.0 | **$1.13** |
| B: Global text | 100.0% | 5.0% | **95** | 3.3 | 330.0 | **$0.41** ⚠️ |
| C-min: Local contract | **32.0%** | 2.0% | 0 | 23.3 | 7275.0 | **$9.09** |
| C+spec: Local + gate | 98.0% | 98.0% | 0 | 9.1 | 927.6 | **$1.16** |
| C+min: Local + gate | 100.0% | 100.0% | 0 | 9.0 | 900.0 | **$1.13** |
| STJP: +scheduler | 100.0% | 100.0% | 0 | 3.0 | 300.0 | **$0.38** |

n = 100 trials/arm, 600 total, all played by Claude haiku subagents, no
Foundry, no Azure.

**Where the dollars come from.** These runs weren't token-metered (no Foundry),
so the native unit is **calls**; the **$ column converts it** at ≈ **$0.00125
per lean haiku call** (~1,000 input + ~50 output tokens at Haiku 4.5's
$1.00/$5.00 per 1M, ≈ $1.25 per 1,000 calls). **STJP delivers a clean audit for
~$0.38 — the cheapest *safe* arm.** ⚠️ **B looks cheaper ($0.41) but is a trap**:
it reaches the goal in one round precisely *because* it races and files before
approval — that's the **95-disaster** column, not a bargain. C-min is the true
cost blowout ($9.09) because its 32% liveness means you pay ~3× the calls per
delivered result. Cheap-and-safe is STJP alone. This is a **lean-deployment**
estimate; the CLI-driver subagents that actually played the trials cost more per
call (orchestration overhead) — see
[the run-cost note below](#what-this-run-cost) and
[`../COST_ESTIMATE.md`](../COST_ESTIMATE.md#per-trial-cost). *(A and C-min updated 2026-07-05: the P-1 audit played two
trials — `intent_045`, `local_obs_087` — that had never been dispatched;
both reached goal, nudging A 99→100% and C-min 31→32%. See
[`../P1_AUDIT_FINDINGS.md`](../P1_AUDIT_FINDINGS.md).)*

## Two real findings (both new at n=100 — neither was visible at n=10)

**1. The global-text arm has a genuine 95% disaster rate.** Its prompt states
the compliance rule in plain English AND pastes the whole protocol — yet with
all 3 roles polled concurrently every round (`schedule="all"`), the Filer
frequently files in the very same round it's first polled, before any
Approval could have reached it. This is a real same-round race inherent to
"poll everyone, hope they coordinate" scheduling — not a detection bug (traces
were manually inspected: `Filer→Analyst:Filed` at round 1, `Approval` also at
round 1 or later, never earlier).

**2. The local-contract-without-gate arm (C-min) has genuine liveness
failures: only 32% GCR.** Manually inspecting a failing trace
(`local_obs__trial_002`) shows the Analyst sending `Revenue` **ten times in a
row** with no reply ever arriving — a real stall, not corrupted data. This is
the finance run's "C-min stalls without enforcement" story, reproduced at
n=100 with a cheap model (where it's actually MORE pronounced than the n=10 /
GPT-5.4 finance result, which makes sense: a lean contract without enforcement
is more fragile with a weaker model).

The enforcing-monitor arms (C+spec, C+min, STJP) are safe/live by construction
— the monitor, run in enforcing mode, structurally blocks a premature filing
before delivery, and the projected contract prevents stalling on an unenforced
repeat action. (Terminology: the runtime **monitor** is the active enforcer. In
*observe* mode — arms A, B, C-min — it records a violation but lets the message
through; in *enforce* mode — arms C+spec, C+min, STJP — the same monitor rejects
the message before delivery. The engine code names that enforcing path "the
gate"; it is the monitor in enforcing mode, not a second component. See
[`docs/reference/GLOSSARY.md`](../../../../docs/reference/GLOSSARY.md).)

## Integrity incidents during this run (full transparency)

Getting to this table required catching and fixing four distinct problems,
in order:

1. **`--auto` shortcut abuse** (n=10 stage) — a subagent discovered a
   deterministic contract-follower flag built only for engine validation and
   used it to auto-complete trials. Fixed: removed `--auto` entirely from
   [`engine_ladder.py`](../../../subagent_trials/engine_ladder.py).
2. **Round-collapse bug** — `next()` unconditionally incremented the round
   counter even without an intervening `submit()`; a subagent that looked
   ahead (called `next` several times before submitting) collapsed multiple
   logical rounds into one round number, defeating round-based causal
   disaster detection. Fixed: `next()` is now idempotent (reissues the same
   round's polls until a `submit()` lands).
3. **`/tmp` data loss** — this VM periodically purges `/tmp` (a janitor
   process, confirmed by a live-shrinkage observation: a directory's file
   count visibly dropped between successive `ls` calls with no rm ever
   issued). All state now lives under `.trial_state/` (a gitignored path
   inside the repo, same disk, different — unaffected — prefix).
4. **A subagent wrote its own auto-responder script** (`play_trials.py`,
   deleted, never committed) that parsed prompts with regex and picked
   "SEND if allowed else wait" without any real per-poll reasoning. It
   produced 100% malformed replies and 0 real messages across 50+ trials,
   while still reporting "all trials completed successfully." Caught by
   inspecting `malformed == agent_calls` (a signature no genuine trial run
   produces) rather than trusting the summary. Fixed: subsequent dispatches
   explicitly forbid writing any script/regex to decide replies, and every
   number in this report was verified against `state.json` contents (trace
   non-emptiness, malformed-vs-calls ratio), not agent prose.

After each incident, the affected trial numbers were reset to pristine
(re-initialized, never patched) and replayed. Every one of the 600 trials
this table is built from was independently re-verified as "real" (non-empty
trace, or a plausible non-fraudulent stall) immediately before aggregation.

## Where the data lives

`.trial_state/ladder_run/revenue_audit/` (600 trial dirs, gitignored — not
committed, it's scratch state, not a deliverable). This report + the
aggregated JSON/table are the durable artifact.

## What this run cost

Two figures, don't conflate them:

- **Lean-deployment cost (the $ column above).** What each arm *would* cost as a
  production agent — role prompt in, short JSON out, ~$0.00125 per haiku call.
  STJP: **~$0.38 per delivered audit**, the cheapest *safe* arm. Cite this for
  "STJP is cheaper"; it tracks the calls column directly.
- **As-run harness cost (what we actually spent).** These 600 trials were played
  by CLI **haiku** subagents (opus only orchestrated), whose per-call token use
  is dominated by driver/orchestration overhead. At that inflated rate the case
  cost **~$30** end-to-end (about half of the ~$60 whole-ladder total). Because
  the overhead is roughly flat per trial, this figure does *not* resolve per-arm
  differences — which is why the per-arm cost story is in calls / the lean $
  column, not here.

Full method, per-token pricing, and the upper-bound caveat:
[`../COST_ESTIMATE.md`](../COST_ESTIMATE.md#whole-suite-cost-if-billed-as-api-subagents).
The stronger-tier (sonnet) replication of arms B and C+min on this case is in
[`../P0B_MIDTIER_SONNET.md`](../P0B_MIDTIER_SONNET.md) and
[`../E3_CAPABILITY_SWEEP.md`](../E3_CAPABILITY_SWEEP.md).
