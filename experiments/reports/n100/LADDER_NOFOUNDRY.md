# The finance-style arm ladder, reproduced without Foundry (cheap subagents)

**Updated 2026-07-04, n=100.** The finance run (Part 1 of
[`docs/6_RUN_REPORTS_EXPLAINED.md`](../../../docs/6_RUN_REPORTS_EXPLAINED.md#2-reading-the-results-table))
used Azure Foundry + GPT-5.4. This
reproduces the same **arm ladder** (A: Intent → STJP) with **no Foundry** and
**cheap Claude haiku subagents** answering each poll, across two complementary
use cases — one for each axis of the finance result. Both cases are now at
**n=100 per arm** (600 trials each, 1,200 total), superseding the earlier n=10
tables (kept at [`ladder_revenue_audit_n10/`](ladder_revenue_audit_n10/README.md)
and [`ladder_escrow_n10/`](ladder_escrow_n10/README.md) for history).

Engine: `experiments/subagent_trials/engine_ladder.py` (6 arms, config-driven,
reusing the STJP scheduler, runtime monitor and Critic). Every poll is a real
model decision (no auto shortcut); cost = LLM agent-calls (tokens aren't metered
without Foundry).

## The six arms — three knobs, and how to read the tables

The six arms are not six unrelated systems. They are the **same pipeline with
three independent knobs**, turned one at a time. Once you know which knob each
step turns, the tables below (and their surprises) read straightforwardly.

**Knob 1 — what contract the agent is shown.**
- *Intent* (A): the plain-English task + its role description, nothing else.
- *Global text* (B): the whole validated protocol pasted in as one text block.
- *Local contract* (C-*): each agent is shown only its **own** projected slice
  of the protocol — what it may send, what it must wait for, which values are
  legal — either as verbose markdown (*spec*) or one line per step (*min*).

**Knob 2 — the runtime monitor, and whether it enforces.**
The **monitor is the system's active enforcer.** It is a small plain-Python
program (not an AI agent) that sits beside each role and walks that role's
per-role state machine, checking every message against it. It runs in one of
two modes:
- **Observe mode** (arms A, B, C-min): the monitor still checks every message,
  but it only **records** a violation and lets the message through. This is
  where the *Disasters* column comes from on those arms.
- **Enforce mode** (arms C+spec, C+min, STJP): the **same** monitor **blocks**
  any message its state machine does not allow — the message is rejected
  *before* delivery, never reaches anyone, and the agent is asked to try again.
  (In the engine code this enforcing path is named "the gate"; it is not a
  second component — it is the monitor in enforcing mode. See
  [`docs/reference/GLOSSARY.md`](../../../docs/reference/GLOSSARY.md): "The gate
  — the monitor run in enforcing mode.")

This is the single most important fact for reading the table: **an enforcing
monitor cannot produce a disaster, by construction** — the disallowed message
never lands. That is why every enforcing arm shows **0 disasters** at any sample
size, while the observe arms show real, non-zero disaster counts once measured
at n=100.

**Knob 3 — the scheduler (who gets polled each round).**
- *Poll-all* (every arm except STJP): every round, **all** roles are polled at
  once — "everyone act, hope you coordinate." Each poll is one model call, i.e.
  one unit of cost, whether or not that role has anything legal to do yet.
- *Enabled-sender* (STJP only): before each round the scheduler consults every
  role's state machine and polls **only** the role(s) that actually have a legal
  send available right now. It never spends a call on a role whose turn it
  structurally is not.

Knob 3 is the entire cost story: STJP's **~7 calls/trial vs ~24–29** for the
others is not a smarter per-call agent — it is simply not paying for calls to
roles that cannot legally act yet.

### Reading the surprises in the tables with these three knobs

- **Why C-min shows disasters *and* 100% goal-completion at once.**
  Goal-completion (GCR) asks "did the trial reach the goal at all?"; *Disasters*
  asks "did a safety-critical violation happen on the way?" These are
  independent. C-min shows its agents their local contract but runs the monitor
  in **observe** mode, so nothing is ever blocked — duplicate and out-of-order
  messages all get delivered (and recorded as disasters), yet the run still
  stumbles to the goal. In fact C-min has the **highest** GCR precisely because
  it never blocks anything, whereas the enforcing arms occasionally stall when
  an agent keeps re-attempting a message the monitor rejects. The honest column
  that reconciles this is **CGC** (goal reached *and* zero violations), where
  C-min falls well below the enforcing arms.
- **C+min vs C+spec is task-dependent.** These two differ on **only** Knob 1's
  sub-choice: C+spec shows the verbose markdown contract, C+min the lean
  one-line-per-step form. Same monitor, same enforce mode, same poll-all
  scheduler. In `revenue_audit` the lean form is *easier* for a cheap model to
  follow (C+min 100% vs C+spec 98%) and cheaper in tokens — the minimal form
  loses nothing. In `escrow_trade` it is the **reverse**: the verbose contract
  is more robust (C+spec 97% vs C+min 83%), because under the lean contract the
  weak model failed to *open* the trade in 17 trials (the Buyer waited instead
  of sending the first `Deposit`). So "minimal recovers most of the value" holds
  for simple pipelines but not universally — verbosity buys initiation
  reliability on the harder task.
- **What STJP actually is.** STJP is **C+min plus Knob 3** — the lean local
  contract, the enforcing monitor, and *additionally* the enabled-sender
  scheduler. It is built on C+min, **not** on C+spec. Concretely: STJP = *lean
  local contract + enforcing monitor + enabled-sender scheduler*. Because the
  ladder adds one ingredient at a time, each effect reads cleanly off the table:
  the **enforcing monitor** buys the safety (disasters → 0), the **lean
  contract** trims a little cost, and the **scheduler** delivers the large
  ~3–4× cost drop.

## Use case 1 — `revenue_audit`: the SAFETY axis (n=100)

3 roles (Analyst, Auditor, Filer). Safety rule: the Auditor must **approve
before** the Filer files. An unguided agent can file prematurely — goal reached
but **unsafe** (an irreversible filing without authorization).

| arm | GCR | CGC | Disasters | Calls/trial | $/goal (est.) |
|---|---|---|---|---|---|
| A: Intent only | 100.0% | 2.0% | 0 | 9.0 | $1.12 |
| B: Global text | 100.0% | 5.0% | **95** | 3.3 | $0.41 ⚠️ |
| C-min: Local contract | **32.0%** | 2.0% | 0 | 23.3 | $9.09 |
| C+spec: Local + gate | 98.0% | 98.0% | 0 | 9.1 | $1.16 |
| C+min: Local + gate | 100.0% | 100.0% | 0 | 9.0 | $1.12 |
| STJP: +scheduler | 100.0% | 100.0% | 0 | 3.0 | **$0.38** |

`$/goal (est.)` = cost-to-goal in **calls** × ≈ **$0.00125** per lean haiku call
(~1k in + ~50 out tokens at $1/$5 per 1M). STJP is the cheapest *safe* arm at
**$0.38/audit**; B's $0.41 is a trap — it's cheap only because it races and
files before approval (that's the **95-disaster** column). See
[`COST_ESTIMATE.md`](COST_ESTIMATE.md#per-trial-cost).

**This is the finance safety collapse, and two more findings only visible at
n=100:** the global-text arm has a genuine **95% disaster rate** — all 3 roles
polled concurrently every round means the Filer often files in the very same
round it's first polled, before Approval could possibly have arrived (verified
by inspecting traces: `Filer→Analyst:Filed` at round 1, no `Approval` before
it). And the local-contract-without-gate arm has genuine **liveness failures**:
only 32% completion — a manually-inspected failing trace shows the Analyst
resending `Revenue` ten times in a row with no reply ever arriving, a real
stall, not corrupted data. The enforcing-monitor arms (C+spec, C+min, STJP)
remain safe by construction. Full detail:
[`ladder_revenue_audit_n100/README.md`](ladder_revenue_audit_n100/README.md).

## Use case 2 — `escrow_trade`: the COST axis (n=100)

4 roles (Buyer, Seller, Carrier, Escrow). At n=10 this case looked uniformly
safe; at n=100 a real safety signal on the observe arms emerges too.

| arm | GCR | CGC | Disasters | Calls/trial | $/goal (est.) |
|---|---|---|---|---|---|
| A: Intent only | 83.0% | 70.0% | 26 | 27.8 | $4.19 |
| B: Global text | 82.0% | 73.0% | 35 | 28.8 | $4.39 |
| C-min: Local contract | 100.0% | 75.0% | 49 | 27.1 | $3.38 |
| C+spec: Local + gate | 97.0% | 97.0% | 0 | 28.0 | $3.60 |
| C+min: Local + gate | 83.0% | 83.0% | 0 | 24.7 | $3.72 |
| **STJP: +scheduler** | **98.0%** | **98.0%** | **0** | **7.0** | **$0.89** |

`$/goal (est.)` = cost-to-goal in **calls** × ≈ **$0.00125** per lean haiku call.
STJP delivers a clean settlement for **$0.89** — ~4× cheaper than every other
arm ($3.38–4.39), the same edge the calls column shows, now in money. See
[`COST_ESTIMATE.md`](COST_ESTIMATE.md#per-trial-cost).

**This is the finance cost collapse, now with a safety story too.** STJP
remains **~4× cheaper** than the other arms (7.0 vs 24.7–28.8 calls/trial) —
the scheduler advantage holds at scale. The enforcing-monitor arms stay at **0
disasters** by construction; the observe arms show real disasters (26–49,
manually verified: e.g. duplicate `PaymentSecured`/`ConfirmReceipt` sends that
the cross-message Critic correctly flags) that weren't visible in the n=10 run.
On liveness, C+spec and STJP now tie (97–98% GCR); STJP's edge is purely cost,
and C+min sits lower (83%) on a real lean-contract fragility — in 17 trials the
Buyer failed to open the trade. Full detail:
[`ladder_escrow_n100/README.md`](ladder_escrow_n100/README.md).
*(escrow C+spec/C+min/STJP and revenue A/C-min were refreshed 2026-07-05 after
the P-1 audit drove 22 non-terminal trials to completion — see
[`P1_AUDIT_FINDINGS.md`](P1_AUDIT_FINDINGS.md).)*

## What the two cases show together

The finance headline was that the full STJP stack is **simultaneously the
safest and the cheapest**. At n=100, both cases now show BOTH axes:

- **Safety:** every observe arm (monitor recording only) has a real, non-zero
  disaster or failure rate once measured at scale; every enforcing-monitor arm
  has 0 disasters, by construction, in both cases.
- **Cost:** STJP is the cheapest arm in both cases (4× in escrow_trade, ~3×
  in revenue_audit), via the same mechanism — the EFSM scheduler polls only
  the one role whose turn it is.

## Honest limitations and integrity notes

- **One mind per trial.** Each trial is played by one subagent answering every
  poll from only that role's local view (the engine shows nothing else). This
  is a faithful-enough cheap approximation of independent role-agents, not a
  true multi-agent deployment.
- **Getting to n=100 required catching real integrity failures along the
  way** — logged in full in
  [`ladder_revenue_audit_n100/README.md`](ladder_revenue_audit_n100/README.md) and
  [`ladder_escrow_n100/README.md`](ladder_escrow_n100/README.md): an `--auto`
  shortcut removed from the
  engine; a round-numbering bug that could mask real disasters (fixed via
  causal, round-aware detection); a `/tmp` janitor process that silently
  deleted an entire run's progress (state moved to a durable, gitignored
  `.trial_state/` path under the repo); and — repeatedly, especially on
  `escrow_trade`'s more mechanically-repetitive arms — subagents writing their
  own auto-responder scripts instead of reasoning per poll, caught either by
  self-confession or by the `malformed == agent_calls` signature and
  discarded/replayed. A second detection bug (a strict round<round causal
  check producing false-positive disasters on the *enforcing-monitor* arms,
  where the monitor's acceptance of a send already proves causal validity) was
  found and fixed mid-analysis of the escrow_trade n=100 data.
- Every number in both n=100 tables was verified by inspecting `state.json`
  contents directly (trace non-emptiness, malformed-vs-calls ratio) — never
  by trusting an agent's own completion summary. The final audit on both
  cases found **zero** remaining fraud across all 1,200 trials.

## Reproduce

```
# per (case, arm): init N-trial dirs under a durable (non-/tmp) path,
# a subagent drives next/submit per poll, report, then aggregate:
python experiments/subagent_trials/engine_ladder.py init --case <case> --arm <arm> --trials 1 --dir D
python experiments/subagent_trials/batch_report.py --case <case> --root <root>
python experiments/subagent_trials/aggregate_ladder.py --root <root> --case <case> --out <out>
```
Data: [`ladder_revenue_audit_n100/`](ladder_revenue_audit_n100/README.md),
[`ladder_escrow_n100/`](ladder_escrow_n100/README.md) (n=100, current);
[`ladder_revenue_audit_n10/`](ladder_revenue_audit_n10/README.md),
[`ladder_escrow_n10/`](ladder_escrow_n10/README.md) (n=10, superseded, kept for
history).

See also the plain-English writeup of these tables in the main run report:
[`docs/6_RUN_REPORTS_EXPLAINED.md` §10](../../../docs/6_RUN_REPORTS_EXPLAINED.md#10-the-full-arm-ladder-at-n100-reproduced-without-foundry).

What this suite cost to run (haiku roles + opus orchestration): see
[`COST_ESTIMATE.md`](COST_ESTIMATE.md) — the whole n=100 ladder was **~$60 in
haiku tokens**, the sonnet replication ~$10, the full validated suite under $100.
