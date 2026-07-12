"""harvest.py — source adapters that enumerate candidate skill artifacts.

Every adapter has the same interface:

    def adapter(checkout_dir: Path, source_repo: str, **kw) -> list[Artifact]

Given a local checkout directory (a git clone, or the in-repo vendored
`experiments/cases/skills_safety/*/skills_original/` tree) and a label for
the source repo, return one `Artifact` per candidate skill/agent file. No
network I/O happens in this module — checkout dirs are prepared by the
caller (see `docs/reference/reports/seam/W8_miner.md` for the exact clone
commands used to build the fixtures this package was run against).

Adapters implemented (R3's ranked shortlist, `SEAM_TRAINING_EXECUTION_PLAN.md`
§3 D5):

  1. `adapter_copilot_style`   — `*.agent.md` / `*.instructions.md`
     (github/awesome-copilot shape).
  2. `adapter_skill_dir_style` — `SKILL.md` (anthropics/skills shape) and
     frontmatter-bearing per-agent `.md` files under a category directory
     (VoltAgent/awesome-claude-code-subagents shape).
  3. `adapter_local_vendored`  — `experiments/cases/skills_safety/*/skills_original/*.md`,
     the in-repo hand-curated precedent this whole package generalizes.

CrewAI and LangGraph are graded "supplemental" by R3 (ordering is only
partially static — `Process.hierarchical` / `speaker_selection_method="auto"`
crews have no fixed choreography to extract at all) — §Task B of
`docs/reference/reports/seam/scouts/R3_datasets_mining.md`. Their adapters
are interface stubs only: same signature, `NotImplementedError` with the
reason, no parsing logic, per the task card's explicit instruction not to
implement them.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ── the artifact record ──────────────────────────────────────────────────

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


@dataclass
class Artifact:
    """One harvested candidate skill/agent file, pre-license-check,
    pre-intent-extraction. `artifact_id` is stable across re-harvests of the
    same (source_repo, path) pair (sha256 of the two, truncated) — used as
    the join key by ledger.py, intent_extract.py, team_builder.py."""

    artifact_id: str
    source_repo: str          # e.g. "github/awesome-copilot"
    path: str                 # path relative to the checkout root (posix)
    role_hint: str             # normalized role/agent name (filename stem)
    text: str                  # raw file content, UTF-8
    frontmatter: dict[str, Any] = field(default_factory=dict)
    adapter: str = ""          # which adapter produced this
    retrieval_route: str = ""  # "git clone" | "local-vendored"

    @property
    def body(self) -> str:
        """Text with any YAML frontmatter block stripped."""
        m = _FRONTMATTER_RE.match(self.text)
        return self.text[m.end():] if m else self.text


def _artifact_id(source_repo: str, path: str) -> str:
    return hashlib.sha256(f"{source_repo}::{path}".encode("utf-8")).hexdigest()[:16]


def _parse_frontmatter(text: str) -> dict[str, Any]:
    """Minimal YAML-frontmatter reader for the `key: value` / `key: "value"`
    lines these repos actually use. Deliberately not a full YAML parser —
    the fields we need (`description`, `name`) are always simple scalars in
    every source sampled during scouting; a block list value (e.g. `tools:
    [...]`) is skipped rather than mis-parsed."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    out: dict[str, Any] = {}
    lines = m.group(1).splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        km = re.match(r'^([A-Za-z_][\w-]*):\s*(.*)$', line)
        if not km:
            i += 1
            continue
        key, val = km.group(1), km.group(2).strip()
        if val == "" and i + 1 < len(lines) and re.match(r"^\s+\S", lines[i + 1]):
            # multi-line block scalar (e.g. `description: |`) — join
            # continuation lines until dedent.
            block = []
            i += 1
            while i < len(lines) and (lines[i].startswith("  ") or not lines[i].strip()):
                block.append(lines[i].strip())
                i += 1
            out[key] = " ".join(x for x in block if x).strip()
            continue
        val = val.strip("'\"")
        out[key] = val
        i += 1
    return out


