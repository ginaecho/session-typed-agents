"""coordination_filter.py — the missing pipeline stage: does the TASK need
more than one interacting party?

W8 (`docs/reference/reports/seam/W8_miner.md`) built 13 candidate "teams" by
grouping harvested files (directory boundary, a handoff-verb regex, a
hand-curated worked example). W16 (`W16_llm_read_extraction.md`) then read
those 13 teams carefully and recovered real protocol structure from 4 of
them. Neither step ever asked the prior question: does the underlying TASK
(not the file layout) actually require two or more parties to interact at
all? The project owner's review (`docs/8_INTENT_TO_PROTOCOL_TRAINING.md`,
2026-07-11 update) found the answer by hand for W16's 13 teams: 6 of 13 did
not need coordination (4 single-agent tool documents grouped only because
they happened to share a directory, 2 pure `team_builder` regex artifacts —
see `W16_llm_read_extraction.md` §5.1). That left only **2** teams as real
evidence for the paper's claim ("independently authored skills don't state
their coordination structure") — the denominator this task (W17) exists to
grow.

This module is that missing filter, promoted to a first-class, reusable,
re-judgeable pipeline stage. It does NOT try to automate the judgment
itself — "does this task need coordination" is exactly the kind of question
a keyword rule would get wrong in both directions (a solo-voice file can
describe a task that plainly needs a counterpart, e.g. "review and merge
this pull request"; a file dense with other agents' names can still
describe fundamentally solo work, e.g. a style guide that happens to link to
other style guides). Discipline, restated from the task card: **judge the
task, not the file structure.** A verdict of "unclear" is legitimate and
expected — never force "yes" to hit a target.

Every verdict is stored with its evidence (verbatim quotes from the
artifact/task text the judge actually read) so a reviewer can re-judge it
later without re-reading the source repo. `build_dossier()` below produces
the compact, quote-carrying input a judge (human or model) reads to reach a
verdict — it does NOT decide anything itself.
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

VERDICT_VALUES = ("yes", "no", "unclear")

RUBRIC = (
    "Does the described TASK require two or more interacting parties to "
    "complete it — not \"could this file's author imagine other agents "
    "existing,\" but \"does finishing the thing this text describes require "
    "someone else to do something and hand back a result, in some order?\" "
    "Judge the task, not the file structure: a pull-request review-and-merge "
    "task needs multiple parties even if the file describing it is written "
    "solo-voice ('you review the diff'); a catalog entry that merely *lists* "
    "other agents by name without the task ever depending on their output is "
    "NOT coordination-requiring. Every 'yes' or 'no' verdict must be backed "
    "by at least one verbatim quote from the artifact/task text. Where the "
    "text is genuinely ambiguous — neither a clear single-actor task nor a "
    "clear dependency on another party — the correct verdict is 'unclear,' "
    "not a forced 'yes'. Never invent evidence; if you cannot quote it, you "
    "cannot claim it."
)


@dataclass
class CoordinationVerdict:
    """One judged verdict for one candidate team (or, degenerate case, a
    single artifact that references collaborators but never got teamed).
    `evidence` is always verbatim substrings of the source artifact text —
    never paraphrase, never invention (same evidence-only discipline W16
    used for local-type extraction, applied one step earlier in the
    pipeline)."""

    team_id: str
    source_repo: str
    roles: list[str]
    requires_coordination: str          # "yes" | "no" | "unclear"
    evidence: list[str] = field(default_factory=list)
    reasoning: str = ""
    judged_by: str = "model-read"       # e.g. "model-read:W17" or "model-read:W17-batch-3"
    task_summary: str = ""              # one-line, judge-authored (not a quote)
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.requires_coordination not in VERDICT_VALUES:
            raise ValueError(
                f"requires_coordination={self.requires_coordination!r} not in {VERDICT_VALUES}")
        if self.requires_coordination == "yes" and not self.evidence:
            raise ValueError(
                f"team {self.team_id!r}: a 'yes' verdict must carry at least "
                f"one verbatim evidence quote — conservative discipline, no "
                f"forced yes without a quote to back it")
        if not self.reasoning.strip():
            raise ValueError(f"team {self.team_id!r}: reasoning must not be empty")

    def to_json(self) -> dict:
        return asdict(self)


# ── dossier building (judge's INPUT, not the verdict itself) ─────────────

def _short_desc(artifact) -> str:
    """Best short human-authored description of what this role/artifact is
    for: frontmatter `description`, else the first non-empty line of body
    text, truncated. Used only to give a judge quick task context — the
    judge must still quote the actual text for evidence, this is not a
    substitute for reading."""
    fm_desc = artifact.frontmatter.get("description")
    if fm_desc:
        return str(fm_desc)[:300]
    for line in artifact.body.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line[:300]
    return ""


def build_dossier(team, artifacts_by_id: dict) -> dict:
    """Compact, quote-preserving summary of one candidate team for a judge
    to read. Includes every role's short description AND every textual
    cross-reference edge `team_builder.py` recorded (with its verbatim
    quote) so 'yes'/'no' judgments can cite team_builder's own evidence
    directly rather than re-deriving it. A judge is free to (and, per the
    rubric, often must) go read the full artifact text beyond this dossier
    before committing to a verdict — this function only bounds the *minimum*
    context, it is not a claim that this is sufficient evidence on its own."""
    roles = []
    for aid in team.artifact_ids:
        a = artifacts_by_id.get(aid)
        if a is None:
            continue
        roles.append({
            "role_hint": a.role_hint,
            "path": a.path,
            "description": _short_desc(a),
        })
    edges = list(getattr(team, "edges", None) or [])
    return {
        "team_id": team.team_id,
        "source_repo": team.source_repo,
        "heuristic": team.heuristic,
        "notes": list(team.notes),
        "roles": roles,
        "edges": edges,   # [{"from":, "to":, "quote":, "kind":}, ...]
    }


# ── I/O: the auditable, re-judgeable JSONL ────────────────────────────────

def write_verdicts_jsonl(path: Path, verdicts: Iterable[CoordinationVerdict]) -> int:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as f:
        for v in verdicts:
            f.write(json.dumps(v.to_json(), sort_keys=True, ensure_ascii=False))
            f.write("\n")
            n += 1
    return n


def read_verdicts_jsonl(path: Path) -> list[CoordinationVerdict]:
    out = []
    with Path(path).open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}:{line_no}: invalid JSON: {e}") from e
            known = {fld.name for fld in CoordinationVerdict.__dataclass_fields__.values()}
            extra_keys = set(obj) - known
            if extra_keys:
                raise ValueError(f"{path}:{line_no}: unknown field(s) {sorted(extra_keys)}")
            out.append(CoordinationVerdict(**obj))
    return out


def funnel_counts(verdicts: Iterable[CoordinationVerdict]) -> dict[str, int]:
    c = Counter(v.requires_coordination for v in verdicts)
    return {k: c.get(k, 0) for k in VERDICT_VALUES}


def merge_verdict_files(paths: list[Path], out_path: Path) -> tuple[int, list[str]]:
    """Merge several judges'/batches' verdict JSONLs into one, erroring on a
    duplicate team_id (each team must be judged exactly once) rather than
    silently picking one — duplicates almost always mean two batches were
    handed overlapping team lists by mistake."""
    seen: dict[str, str] = {}
    merged: list[CoordinationVerdict] = []
    dupes: list[str] = []
    for p in paths:
        for v in read_verdicts_jsonl(p):
            if v.team_id in seen:
                dupes.append(f"{v.team_id} (in both {seen[v.team_id]} and {p})")
                continue
            seen[v.team_id] = str(p)
            merged.append(v)
    n = write_verdicts_jsonl(out_path, merged)
    return n, dupes
