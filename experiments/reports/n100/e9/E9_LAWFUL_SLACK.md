# E9 — Lawful slack: rescued liveness at unchanged safety (Prototype 2)

*2026-07-05, branch `gc/stjp_stateful_extension`. Prototype 2 of
`docs/EXTENSIONS_PLAN`. Licensing theory: **Chen–Dezani–Scalas–Yoshida LMCS'17 /
PPDP'24** — session subtyping characterises every safe deviation from a local
type, and preciseness (soundness + completeness) makes the relation maximal:
anything inside is safe in all contexts, anything outside fails in some context.*

## What was built (all on this branch)

- **(2a) compile-time subtype checker** — `stjp_core/compiler/check_subtype.py`
  `is_subtype(T', T)`: coinductive simulation implementing **output covariance**
  (T' may select a subset of T's sends), **input contravariance** (T' must offer
  a superset of T's receives), **send-polarity** (dropping the only send fails),
  and exact-sort payloads (a provably-safe v1 lattice). Turns "the lean contract
  loses nothing" into a decidable build step (`lean ≤ projection`).
- **(2b) runtime tolerant gate** — `anticipable(efsm, state, peer, label)`: the
  one decidable, provably-safe relaxation — **independent-receive output
  anticipation**. A send is admitted early iff the only pending obligations
  before it are receives and it is enabled on *every* branch reachable by
  completing them (bounded forward search). Connected into `engine_ladder`
  behind `--tolerance=off|anticipate`; the strict gate is the default.
- **Verdict corpus — 14/14** (`experiments/tests/verdict_corpus/subtype/`):
  subset/superset selection, dropped-only-send, payload mismatch; safe /
  dependent-branch / past-a-send / strictly-enabled / two-receive / loop
  anticipation, and the key **all-branches-enable** positive. Passed before any
  benchmark. (Independently re-run 14/14 by a haiku subagent.)

## E9 part 2 — safety non-regression (MANDATORY control) — HOLDS

An illegal-send corpus — off-protocol labels at every role's initial state, and
legal labels sent to the **wrong peer** — was checked against the tolerant gate:

> **50 illegal sends tested, 0 admitted.** The anticipation fragment is provably
> inside the precise relation, so it never widens what the gate accepts beyond
> safe reorderings. Non-regression holds.

## E9 part 1 — deadlock replay (decomposition)

Replaying the **19 genuine gated-arm deadlocks** from `escrow_trade` (the
goods-for-payment case, named for its Escrow role: a neutral third party that
holds funds until both sides deliver — 17 on the C+min arm, 2 on STJP) from
the n=100 run and asking, for each rejected send, whether the tolerant gate
would have admitted it as a safe anticipation:

| | count | what the gate rejected |
|---|---|---|
| deadlocks with a **type-safe anticipable** rejected send | **16 / 19** | `Escrow!PaymentSecured`, `Seller!ShipGoods` |
| deadlocks the gate **correctly held** (not anticipable) | **3 / 19** | `Escrow!SettlementComplete`, late `Buyer!Deposit` |

**The honest reading (this is the finding, not a clean "16 rescued"):** all 16
share the same root cause — the **Buyer never sent `Deposit`** (an agent
give-up; those traces have *zero* delivered messages). The sends the gate
rejected were the *other* roles (Escrow, Seller) correctly waiting on the Buyer.
The tolerant gate *would* admit `PaymentSecured` / `ShipGoods` as type-safe
anticipations — but doing so does not fix the absent Buyer (the session still
needs `Deposit` + `ConfirmReceipt` to settle), and it would relax the
**pay-before-ship** ordering. So the type-level result and the practical one
diverge, and both are worth stating:

- **Type level:** the strict gate *is* stricter than precise subtyping requires
  — 16/19 deadlocks contain a rejected send that subtyping proves safe. That
  vindicates the LMCS'17 preciseness boundary as the right place to draw the
  line.
- **Practical level:** these particular deadlocks are **agent give-ups**, not
  gate over-strictness, so anticipation is not their fix — a more reliable Buyer
  is. And where anticipation *would* apply here, it trades a deadlock for a
  business-ordering inversion that a policy from the Critic (a checker that
  looks across several messages in the conversation at once, catching
  violations no single message reveals on its own; pay-before-ship / settle-
  after-confirm here) must still gate. The 3 the gate held (`SettlementComplete`,
  which depends on `ConfirmReceipt`) show exactly that boundary working: the
  irreversible step is **not** anticipable, so the tolerant gate never relaxes
  it.

This is a *stronger* story than a bare rescue count: **lawful slack has a
precise boundary, and STJP's safety-critical steps sit outside it.**

## E9 part 3 — live tolerant-gate rerun (haiku roles, n=15/arm)

Escrow `min_gate` driven by haiku subagents, strict gate vs tolerant gate, every
trial verified from `state.json` (`malformed=0`):

| arm | success | deadlocks | disasters | anticipations admitted |
|---|---|---|---|---|
| strict gate (`--tolerance off`) | 15/15 | 0 | **0** | — |
| tolerant gate (`--tolerance anticipate`) | 15/15 | 0 | **0** | **0** |

**The tolerant gate is transparent and safe.** With agents acting in contract
order, every send is *strictly* legal when made, so the tolerant gate never
needs to admit an anticipation — outcomes are identical to strict (15/15, 0
disasters), confirming **live safety non-regression**: turning tolerance on
costs nothing and changes nothing under normal play. The anticipation
*mechanism* is exercised where it actually applies:

- **Engine smoke test (a quick end-to-end check):** a Carrier polled ahead-of-turn *anticipates* `DeliverGoods`
  before receiving `ShipGoods`; the tolerant gate admits it (safe on all
  branches), the deferred receive is consumed when it arrives, and the session
  reaches goal with **0 disasters**.
- **Deterministic replay (part 1):** 16/19 rejected sends are anticipable, and
  the mandatory illegal-send control admits **0/50** — the fragment widens
  acceptance only to safe reorderings, never to illegal sends.

*Honest note:* an earlier tolerant run deadlocked 15/15 — but that was a **driver
bug** (the subagent misread the "Allowed action(s)" line and made every role
wait), reproducing the agent-give-up mode with **0 anticipations and 0
disasters**. It is reported here for transparency (verified from `state.json`),
not as a tolerance result; the rerun above with a corrected driver is the clean
comparison. This also empirically re-confirms the part-1 finding: tolerance does
not rescue agent-give-up deadlocks (no send is even attempted to anticipate).

Data: `experiments/reports/n100/e9/e9_live_summary.json`.

## Paper insertion

Extend §7's ladder discussion with a "lawful slack" paragraph: the subtype
checker (2a) makes lean-contract compression a checked step; the tolerant gate
(2b) admits exactly the precise relation's safe reorderings and **nothing more**
(50/50 illegal sends still rejected; `SettlementComplete` still gated). Cite
`\citep{cdsy17}` for why the boundary is exactly there. Data:
`experiments/reports/n100/e9/e9_deterministic.json`.
