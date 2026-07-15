# Result 1 — Only a static checker catches a deadlock

**Measured 2026-06-17. Case: `trade_deadlock`. Model: gpt-5.4. 6 trials per setting.**

> **At a glance:** Two agents, each following a perfectly reasonable rule written by its own team, waited for each other forever — 0 of 6 trials finished, zero messages were ever sent, and every trial still burned 24,800 tokens (about 27 model calls) discovering nothing. The same task with a checker-validated protocol finished 6 of 6 trials, first try, at half the token cost. The checker found the problem **before any agent ran**, for free.

---

<!-- MENU:START (auto-generated — edit headings, then regenerate) -->
## Menu

- [1. What this result proves](#1-what-this-result-proves)
- [2. The story — why this happens in real companies](#2-the-story--why-this-happens-in-real-companies)
- [3. How the test was set up (one variable only)](#3-how-the-test-was-set-up-one-variable-only)
  - [Is it rigged? No — we also measured how often unchecked authoring goes wrong](#is-it-rigged-no--we-also-measured-how-often-unchecked-authoring-goes-wrong)
- [4. The numbers](#4-the-numbers)
- [5. What the numbers mean](#5-what-the-numbers-mean)
  - [Before the full run: a 2-agent sanity check](#before-the-full-run-a-2-agent-sanity-check)
- [6. What counts as "breaking the rules" here (the fine print)](#6-what-counts-as-breaking-the-rules-here-the-fine-print)
- [7. Honest caveats](#7-honest-caveats)
- [8. Where the raw data is](#8-where-the-raw-data-is)
<!-- MENU:END -->

## 1. What this result proves

Two claims:

1. **Rules written by a human or an AI cannot be fully trusted at the *interaction* level.** A deadlock — everyone waiting for everyone else — can hide inside a set of rules that are each individually correct. The only way to *know* a set of rules is deadlock-free is a static checker (here, Scribble) that analyzes the whole conversation mathematically and either proves it safe or points at the cycle.

2. **A deadlock is not a cheap hang — it is a meter running at full speed.** A deadlocked agent doesn't sit quietly like a blocked program. It keeps re-reading the task, re-planning, asking "any update?", and retrying — spending real money to produce nothing.

---

## 2. The story — why this happens in real companies

This is the **order-to-cash** flow that companies are automating with agents right now. Picture two agents owned by two departments:

- The **Payments agent**, configured by the finance team. Its rule: *"Never release payment until Fulfilment confirms the goods have shipped."* Prudent and correct — it stops the company paying for goods that never ship. The finance team reviewed it. It is right.
- The **Fulfilment agent**, configured by the operations team. Its rule: *"Never ship the goods until Payments confirms the customer has paid."* Also prudent and correct. Operations reviewed it. It is right.

Each rule is sensible and was signed off by the team that owns it. **Nobody owns the interaction between them.** In production, a real order arrives and each agent correctly does what its own rule says: it waits for the other. The order sits forever — no goods ship, no money moves.

Why this is worse for AI agents than for traditional software:

1. **It is invisible to normal testing.** The bug is in no single agent — every agent passes its own tests and its own review. It only appears when the agents are put together, which no single owner reviews.
2. **A stuck agent keeps spending.** Unlike a frozen program, an agent loop keeps *working* while deadlocked: rereading, replanning, polling. In our run: 24,800 tokens per trial, zero output.

The classic fix in payment systems is an **escrow** (a neutral third party that holds funds until both sides deliver) — and that is exactly the fix the checker points to.

---

## 3. How the test was set up (one variable only)

Same task description, same model, same runner, same number of trials. The **only** difference between the settings is whether a static checker validated the rules:

- **Unchecked rules** — each agent gets a plausible, human-written rule file. The Buyer's says "don't pay until the goods arrive"; the Seller's says "don't ship until paid." Read alone, each is reasonable. Together, they are a circular wait.
- **Validated (checked) protocol** — the same intent, but the Scribble checker *rejects* any protocol containing the cycle and forces the escrow-first ordering: fund escrow → funds secured → ship → deliver → confirm → release payment. The validated protocol is then split into one contract per agent — a full version (`spec`) and a compressed one-line-per-step version (`min`).

### Is it rigged? No — we also measured how often unchecked authoring goes wrong

A fair objection: "you hand-wrote rules that deadlock." So we also asked a capable model (gpt-5.4) to author the whole protocol from the task description, **10 independent times, with a normal developer prompt**, and had Scribble classify each draft:

| Outcome of 10 unchecked, AI-authored protocol drafts | Count |
|---|---|
| Safe: deadlock-free and valid | **3 / 10** |
| Outright deadlock (circular wait) | **1 / 10** |
| Some other interaction/structure error | 6 / 10 |
| **Unsafe in some way — and the checker caught it** | **7 / 10 (100% of the unsafe drafts)** |

So on a genuinely tricky task, an unchecked AI-authored protocol is safe only **30% of the time** — and the checker caught **every one** of the 7 unsafe drafts before any agent ran. Without the check, some of those would have shipped.

---

## 4. The numbers

Run directory: `experiments/cases/trade_deadlock/runs/20260617T183345-n6-dual` — 3 settings × 6 trials, gpt-5.4.

| Measure | Unchecked rules | Validated, full contract (`spec`) | Validated, lean contract (`min`) |
|---|---|---|---|
| Trades completed | **0 / 6** | **6 / 6** | **6 / 6** |
| Messages ever sent | **0** (pure deadlock — every turn was "WAIT") | 42 | 42 |
| Attempts used (out of 3 allowed) | 3.0 — all failed | 1.0 — first try | 1.0 — first try |
| Model calls per trial | 27 | 15 | 15 |
| Tokens per trial | 24,800 | 24,800 | **12,000** |
| Seconds per trial | 75 | 48 | 47 |
| **Tokens per completed trade** | **∞ (never completes)** | 24,800 | **12,000** |

("Tokens per completed trade" is the honest cost measure: total tokens divided by how many trials actually finished. An arm that never finishes has infinite cost, no matter how cheap each attempt looks.)

---

## 5. What the numbers mean

**The headline is "0 messages, ever."** The unchecked agents did not do anything *wrong* — they did *nothing*, because each was correctly waiting for the other, exactly as its own reasonable rule instructed. Note two things:

- **A runtime watcher cannot see this failure.** A monitor that judges messages has no messages to judge. A deadlock is the *absence* of action, and only a tool that analyzes the whole protocol structure *ahead of time* can detect an absence.
- **The failure is expensive.** 27 calls, 24,800 tokens, 75 seconds per trial — all pure loss, roughly 149,000 tokens across the 6 trials just to "discover" empirically, six times over, what the checker proves in one pass at zero runtime cost.

Also worth noting: the **lean** contract completed everything at **half the tokens** of the full contract (12,000 vs 24,800) — a preview of the efficiency result in [`RESULT_2_TOKEN_EFFICIENCY.md`](RESULT_2_TOKEN_EFFICIENCY.md).

### Before the full run: a 2-agent sanity check

A small probe (`experiments/scripts/deadlock_probe.py`) first confirmed real agents genuinely deadlock on the unchecked rules:

```
UNCHECKED:  Buyer WAITs -> Seller WAITs -> Buyer WAITs -> Seller WAITs
            --> DEADLOCK: no progress, never completes
ESCROW   :  FundEscrow -> FundsSecured -> GoodsDelivered -> ConfirmReceipt
            -> ReleasePayment -> SettlementComplete   (COMPLETED, 8 steps)
```

Even a *strong* model deadlocks — each agent faithfully follows its reasonable rule, and the pair is stuck.

---

## 6. What counts as "breaking the rules" here (the fine print)

When we say the runtime monitor flags a message as forbidden, we mean one of:

- **Wrong message at this moment** (`off_protocol`) — the agent's contract does not allow this message at its current step.
- **Right message, wrong partner** (`unexpected_peer`).
- **Right message, bad value** (`refinement_failed`) — e.g., a payment amount of zero.
- **Wrong branch for the data** (`choice_guard_violation`) — e.g., a high-value order routed down the no-review path.

What is **not** a violation: two unrelated messages between *different* pairs of agents arriving in either order. The theory (multiparty session types) says independent actions may interleave freely, and the monitor respects that — an earlier, over-strict version flagged these falsely and was fixed on 2026-06-17 (analysis preserved in `../archive/WHY_B_MATCHES_C_ANALYSIS.md`).

And a **deadlock is a different kind of failure from all of the above**: not a forbidden message but the absence of any message. That is precisely why only the static checker catches it.

---

## 7. Honest caveats

- The earlier versions of this comparison were muddy: goals were scored by magic words (an agent that wrote "goods prepared for delivery" instead of "pass" scored as failed), and too many variables changed at once. This clean version changes **one variable** (checked vs unchecked), uses structural goals, and holds everything else constant.
- The hardened STJP authoring prompt raises the AI's first-draft success rate above 30% — but the load-bearing claim is that the checker catches whatever slips through, at any prompt quality.

## 8. Where the raw data is

- Run directory: `experiments/cases/trade_deadlock/runs/20260617T183345-n6-dual/` (per-message logs in `events_<setting>.jsonl`, metrics in `summary.json`)
- Unchecked rule files: `experiments/cases/trade_deadlock/unchecked_skills/<role>.md`
- Authoring-risk script: `experiments/scripts/authoring_risk.py`; probe: `experiments/scripts/deadlock_probe.py`
