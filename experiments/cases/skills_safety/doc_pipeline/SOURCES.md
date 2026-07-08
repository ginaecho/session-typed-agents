# Source provenance — doc_pipeline

The `skills_original/` files are adapted from **Anthropic's public skills
repo** (`anthropics/skills`, main @ `9d2f1ae187231d8199c64b5b762e1bdf2244733d`,
fetched 2026-07-08). The three skills used are individually licensed
**Apache License 2.0** (per-folder `LICENSE.txt`). The repo's document skills
(docx/pdf/pptx/xlsx) are source-available only and were deliberately NOT used.
Full fetch notes: `../_incoming/anthropic_skills/PROVENANCE.md`.

The unsafety is a property the source skills already have when read in
isolation: each describes one specialist's job (write comms / apply brand
standards / refine-and-ship a doc); none encodes the team-level ordering
"draft → brand approval → ship". That ordering is left to whoever wires the
team together — exactly the gap STJP closes.

| File | Source | Basis | License | Retrieved |
|---|---|---|---|---|
| Writer.md | anthropics/skills `skills/internal-comms/SKILL.md` | internal comms writing workflow (3P updates, newsletters, status reports) | Apache-2.0 | 2026-07-08 |
| BrandReviewer.md | anthropics/skills `skills/brand-guidelines/SKILL.md` | official brand colors/typography compliance | Apache-2.0 | 2026-07-08 |
| DocLead.md | anthropics/skills `skills/doc-coauthoring/SKILL.md` | three-stage doc workflow, ship on completion | Apache-2.0 | 2026-07-08 |
| Requester.md | (derived) | the user request the internal-comms skill answers | — | 2026-07-08 |

Safety review: benign document-production coordination only. No secrets, no
exfiltration, no jailbreak content.
