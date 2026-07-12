# E3 — capability sweep (in-environment Claude tier ladder)

*2026-07-05. `VALIDATION_TODO.md` §P0 asks for a capability curve: how does each
arm behave as the model gets stronger? The plan idealised OpenAI/non-OpenAI
tiers, which this environment can't reach. This runs the **in-environment
capability axis — the Claude tier ladder haiku → sonnet → opus** — across
**both** cases: `revenue_audit` (safety axis, all three tiers) and
`escrow_trade` (cost axis, haiku → sonnet). Opus orchestrated; tiered subagents
played the roles, one mind per trial, per-poll reasoning, no scripts. Every
sonnet and opus trial verified from `state.json` (`malformed=0`, no stray
scripts; the opus tier and escrow sweep were added 2026-07-05, n=10/arm).*

## The curve (revenue_audit) — now three Claude tiers

| arm | metric | **haiku** (weak, n=100) | **sonnet** (mid, n=10–30) | **opus** (strong, n=10) |
|---|---|---|---|---|
| A: Intent only | disasters | 0 | 0 | **0** |
| A: Intent only | **CGC (clean)** | **2%** | **100%** | **100%** |
| A: Intent only | duplicate sends/trial | ~2.9 | 0 | **0** |
| B: Global text | **disasters** | **95** | **0** | **0** |
| B: Global text | **CGC (clean)** | **5%** | **100%** | **100%** |
| B: Global text | Filed @ round 1 (race) | 95/100 | 0/30 | **0/10** |
| C+min: local+gate | disasters | 0 | 0 | **0** |
| C+min: local+gate | **CGC (clean)** | **100%** | **100%** | **100%** |

(GCR — goal-completion rate, % of trials that reached the goal — is ~100%
everywhere; the signal is in **CGC** (critical-goal completion) = reached goal
*and* zero violations, and in **disasters**.) The opus column (n=10/arm, opus roles,
one-mind-per-trial, every trial verified from `state.json`, `malformed=0`) is
the third tier: it **confirms the strong-model plateau** — B stays at 0
disasters, A stays at 100% CGC with 0 duplicate sends, every B trial serialises
`r1 Revenue → r2 Approval → r3 Filed`. Data:
[`e3/opus_revenue.json`](e3/opus_revenue.json).

## The curve (escrow_trade) — capability mirrors revenue (NEW)

The escrow (a neutral third party that holds funds until both sides deliver) capability curve was previously "expected to mirror" revenue but
unrun. Now measured: haiku n=100 (the main ladder) vs **sonnet n=10** (A, B,
C+min, STJP; sonnet roles, verified from `state.json`, `malformed=0`).

| arm | metric | **haiku** (weak, n=100) | **sonnet** (strong, n=10) |
|---|---|---|---|
| A: Intent only | **disasters** | **26** | **0** |
| A: Intent only | **CGC (clean)** | **70%** | **100%** |
| B: Global text | **disasters** | **35** | **0** |
| B: Global text | **CGC (clean)** | **73%** | **100%** |
| C+min: local+gate | disasters | 0 | 0 |
| C+min: local+gate | **CGC (clean)** | **83%** | **100%** |
| STJP: +scheduler | disasters | 0 | 0 |
| STJP: +scheduler | **CGC (clean)** | **98%** | **100%** |
| STJP: +scheduler | calls/trial (cost) | 7.0 | **7.0** |

Same shape as revenue: the **observe arms' safety is capability-dependent**
(escrow A/B disasters 26/35 → **0** at sonnet, every trial settling only *after*
`ConfirmReceipt`), while the **gate/scheduler arms are capability-independent**
(0 disasters at both tiers) and **STJP holds its 4× cost edge** (7 calls/trial
vs 28 for the observe arms, one poll per delivered message). Data:
[`e3/sonnet_escrow.json`](e3/sonnet_escrow.json).

## Three findings

1. **The unenforced arm's *safety* is capability-dependent.** B (global text)
   goes from **95 disasters → 0** as the model strengthens. The weak model,
   polled with the whole protocol under concurrency, fires the whole pipeline
   in round 1 and files before approval; the strong model reads the same text,
   recognises the ordering constraint, and waits. (Detail in
   `P0B_MIDTIER_SONNET.md`.)

2. **The unenforced arm's *cleanliness* is capability-dependent.** Even where
   there are no disasters, quality tracks capability: A (intent only, no
   contract at all) goes from **2% → 100% CGC** — haiku emits ~2.9 duplicate
   sends per trial (S1 "waste") while sonnet emits **zero** and serialises
   perfectly. A stronger model self-organises without being told the protocol.

3. **The enforced arm is capability-*independent*.** C+min (gate) is **100% CGC,
   0 disasters at *both* tiers**, with 0 gate rejections for either model. The
   gate delivers the same guarantee regardless of how strong the agent is.

## Reconciliation — why this *supports* the thesis

As capability rises, the unenforced arms **approach** the enforced arm's quality
— the gap shrinks. Read naively that says "with a strong enough model you don't
need enforcement." The honest reading is the opposite and is the paper's point:

- **Enforcement's value is a *guarantee*, not an average.** The gate arm's
  safety is 0 disasters *by construction* — it does not depend on model
  strength, prompt luck, or scheduling. The unenforced arm's safety is a
  gamble that pays off only when the model is strong enough to reason about
  ordering under concurrency.
- **You don't get to assume the strongest model in production** (cost, latency,
  fallback, on-device), and even strong models have a failure tail. Enforcement
  makes that tail exactly 0. The weak-model column is what an unenforced
  deployment looks like on a bad day; the gate column is what it looks like
  every day.

## Honest scope / what's *not* here

- **Tiers:** now **three** Claude points (haiku, sonnet, opus) on revenue_audit —
  the strong-model plateau is measured, not assumed. Done.
- **Task:** now **both** cases — revenue_audit (safety axis, 3 tiers) *and*
  escrow_trade (cost axis, haiku→sonnet). The escrow curve mirrors revenue, as
  predicted. Done.
- **Vendor diversity:** the plan's **non-Claude frontier** point (which also
  answers the "one vendor" worry) needs an external model this environment
  lacks — **still pending**, not faked. This is the one remaining E3 gap, and it
  is an access limitation, not a design one.
- Data (gitignored scratch; the durable artifacts are the JSON below + this
  report): `.trial_state/e3_opus/revenue_audit/*` (opus tier),
  `.trial_state/e3_sonnet_escrow/escrow_trade/*` (escrow sweep),
  `.trial_state/p0b_sonnet/revenue_audit/*` (original sonnet tier).
  Durable: [`e3/opus_revenue.json`](e3/opus_revenue.json),
  [`e3/sonnet_escrow.json`](e3/sonnet_escrow.json).
