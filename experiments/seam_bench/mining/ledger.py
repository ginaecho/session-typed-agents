"""ledger.py — provenance ledger, one record per harvested artifact.

Every artifact `harvest.py` finds gets exactly one `LedgerEntry`: source
repo, license (verbatim SPDX id + a verbatim quote from the license file —
never a guess), commit SHA, path, retrieval route. Items without a
permissive license verdict are **quarantined**: `formalize.py` refuses to
run them through the compactor and `run_mining.py` refuses to emit a
`DatasetRecord` for anything a quarantined artifact contributed to (§
"Provenance/license ledger" in the task card).

License facts below were read directly off the checked-out repos during
this task's harvest run (not guessed, not carried over unverified from an
older report):

  - `github/awesome-copilot`   MIT, root `LICENSE` ("MIT License /
    Copyright GitHub, Inc."), commit `30472ecf0f...` (HEAD at harvest time).
  - `VoltAgent/awesome-claude-code-subagents`   MIT, root `LICENSE` ("MIT
    License / Copyright (c) 2025 VoltAgent"), commit `947b44ca0c...`.
  - `anthropics/skills`   Apache-2.0 **per skill folder** (`LICENSE.txt`
    inside each `skills/<name>/`), commit `9d2f1ae187...`. Four skill
    folders (`docx`, `pdf`, `pptx`, `xlsx`) ship a **restrictive**,
    source-available `LICENSE.txt` ("users may not: ... Reproduce or copy
    these materials ... Create derivative works") — those paths are
    quarantined by prefix regardless of the repo-level Apache-2.0 default.

The in-repo `skills_safety` vendored sets are each traced to their real
upstream repo (per that case's `SOURCES.md`, already human-verified) rather
than credited to this repo — `IN_REPO_UPSTREAMS` below is a direct
transcription of those six `SOURCES.md` tables.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from harvest import Artifact

# ── known repo license facts (verified, not guessed) ─────────────────────

REPO_LICENSES: dict[str, dict[str, str]] = {
    "github/awesome-copilot": {
        "spdx": "MIT",
        "quote": "MIT License\n\nCopyright GitHub, Inc.",
        "commit_sha": "30472ecf0fe34cc561df958c08501ecc5ca80ea4",
    },
    "VoltAgent/awesome-claude-code-subagents": {
        "spdx": "MIT",
        "quote": "MIT License\n\nCopyright (c) 2025 VoltAgent",
        "commit_sha": "947b44ca0c58d606b084e9cb1a2389335b49278b",
    },
    "anthropics/skills": {
        "spdx": "Apache-2.0",
        "quote": "Apache License / Version 2.0, January 2004 "
                 "(per-skill LICENSE.txt)",
        "commit_sha": "9d2f1ae187231d8199c64b5b762e1bdf2244733d",
    },
    "crewAIInc/crewAI": {
        "spdx": "MIT",
        "quote": "MIT License\n\nCopyright (c) 2025 crewAI, Inc.",
        "commit_sha": "fb8e93be25d97776cf18368c3ac56e7ac69661b9",
    },
    "rohitg00/awesome-claude-code-toolkit": {
        "spdx": "Apache-2.0",
        "quote": "Apache License\n                           Version 2.0, January 2004",
        "commit_sha": "ebdf1d596d2cde5c5cceb32177e8d1cf4829e7d9",
    },
    # crewAIInc/crewAI-examples is DELIBERATELY absent from this table.
    # Verified 2026-07-12 (W17): no LICENSE file anywhere in the repo tree,
    # no `license =` field in any of its 20 pyproject.toml files, and the
    # README states only "Check individual examples for specific licensing
    # information" without any example actually doing so. A live WebFetch
    # of the repo's GitHub page confirmed no SPDX badge/declaration either.
    # `ledger.entry_for` therefore falls through to its `spdx is None`
    # branch for every crewAI-examples artifact: verdict "unknown",
    # quarantined, `quarantine_reason` records exactly this. The 12
    # candidate teams this repo's crews form (see W17_coordination_scale_up)
    # still go through `coordination_filter` — the license gate is a
    # DatasetRecord-emission gate (`formalize.py::team_license_ok`), not a
    # reason to skip judging whether the task needs coordination.
}

# path prefixes (relative to the repo checkout root) that carry a
# RESTRICTIVE per-folder license overriding the repo-level default above.
RESTRICTIVE_PATH_PREFIXES: dict[str, tuple[str, ...]] = {
    "anthropics/skills": ("skills/docx/", "skills/pdf/", "skills/pptx/", "skills/xlsx/"),
}

# in-repo skills_safety case -> true upstream (repo, spdx, commit_sha).
# Transcribed from each case's SOURCES.md (all human-verified prior to this
# task; see experiments/cases/skills_safety/<case>/SOURCES.md). commit_sha
# is None where the case's SOURCES.md itself recorded "not retrievable" —
# `content_pipeline`/`airline_seat`/`booking_saga`/`code_execution` are
# each adapted (paraphrased, not literal file copies) from patterns
# described in the named upstream repo, so there is no single upstream
# file/commit pair to cite beyond the repo itself.
IN_REPO_UPSTREAMS: dict[str, dict[str, Any]] = {
    "pr_merge": {
        "repo": "github/awesome-copilot", "spdx": "MIT",
        "commit_sha": "30472ecf0fe34cc561df958c08501ecc5ca80ea4",
        "quote": "MIT License\n\nCopyright GitHub, Inc.",
        "note": "literal file adaptation (near-verbatim), see SOURCES.md",
    },
    "doc_pipeline": {
        "repo": "anthropics/skills", "spdx": "Apache-2.0",
        "commit_sha": "9d2f1ae187231d8199c64b5b762e1bdf2244733d",
        "quote": "Apache License / Version 2.0, January 2004",
        "note": "literal file adaptation (near-verbatim), see SOURCES.md",
    },
    "content_pipeline": {
        # CORRECTED 2026-07-12 (W20 live-web verification): crewAIInc/crewAI-examples
        # has NO license file anywhere in the tree (root LICENSE -> HTTP 404 at
        # main and at the pinned commit; no pyproject license field). The earlier
        # "MIT" claim did not hold. This item is therefore NOT releasable as a
        # permissively-licensed test-real item; it is quarantined on the license
        # dimension, consistent with how freshly-harvested artifacts from this
        # same repo are treated. See docs/reference/MINED_SKILLS_SOURCES.md.
        "repo": "crewAIInc/crewAI-examples", "spdx": None,
        "commit_sha": None,
        "quote": "NO LICENSE found on the live repo (verified 2026-07-12); "
                 "prior MIT claim withdrawn",
        "note": "role/goal/backstory PATTERN adapted, not a literal file copy; "
                "license unverified -> not releasable",
        "quarantined": True,
    },
    "airline_seat": {
        "repo": "openai/openai-agents-python", "spdx": "MIT",
        "commit_sha": None,
        "quote": "MIT-licensed examples/customer_service/main.py (per case "
                 "SOURCES.md; repo not cloned for this task's harvest)",
        "note": "prompt PATTERN adapted, not a literal file copy",
    },
    "booking_saga": {
        "repo": "langchain-ai/langgraph", "spdx": "MIT",
        "commit_sha": None,
        "quote": "MIT-licensed LangGraph supervisor/booking examples (per "
                 "case SOURCES.md; repo not cloned for this task's harvest)",
        "note": "supervisor/worker PATTERN adapted, not a literal file copy",
    },
    "code_execution": {
        "repo": "microsoft/autogen", "spdx": "MIT",
        "commit_sha": None,
        "quote": "MIT-licensed AutoGen two-agent code pattern (per case "
                 "SOURCES.md; repo not cloned for this task's harvest)",
        "note": "AssistantAgent/CodeExecutor PATTERN adapted, not a literal "
                "file copy",
    },
}

PERMISSIVE_SPDX = {"MIT", "Apache-2.0", "BSD-3-Clause", "BSD-2-Clause",
                    "CC0-1.0", "CC-BY-4.0", "Unlicense", "ISC"}


@dataclass
class LedgerEntry:
    artifact_id: str
    source_repo: str          # true upstream repo (not the umbrella label)
    path: str
    license_spdx: Optional[str]
    license_quote: Optional[str]
    commit_sha: Optional[str]
    retrieval_route: str
    verdict: str               # "permissive" | "restrictive" | "unknown"
    quarantined: bool
    quarantine_reason: Optional[str] = None
    extra: dict[str, Any] = field(default_factory=dict)


def _license_for(source_repo: str, path: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Return (spdx, quote, commit_sha) for a (repo, path) pair, applying
    the restrictive-path-prefix override where one exists."""
    facts = REPO_LICENSES.get(source_repo)
    if facts is None:
        return None, None, None
    for prefix in RESTRICTIVE_PATH_PREFIXES.get(source_repo, ()):
        if path.startswith(prefix):
            return "LicenseRef-restrictive-source-available", (
                "per-folder LICENSE.txt: \"users may not: ... Reproduce or "
                "copy these materials ... Create derivative works\" "
                "(verified 2026-07-08 in experiments/cases/skills_safety/"
                "_incoming/anthropic_skills/PROVENANCE.md)"
            ), facts["commit_sha"]
    return facts["spdx"], facts["quote"], facts["commit_sha"]


