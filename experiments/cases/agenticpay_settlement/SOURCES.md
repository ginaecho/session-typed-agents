# Source provenance — agenticpay_settlement

This case is the **real-repo-grounded** version of the hand-authored
`trade_deadlock` case (`experiments/cases/trade_deadlock/`). Where
`trade_deadlock`'s `unchecked_skills/` were entirely invented in-house
(see `trade_deadlock/SOURCES.md`, "Part 3" — it explicitly names
AgenticPay as a real, MIT-licensed negotiation benchmark that stops short
of settlement/escrow), this case takes AgenticPay's actual buyer and
seller agent code and adapts it, then adds the escrow/carrier settlement
layer AgenticPay does not model.

## What "adapted" vs "authored" means here

- **Buyer.md and Seller.md are ADAPTED**: their negotiation-persona text
  (confidential reservation price, "negotiate but don't go below/above your
  limit," short-message discipline, "only finalize when the price is
  reasonably balanced") is paraphrased and partly quoted directly from
  AgenticPay's real `BuyerAgent`/`SellerAgent` prompt-building code. The
  settlement rule appended to each ("don't pay until goods received" /
  "don't ship until paid") is **authored for this case** — AgenticPay's
  negotiation agents reach a price agreement and stop; they have no concept
  of who moves first afterward.
- **Escrow.md and Carrier.md are AUTHORED**: AgenticPay has no escrow role,
  no carrier/shipment role, and no settlement-ordering logic of any kind.
  These two files, and the escrow-first protocol in `protocols/v1.scr`,
  are original to this project (same authorship as `trade_deadlock`'s
  Escrow/Carrier skills, which this case's Escrow/Carrier are structurally
  modeled on).

AgenticPay benchmarks the *negotiation* half of a trade (do two LLM agents
converge on a price both can accept). This case benchmarks the *settlement*
half (once a price is agreed, does the trade actually complete without a
deadlock). The two are complementary, not competing: a full pipeline would
run AgenticPay's negotiation first, then hand its output into this case's
escrow-first settlement protocol.

## The real repository

- Repository: <https://github.com/SafeRL-Lab/AgenticPay>
- Commit cloned and read: `9740c5e3f5fd1c469a84bfc58ab1ea4d3d6a5614`
  (branch head at clone time, 2026-07-12; `git log -1` on the clone shows
  this as the "update readme" commit by Xianyang Liu)
- License: MIT. License file (verified live, fetched clean, quoted below):
  <https://github.com/SafeRL-Lab/AgenticPay/blob/9740c5e3f5fd1c469a84bfc58ab1ea4d3d6a5614/LICENSE>
  (mirror if the blob view is ever rate-limited:
  <https://raw.githubusercontent.com/SafeRL-Lab/AgenticPay/9740c5e3f5fd1c469a84bfc58ab1ea4d3d6a5614/LICENSE>)

  > MIT License
  >
  > Copyright (c) 2025 SAIL-Lab
  >
  > Permission is hereby granted, free of charge, to any person obtaining a
  > copy of this software and associated documentation files (the
  > "Software"), to deal in the Software without restriction, including
  > without limitation the rights to use, copy, modify, merge, publish,
  > distribute, sublicense, and/or sell copies of the Software...

  MIT permits exactly this use: reading, adapting, and redistributing
  modified excerpts, provided the copyright/permission notice is preserved
  somewhere in the project — recorded here for that purpose.

## The real buyer and seller agent files

- **Buyer agent**: `agenticpay/agents/buyer_agent.py` (387 lines), class
  `BuyerAgent(BaseAgent)`.
  <https://github.com/SafeRL-Lab/AgenticPay/blob/9740c5e3f5fd1c469a84bfc58ab1ea4d3d6a5614/agenticpay/agents/buyer_agent.py>
  (fetched live and confirmed to open with `"""Buyer Agent Implementation"""`
  and define `class BuyerAgent`).
  Default `role_description` (line 23): `"You are a buyer looking for a
  good deal."` Negotiation instructions actually used at runtime (the
  no-contract-schema branch, lines 276–293 of that file) include, verbatim:
  `"Your top price is ${max_price} (confidential, do not reveal)."`,
  `"NEVER reveal your maximum acceptable price to the seller."`, and the
  deal-agreement rule `"Only finalize the transaction when you believe the
  price is reasonably balanced."`

- **Seller agent**: `agenticpay/agents/seller_agent.py` (318 lines), class
  `SellerAgent(BaseAgent)`.
  <https://github.com/SafeRL-Lab/AgenticPay/blob/9740c5e3f5fd1c469a84bfc58ab1ea4d3d6a5614/agenticpay/agents/seller_agent.py>
  Default `role_description` (line 22): `"You are a seller looking to make
  a good deal."` Negotiation instructions (lines 201–212 of that file)
  include, verbatim: `"Your minimum acceptable price (confidential) is
  ${min_price}. Never reveal it."` and `"Be willing to negotiate but don't
  go below your minimum acceptable price."`

- **Shared base class**: `agenticpay/agents/base_agent.py` (144 lines),
  class `BaseAgent(ABC)` — defines the generic prompt template both
  `BuyerAgent` and `SellerAgent` extend (`_build_prompt`, `_format_context`,
  `_format_history`). Read for context; not directly quoted in the skill
  files, since it contributes no negotiation-specific language of its own.
  <https://github.com/SafeRL-Lab/AgenticPay/blob/9740c5e3f5fd1c469a84bfc58ab1ea4d3d6a5614/agenticpay/agents/base_agent.py>

Both `BuyerAgent.respond()` and `SellerAgent.respond()` require the agent's
reply to include a specific price tag every turn (`### BUYER_PRICE($X) ###`
/ `### SELLER_PRICE($X) ###`) and a `<mental_model>` block estimating the
counterparty's reservation price and strategy before replying — real,
distinctive features of AgenticPay's negotiation design, described (not
mechanically reproduced, since this case's harness uses its own
send_to/label/payload JSON output schema — see
`experiments/baselines/instructions.py::build_unchecked_skills_instructions`)
in `unchecked_skills/Buyer.md` and `unchecked_skills/Seller.md`.

## Verification method

The repository was cloned directly (`git clone --depth 1
https://github.com/SafeRL-Lab/AgenticPay`) into a scratch directory, and the
files above were read from that clone. The commit SHA above is `git log -1`
on the clone. The GitHub blob permalinks for `buyer_agent.py` and `LICENSE`
were independently re-fetched live (not just assumed from the clone) and
their content cross-checked against the local clone; both matched. Unlike
several sources cited in `trade_deadlock/SOURCES.md` (which reported
403s from ACM/Wikipedia/Imperial College domains), GitHub's own pages here
fetched cleanly.

## What is NOT claimed

- The Escrow and Carrier roles, and the entire escrow-first settlement
  protocol (`protocols/v1.scr`), are **not** from AgenticPay. They are
  authored for this case, following the same pattern as `trade_deadlock`'s
  Escrow/Carrier (see `trade_deadlock/SOURCES.md` for that pattern's own
  academic and industry lineage — multiparty session types, fair-exchange
  protocols, trade-finance documentary collection/letters of credit — which
  applies equally here and is not re-derived in this file).
- AgenticPay's actual runtime message schema (`### BUYER_PRICE($X) ###`
  tags, `<mental_model>`, `<selected_seller>`, JSON `<contract>` blocks for
  its multi-term negotiation mode) is not reproduced verbatim as the wire
  format for this case — this case's harness (`case_runner.py` /
  `instructions.py`) uses its own `{"send_to", "label", "payload",
  "rationale"}` JSON schema for every case, and the skill files describe
  AgenticPay's real instructions in prose rather than trying to run its
  literal parser.
