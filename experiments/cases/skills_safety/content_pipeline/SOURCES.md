# Source provenance — content_pipeline

The `skills_original/` files are adapted from the public, MIT-licensed CrewAI
examples' content-creation pattern (role/goal/backstory prompts for a
Researcher, Writer, and Editor collaborating on an article). The unsafety is a
property the source role prompts already have when read in isolation — none of
them encodes the Editor-approval-before-publish ordering; that is left to the
crew's process wiring.

| File | Source repo | Basis | License | Retrieved |
|---|---|---|---|---|
| Researcher.md | crewAIInc/crewAI-examples | content-creation crew, researcher role prompt | MIT | 2026-07-06 |
| Writer.md | crewAIInc/crewAI-examples | content-creation crew, writer role prompt | MIT | 2026-07-06 |
| Editor.md | crewAIInc/crewAI-examples | content-creation crew, editor role prompt | MIT | 2026-07-06 |
| Publisher.md | (derived) | the "publish the finished article" step wired after the crew | MIT | 2026-07-06 |

Safety review: benign content-creation coordination only. No secrets, no
exfiltration, no jailbreak content.

## Verified URLs and a license correction (added 2026-07-12, W20 source verification)

Repo: https://github.com/crewAIInc/crewAI-examples — confirmed live and
reachable. **The "MIT" license shown in the table above does not hold on
the live repo.** Checked directly: no `LICENSE`/`LICENSE.txt` file exists
anywhere in the tree (root `LICENSE` returns HTTP 404 at both the current
`main` branch and the specific commit `da94a91e691e1cf5b3151416bb15b5b62729bea8`
that `docs/reference/reports/seam/W17_coordination_scale_up.md` records for
this repo), no `pyproject.toml` in the repo declares a `license =` field,
and the repo's own README says only "Check individual examples for specific
licensing information" — no example actually does. This matches
`W17_coordination_scale_up.md` §2's finding exactly, which quarantines
every freshly-harvested artifact from this repo for that reason.

No single upstream file is claimed here — the table above already says
"role/goal/backstory PATTERN adapted, not a literal file copy," which is
accurate and unaffected by the license finding. What is affected is the
"License: MIT" column: until a specific, actually-licensed upstream file
is identified, this item should be described as "pattern inspired by an
unlicensed public repo," not as resting on permissively-licensed source
text. See `docs/reference/MINED_SKILLS_SOURCES.md` Part A row 2 for the
full record, including the related inconsistency in
`experiments/seam_bench/mining/ledger.py::IN_REPO_UPSTREAMS`, which still
marks this case's upstream as `spdx: "MIT"`.
