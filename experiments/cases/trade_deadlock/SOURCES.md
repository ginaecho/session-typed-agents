# Source provenance — trade_deadlock

## Menu

- [Authored case; documented lineage (not mined)](#authored-case-documented-lineage-not-mined)
- [Part 1 — Academic origin of the multiparty pattern](#part-1--academic-origin-of-the-multiparty-pattern)
- [Part 2 — The pay-vs-ship deadlock and the escrow fix as a real coordination pattern](#part-2--the-pay-vs-ship-deadlock-and-the-escrow-fix-as-a-real-coordination-pattern)
- [Part 3 — Real agent-framework instances: search results](#part-3--real-agent-framework-instances-search-results)
- [Summary for anyone auditing this case](#summary-for-anyone-auditing-this-case)

## Authored case; documented lineage (not mined)

The four files in `unchecked_skills/` (`Buyer.md`, `Seller.md`, `Escrow.md`,
`Carrier.md`) were written by this project to demonstrate a specific failure
mode: a **circular wait** (also called a deadlock — two or more parties each
waiting on a message only the other can send, so neither ever moves). They
are **not** copied, scraped, or adapted from any specific external repository,
paper, or dataset. Nobody "mined" this case from the wild. The project owner
is right, though, that the *pattern* it demonstrates — goods-for-payment
trade with a pay-vs-ship deadlock, fixed by an escrow — has real, well
documented lineage outside this project. This file records that lineage
honestly, in three parts, and is explicit about where the trail runs cold.

All URLs below were located and cross-checked with a live web search engine
in July 2026. Several publisher/university domains (ACM Digital Library,
Wikipedia, arXiv, Imperial College's `doc.ic.ac.uk`) refused direct
page fetches from this environment's network (HTTP 403), so their content
could not be quoted verbatim here; where that happened it is noted, and only
the DOI / canonical URL (confirmed to exist by the search engine returning it
from the publisher's own index) is given rather than a claim about the page's
exact wording. GitHub-hosted pages fetched cleanly and are quoted directly.

---

## Part 1 — Academic origin of the multiparty pattern

**Multiparty session types (MPST)** are a type system for checking, before
any code runs, that a group of communicating parties ("roles") — not just
two — will exchange messages in an order that can't deadlock and can't
receive a message nobody sent. This is the theory `trade_deadlock`'s
"Scribble's deadlock check" line refers to.

The foundational paper is:

- K. Honda, N. Yoshida, M. Carbone, **"Multiparty Asynchronous Session
  Types,"** *POPL 2008* (35th ACM SIGPLAN-SIGACT Symposium on Principles of
  Programming Languages). DOI: <https://doi.org/10.1145/1328438.1328472>
- Extended journal version: *Journal of the ACM* 63(1), 2016.
  DOI: <https://doi.org/10.1145/2827695>. Author-hosted PDF (Imperial
  College Mobility Reading Group publications page, found via search, not
  independently fetchable from this environment):
  `http://mrg.doc.ic.ac.uk/publications/multiparty-asynchronous-session-types-jacm/jacm.pdf`

This repository's own paper already cites this paper as `hyc08` and reuses
it for exactly the three guarantees `trade_deadlock` is built to exercise —
see `paper-writing/v9/main.tex:472` (bibliography entry) and
`paper-writing/v9/main.tex:127-129` (T1 communication safety, T2 session
fidelity, **T3 deadlock-freedom**, all cited to `hyc08`).

**The canonical teaching example.** MPST papers and tutorials standardly
introduce the theory with the **"two-buyer protocol"**: two buyers jointly
purchase a book from a seller, splitting the cost — described in tutorial
material as "the 'hello world' of multiparty session types" because it is
the simplest protocol that needs three roles (seller + two buyers) to show
why *binary* (two-party) session types aren't enough. It appears in the
Scribble project's own language guide as the `BuyGoods` protocol
(`role Buyer, role Seller` with a `choice at Seller` branch), confirmed by
fetching:
<https://github.com/scribble/scribble-language-guide/tree/master/defineprotocol>
It also recurs (as the two-buyer / recursive two-buyers example) in the
tutorial paper "A Gentle Introduction to Multiparty Asynchronous Session
Types" —
`https://mrg.cs.ox.ac.uk/publications/a-gentle-introduction-to-multiparty-asynchronous-session-types/paper.pdf`
— and in A. Scalas & N. Yoshida, **"Less Is More: Multiparty Session Types
Revisited,"** *POPL 2019*, DOI <https://doi.org/10.1145/3290343> (technical
report PDF: `https://www.doc.ic.ac.uk/research/technicalreports/2018/DTRS18-6.pdf`),
which `paper-writing/v9/main.tex` also already cites as `scalas19`.

**Honest caveat — do not overclaim this connection.** The two-buyer protocol
is *not* the same scenario as `trade_deadlock`: it has no escrow role and no
pay-before-ship / ship-before-pay circular wait built into it. What it
establishes is (a) the MPST theory and Scribble tooling lineage that this
project's deadlock checker directly descends from, and (b) that a
buyer/seller trade is the field's own standard choice of running example for
introducing multiparty protocols — which is why a trade scenario is a
natural, well-precedented vehicle for demonstrating a deadlock, even though
this specific escrow-fixed variant was authored here, not copied from the
two-buyer papers.

---

## Part 2 — The pay-vs-ship deadlock and the escrow fix as a real coordination pattern

Independent of session types, "who moves first" in a trade between parties
who don't fully trust each other is a well-studied problem outside academia,
under several names:

- **Fair exchange protocols.** N. Asokan, V. Shoup, M. Waidner's
  "Optimistic Fair Exchange of Digital Signatures" gives a provably fair
  protocol for exchanging items of value (e.g., a signed payment for a
  signed receipt) using a **trusted third party (TTP)** — an escrow, a neutral third party that holds funds until both sides deliver — that only has to
  step in if someone tries to cheat — the same "neutral intermediary breaks
  the standoff" idea `trade_deadlock`'s Escrow role embodies.
  Semantic Scholar record: <https://www.semanticscholar.org/paper/Optimistic-fair-exchange-of-digital-signatures-Asokan-Shoup/0b51b0acf1f2025fb95c65072a0905c309e02858>
- I. Ray & I. Ray, **"Fair Exchange in E-commerce,"** *ACM SIGecom
  Exchanges* 3(2), 2002 — a survey specifically framed around e-commerce
  goods-for-payment exchange and escrow/TTP designs.
  DOI: <https://doi.org/10.1145/844340.844345>; PDF:
  <https://www.sigecom.org/exchanges/volume_3/3.2-Ray.pdf>
- A.C.-C. Yao et al. (and others) studied **escrow services as trusted
  third parties** empirically in online auctions: "Hope or Hype: On the
  Viability of Escrow Services as Trusted Third Parties in Online Auction
  Environments," *Information Systems Research*, DOI:
  <https://doi.org/10.1287/isre.1040.0027>
- **Two-phase commit (2PC)**, the standard distributed-systems coordinator
  pattern, is the general shape of "hold everyone's vote/resource, then
  release together" that an escrow specializes for payments — background:
  <https://en.wikipedia.org/wiki/Two-phase_commit_protocol> (page content
  not independently fetchable from this environment; cited for the
  well-established standard description of 2PC's coordinator role).

**The real-world, non-cryptographic version of exactly this problem** is
solved every day in international trade finance by **documentary
collection** and **letters of credit**: a bank sits between an exporter
(seller) and importer (buyer) and releases the shipping documents (or
payment) only against the matching payment (or documents), so neither side
has to ship first or pay first on trust alone. This is a literal real-world
instance of `trade_deadlock`'s Escrow role. See, e.g., the trade-finance
primer at
<https://www.msbdc.org/export/ResourceCenter/banking/trade_services_primer.pdf>
and the comparison of documentary collection vs. letters of credit at
<https://www.briskpe.com/export-payment-method/> (both describe a bank
intermediary releasing goods-title documents only against payment, or vice
versa, to break the same "who goes first" standoff `trade_deadlock` encodes
as Buyer/Seller/Escrow).

---

## Part 3 — Real agent-framework instances: search results

The most valuable thing to find would be a genuine, permissively-licensed
multi-agent-framework example (CrewAI, LangGraph, AutoGen, or similar) that
implements a buyer/seller/escrow or marketplace-settlement flow — either
correctly ordered, or (even more useful) exhibiting the same deadlock this
case demonstrates. The following were found and checked; none is a match for
this case's specific shape (goods-for-payment settlement with an escrow role
that breaks a pay-vs-ship circular wait):

| Repo | URL | License | What it actually is |
|---|---|---|---|
| SafeRL-Lab/AgenticPay | <https://github.com/SafeRL-Lab/AgenticPay> | MIT (confirmed) | Real, genuine buyer-seller **negotiation** benchmark for LLM agents (e-commerce, ride-hailing, food delivery, rentals). No escrow role, no payment/shipment ordering or deadlock modeling — it stops at reaching a negotiated contract. |
| RayaneBelaid/buyer-seller-sma | <https://github.com/RayaneBelaid/buyer-seller-sma> | none declared | Real JADE (Java Agent DEvelopment Framework) buyer/seller negotiation and auction platform. No escrow, no payment-vs-shipment ordering. |
| crewAIInc/marketplace-crew-template | <https://github.com/crewAIInc/marketplace-crew-template> | none declared on the fetched page | Generic scaffold for submitting *any* crew to the CrewAI marketplace — not a trade/settlement example at all. |
| "EscrowGuard" (hackathon project, CrewAI-based) | found via web search only, no stable repo URL confirmed | UNVERIFIED | Described in search results as a compliance/anti-money-laundering tool built with CrewAI for reviewing escrow transactions — a compliance auditor, not a buyer/seller/escrow settlement protocol. Could not verify a canonical repo URL, so treat this row as unverified and do not cite it further. |
| "SwarmTrade" (agent-to-agent marketplace with escrow, negotiation, reputation) | product page only (`swarmtrade.store`), no GitHub repository located | UNVERIFIED | Appears in search-result summaries as a commerce product description, not as inspectable open-source code. No repo, no license, no way to check whether it handles pay-vs-ship ordering safely or would deadlock. Not usable as a source; flagged here only so a future search doesn't waste time re-discovering the same dead end. |

**Conclusion for Part 3: no direct real-world agent-framework example of
this exact pattern (buyer/seller/escrow avoiding a pay-vs-ship deadlock) was
found in the sources searched.** The closest genuine, licensed match
(AgenticPay) covers the negotiation half of a trade but not settlement
ordering or escrow. This is itself the honest result, not a gap in the
search — see the note in the task instructions for a possible future lead if
someone locates one.

---

## Summary for anyone auditing this case

- The **skill files are authored**, not mined — no adaptation claim is made
  or should be made about them.
- The **deadlock shape** (circular wait, each side waiting on the other) has
  solid academic lineage in multiparty session types (`hyc08`, already cited
  in this project's own papers) and the escrow fix has solid lineage in
  fair-exchange / trusted-third-party literature and in real trade-finance
  practice (documentary collection, letters of credit).
- The **two-buyer protocol** is the field's canonical multiparty teaching
  example and a buyer/seller scenario is thus an unsurprising, well
  precedented choice — but it is a different scenario, not something
  `trade_deadlock` was derived from.
- No real, licensed, open-source **agent-framework** example matching this
  exact shape was found; that absence is reported honestly rather than
  papered over.
