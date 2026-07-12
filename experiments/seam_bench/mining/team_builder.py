"""team_builder.py — group harvested artifacts into interacting TEAMS.

A protocol needs >= 2 roles, so a "team" is the unit `formalize.py` feeds to
the compactor. Four heuristics, applied in priority order (an artifact
already claimed by a higher-priority team is not reconsidered by a lower
one):

  1. `worked_example_teams`   — the existing skills_safety groupings
     (case directory boundary) PLUS the literal upstream-file team a human
     already curated for `pr_merge`/`doc_pipeline` (same file *selection*,
     now sourced from the real harvested artifacts rather than the
     paraphrased skills_original/ copies) — the task card's "existing
     skills_safety groupings as worked examples".
  2. `explicit_reference_teams` — artifacts in the same source repo whose
     text names another artifact's role/agent name near a handoff verb
     ("hand off to", "delegate to", "escalate to", "send to", "pass to",
     "invoke the ... agent") — the task card's "explicit role references
     in text". W17 addition: every matched edge now records its verbatim
     quote in `Team.edges`, feeding `coordination_filter.py`'s dossier
     directly instead of losing the evidence at team-formation time.
  3. `named_counterpart_star_teams` (W17 addition) — an artifact that NAMES
     a counterpart role can seed a team even across directories, per the
     task card. Broader than #2 in two ways: (a) it matches a wider set of
     collaboration verbs (VoltAgent's near-universal "Integration with other
     agents:" section uses "Receive ... from", "Provide ... to", "Share ...
     with", "Support ... on", "Guide ... on", "Assist ... with", "Partner
     with", "Sync with" — none of which #2's narrower handoff-verb list
     matches); (b) instead of taking a whole connected component (which, on
     a densely cross-referenced catalog like VoltAgent's 130/172
     collaboration-bearing files, collapses into one unusable 100+-role
     blob), it forms one STAR team per hub artifact: the artifact itself
     plus up to `MAX_STAR_TEAM - 1` of the *specific* counterparts it names,
     greedily claimed so no artifact is double-counted. This mirrors the
     shape W16 already validated as extractable by hand for the
     `gem-orchestrator` case (team 9 in that report) — one coordinator/actor
     naming several specific others — rather than inventing a new topology.
  4. `same_directory_teams` — artifacts sharing an immediate parent
     directory, capped at a small size so this heuristic doesn't propose a
     20-role "team" out of an unrelated agent-catalog folder (which would
     be certain to fail multiparty-compatibility and isn't really a team
     in the protocol sense — R3 flags exactly this failure mode for
     directory-shaped sources). Directories above the cap are recorded as
     `skipped_too_large` (their artifacts fall through to `unteamed`,
     which is itself a yield statistic, not an error).

Singleton artifacts claimed by no heuristic are returned as `unteamed`.

IMPORTANT: none of these four heuristics judges whether the underlying TASK
needs coordination — they only decide whether two files' TEXT cross-
reference each other or share a directory. That judgment is a separate,
later pipeline stage (`coordination_filter.py`), applied to every team this
module proposes, precisely because file-level grouping and task-level
coordination need are two different questions (a team can be textually
well-connected and still describe purely solo work, e.g. two tool-variant
docs of the same skill; a team can look flimsy here and still describe a
genuinely multi-party task, e.g. a solo-voice PR-merge doc).
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Optional

from harvest import Artifact

MAX_SAME_DIR_TEAM = 6   # roles; above this, directory heuristic is skipped
MAX_STAR_TEAM = 6       # roles; hub + up to 5 named counterparts
MIN_TEAM_ROLES = 2

_HANDOFF_RE = re.compile(
    r"\b(?:hand(?:s|ed)?[\s-]?off to|delegat(?:e|es|ed) to|escalat(?:e|es|ed) to|"
    r"send(?:s)? (?:it |this )?to|pass(?:es)? (?:it |this )?to|"
    r"invoke(?:s)? the|route(?:s)? to)\b",
    re.IGNORECASE)

# Broader collaboration-verb list — covers the VoltAgent-style "Integration
# with other agents:" bullet convention (verified 2026-07-12 against a live
# clone: 130/172 VoltAgent subagent files carry this exact heading, each
# with 4-8 bullet lines of the form "<Verb> ... <role-name>"; sample
# verbatim bullets: "Receive API specifications from api-designer",
# "Collaborate with security-auditor on vulnerabilities", "Guide debugger on
# issue patterns") plus a few generic additions seen in awesome-copilot
# prose ("consult", "notify", "report to").
_COLLAB_VERB_RE = re.compile(
    r"\b(?:receiv(?:e|es|ed) .{0,40}?from|provid(?:e|es|ed) .{0,40}?to|"
    r"shar(?:e|es|ed) .{0,40}?with|coordinat(?:e|es|ed) with|work(?:s|ed)? with|"
    r"support(?:s|ed)? .{0,40}?(?:with|on)|collaborat(?:e|es|ed) with|"
    r"guid(?:e|es|ed) .{0,40}?on|assist(?:s|ed)? .{0,40}?(?:with|on)|"
    r"help(?:s|ed)? .{0,40}?(?:with|on)|partner(?:s|ed)? with|sync(?:s|ed|hronize)? with|"
    r"consult(?:s|ed)? with|notif(?:y|ies|ied)|report(?:s|ed)? to|escalat(?:e|es|ed) to)\b",
    re.IGNORECASE)

_COLLAB_SECTION_RE = re.compile(
    r"(?im)^#{0,3}\s*integration with other agents:?\s*$(?P<body>(?:\n-[^\n]*)+)")


@dataclass
class Team:
    team_id: str
    source_repo: str
    artifact_ids: list[str]
    role_names: list[str]
    heuristic: str
    notes: list[str] = field(default_factory=list)
    edges: list[dict] = field(default_factory=list)   # [{"from","to","quote","kind"}]


@dataclass
class TeamBuildResult:
    teams: list[Team]
    unteamed: list[str]                       # artifact_ids
    skipped_too_large: list[dict]              # [{dir, count}]


# ── 1. worked-example teams ───────────────────────────────────────────────

# case_id -> ordered list of role_hints (matches each case's skills_original
# directory contents exactly — see experiments/cases/skills_safety/<case>/).
SKILLS_SAFETY_TEAMS: dict[str, list[str]] = {
    "pr_merge": ["Author", "CodeReviewer", "SecurityReviewer", "Merger"],
    "content_pipeline": ["Researcher", "Writer", "Editor", "Publisher"],
    "airline_seat": ["Triage", "SeatBooking", "FlightSystem"],
    "booking_saga": ["Traveler", "Hotel", "Payment"],
    "code_execution": ["Coder", "Executor", "Reviewer"],
    "doc_pipeline": ["Requester", "Writer", "BrandReviewer", "DocLead"],
}

# curated real-upstream-file teams: (source_repo, [path substrings]) — the
# SAME role selection a human made for the skills_safety case, now pointed
# at the literal harvested files instead of the paraphrased skills_original/
# copies. Lets the funnel show whether the *real* prose (not the STJP
# author's paraphrase of it) formalizes any differently.
CURATED_REMOTE_TEAMS: dict[str, tuple[str, list[str]]] = {
    "pr_merge_upstream": ("github/awesome-copilot", [
        "agents/address-comments.agent.md",
        "instructions/code-review-generic.instructions.md",
        "agents/se-security-reviewer.agent.md",
        "agents/principal-software-engineer.agent.md",
    ]),
    "doc_pipeline_upstream": ("anthropics/skills", [
        "skills/internal-comms/SKILL.md",
        "skills/brand-guidelines/SKILL.md",
        "skills/doc-coauthoring/SKILL.md",
    ]),
}


def worked_example_teams(artifacts: list[Artifact]) -> list[Team]:
    by_path: dict[tuple[str, str], Artifact] = {(a.source_repo, a.path): a for a in artifacts}
    by_case_role: dict[tuple[str, str], Artifact] = {}
    for a in artifacts:
        if a.adapter == "local_vendored":
            by_case_role[(a.frontmatter.get("_case", ""), a.role_hint)] = a

    teams: list[Team] = []
    for case_id, roles in SKILLS_SAFETY_TEAMS.items():
        members = [by_case_role.get((case_id, r)) for r in roles]
        members = [m for m in members if m is not None]
        if len(members) < MIN_TEAM_ROLES:
            continue
        teams.append(Team(
            team_id=f"worked_example:{case_id}",
            source_repo="in-repo:skills_safety",
            artifact_ids=[m.artifact_id for m in members],
            role_names=[m.role_hint for m in members],
            heuristic="worked-example",
            notes=[f"mirrors experiments/cases/skills_safety/{case_id}/skills_original/"]))

    for team_id, (repo, paths) in CURATED_REMOTE_TEAMS.items():
        members = [by_path.get((repo, p)) for p in paths]
        members = [m for m in members if m is not None]
        if len(members) < MIN_TEAM_ROLES:
            continue
        teams.append(Team(
            team_id=f"worked_example:{team_id}",
            source_repo=repo,
            artifact_ids=[m.artifact_id for m in members],
            role_names=[m.role_hint for m in members],
            heuristic="worked-example",
            notes=["curated selection mirroring the skills_safety worked "
                   "example, applied to the literal upstream files"]))
    return teams


# ── 2. explicit textual cross-reference ───────────────────────────────────

def explicit_reference_teams(artifacts: list[Artifact],
                             claimed: set[str]) -> list[Team]:
    """Weakly-connected components of the "A's text names B near a handoff
    verb" graph, restricted to unclaimed artifacts within the same source
    repo. Two artifacts both naming a *third*, unharvested role are not
    linked (no such role exists in `artifacts`, so no edge is added)."""
    candidates = [a for a in artifacts if a.artifact_id not in claimed]
    by_repo: dict[str, list[Artifact]] = defaultdict(list)
    for a in candidates:
        by_repo[a.source_repo].append(a)

    teams: list[Team] = []
    for repo, group in by_repo.items():
        # role_hint (lowercased, word-boundary safe) -> artifact
        name_index = {a.role_hint.lower(): a for a in group}
        adj: dict[str, set[str]] = defaultdict(set)
        edge_quotes: dict[tuple[str, str], str] = {}
        for a in group:
            for m in _HANDOFF_RE.finditer(a.text):
                window = a.text[m.end(): m.end() + 80]
                for name, other in name_index.items():
                    if other.artifact_id == a.artifact_id:
                        continue
                    if re.search(r"\b" + re.escape(name) + r"\b", window, re.IGNORECASE):
                        adj[a.artifact_id].add(other.artifact_id)
                        adj[other.artifact_id].add(a.artifact_id)
                        quote = a.text[max(0, m.start() - 20):m.end() + 80].strip()
                        edge_quotes.setdefault((a.artifact_id, other.artifact_id), quote)

        seen: set[str] = set()
        by_id = {a.artifact_id: a for a in group}
        for aid in list(adj):
            if aid in seen or not adj[aid]:
                continue
            # BFS component
            comp = {aid}
            frontier = [aid]
            while frontier:
                cur = frontier.pop()
                for nb in adj.get(cur, ()):
                    if nb not in comp:
                        comp.add(nb)
                        frontier.append(nb)
            seen |= comp
            if len(comp) >= MIN_TEAM_ROLES:
                members = [by_id[i] for i in sorted(comp)]
                edges = []
                for (fr, to), quote in edge_quotes.items():
                    if fr in comp and to in comp:
                        edges.append({"from": by_id[fr].role_hint, "to": by_id[to].role_hint,
                                      "quote": quote, "kind": "handoff-verb"})
                teams.append(Team(
                    team_id=f"explicit_ref:{repo}:{'+'.join(sorted(m.role_hint for m in members))}",
                    source_repo=repo,
                    artifact_ids=[m.artifact_id for m in members],
                    role_names=[m.role_hint for m in members],
                    heuristic="explicit-reference",
                    notes=["connected via a handoff-verb + role-name text match"],
                    edges=edges))
    return teams


# ── 2b. named-counterpart star teams (W17 addition) ───────────────────────

def _extract_collab_edges(a: Artifact, name_index: dict[str, Artifact]
                          ) -> list[tuple[str, str]]:
    """Return [(target_artifact_id, verbatim_quote), ...] for every OTHER
    known role this artifact's text names next to a collaboration verb.
    Prefers a dedicated 'Integration with other agents:' section when
    present (VoltAgent's convention — one collaborator per bullet line, so
    the quote is exactly that bullet); falls back to a same-text-window
    scan (mirroring explicit_reference_teams but with the broader verb
    list) for sources without that heading."""
    out: list[tuple[str, str]] = []
    sec = _COLLAB_SECTION_RE.search(a.text)
    scanned_body = sec.group("body") if sec else a.text
    for m in _COLLAB_VERB_RE.finditer(scanned_body):
        window = scanned_body[m.end(): m.end() + 60]
        # also allow the name to appear inside the verb match itself
        # (e.g. "receive ... from api-designer" — verb regex already
        # consumed up to 40 chars after "from"), so search a slightly
        # wider span anchored at the verb match start too.
        span = scanned_body[m.start(): m.end() + 60]
        for name, other in name_index.items():
            if other.artifact_id == a.artifact_id:
                continue
            if re.search(r"\b" + re.escape(name) + r"\b", span, re.IGNORECASE):
                if sec:
                    # whole bullet line containing this verb match
                    line_start = scanned_body.rfind("\n", 0, m.start()) + 1
                    line_end = scanned_body.find("\n", m.end())
                    if line_end == -1:
                        line_end = len(scanned_body)
                    quote = scanned_body[line_start:line_end].strip().lstrip("-").strip()
                else:
                    quote = span.strip()
                out.append((other.artifact_id, quote))
    return out


def named_counterpart_star_teams(artifacts: list[Artifact],
                                 claimed: set[str]) -> list[Team]:
    """One STAR team per hub artifact: the hub plus up to
    `MAX_STAR_TEAM - 1` specific counterparts its own text names next to a
    collaboration verb, greedily claimed (an artifact already used as a
    counterpart in an earlier star cannot be reused as a counterpart in a
    later one, though it CAN still later serve as its own hub if it has
    unclaimed counterparts of its own). Restricted to the same source repo,
    same as every other heuristic here. Processing order is a stable sort
    by artifact_id so a re-run is byte-identical."""
    candidates = [a for a in artifacts if a.artifact_id not in claimed]
    by_repo: dict[str, list[Artifact]] = defaultdict(list)
    for a in candidates:
        by_repo[a.source_repo].append(a)

    teams: list[Team] = []
    for repo, group in sorted(by_repo.items()):
        name_index = {a.role_hint.lower(): a for a in group}
        by_id = {a.artifact_id: a for a in group}
        local_claimed: set[str] = set()
        for a in sorted(group, key=lambda x: x.artifact_id):
            if a.artifact_id in local_claimed:
                continue
            raw_edges = _extract_collab_edges(a, name_index)
            # de-dupe targets, keep first quote per target, stable order
            picked: list[tuple[str, str]] = []
            seen_targets: set[str] = set()
            for tid, quote in raw_edges:
                if tid in local_claimed or tid in seen_targets or tid == a.artifact_id:
                    continue
                seen_targets.add(tid)
                picked.append((tid, quote))
                if len(picked) >= MAX_STAR_TEAM - 1:
                    break
            if not picked:
                continue
            members = [a.artifact_id] + [tid for tid, _ in picked]
            local_claimed.update(members)
            edges = [{"from": a.role_hint, "to": by_id[tid].role_hint,
                      "quote": quote, "kind": "named-counterpart"}
                     for tid, quote in picked]
            teams.append(Team(
                team_id=f"named_counterpart:{repo}:{a.role_hint}+"
                        f"{'+'.join(by_id[tid].role_hint for tid, _ in picked)}",
                source_repo=repo,
                artifact_ids=members,
                role_names=[a.role_hint] + [by_id[tid].role_hint for tid, _ in picked],
                heuristic="named-counterpart",
                notes=[f"star team: {a.role_hint} names {len(picked)} counterpart(s) "
                       f"next to a collaboration verb"],
                edges=edges))
        claimed.update(local_claimed)
    return teams


# ── 2c. crewai config-pair teams (W17 addition) ───────────────────────────

def crewai_config_teams(artifacts: list[Artifact], claimed: set[str]) -> list[Team]:
    """One team per `config/agents.yaml` (grouped by
    `frontmatter["_crew_dir"]`) — NOT a text-heuristic guess: every agent in
    one `agents.yaml` is, by CrewAI's own `Crew(agents=..., tasks=...)`
    construction, a real member of the same crew (`harvest.py
    ::adapter_crewai_style`). Edges are only added where a task's `context:`
    field literally names another task (a real, quotable dependency); most
    scaffolded crews here rely on `Process.sequential` file-order instead,
    which is recorded as a note (an ordering claim, not a quoted edge) since
    no single line of YAML states it — the evidence-only discipline applies
    to edges the same way it applies everywhere else in this pipeline."""
    candidates = [a for a in artifacts
                  if a.artifact_id not in claimed and a.adapter == "crewai_style"]
    by_crew: dict[tuple[str, str], list[Artifact]] = defaultdict(list)
    for a in candidates:
        by_crew[(a.source_repo, a.frontmatter.get("_crew_dir", ""))].append(a)

    teams: list[Team] = []
    for (repo, crew_dir), members in sorted(by_crew.items()):
        if len(members) < MIN_TEAM_ROLES:
            continue
        # task_key -> owning agent's role_hint (for resolving context: deps)
        task_owner = {tk: m.role_hint for m in members
                     for tk in m.frontmatter.get("_own_task_keys", [])}
        edges = []
        for m in members:
            for line in m.text.splitlines():
                if line.startswith("Context (depends on prior task output of):"):
                    dep_str = line.split(":", 1)[1].strip()
                    for other_tk, other_role in task_owner.items():
                        if other_tk in dep_str and other_role != m.role_hint:
                            edges.append({"from": other_role, "to": m.role_hint,
                                         "quote": line.strip(), "kind": "task-context-field"})
        teams.append(Team(
            team_id=f"crewai_config:{repo}:{crew_dir}",
            source_repo=repo,
            artifact_ids=[m.artifact_id for m in members],
            role_names=[m.role_hint for m in members],
            heuristic="crewai-config",
            notes=[f"all agents defined in {crew_dir}/config/agents.yaml "
                   f"({len(members)} agents); task order in "
                   f"{crew_dir}/config/tasks.yaml is "
                   f"{members[0].frontmatter.get('_task_order', [])!r} "
                   f"(Process.sequential file order is CrewAI's own default "
                   f"execution order; not itself a quoted per-edge claim)"],
            edges=edges))
        claimed.update(m.artifact_id for m in members)
    return teams


# ── 3. same-directory grouping (capped) ───────────────────────────────────

def same_directory_teams(artifacts: list[Artifact],
                         claimed: set[str]) -> tuple[list[Team], list[dict]]:
    candidates = [a for a in artifacts if a.artifact_id not in claimed]
    by_dir: dict[tuple[str, str], list[Artifact]] = defaultdict(list)
    for a in candidates:
        parent = PurePosixPath(a.path).parent.as_posix()
        by_dir[(a.source_repo, parent)].append(a)

    teams: list[Team] = []
    skipped: list[dict] = []
    for (repo, d), members in sorted(by_dir.items()):
        if len(members) < MIN_TEAM_ROLES:
            continue
        if len(members) > MAX_SAME_DIR_TEAM:
            skipped.append({"source_repo": repo, "dir": d, "count": len(members)})
            continue
        teams.append(Team(
            team_id=f"same_dir:{repo}:{d}",
            source_repo=repo,
            artifact_ids=[m.artifact_id for m in members],
            role_names=[m.role_hint for m in members],
            heuristic="same-directory",
            notes=[f"all files directly under {d!r} ({len(members)} roles)"]))
    return teams, skipped


# ── driver ─────────────────────────────────────────────────────────────

def build_teams(artifacts: list[Artifact]) -> TeamBuildResult:
    teams: list[Team] = []
    claimed: set[str] = set()

    worked = worked_example_teams(artifacts)
    teams.extend(worked)
    for t in worked:
        claimed.update(t.artifact_ids)

    explicit = explicit_reference_teams(artifacts, claimed)
    teams.extend(explicit)
    for t in explicit:
        claimed.update(t.artifact_ids)

    named = named_counterpart_star_teams(artifacts, claimed)  # mutates claimed itself
    teams.extend(named)

    crewai = crewai_config_teams(artifacts, claimed)   # mutates claimed itself
    teams.extend(crewai)

    same_dir, skipped = same_directory_teams(artifacts, claimed)
    teams.extend(same_dir)
    for t in same_dir:
        claimed.update(t.artifact_ids)

    unteamed = [a.artifact_id for a in artifacts if a.artifact_id not in claimed]
    return TeamBuildResult(teams=teams, unteamed=unteamed, skipped_too_large=skipped)