def _role_hint_from_path(path: Path, strip_suffixes: tuple[str, ...]) -> str:
    stem = path.name
    for suf in strip_suffixes:
        if stem.endswith(suf):
            stem = stem[: -len(suf)]
            break
    else:
        stem = path.stem
    return stem


# ── 1. copilot-style: *.agent.md / *.instructions.md ─────────────────────

def adapter_copilot_style(checkout_dir: Path, source_repo: str) -> list[Artifact]:
    """github/awesome-copilot shape: `agents/*.agent.md`,
    `instructions/*.instructions.md`. Each file is one standalone
    persona/instruction prose block with a `description:` frontmatter
    field — the exact shape the in-repo `pr_merge` case was hand-pulled
    from (`experiments/cases/skills_safety/pr_merge/SOURCES.md`)."""
    checkout_dir = Path(checkout_dir)
    suffixes = (".agent.md", ".instructions.md")
    out: list[Artifact] = []
    for pattern in ("**/*.agent.md", "**/*.instructions.md"):
        for p in sorted(checkout_dir.glob(pattern)):
            if ".git" in p.parts:
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            rel = p.relative_to(checkout_dir).as_posix()
            out.append(Artifact(
                artifact_id=_artifact_id(source_repo, rel),
                source_repo=source_repo,
                path=rel,
                role_hint=_role_hint_from_path(p, suffixes),
                text=text,
                frontmatter=_parse_frontmatter(text),
                adapter="copilot_style",
                retrieval_route="git clone",
            ))
    return out


# ── 2. skill-dir style: SKILL.md / per-agent .md with frontmatter ────────

_SKILL_DIR_NOISE = {
    "readme.md", "license.md", "contributing.md", "changelog.md",
    "code_of_conduct.md", "code-of-conduct.md", "security.md",
}


def adapter_skill_dir_style(checkout_dir: Path, source_repo: str,
                            require_frontmatter_description: bool = True
                            ) -> list[Artifact]:
    """Two shapes covered by one adapter, both "one markdown file = one
    agent/skill":

      - `**/SKILL.md` (anthropics/skills: `skills/<name>/SKILL.md`,
        `license: ...` + prose "when to use" in the frontmatter/body);
      - loose per-agent `.md` files with YAML frontmatter carrying a
        `description:` field (VoltAgent/awesome-claude-code-subagents:
        `categories/<cat>/<agent>.md`).

    Noise files (README/LICENSE/CONTRIBUTING/...) are excluded by name.
    Non-SKILL.md files without a `description:` frontmatter field are
    excluded too (`require_frontmatter_description`) — this is what keeps
    e.g. a plain prose README-shaped file out of the harvest without an LLM
    read; SKILL.md files are always kept even without a description field,
    since that convention alone is a strong enough signal (per R3, this is
    the exact shape `doc_pipeline` was hand-pulled from)."""
    checkout_dir = Path(checkout_dir)
    out: list[Artifact] = []
    for p in sorted(checkout_dir.rglob("*.md")):
        if ".git" in p.parts:
            continue
        name_lower = p.name.lower()
        if name_lower in _SKILL_DIR_NOISE:
            continue
        if name_lower.endswith(".agent.md") or name_lower.endswith(".instructions.md"):
            continue  # claimed by adapter_copilot_style
        text = p.read_text(encoding="utf-8", errors="replace")
        fm = _parse_frontmatter(text)
        is_skill_md = name_lower == "skill.md"
        if not is_skill_md:
            if require_frontmatter_description and "description" not in fm:
                continue
            if not fm:
                continue  # no frontmatter at all -> not an agent-shaped file
        rel = p.relative_to(checkout_dir).as_posix()
        role_hint = p.parent.name if is_skill_md else _role_hint_from_path(p, (".md",))
        out.append(Artifact(
            artifact_id=_artifact_id(source_repo, rel),
            source_repo=source_repo,
            path=rel,
            role_hint=role_hint,
            text=text,
            frontmatter=fm,
            adapter="skill_dir_style",
            retrieval_route="git clone",
        ))
    return out


