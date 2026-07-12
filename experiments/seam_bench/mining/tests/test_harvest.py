"""Offline adapter tests over small fixture trees under tests/fixtures/."""
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from harvest import (                                    # noqa: E402
    adapter_copilot_style, adapter_skill_dir_style, adapter_local_vendored,
    adapter_crewai_style, adapter_crewai_stub, adapter_langgraph_stub, _parse_frontmatter)

FIXTURES = HERE / "fixtures"


def test_copilot_style_finds_agent_and_instructions_files():
    arts = adapter_copilot_style(FIXTURES / "copilot_repo", "fixture/copilot")
    paths = {a.path for a in arts}
    assert "agents/reviewer.agent.md" in paths
    assert "agents/merger.agent.md" in paths
    assert "instructions/style.instructions.md" in paths
    assert len(arts) == 3
    # LICENSE and other non-matching files must not appear
    assert all(a.path.endswith((".agent.md", ".instructions.md")) for a in arts)


def test_copilot_style_role_hint_and_frontmatter():
    arts = {a.path: a for a in adapter_copilot_style(FIXTURES / "copilot_repo", "fixture/copilot")}
    reviewer = arts["agents/reviewer.agent.md"]
    assert reviewer.role_hint == "reviewer"
    assert reviewer.frontmatter["description"] == "Reviews pull requests for correctness and style"
    assert reviewer.adapter == "copilot_style"
    assert reviewer.retrieval_route == "git clone"
    # instructions file has no frontmatter at all -> {}
    style = arts["instructions/style.instructions.md"]
    assert style.frontmatter == {}
    assert "When to use" in style.text


def test_copilot_style_artifact_id_stable_and_unique():
    a1 = adapter_copilot_style(FIXTURES / "copilot_repo", "fixture/copilot")
    a2 = adapter_copilot_style(FIXTURES / "copilot_repo", "fixture/copilot")
    ids1 = {a.artifact_id for a in a1}
    ids2 = {a.artifact_id for a in a2}
    assert ids1 == ids2                     # stable across re-harvests
    assert len(ids1) == len(a1)              # unique within one harvest


def test_skill_dir_style_finds_skill_md_and_frontmatter_agents():
    arts = adapter_skill_dir_style(FIXTURES / "skilldir_repo", "fixture/skilldir")
    paths = {a.path for a in arts}
    assert "skills/frobnicate/SKILL.md" in paths
    assert "categories/core/api-designer.md" in paths
    # README.md (no frontmatter) must be excluded
    assert "categories/core/README.md" not in paths
    assert len(arts) == 2


def test_skill_dir_style_role_hint():
    arts = {a.path: a for a in adapter_skill_dir_style(FIXTURES / "skilldir_repo", "fixture/skilldir")}
    skill = arts["skills/frobnicate/SKILL.md"]
    assert skill.role_hint == "frobnicate"      # parent dir name for SKILL.md
    agent = arts["categories/core/api-designer.md"]
    assert agent.role_hint == "api-designer"


def test_local_vendored_finds_skills_safety_originals():
    repo_root = HERE.parents[3]
    cases_dir = repo_root / "experiments" / "cases" / "skills_safety"
    arts = adapter_local_vendored(cases_dir)
    assert len(arts) >= 20    # 6 known teams, 3-4 roles each
    cases = {a.frontmatter["_case"] for a in arts}
    assert "pr_merge" in cases
    assert "content_pipeline" in cases
    pr_merge_roles = {a.role_hint for a in arts if a.frontmatter["_case"] == "pr_merge"}
    assert pr_merge_roles == {"Author", "CodeReviewer", "SecurityReviewer", "Merger"}


def test_frontmatter_parser_handles_quoted_and_block_scalars():
    text = (
        "---\n"
        "description: \"Quoted value\"\n"
        "name: 'Single quoted'\n"
        "---\n"
        "body\n"
    )
    fm = _parse_frontmatter(text)
    assert fm["description"] == "Quoted value"
    assert fm["name"] == "Single quoted"


def test_frontmatter_parser_returns_empty_without_fence():
    assert _parse_frontmatter("no frontmatter here") == {}


def test_langgraph_adapter_is_a_documented_stub():
    with pytest.raises(NotImplementedError):
        adapter_langgraph_stub(Path("."), "fixture/langgraph")


def test_crewai_style_parses_agents_and_assigns_own_tasks():
    arts = adapter_crewai_style(FIXTURES / "crewai_repo", "fixture/crewai")
    by_role = {a.role_hint: a for a in arts}
    assert set(by_role) == {"researcher", "writer"}
    researcher = by_role["researcher"]
    assert researcher.adapter == "crewai_style"
    assert researcher.frontmatter["_crew_dir"] == "crews/demo_crew"
    assert "research_task" in researcher.frontmatter["_own_task_keys"]
    assert "Senior Researcher" in researcher.text
    assert "Research the given topic" in researcher.text
    writer = by_role["writer"]
    assert "writing_task" in writer.frontmatter["_own_task_keys"]
    # the context: [research_task] dependency must be carried into the
    # rendered text verbatim so team_builder can find it as a real edge,
    # not invent one.
    assert "research_task" in writer.text


def test_crewai_stub_alias_delegates_to_real_adapter():
    # kept for backward compatibility with any external caller of the old
    # stub name; no longer raises.
    arts = adapter_crewai_stub(FIXTURES / "crewai_repo", "fixture/crewai")
    assert len(arts) == 2
