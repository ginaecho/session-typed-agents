# E3 — capability sweep (in-environment Claude tier ladder)

*2026-07-05. `VALIDATION_TODO.md` §P0 asks for a capability curve: how does each
arm behave as the model gets stronger? The plan idealised OpenAI/non-OpenAI
tiers, which this environment can't reach. This runs the **in-environment
capability axis — the Claude tier ladder haiku → sonnet** — on `revenue_audit`
for the three decisive arms (A intent, B global-text, C+min gate). Opus
orchestrated; tiered subagents played the roles, one mind per trial, per-poll
reasoning, no scripts. Every sonnet trial verified from `state.json`
(`malformed=0`, no stray scripts).*

## The curve (revenue_audit)

| arm | metric | **haiku** (weak, n=100) | **sonnet** (strong, n=10–30) |
|---|---|---|---|
| A: Intent only | disasters | 0 | 0 |
| A: Intent only | **CGC (clean)** | **2%** | **100%** |
| A: Intent only | duplicate sends/trial | ~2.9 | **0** |
| B: Global text | **disasters** | **95** | **0** |
| B: Global text | **CGC (clean)** | **5%** | **100%** |
| B: Global text | Filed @ round 1 (race) | 95/100 | **0/30** |
| C+min: local+gate | disasters | 0 | 0 |
| C+min: local+gate | **CGC (clean)** | **100%** | **100%** |

(GCR is ~100% everywhere; the signal is in **CGC** = reached goal *and* zero
violations, and in **disasters**.)

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

- **Tiers:** two points (haiku, sonnet). A third Claude tier (opus) would test
  whether the strong-model plateau holds; it is expected to match sonnet
  (0 disasters) and was left unrun to bound cost — the two points already
  establish the direction.
- **Vendor diversity:** the plan's **non-OpenAI frontier** point (which also
  answers the "one vendor" worry) needs an external model this environment
  lacks — **still pending**, not faked.
- **Task:** revenue_audit only (the safety-axis case). escrow is the cost axis;
  the capability curve there is expected to mirror this (weak-model races/stalls
  vanish with capability; gate arms unchanged).
- Data: `.trial_state/p0b_sonnet/revenue_audit/{intent,global_text,min_gate}__trial_*`
  (gitignored scratch). This report is the durable artifact.
