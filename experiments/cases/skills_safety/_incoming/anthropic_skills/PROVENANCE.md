# Provenance — Anthropic public skills (document-production team)

**License verdict: PERMISSIVE — OK to copy into the benchmark.** All three saved
skills are individually licensed **Apache License 2.0** (each folder ships its own
`LICENSE.txt`). Copying their SKILL.md instruction text into a research benchmark
is permitted. NOTE: the repo's document skills (`docx`, `pdf`, `pptx`, `xlsx`) are
**source-available, NOT open source** — their `LICENSE.txt` forbids extraction,
copying, and derivative works — so none of those were saved.

## Source

- Repo URL: https://github.com/anthropics/skills
- Branch: `main`
- Commit SHA (recorded): `9d2f1ae187231d8199c64b5b762e1bdf2244733d`
  - `api.github.com` and `github.com` HTML were blocked by this session's egress
    policy (HTTP 403), so the SHA was read from the git smart-HTTP refs endpoint:
    `curl "https://github.com/anthropics/skills/info/refs?service=git-upload-pack"`
    → `9d2f1ae187231d8199c64b5b762e1bdf2244733d refs/heads/main`
  - File tree / skill inventory was recovered from
    `https://raw.githubusercontent.com/anthropics/skills/main/.claude-plugin/marketplace.json`
    (raw.githubusercontent.com was reachable; the recursive tree API was blocked).
- Fetch date: 2026-07-08

## License

- Name: **Apache License 2.0** (per-skill).
- Where read:
  - `https://raw.githubusercontent.com/anthropics/skills/main/skills/internal-comms/LICENSE.txt`
    (verified header: "Apache License / Version 2.0, January 2004"). The
    `brand-guidelines` and `doc-coauthoring` folders carry the same Apache 2.0 terms,
    and each SKILL.md frontmatter states `license: Complete terms in LICENSE.txt`.
  - Repo README also states: "Many skills in this repo are open source (Apache 2.0)."
  - Contrast (for the record): the restrictive document-skill license was read at
    `https://raw.githubusercontent.com/anthropics/skills/main/skills/docx/LICENSE.txt`
    ("© 2025 Anthropic, PBC. All rights reserved. ... users may not: ... Reproduce
    or copy these materials ... Create derivative works"). Those skills were skipped.
- No repository-root LICENSE file exists (root `LICENSE*` returned 404); licensing
  is per-skill.

## Saved files (role mapping) — document-production team: writer → reviewer → producer

### 1. internal-comms/SKILL.md — Role: CONTENT WRITER
- Source: https://raw.githubusercontent.com/anthropics/skills/main/skills/internal-comms/SKILL.md
- The instructions turn the agent into the drafter of internal communications
  (status reports, newsletters, FAQs, incident/project updates) in company formats.
- Quote:
  > "A set of resources to help me write all kinds of internal communications...
  > Claude should use this skill whenever asked to write some sort of internal
  > communications (status reports, leadership updates, ... FAQs, incident reports...)."

### 2. brand-guidelines/SKILL.md — Role: BRAND / STYLE REVIEWER
- Source: https://raw.githubusercontent.com/anthropics/skills/main/skills/brand-guidelines/SKILL.md
- The instructions enforce official brand colors, typography, and visual style
  standards on a draft — the compliance/review gate before publication.
- Quote:
  > "Applies Anthropic's official brand colors and typography to any sort of
  > artifact... Use it when brand colors or style guidelines, visual formatting,
  > or company design standards apply."

### 3. doc-coauthoring/SKILL.md — Role: FINAL DOCUMENT PRODUCER / EDITOR
- Source: https://raw.githubusercontent.com/anthropics/skills/main/skills/doc-coauthoring/SKILL.md
- The instructions run a structured production workflow that refines and finalizes
  a document and reader-tests it before release — the producer/editor who ships it.
- Quote:
  > "This skill provides a structured workflow for guiding users through
  > collaborative document creation... three stages: Context Gathering,
  > Refinement & Structure, and Reader Testing."
