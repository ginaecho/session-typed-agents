# Mined "real-world skills" — verified source registry

This document exists because earlier mining reports (`W8_miner.md`,
`W16_llm_read_extraction.md`, `W17_coordination_scale_up.md`) and the
per-case `SOURCES.md` files record which public repository a piece of
evidence came from, and often a commit hash, but not a clickable URL a
reader can actually open to check the claim. This registry closes that gap:
every claimed source below was checked against the live repository on
2026-07-12 (`git ls-remote`, `raw.githubusercontent.com` file fetches, and
web search where direct fetch was blocked — see "How verification was
done" below). Nothing here was guessed; anything that could not be
confirmed is labeled **UNVERIFIED** with the reason.

## Two kinds of "source" — why the distinction matters

Some entries below are **verbatim**: this project copied a file's text
directly from the upstream repository at a specific commit, and a reader
can open `github.com/<owner>/<repo>/blob/<commit>/<path>` and see the exact
words this project used.

Other entries are **adapted-from**: this project's authors read an upstream
file or a well-known code pattern (e.g. "the OpenAI Agents SDK customer
service example uses a triage agent that hands off to a seat-booking
agent") and then **hand-wrote a new file** describing that same shape, in
this project's own words. No single upstream file is a byte-for-byte match
for the adapted file. The upstream link in these rows points to the file or
example that inspired the adaptation, not to a copy's source.

This distinction matters for the paper's claim that some evidence is "real,
not paraphrased." A verbatim entry supports that claim directly — a reader
can diff the two files. An adapted-from entry supports a weaker but still
honest claim — the *coordination structure* (who talks to whom, in what
order) was read off a real upstream artifact, but the *wording* is this
project's own. The tables below mark every row one way or the other so
readers do not have to guess which claim is being made.

## How verification was done

- **Repo existence + current HEAD commit**: `git ls-remote https://github.com/<owner>/<repo> HEAD` (works in this sandbox even though `api.github.com` and the `github.com` HTML pages are blocked by the session's network policy for direct `curl`).
- **File existence at a pinned commit**: `curl https://raw.githubusercontent.com/<owner>/<repo>/<commit-sha>/<path>` — HTTP 200 confirms the exact byte content is retrievable at that commit; this is what backs every "permalink verified" row.
- **License text**: fetched the actual `LICENSE` (or per-folder `LICENSE.txt`) file at the pinned commit and read its opening lines directly, rather than trusting a badge or a README claim.
- **Where direct HTTPS fetch of a non-GitHub documentation site was blocked** (`www.anthropic.com`, `agents.md`, `model-spec.openai.com`, `modelcontextprotocol.io` all returned `403 host_not_allowed` from this session's outbound proxy — a sandbox network-policy restriction, not evidence the site doesn't exist), verification instead used (a) a live web search returning the exact page title and a consistent description from multiple independent sources, and (b) where the standard has a backing GitHub repository, a direct `git ls-remote` + `raw.githubusercontent.com` fetch of that repository, which the proxy does allow. Rows built this way are marked "verified via search + backing repo; direct fetch blocked by session network policy" rather than a plain "verified," so the difference is visible.

---

## Part A — Sources of the 5 recovered `test-real` dataset items (highest stakes)

These are the only mined items the project's `test-real` split actually
uses in the paper's evidence for "real, in-the-wild, unsafe-when-combined
skills" (`experiments/seam_bench/mining/samples/llm_read_dataset_records.jsonl`
+ `samples/w17_sample_dataset_records.jsonl`). Every one of these must be
fully traceable or explicitly flagged.

| # | `test-real` item | Case / role files | Claimed upstream | Canonical URL | License (SPDX) + license URL | Verification status | Notes |
|---|---|---|---|---|---|---|---|
| 1 | `mined:llm_read:worked_example:pr_merge` | `experiments/cases/skills_safety/pr_merge/skills_original/{Author,Merger}.md` | `github/awesome-copilot` @ `30472ecf0f...` | https://github.com/github/awesome-copilot | MIT — https://github.com/github/awesome-copilot/blob/30472ecf0fe34cc561df958c08501ecc5ca80ea4/LICENSE | **VERIFIED, adapted-from** (SOURCES.md itself says "literal file adaptation (near-verbatim)") | Author.md adapted from `agents/address-comments.agent.md` (permalink verified: https://github.com/github/awesome-copilot/blob/30472ecf0fe34cc561df958c08501ecc5ca80ea4/agents/address-comments.agent.md), Merger.md from `agents/principal-software-engineer.agent.md` (permalink verified: https://github.com/github/awesome-copilot/blob/30472ecf0fe34cc561df958c08501ecc5ca80ea4/agents/principal-software-engineer.agent.md). Pinned SHA confirmed reachable. |
| 2 | `mined:llm_read:worked_example:content_pipeline` | `experiments/cases/skills_safety/content_pipeline/skills_original/{Researcher,Writer,Editor,Publisher}.md` | `crewAIInc/crewAI-examples` (no path, no commit recorded) | https://github.com/crewAIInc/crewAI-examples | **FLAGGED — license claim does not hold on the live repo.** SOURCES.md and the ledger's `IN_REPO_UPSTREAMS` table both say "MIT" / "permissive." The live repo has **no LICENSE file** (`raw.githubusercontent.com/.../LICENSE` → HTTP 404, confirmed at both `main` HEAD and the `da94a91e69...` commit W17 records) and its own README says only "Check individual examples for specific licensing information" with no example doing so. `docs/reference/reports/seam/W17_coordination_scale_up.md` §2 already found this and quarantines *freshly harvested* artifacts from this repo — but `ledger.py::IN_REPO_UPSTREAMS["content_pipeline"]` still hardcodes `spdx: "MIT"` for this specific in-repo item, so the ledger treats the *same repo* two different ways depending on retrieval route. That is an internal inconsistency, not a resolved question. | **UNVERIFIED (license) / adapted-from (structure)** | This is the single most important finding in this registry (see "Honesty bar" note below). The coordination *pattern* (Researcher → Writer → Editor → Publisher) is a real, recognizable CrewAI example shape, and no exact file is claimed to have been copied — SOURCES.md itself says "role/goal/backstory PATTERN adapted, not a literal file copy." But the item should **not** be described as MIT-licensed or as resting on a permissively-licensed upstream text until a specific, licensed upstream file is identified. |
| 3 | `mined:llm_read:worked_example:airline_seat` | `experiments/cases/skills_safety/airline_seat/skills_original/{Triage,SeatBooking,FlightSystem}.md` | `openai/openai-agents-python`, `examples/customer_service/main.py` | https://github.com/openai/openai-agents-python | MIT — https://github.com/openai/openai-agents-python/blob/main/LICENSE | **VERIFIED, adapted-from** | Exact file confirmed live: https://github.com/openai/openai-agents-python/blob/main/examples/customer_service/main.py — contains `triage_agent`, `seat_booking_agent`, `update_seat`, `on_seat_booking_handoff`, matching every claim in `airline_seat/SOURCES.md`. No commit SHA was recorded when this was fetched (SOURCES.md says "Commit at retrieval: `main`"); branch-tip permalink given above — **path verified, pinned-SHA missing**. |
| 4 | `mined:llm_read:w17:crewai_config:...templates/crew` | (in `experiments/seam_bench/mining/samples/w17_sample_dataset_records.jsonl`) | `crewAIInc/crewAI` (the framework repo itself, **not** crewAI-examples) @ `fb8e93be25...` | https://github.com/crewAIInc/crewAI | MIT — https://github.com/crewAIInc/crewAI/blob/fb8e93be25d97776cf18368c3ac56e7ac69661b9/LICENSE | **VERIFIED** | Repo and pinned commit both confirmed reachable live. This is the framework's own repo, distinct from the unlicensed `crewAI-examples` repo — do not conflate the two when citing this item. |
| 5 | `mined:llm_read:w17:...content_crew` | (in `experiments/seam_bench/mining/samples/w17_sample_dataset_records.jsonl`) | `crewAIInc/crewAI` @ `fb8e93be25...` | https://github.com/crewAIInc/crewAI | MIT — https://github.com/crewAIInc/crewAI/blob/fb8e93be25d97776cf18368c3ac56e7ac69661b9/LICENSE | **VERIFIED** | Same repo/commit as row 4. |

**Honesty-bar summary for Part A**: 4 of the 5 `test-real` items (rows 1, 3,
4, 5) are fully traceable to a live, correctly-licensed upstream, with a
working permalink for at least one representative file. Row 2
(`content_pipeline`) is **not** fully traceable on the license dimension —
the repo it is attributed to (`crewAIInc/crewAI-examples`) has no license
on the live site, contradicting the "MIT" verdict recorded in
`ledger.py::IN_REPO_UPSTREAMS`. The coordination structure itself is a
plausible, recognizable adaptation of a real CrewAI example pattern, but
the paper should not describe this item as resting on a permissively
licensed real-world artifact without either (a) finding and citing a
specific MIT-licensed upstream file, or (b) re-labeling it as "pattern
inspired by an unlicensed public repo" rather than "real, permissively
licensed."

---

## Part B — Sources harvested-and-assessed (the 7 mining-corpus repos)

These are the repositories `run_mining.py` actually cloned and harvested
artifacts from (`W17_coordination_scale_up.md` §2, 923 artifacts total),
plus the three "adapted-from" repos named in the `skills_safety` case
`SOURCES.md` files for cases that did not make the `test-real` cut
(`booking_saga`, `code_execution`) or that make it via pattern-adaptation
rather than harvesting (`doc_pipeline`).

| Claimed source repo | Canonical URL | License (SPDX) + license URL | Verification status | Notes |
|---|---|---|---|---|
| `github/awesome-copilot` | https://github.com/github/awesome-copilot | MIT — https://github.com/github/awesome-copilot/blob/30472ecf0fe34cc561df958c08501ecc5ca80ea4/LICENSE | **VERIFIED** | Pinned commit `30472ecf0fe34cc561df958c08501ecc5ca80ea4` confirmed live (root LICENSE + 5 named agent/instruction files all HTTP 200). Also backs `pr_merge` (Part A) and the `doc_pipeline` upstream's sibling case. |
| `VoltAgent/awesome-claude-code-subagents` | https://github.com/VoltAgent/awesome-claude-code-subagents | MIT — https://github.com/VoltAgent/awesome-claude-code-subagents/blob/947b44ca0c58d606b084e9cb1a2389335b49278b/LICENSE | **VERIFIED** | Pinned commit `947b44ca0c...` confirmed live; sample file `categories/01-core-development/api-designer.md` confirmed at that commit. |
| `anthropics/skills` | https://github.com/anthropics/skills | **Split license** — Apache-2.0 per skill folder for most skills (e.g. https://github.com/anthropics/skills/blob/9d2f1ae187231d8199c64b5b762e1bdf2244733d/skills/internal-comms/LICENSE.txt); **no repo-root LICENSE** (confirmed 404 at root, matching the ledger's note that licensing is per-skill); `docx`/`pdf`/`pptx`/`xlsx` folders carry a **restrictive, source-available** `LICENSE.txt` ("users may not: ... Reproduce or copy these materials ... Create derivative works") — confirmed verbatim live at https://github.com/anthropics/skills/blob/9d2f1ae187231d8199c64b5b762e1bdf2244733d/skills/docx/LICENSE.txt. | **VERIFIED** | Pinned commit `9d2f1ae187...` confirmed live. Backs `doc_pipeline` (permalinks below) and the quarantined docx/pdf/pptx/xlsx harvest rows in Part C. |
| `crewAIInc/crewAI` (the framework repo) | https://github.com/crewAIInc/crewAI | MIT — https://github.com/crewAIInc/crewAI/blob/fb8e93be25d97776cf18368c3ac56e7ac69661b9/LICENSE | **VERIFIED** | Distinct from `crewAI-examples` below — do not conflate. Backs `test-real` rows 4-5 in Part A. |
| `crewAIInc/crewAI-examples` | https://github.com/crewAIInc/crewAI-examples | **NONE** — confirmed live: no `LICENSE`/`LICENSE.txt` file anywhere in the tree (root `LICENSE` → HTTP 404 at both `main` and the pinned `da94a91e691e1cf5b3151416bb15b5b62729bea8`), no `license =` field in any `pyproject.toml`, README states only "Check individual examples for specific licensing information" with no example doing so. | **VERIFIED — confirmed unlicensed**, matching `W17_coordination_scale_up.md`'s finding exactly | Quarantined for any freshly-harvested artifact (`ledger.py::REPO_LICENSES` deliberately omits it). See Part A row 2 for the unresolved inconsistency where the in-repo `content_pipeline` adaptation is still marked "MIT" despite this. |
| `rohitg00/awesome-claude-code-toolkit` | https://github.com/rohitg00/awesome-claude-code-toolkit | Apache-2.0 — https://github.com/rohitg00/awesome-claude-code-toolkit/blob/ebdf1d596d2cde5c5cceb32177e8d1cf4829e7d9/LICENSE | **VERIFIED** | Pinned commit `ebdf1d596d...` confirmed live. Added as W17's task-card-named fallback source; contributed 259 harvested artifacts, 0 test-real items (checked directly: no collaboration language in a representative sample — see `W17_coordination_scale_up.md` §2). |
| `openai/openai-agents-python` | https://github.com/openai/openai-agents-python | MIT — https://github.com/openai/openai-agents-python/blob/main/LICENSE | **VERIFIED** | See Part A row 3 for the exact file. |
| `langchain-ai/langgraph` | https://github.com/langchain-ai/langgraph | MIT — https://github.com/langchain-ai/langgraph/blob/main/LICENSE | **VERIFIED (repo + license only)** | `booking_saga/SOURCES.md` names this repo's "supervisor + booking/saga examples" as the adapted-from pattern but gives no single file path, so no exact-file permalink can be constructed or verified — this is a repo-level pattern attribution, not a pinned file. Marked "path not given, cannot verify a specific permalink" rather than guessing one. |
| `microsoft/autogen` | https://github.com/microsoft/autogen | **Split license — read carefully.** The repo-root `LICENSE` is **CC-BY-4.0** (Creative Commons Attribution 4.0 International — confirmed live, this covers the docs/website), while the actual code is under a separate `LICENSE-CODE` file which **is MIT** (confirmed live: https://github.com/microsoft/autogen/blob/main/LICENSE-CODE). `code_execution/SOURCES.md`'s "MIT-licensed AutoGen" claim is correct for the code, but citing only the root `LICENSE` (as a casual check would) gives the wrong SPDX id. | **VERIFIED, with a correction** | `booking_saga`'s sibling case; same caveat as `langchain-ai/langgraph` — no single file path was recorded in `code_execution/SOURCES.md` ("AssistantAgent 'write code to solve the task' role", no path), so no exact-file permalink is possible; this is a repo-level, not file-level, attribution. |

### `doc_pipeline` exact-file permalinks (adapted-from, `anthropics/skills` @ `9d2f1ae187231d8199c64b5b762e1bdf2244733d`)

| Case file | Upstream file | Permalink | Status |
|---|---|---|---|
| `Writer.md` | `skills/internal-comms/SKILL.md` | https://github.com/anthropics/skills/blob/9d2f1ae187231d8199c64b5b762e1bdf2244733d/skills/internal-comms/SKILL.md | **VERIFIED** (HTTP 200 at pinned commit) |
| `BrandReviewer.md` | `skills/brand-guidelines/SKILL.md` | https://github.com/anthropics/skills/blob/9d2f1ae187231d8199c64b5b762e1bdf2244733d/skills/brand-guidelines/SKILL.md | **VERIFIED** |
| `DocLead.md` | `skills/doc-coauthoring/SKILL.md` | https://github.com/anthropics/skills/blob/9d2f1ae187231d8199c64b5b762e1bdf2244733d/skills/doc-coauthoring/SKILL.md | **VERIFIED** |
| `Requester.md` | (derived, no upstream file — SOURCES.md itself says "—") | n/a | n/a — not a mined item, correctly recorded as locally authored |

### `pr_merge` remaining exact-file permalinks (adapted-from, `github/awesome-copilot` @ `30472ecf0fe34cc561df958c08501ecc5ca80ea4`)

| Case file | Upstream file | Permalink | Status |
|---|---|---|---|
| `CodeReviewer.md` | `instructions/code-review-generic.instructions.md` | https://github.com/github/awesome-copilot/blob/30472ecf0fe34cc561df958c08501ecc5ca80ea4/instructions/code-review-generic.instructions.md | **VERIFIED** |
| `SecurityReviewer.md` | `agents/se-security-reviewer.agent.md` | https://github.com/github/awesome-copilot/blob/30472ecf0fe34cc561df958c08501ecc5ca80ea4/agents/se-security-reviewer.agent.md | **VERIFIED** |

---

## Part C — Quarantined / unusable sources

| Source | Why quarantined | Verification status |
|---|---|---|
| `crewAIInc/crewAI-examples` (all freshly-harvested artifacts, 48 in the W17 harvest) | No license anywhere in the live repo (see Part B). `ledger.py::entry_for` correctly quarantines every artifact retrieved via `git clone` from this repo. | **VERIFIED unlicensed** — quarantine is correct for harvested artifacts. **NOT correct** for the in-repo `content_pipeline` adaptation, which the ledger still marks permissive (Part A row 2, flagged). |
| `anthropics/skills` — `docx`, `pdf`, `pptx`, `xlsx` folders | Each carries its own restrictive, source-available `LICENSE.txt` ("users may not: ... Reproduce or copy these materials ... Create derivative works"), overriding the repo's otherwise-Apache-2.0 default. | **VERIFIED restrictive** — confirmed verbatim at `skills/docx/LICENSE.txt` (quoted in Part B). Correctly quarantined by `ledger.py::RESTRICTIVE_PATH_PREFIXES`; none of these 4 folders' `SKILL.md` files are used in any `test-real` item. |

---

## Part D — Standards cited in every paper's introduction (`\citep{anthropic-skills}`)

All four papers (`paper-writing/v6` through `v9`, `main.tex` line ~44-51)
open with a sentence naming four industry conventions for steering LLM
agents with markdown/spec artifacts, currently backed by one bibliography
entry with no URL. Each was checked independently below.

| Standard | Canonical URL | Verification status | Notes |
|---|---|---|---|
| Anthropic Agent Skills open standard (`SKILL.md`) | https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills | **Verified via search + backing repo; direct fetch blocked by session network policy.** `curl` to `www.anthropic.com` returned `403 x-deny-reason: host_not_allowed` from this session's outbound proxy — a sandbox restriction, not a sign the page doesn't exist. Multiple independent search results return this exact URL and title ("Equipping agents for the real world with Agent Skills — Anthropic") describing the December 2025 open-standard release. The standard's reference implementation, `github.com/anthropics/skills`, is independently and fully verified live (Part B). | Reference implementation repo: https://github.com/anthropics/skills |
| `AGENTS.md` convention | https://agents.md/ | **Verified via search + backing repo; direct fetch of `agents.md` blocked by session network policy** (same `403 host_not_allowed`). Backing GitHub repo confirmed live and reachable via `git ls-remote`: https://github.com/agentsmd/agents.md (HEAD `d1ac7f063d20e70015ed6732664049ae4ba9d74e`), with `README.md` fetched successfully at that pinned commit. | Repo permalink: https://github.com/agentsmd/agents.md/blob/d1ac7f063d20e70015ed6732664049ae4ba9d74e/README.md |
| OpenAI Model Spec | https://model-spec.openai.com/ | **Verified via search + backing repo; direct fetch of `model-spec.openai.com` blocked by session network policy** (same `403`). Backing GitHub repo confirmed live: https://github.com/openai/model_spec (HEAD `19789a7350fda589cd74bc7491f348f68359b0ab`), with `model_spec.md` fetched successfully at that pinned commit. | Repo permalink: https://github.com/openai/model_spec/blob/19789a7350fda589cd74bc7491f348f68359b0ab/model_spec.md |
| Model Context Protocol (MCP) specification, version 2025-11-25 | https://modelcontextprotocol.io/specification/2025-11-25 | **Verified via search + backing repo; direct fetch of `modelcontextprotocol.io` blocked by session network policy** (same `403`). Multiple independent search results confirm this exact URL and the "2025-11-25" version label (a stable spec release, per the project's own blog post title "One Year of MCP: November 2025 Spec Release"). Backing GitHub repo confirmed live: https://github.com/modelcontextprotocol/modelcontextprotocol (HEAD `2807f9d6d8ae2012e09377908f47cff16a2b9489`), `README.md` fetched successfully at that pinned commit. | Repo permalink: https://github.com/modelcontextprotocol/modelcontextprotocol/blob/2807f9d6d8ae2012e09377908f47cff16a2b9489/README.md |

All four standards verified to the extent this session's network access
allows; none required inventing a URL, and none is marked UNVERIFIED —
each has at least one directly-fetched, pinned-commit confirmation via its
backing GitHub repository, even where the polished documentation site
itself could not be fetched directly in this session.

---

## Machine-readable companion

`experiments/seam_bench/mining/sources.json` carries the same facts in a
structured form (`claimed_repo`, `url`, `license_spdx`, `license_url`,
`permalinks`, `status`, `notes`) for future mining runs to consume
programmatically.