# ── 3. local-vendored: experiments/cases/skills_safety/*/skills_original ─

def adapter_local_vendored(cases_dir: Path,
                           source_repo: str = "in-repo:skills_safety"
                           ) -> list[Artifact]:
    """The in-repo precedent this whole package generalizes:
    `experiments/cases/skills_safety/<case>/skills_original/*.md`. Each
    case's `SOURCES.md` already records the true upstream repo/license per
    file (see `ledger.py::ledger_from_sources_md`) — this adapter's
    `source_repo` label is deliberately the umbrella "in-repo:skills_safety"
    so `team_builder.py`'s worked-example heuristic can find them by case
    directory name; the per-file *original* provenance travels in
    `Artifact.frontmatter["_case"]` / `["_upstream"]` for the ledger to
    consume alongside `SOURCES.md`."""
    cases_dir = Path(cases_dir)
    out: list[Artifact] = []
    for case_dir in sorted(cases_dir.glob("*/")):
        skills_orig = case_dir / "skills_original"
        if not skills_orig.is_dir():
            continue
        case_id = case_dir.name
        for p in sorted(skills_orig.glob("*.md")):
            text = p.read_text(encoding="utf-8", errors="replace")
            rel = p.relative_to(cases_dir).as_posix()
            out.append(Artifact(
                artifact_id=_artifact_id(source_repo, rel),
                source_repo=source_repo,
                path=rel,
                role_hint=_role_hint_from_path(p, (".md",)),
                text=text,
                frontmatter={"_case": case_id},
                adapter="local_vendored",
                retrieval_route="local-vendored",
            ))
    return out


# ── CrewAI — config-pair adapter (W17 addition) ───────────────────────────

def _yaml_safe_load(path: Path) -> dict:
    import yaml
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def adapter_crewai_style(checkout_dir: Path, source_repo: str) -> list[Artifact]:
    """`config/agents.yaml` + `config/tasks.yaml` pairs (CrewAI's own
    scaffolded project shape — R3 §Task B.2, task card item 2.d). Unlike the
    markdown adapters above, team membership here is NOT a text-heuristic
    guess: every agent defined in one `agents.yaml` is, by CrewAI's own
    `Crew(agents=..., tasks=...)` construction, a member of the SAME crew as
    every other agent in that file — `team_builder.crewai_config_teams`
    trusts that structural fact directly instead of re-deriving it from
    prose cross-references.

    One `Artifact` per agent (`role`/`goal`/`backstory` from `agents.yaml`,
    rendered as markdown, plus the text of every task in `tasks.yaml` whose
    literal `agent:` field names this agent — R3's caveat applies unchanged:
    `Process.sequential` ordering and a task's `context: [other_task]`
    dependency are the only STATICALLY recoverable ordering signals; a
    `Process.hierarchical` crew (manager-LLM-decided order, not visible in
    these two YAML files) has no static protocol to extract, and this
    adapter does not attempt to read the crew's `crew.py` to distinguish
    the two — that is left to `coordination_filter`/two-track assessment,
    which reads the actual crew source when judging a specific team, not to
    a blanket per-repo adapter decision."""
    checkout_dir = Path(checkout_dir)
    out: list[Artifact] = []
    for agents_path in sorted(checkout_dir.rglob("agents.yaml")):
        if ".git" in agents_path.parts:
            continue
        config_dir = agents_path.parent
        tasks_path = config_dir / "tasks.yaml"
        if not tasks_path.is_file():
            continue
        agents = _yaml_safe_load(agents_path)
        tasks = _yaml_safe_load(tasks_path)
        if not agents:
            continue
        crew_dir = config_dir.parent.relative_to(checkout_dir).as_posix()
        task_order = list(tasks.keys())

        # normalize crewAI's underscore/hyphen-insensitive agent-name match
        def _norm(s: str) -> str:
            return re.sub(r"[_\-\s]+", "", s.lower())

        agent_key_by_norm = {_norm(k): k for k in agents}

        for agent_key, spec in agents.items():
            if not isinstance(spec, dict):
                continue
            role = str(spec.get("role", agent_key)).strip()
            goal = str(spec.get("goal", "")).strip()
            backstory = str(spec.get("backstory", "")).strip()
            own_tasks = []
            for tk in task_order:
                tspec = tasks.get(tk) or {}
                if not isinstance(tspec, dict):
                    continue
                t_agent = tspec.get("agent")
                if t_agent is not None and _norm(str(t_agent)) == _norm(agent_key):
                    own_tasks.append((tk, tspec))
            lines = [f"# Role: {role}", "", "## Goal", goal, "", "## Backstory", backstory]
            if own_tasks:
                lines += ["", "## Assigned tasks"]
                for tk, tspec in own_tasks:
                    lines += [f"### {tk}", str(tspec.get("description", "")).strip(),
                             "", f"Expected output: {str(tspec.get('expected_output', '')).strip()}"]
                    ctx = tspec.get("context")
                    if ctx:
                        lines += [f"Context (depends on prior task output of): {ctx}"]
            text = "\n".join(lines)
            rel = f"{crew_dir}/config/agents.yaml#{agent_key}"
            out.append(Artifact(
                artifact_id=_artifact_id(source_repo, rel),
                source_repo=source_repo,
                path=rel,
                role_hint=agent_key,
                text=text,
                frontmatter={
                    "description": (goal or role)[:300],
                    "_crew_dir": crew_dir,
                    "_task_order": task_order,
                    "_own_task_keys": [tk for tk, _ in own_tasks],
                    "_agents_path": agents_path.relative_to(checkout_dir).as_posix(),
                    "_tasks_path": tasks_path.relative_to(checkout_dir).as_posix(),
                },
                adapter="crewai_style",
                retrieval_route="git clone",
            ))
    return out


