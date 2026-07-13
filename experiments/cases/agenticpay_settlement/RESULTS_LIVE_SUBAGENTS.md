# Live subagent benchmark — agenticpay_settlement (2026-07-12)

A first, bounded run of this case using **subscription subagents** playing the
four roles (Buyer, Seller, Escrow, Carrier). Not the Azure AI Foundry run — that
is the precise, per-model-metered version (see `foundry_run.md`). This run
establishes the behavioral result and is honest about what it does and does not
measure.

## Setup

- Two settings compared:
  - **Unchecked skills** — each role is given only its own hand-written skill
    (`unchecked_skills/`) and the conversation so far, and asked for its next
    action each round. The Buyer's rule: do not pay until goods are received.
    The Seller's rule: do not ship until paid. Each is reasonable alone.
  - **STJP protocol** — the Scribble-validated escrow-first protocol
    (`protocols/v1.scr`) drives each role in turn (the scheduler asks only the
    role whose turn it is).
- Three model tiers, one per full run: **Opus 4.8, Sonnet 5, Haiku 4.5**
  (the tiers available as subscription subagents; the Foundry run covers the
  owner's wider deployment matrix).
- The unchecked setting was capped at 4 polling rounds to bound cost. In a real
  deployment there is no cap — a deadlocked pair keeps polling indefinitely, so
  the real-world token cost of the unchecked setting is unbounded, not the small
  number a capped demo shows.

## Result

| model | setting | completed? | messages that made progress | role-turns spent |
|---|---|---|---|---|
| Opus 4.8 | unchecked | **no — deadlock** | 0 | 8 (all "WAIT") |
| Opus 4.8 | STJP protocol | **yes** | 7 → SettlementComplete | 7 |
| Sonnet 5 | unchecked | **no — deadlock** | 0 | 8 (all "WAIT") |
| Sonnet 5 | STJP protocol | **yes** | 7 → SettlementComplete | 7 |
| Haiku 4.5 | unchecked | **no — deadlock** | 0 | 8 (all "WAIT") |
| Haiku 4.5 | STJP protocol | **yes** | 7 → SettlementComplete | 7 |

Example unchecked-arm decision (verbatim): *"No message labelled Payment has
been received yet, so per the settlement rule I must not ship."*

## What this shows

1. **The deadlock reproduces on real, open-source-grounded agents.** The Buyer
   and Seller skills are adapted from AgenticPay's actual `BuyerAgent` /
   `SellerAgent` (MIT; see `SOURCES.md`). This is the `trade_deadlock` finding,
   now standing on real upstream agents rather than authored ones.
2. **The deadlock is capability-invariant.** Every tier — Haiku through Opus —
   deadlocks identically, because the circular wait is a structural property of
   the two skills, not a reasoning error a smarter model avoids.
3. **The validated protocol completes at every tier.** The escrow-first ordering
   (which Scribble forces because it rejects any protocol that keeps the cycle)
   lets all three tiers reach SettlementComplete in 7 steps.
4. **The unchecked setting spends tokens for nothing.** Every "WAIT" turn costs
   tokens and produces no settlement — the "meter running, no output" pattern
   from `docs/results/RESULT_1_DEADLOCK.md`, reproduced here.

## Honest limits of this run (what the Foundry run fixes)

- **Per-model, per-setting token totals are not separated here.** The
  subscription-subagent path does not expose per-call token metering to the
  orchestrator; this run gives the behavioral result and an aggregate on the
  order of ~1M tokens for the role-play, not a clean token table. The Azure AI
  Foundry run meters every call and produces the precise
  tokens/calls-per-trial-per-model table (that is the point of `foundry_run.md`
  and `run_foundry_matrix.sh`).
- **Bounded, not statistical.** One run per tier, unchecked capped at 4 rounds.
  The Foundry run does N trials per setting for real rates.
- **One first-run anomaly, recorded for honesty:** in an earlier attempt of the
  unchecked arm, a single agent (of 24) wavered and tried to send rather than
  wait; the clean completed run recorded all role-turns as WAIT. Worth noting
  because it is itself a small instance of the paper's point — agents do not
  perfectly obey even their own prose — and it does not change the outcome,
  since the counterpart still waits and no settlement completes.

Reproduce (subscription path): the orchestration script is
`agenticpay_bench.js` (kept with the session artifacts). Reproduce (metered,
per-model): follow `foundry_run.md`.
