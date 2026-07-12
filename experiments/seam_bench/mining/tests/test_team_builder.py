"""Team-building heuristic tests."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from harvest import Artifact, adapter_local_vendored, adapter_crewai_style  # noqa: E402
from team_builder import (                                  # noqa: E402
    build_teams, worked_example_teams, explicit_reference_teams,
    same_directory_teams, named_counterpart_star_teams, crewai_config_teams,
    MAX_SAME_DIR_TEAM, MAX_STAR_TEAM, SKILLS_SAFETY_TEAMS)


def _art(source_repo, path, role_hint, text="", adapter="copilot_style") -> Artifact:
    return Artifact(
        artifact_id=f"id:{source_repo}:{path}", source_repo=source_repo, path=path,
        role_hint=role_hint, text=text, frontmatter={}, adapter=adapter,
        retrieval_route="git clone")


def test_worked_example_teams_from_real_local_vendored_artifacts():
    repo_root = HERE.parents[3]
    cases_dir = repo_root / "experiments" / "cases" / "skills_safety"
    artifacts = adapter_local_vendored(cases_dir)
    teams = worked_example_teams(artifacts)
    team_ids = {t.team_id for t in teams}
    for case_id in SKILLS_SAFETY_TEAMS:
        assert f"worked_example:{case_id}" in team_ids
    pr_merge_team = next(t for t in teams if t.team_id == "worked_example:pr_merge")
    assert set(pr_merge_team.role_names) == set(SKILLS_SAFETY_TEAMS["pr_merge"])
    assert pr_merge_team.heuristic == "worked-example"


def test_explicit_reference_links_handoff_mentions():
    a = _art("repo/x", "a.md", "Reviewer", text="When done, hand off to the Merger.")
    b = _art("repo/x", "b.md", "Merger", text="I merge once approved.")
    c = _art("repo/x", "c.md", "Unrelated", text="I do my own thing entirely.")
    teams = explicit_reference_teams([a, b, c], claimed=set())
    assert len(teams) == 1
    assert set(teams[0].role_names) == {"Reviewer", "Merger"}
    assert teams[0].heuristic == "explicit-reference"


def test_explicit_reference_respects_already_claimed():
    a = _art("repo/x", "a.md", "Reviewer", text="hand off to the Merger")
    b = _art("repo/x", "b.md", "Merger", text="merges changes")
    teams = explicit_reference_teams([a, b], claimed={a.artifact_id})
    assert teams == []    # a is already claimed, b alone can't form a team


def test_same_directory_groups_and_caps_large_directories():
    small = [_art("repo/y", f"dir1/{i}.md", f"role{i}") for i in range(3)]
    large = [_art("repo/y", f"dir2/{i}.md", f"role{i}") for i in range(MAX_SAME_DIR_TEAM + 2)]
    teams, skipped = same_directory_teams(small + large, claimed=set())
    assert len(teams) == 1
    assert teams[0].heuristic == "same-directory"
    assert len(teams[0].artifact_ids) == 3
    assert len(skipped) == 1
    assert skipped[0]["count"] == MAX_SAME_DIR_TEAM + 2


def test_build_teams_unteamed_are_singletons_not_claimed_anywhere():
    lonely = _art("repo/z", "solo/only.md", "Solo", text="I stand alone.")
    result = build_teams([lonely])
    assert result.teams == []
    assert result.unteamed == [lonely.artifact_id]


def test_named_counterpart_finds_integration_section_bullets():
    # mirrors the real VoltAgent "Integration with other agents:" convention
    a = _art("repo/w", "backend.md", "backend-developer", text=(
        "Backend dev stuff.\n\nIntegration with other agents:\n"
        "- Receive API specifications from api-designer\n"
        "- Collaborate with security-auditor on vulnerabilities\n"))
    b = _art("repo/w", "api.md", "api-designer", text="Designs APIs.")
    c = _art("repo/w", "sec.md", "security-auditor", text="Audits security.")
    teams = named_counterpart_star_teams([a, b, c], claimed=set())
    assert len(teams) == 1
    t = teams[0]
    assert t.heuristic == "named-counterpart"
    assert set(t.role_names) == {"backend-developer", "api-designer", "security-auditor"}
    quotes = {e["to"]: e["quote"] for e in t.edges}
    assert "api-designer" in quotes and "Receive API specifications from api-designer" in quotes["api-designer"]


def test_named_counterpart_caps_star_team_size():
    hub = _art("repo/w", "hub.md", "hub", text="Integration with other agents:\n" + "\n".join(
        f"- Collaborate with peer{i} on things" for i in range(10)))
    peers = [_art("repo/w", f"p{i}.md", f"peer{i}", text=f"peer {i}") for i in range(10)]
    teams = named_counterpart_star_teams([hub] + peers, claimed=set())
    assert len(teams) == 1
    assert len(teams[0].role_names) == MAX_STAR_TEAM


def test_named_counterpart_greedy_claiming_no_double_use():
    a = _art("repo/w", "a.md", "a", text="Integration with other agents:\n- Collaborate with b on x")
    b = _art("repo/w", "b.md", "b", text="Integration with other agents:\n- Collaborate with a on x")
    claimed = set()
    teams = named_counterpart_star_teams([a, b], claimed)
    assert len(teams) == 1     # a claims b; b has no unclaimed counterparts left to be its own hub
    assert claimed == {a.artifact_id, b.artifact_id}


def test_crewai_config_teams_group_by_crew_and_capture_context_edges(tmp_path):
    crew_dir = tmp_path / "crews" / "demo" / "config"
    crew_dir.mkdir(parents=True)
    (crew_dir / "agents.yaml").write_text(
        "researcher:\n  role: R\n  goal: research\n  backstory: b\n"
        "writer:\n  role: W\n  goal: write\n  backstory: b\n", encoding="utf-8")
    (crew_dir / "tasks.yaml").write_text(
        "research_task:\n  description: research it\n  expected_output: notes\n  agent: researcher\n"
        "writing_task:\n  description: write it\n  expected_output: post\n  agent: writer\n"
        "  context: [research_task]\n", encoding="utf-8")
    arts = adapter_crewai_style(tmp_path, "fixture/crewai")
    teams = crewai_config_teams(arts, claimed=set())
    assert len(teams) == 1
    t = teams[0]
    assert t.heuristic == "crewai-config"
    assert set(t.role_names) == {"researcher", "writer"}
    assert len(t.edges) == 1
    assert t.edges[0]["from"] == "researcher" and t.edges[0]["to"] == "writer"


def test_build_teams_priority_worked_example_beats_same_directory():
    # two artifacts that would ALSO satisfy same-directory grouping, but
    # already claimed by a worked-example team must not double-count.
    repo_root = HERE.parents[3]
    cases_dir = repo_root / "experiments" / "cases" / "skills_safety"
    artifacts = adapter_local_vendored(cases_dir)
    result = build_teams(artifacts)
    all_claimed = [aid for t in result.teams for aid in t.artifact_ids]
    assert len(all_claimed) == len(set(all_claimed))   # no artifact in two teams