def adapter_crewai_stub(checkout_dir: Path, source_repo: str) -> list[Artifact]:
    """Deprecated alias — kept for any external caller of the old stub name.
    W17 implemented the real adapter as `adapter_crewai_style` above (R3
    graded CrewAI "B", not "A": ordering is only reliably static for
    `Process.sequential` crews; `Process.hierarchical` has no static
    protocol, and this module doesn't attempt to distinguish the two from
    the YAML alone — see the real adapter's docstring)."""
    return adapter_crewai_style(checkout_dir, source_repo)


def adapter_langgraph_stub(checkout_dir: Path, source_repo: str) -> list[Artifact]:
    """STUB — not implemented in this task.

    Why: `add_node`/`add_edge`/`add_conditional_edges` calls ARE already an
    explicit graph (R3 calls this the best mechanical fit of the three
    frameworks surveyed — nodes/edges are nearly 1:1 with an EFSM skeleton),
    but the *intent* half of the (intent, protocol) pair is typically thin
    or tutorial-boilerplate rather than a genuine human ask, which is
    exactly the axis D5 needs to be "gold" on. A real adapter would need an
    AST-level reader of `StateGraph` construction calls (not a markdown/
    frontmatter parser like the other three adapters), which is a different
    enough parsing strategy that it deserves its own implementation pass
    rather than a token stub bolted onto this module. See
    `docs/reference/reports/seam/scouts/R3_datasets_mining.md` §Task B.2.
    """
    raise NotImplementedError(
        "adapter_langgraph_stub: interface only — see docstring "
        "(R3: needs an AST reader over StateGraph construction calls, not "
        "a markdown/frontmatter parser; intent text is typically weak even "
        "when the graph extracts cleanly)")


ADAPTERS = {
    "copilot_style": adapter_copilot_style,
    "skill_dir_style": adapter_skill_dir_style,
    "local_vendored": adapter_local_vendored,
    "crewai_style": adapter_crewai_style,
    "crewai_stub": adapter_crewai_stub,   # deprecated alias, see docstring
    "langgraph_stub": adapter_langgraph_stub,
}
