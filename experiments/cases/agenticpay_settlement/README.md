# agenticpay_settlement

This case takes the real buyer and seller negotiation agents from
**AgenticPay** (SafeRL-Lab/AgenticPay, MIT-licensed, commit
`9740c5e3f5fd1c469a84bfc58ab1ea4d3d6a5614` — full lineage in
`SOURCES.md`) and adds the settlement/escrow layer that benchmark does not
model: once a price is agreed, who moves first — the buyer paying, or the
seller shipping? Left to each agent's own reasonable caution ("don't pay
before you have the goods" / "don't ship before you're paid"), the two
rules form a circular wait — a deadlock, meaning both agents are stuck
forever each waiting on a message only the other one can send, and neither
ever will. This case supersedes the hand-authored `trade_deadlock` case
(`experiments/cases/trade_deadlock/`) as the **real-repo-grounded**
benchmark for the same deadlock/escrow-fix pattern: `trade_deadlock`'s
Buyer/Seller skills were entirely invented in-house, while this case's
Buyer/Seller skills are adapted from AgenticPay's actual agent code (see
`SOURCES.md` for exactly which lines are quoted vs. paraphrased vs.
authored).

It is run two ways: **live**, with subagents playing each of the four
roles (Buyer, Seller, Escrow, Carrier) directly in a Claude Code session,
and later as part of the benchmark matrix on **Azure AI Foundry**, using
the same `case.yaml` / `protocols/v1.scr` / `unchecked_skills/*.md` files
this directory contains — no case-specific code is needed in either
runner; both read the same drop-in case format the harness already uses
for every other case under `experiments/cases/`.

## Where the deadlock is

The circular wait is entirely contained in the pair
`unchecked_skills/Buyer.md` and `unchecked_skills/Seller.md`:

- The Buyer's rule: wait for `DeliverGoods`, only then send `Payment`.
- The Seller's rule: wait for `Payment`, only then send `ShipGoods`.

Read alone, each rule is ordinary self-protective caution — a buyer not
wanting to pay for goods that never arrive, a seller not wanting to ship
goods that are never paid for. Read together, they are unsatisfiable: the
Buyer will not act until the Seller acts, and the Seller will not act
until the Buyer acts. `unchecked_skills/Escrow.md` and
`unchecked_skills/Carrier.md` are authored to add the missing settlement
layer, but in the unchecked run they never even get triggered — the
Buyer/Seller pair never routes anything through them, because their skills
tell them to deal with each other directly.

`protocols/v1.scr` is the fix: an escrow-first global protocol (Buyer funds
Escrow, Escrow tells Seller funds are secured, Seller ships via Carrier,
Carrier delivers to Buyer, Buyer confirms receipt to Escrow, Escrow
releases payment to Seller and signals completion to Buyer). It passes the
real Scribble deadlock-freedom checker
(`stjp_core.compiler.validator.ScribbleValidator.validate_protocol`
returns `(True, "")`). Scribble's checker would reject any protocol variant
that kept the Buyer-pays-only-after-delivery / Seller-ships-only-after-payment
cycle intact — the escrow-first ordering is not a stylistic choice, it is
what a protocol has to look like to pass the check at all.

## Expected qualitative result

- **Unchecked skills** (Buyer.md / Seller.md read in isolation, no protocol
  given): mutual `WAIT`. Neither the Buyer nor the Seller ever sends the
  message the other is waiting on. No progress toward `SettlementComplete`
  regardless of how many turns or retries are allowed.
- **STJP-validated protocol** (`protocols/v1.scr` given to the agents):
  completes. Funds move to Escrow first, which unblocks the Seller without
  the Seller ever having to trust the Buyer's word, and the trade reaches
  `SettlementComplete`.

Exact numbers (turns to completion, token cost, success rate across
trials) are not asserted here — they come from the live and Azure AI
Foundry runs, not from this authoring pass.

## Running this on Azure AI Foundry

This case is set up (author-time, no credentials required to read or
review) as an almost-ready Azure AI Foundry benchmark run, including a
sweep across a matrix of model deployments:

- `foundry_run.md` (this directory) — the exact commands, prerequisites,
  and one documented harness gap.
- `run_foundry_matrix.sh` (this directory) — a wrapper that loops the
  Foundry run once per model deployment name.
- `.claude/skills/foundry-run-agenticpay/SKILL.md` — the condensed
  copilot runbook version of the above.
- `.claude/agents/foundry-benchmark-runner.md` — a subagent that executes
  the run and assembles the model-comparison table.

## Files

- `case.yaml` — intent, roles, goals, terminal label, max steps (same
  shape as `trade_deadlock/case.yaml`, so `experiments/scripts/case_loader.py`
  reads it without modification)
- `unchecked_skills/Buyer.md`, `Seller.md` — adapted from AgenticPay's real
  `BuyerAgent`/`SellerAgent`, plus the authored settlement rule that creates
  the circular wait
- `unchecked_skills/Escrow.md`, `Carrier.md` — authored; add the settlement
  layer AgenticPay does not model
- `protocols/v1.scr` — the escrow-first Scribble global protocol (passes
  real Scribble validation)
- `protocols/v1.refn` — refinement contracts (funded amount and released
  payment must both be positive)
- `SOURCES.md` — full provenance: exact AgenticPay file paths, permalinks,
  commit SHA, license text, and what is adapted vs. authored
