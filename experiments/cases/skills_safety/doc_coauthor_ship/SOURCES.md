# Source provenance — doc_coauthor_ship

The `skills_original/` files are adapted from **Anthropic's public skills
repo** (`anthropics/skills`, `main`, commit `9d2f1ae187231d8199c64b5b762e1bdf2244733d`
per `../_incoming/anthropic_skills/PROVENANCE.md`, originally fetched
2026-07-08, re-fetched and re-read 2026-07-15 for this corrected
re-implementation). The three skills used are individually licensed
**Apache License 2.0** (per-folder `LICENSE.txt`; see
`../_incoming/anthropic_skills/PROVENANCE.md` for the full license trail,
including the contrasting source-available `docx`/`pdf`/`pptx`/`xlsx`
skills that were deliberately not used).

This case corrects two misreadings and one structural hole that the
earlier `doc_pipeline` case (see `../doc_pipeline/`) had in the same three
skills:

1. `brand-guidelines/SKILL.md` contains **zero** approve/reject language.
   Its entire "Features" section is mechanical: "Applies Poppins font to
   headings (24pt and larger)", "Applies Lora font to body text", "Uses RGB
   color values for precise brand matching. Applied via python-pptx's
   RGBColor class." Casting it as `BrandReviewer` with a `BrandApproved`
   gate message invented semantics the file does not contain. It is a
   styling APPLICATOR, not a checkpoint.
2. `internal-comms/SKILL.md` is a single-pass template writer: "Identify
   the communication type ... Load the appropriate guideline file ...
   Follow the specific instructions ... for formatting, tone, and content
   gathering." It has no feedback-handling or revision-loop language of
   its own — any loop in the team has to come from elsewhere.
3. `doc-coauthoring/SKILL.md` is the only one of the three with real
   loop/gate language: a staged workflow (Context Gathering -> Refinement
   & Structure -> Reader Testing), "Continue iterating until user is
   satisfied", and an explicit reader-test loop-back: "If issues found: ...
   Loop back to refinement for problematic sections." Read against the
   other two files, the real gate belongs to this skill, on the reader
   test — not on brand styling.
4. The old `doc_pipeline` protocol also had a content hole independent of
   the miscasting above: the DocLead shipped the document having received
   only a `BrandApproved` token, never the drafted text itself
   (`DraftComms` went Writer -> BrandReviewer, never to the DocLead). The
   no-plan (bare-arm) traces for that case showed exactly this: a DocLead
   waiting to ship content it had never actually received.

| File | Source | Basis | License | Retrieved |
|---|---|---|---|---|
| Writer.md | anthropics/skills [`skills/internal-comms/SKILL.md`](https://github.com/anthropics/skills/blob/main/skills/internal-comms/SKILL.md) | single-pass template lookup by communication type ("Identify the communication type ... Load the appropriate guideline file ... Follow the specific instructions"), no feedback loop of its own | Apache-2.0 | 2026-07-15 |
| BrandStyler.md | anthropics/skills [`skills/brand-guidelines/SKILL.md`](https://github.com/anthropics/skills/blob/main/skills/brand-guidelines/SKILL.md) | mechanical styling applicator (fonts, RGB colors, formatting); no approve/reject language anywhere in the file | Apache-2.0 | 2026-07-15 |
| DocLead.md | anthropics/skills [`skills/doc-coauthoring/SKILL.md`](https://github.com/anthropics/skills/blob/main/skills/doc-coauthoring/SKILL.md) | staged workflow (Context Gathering -> Refinement & Structure -> Reader Testing) with explicit iterate-until-satisfied and reader-test loop-back language | Apache-2.0 | 2026-07-15 |
| Requester.md | (derived) | the person the `internal-comms` skill writes for, and the "reader" that `doc-coauthoring`'s Stage 3 Reader Testing calls on to answer questions | — | 2026-07-15 |

All three `anthropics/skills` links above were fetched directly (the
`github.com/.../blob/main/...` page, not just the raw mirror) and confirmed
live and on-content on 2026-07-15: each page renders the named SKILL.md
with the frontmatter `description:` quoted in the table above.

Safety review: benign document-production coordination only. No secrets, no
exfiltration, no jailbreak content.
