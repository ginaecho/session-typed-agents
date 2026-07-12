"""coordination_filter.py — schema validity, JSONL round-trip, dossier
shape, and merge-dedup tests."""
import sys
import tempfile
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from coordination_filter import (                                   # noqa: E402
    CoordinationVerdict, build_dossier, funnel_counts, merge_verdict_files,
    read_verdicts_jsonl, write_verdicts_jsonl)
from team_builder import Team                                        # noqa: E402
from harvest import Artifact                                         # noqa: E402


def _verdict(**overrides) -> CoordinationVerdict:
    base = dict(team_id="t1", source_repo="fixture/repo", roles=["A", "B"],
               requires_coordination="yes", evidence=["send X to B"],
               reasoning="A's task explicitly hands off to B.")
    base.update(overrides)
    return CoordinationVerdict(**base)


def test_rejects_bad_verdict_value():
    with pytest.raises(ValueError):
        _verdict(requires_coordination="maybe")


def test_yes_requires_evidence():
    with pytest.raises(ValueError):
        _verdict(requires_coordination="yes", evidence=[])


def test_no_and_unclear_do_not_require_evidence():
    _verdict(requires_coordination="no", evidence=[])
    _verdict(requires_coordination="unclear", evidence=[])


def test_requires_nonempty_reasoning():
    with pytest.raises(ValueError):
        _verdict(reasoning="")
    with pytest.raises(ValueError):
        _verdict(reasoning="   ")


def test_jsonl_roundtrip():
    verdicts = [_verdict(team_id="t1"), _verdict(team_id="t2", requires_coordination="no", evidence=[])]
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "v.jsonl"
        n = write_verdicts_jsonl(p, verdicts)
        assert n == 2
        back = read_verdicts_jsonl(p)
        assert [v.team_id for v in back] == ["t1", "t2"]
        assert back[0].requires_coordination == "yes"
        assert back[1].requires_coordination == "no"


def test_read_rejects_unknown_field():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "v.jsonl"
        p.write_text('{"team_id": "t1", "source_repo": "r", "roles": [], '
                    '"requires_coordination": "no", "reasoning": "x", "bogus_field": 1}\n',
                    encoding="utf-8")
        with pytest.raises(ValueError):
            read_verdicts_jsonl(p)


def test_funnel_counts_all_three_buckets_present():
    verdicts = [_verdict(team_id="a", requires_coordination="yes"),
               _verdict(team_id="b", requires_coordination="no", evidence=[]),
               _verdict(team_id="c", requires_coordination="no", evidence=[])]
    counts = funnel_counts(verdicts)
    assert counts == {"yes": 1, "no": 2, "unclear": 0}


def test_merge_verdict_files_detects_duplicate_team_id():
    v1 = [_verdict(team_id="dup")]
    v2 = [_verdict(team_id="dup", requires_coordination="no", evidence=[])]
    with tempfile.TemporaryDirectory() as td:
        p1, p2, out = Path(td) / "a.jsonl", Path(td) / "b.jsonl", Path(td) / "merged.jsonl"
        write_verdicts_jsonl(p1, v1)
        write_verdicts_jsonl(p2, v2)
        n, dupes = merge_verdict_files([p1, p2], out)
        assert n == 1
        assert len(dupes) == 1
        assert "dup" in dupes[0]


def test_merge_verdict_files_no_duplicates():
    v1 = [_verdict(team_id="x")]
    v2 = [_verdict(team_id="y", requires_coordination="unclear", evidence=[])]
    with tempfile.TemporaryDirectory() as td:
        p1, p2, out = Path(td) / "a.jsonl", Path(td) / "b.jsonl", Path(td) / "merged.jsonl"
        write_verdicts_jsonl(p1, v1)
        write_verdicts_jsonl(p2, v2)
        n, dupes = merge_verdict_files([p1, p2], out)
        assert n == 2
        assert dupes == []


def test_build_dossier_shape():
    a1 = Artifact(artifact_id="a1", source_repo="fixture/repo", path="a.md", role_hint="A",
                 text="---\ndescription: does the A thing\n---\nBody text.",
                 frontmatter={"description": "does the A thing"})
    a2 = Artifact(artifact_id="a2", source_repo="fixture/repo", path="b.md", role_hint="B",
                 text="No frontmatter here.\nSecond line.", frontmatter={})
    team = Team(team_id="t1", source_repo="fixture/repo", artifact_ids=["a1", "a2"],
               role_names=["A", "B"], heuristic="explicit-reference",
               notes=["test team"],
               edges=[{"from": "A", "to": "B", "quote": "send X to B", "kind": "handoff-verb"}])
    dossier = build_dossier(team, {"a1": a1, "a2": a2})
    assert dossier["team_id"] == "t1"
    assert dossier["heuristic"] == "explicit-reference"
    assert len(dossier["roles"]) == 2
    assert dossier["roles"][0]["description"] == "does the A thing"
    # no frontmatter description -> falls back to first non-empty body line
    assert dossier["roles"][1]["description"] == "No frontmatter here."
    assert dossier["edges"] == [{"from": "A", "to": "B", "quote": "send X to B", "kind": "handoff-verb"}]


def test_build_dossier_skips_missing_artifact():
    team = Team(team_id="t2", source_repo="fixture/repo", artifact_ids=["missing"],
               role_names=["Ghost"], heuristic="same-directory")
    dossier = build_dossier(team, {})
    assert dossier["roles"] == []
