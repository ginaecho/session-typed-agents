# doc_coauthor_ship

## Menu

- [The intent](#the-intent)
- [The real skills — and the miscasting the old case made](#the-real-skills--and-the-miscasting-the-old-case-made)
- [The corrected protocol](#the-corrected-protocol)
- [A two-round walkthrough](#a-two-round-walkthrough)
- [Where the gate really lives](#where-the-gate-really-lives)
- [Why the content must flow to the DocLead](#why-the-content-must-flow-to-the-doclead)
- [Files](#files)

## The intent

Produce an internal announcement, iterate it until it reads correctly,
apply the brand styling, then ship it.

That one sentence is the whole point of this case. This is a corrected
re-implementation of an earlier case, `../doc_pipeline/`. That older case
is left untouched on disk because published results reference it — but
re-reading the three real Anthropic skill files it was built from showed
it had cast two of the three roles wrong, and left a hole in the protocol
on top of that. This document explains what was wrong and what changed.

## The real skills — and the miscasting the old case made

This case reuses three public skill files from Anthropic's
`anthropics/skills` repository (Apache-2.0 per skill; exact links, quotes,
and fetch dates are in [`SOURCES.md`](SOURCES.md)). Each file reads fine on
its own — the problem was in how the earlier `doc_pipeline` case mapped
them onto team roles.

**1. `brand-guidelines/SKILL.md` is not a reviewer.** The old case cast it
as `BrandReviewer`, gating everything on a `BrandApproved` message. But
read the file itself: its entire "Features" section is mechanical
styling, with no approve/reject language anywhere —

> "Applies Poppins font to headings (24pt and larger)"
> "Applies Lora font to body text"
> "Uses RGB color values for precise brand matching. Applied via
> python-pptx's RGBColor class."

There is nothing in this skill that judges content. It is a styling
APPLICATOR — a transform you run on a document, not a gate a document has
to clear. This case renames the role `BrandStyler` and gives it exactly
one message pair: it receives a `StyleRequest` and returns a `StyledDoc`.
It never gets to reject anything.

**2. `internal-comms/SKILL.md` is a single-pass template writer.** Its
entire "How to use this skill" section is:

> "1. Identify the communication type from the request. 2. Load the
> appropriate guideline file from the `examples/` directory ... 3. Follow
> the specific instructions in that file for formatting, tone, and content
> gathering."

That is a lookup-and-write job. There is no feedback-handling or
revision-loop step anywhere in the file. If a document-production team
needs a loop where a draft gets revised more than once, that loop has to
live somewhere else — it is not the Writer's own idea.

**3. `doc-coauthoring/SKILL.md` is the only file with real loop and gate
language.** It describes a staged workflow — "walking users through three
stages: Context Gathering, Refinement & Structure, and Reader Testing" —
and Stage 2 says plainly, "Continue iterating until user is satisfied."
Stage 3 (Reader Testing) is explicit about looping back on failure:

> "For each question, invoke a sub-agent with just the document content
> and the question ... If issues found: Report that Reader Claude
> struggled with specific issues ... Loop back to refinement for
> problematic sections."

and gives an explicit exit condition: "When Reader Claude consistently
answers questions correctly and doesn't surface new gaps or ambiguities,
the doc is ready." Of the three source files, this is the only one that
actually contains a decision to keep iterating versus stop. The real gate
belongs here — on the reader test — not on brand styling.

**4. The old protocol also had a content hole, independent of the
miscasting above.** In `doc_pipeline/protocols/DocPipeline.scr`, the
Writer's `DraftComms` went only to the `BrandReviewer`; the `DocLead`
received nothing but a `BrandApproved` token before shipping. The DocLead
shipped a document whose text it never actually saw. The no-plan (bare
arm) traces for that case showed this precisely: a DocLead stuck waiting
to ship content that had never arrived at it. This case fixes it by
routing `Draft` straight from Writer to DocLead (see goal G1 below).

## The corrected protocol

The full global protocol is in [`protocols/v1.scr`](protocols/v1.scr). In
plain language:

1. The Requester sends its brief to **both** the Writer and the DocLead at
   once (`DocRequest`) — the DocLead knows the loop is about to start
   even before a draft exists.
2. The Writer drafts the announcement and sends it straight to the
   DocLead (`Draft`) — no middle role sits between the drafted text and
   the person who owns finishing it.
3. The DocLead runs the refine/reader-test loop. Every round, the DocLead
   decides:
   - **Not ready yet**: send reader-test feedback to the Writer, the
     Requester, and the BrandStyler (so every role knows the loop is
     continuing), then wait for a revised draft from the Writer. Back to
     the top of the round.
   - **Reads correctly**: request styling from the BrandStyler, the
     Writer, and the Requester (broadcasting the decision the same way),
     then wait for the styled document back from the BrandStyler.
4. Only after the styled document comes back does the DocLead ship it to
   the Requester (`DocShipped`).

A technical note on how this draft actually validated: the starting draft
of this protocol already applied the broadcast lesson learned while
building the sibling case `../pr_review_merge/` — every branch decision
inside the loop (`ReaderTestFeedback`, `StyleRequest`) is sent to *every*
other role, not just the two roles directly exchanging content, and the
terminal `DocShipped` message sits outside the `rec` block. Applying that
lesson up front meant the real Scribble compiler accepted this protocol on
the first attempt:

```
(True, '')
```

with all four role projections (`Requester`, `Writer`, `BrandStyler`,
`DocLead`) non-empty — see the pasted validator and projection output in
the acceptance section of the authoring log kept alongside this case. That
is different from `pr_review_merge`, whose first two drafts were rejected
before broadcasting fixed them; the point still holds, it just didn't need
a second correction pass here because the earlier case's lesson was
applied before drafting rather than after.

## A two-round walkthrough

Round 1 — feedback, then a revision:

1. `Requester -> Writer, DocLead: DocRequest` — the brief goes out to both.
2. `Writer -> DocLead: Draft` — the first draft, sent straight to the
   DocLead.
3. `DocLead -> Writer, Requester, BrandStyler: ReaderTestFeedback` — the
   DocLead ran the reader test and it surfaced a real gap.
4. `Writer -> DocLead: RevisedDraft` — the Writer fixes it and sends the
   revision back.

Round 2 — reads correctly, styling, ship:

5. `DocLead -> BrandStyler, Writer, Requester: StyleRequest` — this time
   the reader test passed; the DocLead asks for the styling pass.
6. `BrandStyler -> DocLead: StyledDoc` — colors, typography, and
   formatting applied; the content itself is unchanged.
7. `DocLead -> Requester: DocShipped` — styled, reader-tested document
   goes out.

Notice the loop ran twice (step 3 forced a second round) before styling
and shipping in steps 5-7 — the multi-round property the earlier
`doc_pipeline` case never modeled at all (it had no loop, just four
messages in a straight line).

## Where the gate really lives

The old `doc_pipeline` case put its only gate on brand approval
(`BrandApproved`). Re-reading the source material shows that's backwards:
`brand-guidelines/SKILL.md` has no gate logic in it at all, while
`doc-coauthoring/SKILL.md` is built entirely around one — "Continue
iterating until user is satisfied" and "Loop back to refinement for
problematic sections" are gate language; "Applies Poppins font to
headings" is not.

In this protocol, the real gate is the DocLead's own `choice` inside
`rec REFINE`: every round, the DocLead decides whether the reader test
passed or not. The BrandStyler never gets a vote — its projection (in
`skills_revised/BrandStyler.md`) has exactly one job, receive a
`StyleRequest` and answer with a `StyledDoc`, with no branch of its own
that could reject or loop the document back. Goal G2 in
[`case.yaml`](case.yaml) anchors on `DocLead -> Writer: ReaderTestFeedback`
specifically to check that this loop — the real gate — actually ran, not
just that some approval token showed up somewhere.

## Why the content must flow to the DocLead

The old case's `DocPipeline.scr` had the Writer send `DraftComms` only to
the `BrandReviewer`; the `DocLead` received `BrandApproved` and shipped
without ever having the underlying text. That is the "ship content you
never received" failure — as concrete a hole as "merge before both
reviews land" is in `pr_review_merge`.

This protocol closes it structurally: `Draft(String) from Writer to
DocLead` is the very first content-bearing message after the two
`DocRequest` broadcasts, and every later revision (`RevisedDraft`) also
goes straight to the DocLead. Goal G1 in `case.yaml` anchors on exactly
this message and requires `len(x) > 0` in `protocols/v1.refn` — a trial
that skips this message, or sends an empty draft, fails the goal, which is
the point: a DocLead cannot legitimately ship what it was never sent.

## Files

- `case.yaml` — intent, roles, goals, terminal label, max steps
- `protocols/v1.scr` — the corrected global protocol (validated with the
  repo's real Scribble compiler)
- `protocols/v1.refn` — refinement contracts: every draft, revision, and
  styled document must be non-empty (`len(x) > 0`), and so must the
  shipped document — a positive presence check, not a keyword ban (an
  honest `DocShipped` payload has no reason to contain the literal word
  "shipped")
- `skills_original/` — the four role files as the real source material
  actually reads: `Writer.md` faithful to `internal-comms` (template
  lookup, no ordering), `BrandStyler.md` faithful to `brand-guidelines`
  (styling applicator, no approval language), `DocLead.md` faithful to
  `doc-coauthoring` (staged refine + reader-test loop), `Requester.md`
  derived
- `skills_revised/` — the same four roles with their STJP-projected local
  contracts (who they send to, who they wait for, in what order) added on
  top
- `SOURCES.md` — exact source files, deep links, license, fetch dates