def entry_for(artifact: Artifact) -> LedgerEntry:
    """Build the ledger entry for one artifact. `local_vendored` artifacts
    are re-attributed to their true upstream repo via `IN_REPO_UPSTREAMS`
    (keyed by the skills_safety case directory, carried in
    `artifact.frontmatter["_case"]`); every other adapter's artifacts are
    attributed to `artifact.source_repo` directly."""
    if artifact.adapter == "local_vendored":
        case_id = artifact.frontmatter.get("_case", "")
        up = IN_REPO_UPSTREAMS.get(case_id)
        if up is None:
            return LedgerEntry(
                artifact_id=artifact.artifact_id, source_repo=artifact.source_repo,
                path=artifact.path, license_spdx=None, license_quote=None,
                commit_sha=None, retrieval_route=artifact.retrieval_route,
                verdict="unknown", quarantined=True,
                quarantine_reason=f"no upstream registered for case {case_id!r}")
        verdict = "permissive" if up["spdx"] in PERMISSIVE_SPDX else "restrictive"
        return LedgerEntry(
            artifact_id=artifact.artifact_id, source_repo=up["repo"],
            path=artifact.path, license_spdx=up["spdx"], license_quote=up["quote"],
            commit_sha=up["commit_sha"], retrieval_route="local-vendored "
            "(hand-curated adaptation, see experiments/cases/skills_safety/"
            f"{case_id}/SOURCES.md)",
            verdict=verdict, quarantined=(verdict != "permissive"),
            quarantine_reason=None if verdict == "permissive" else
            f"upstream {up['repo']} license {up['spdx']!r} not on the permissive allowlist",
            extra={"case": case_id, "note": up["note"]})

    spdx, quote, sha = _license_for(artifact.source_repo, artifact.path)
    if spdx is None:
        return LedgerEntry(
            artifact_id=artifact.artifact_id, source_repo=artifact.source_repo,
            path=artifact.path, license_spdx=None, license_quote=None,
            commit_sha=None, retrieval_route=artifact.retrieval_route,
            verdict="unknown", quarantined=True,
            quarantine_reason=f"no license fact registered for repo {artifact.source_repo!r} "
                              f"in ledger.REPO_LICENSES")
    verdict = "permissive" if spdx in PERMISSIVE_SPDX else "restrictive"
    return LedgerEntry(
        artifact_id=artifact.artifact_id, source_repo=artifact.source_repo,
        path=artifact.path, license_spdx=spdx, license_quote=quote,
        commit_sha=sha, retrieval_route=artifact.retrieval_route,
        verdict=verdict, quarantined=(verdict != "permissive"),
        quarantine_reason=None if verdict == "permissive" else
        f"license {spdx!r} not on the permissive allowlist")


def build_ledger(artifacts: list[Artifact]) -> dict[str, LedgerEntry]:
    """One LedgerEntry per artifact, keyed by artifact_id."""
    return {a.artifact_id: entry_for(a) for a in artifacts}


def to_json(entry: LedgerEntry) -> dict:
    from dataclasses import asdict
    return asdict(entry)
