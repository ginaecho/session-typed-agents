from __future__ import annotations

from pathlib import Path

import pytest

from experiments.seam_bench.judge.aggregate import (
    ESCALATION_HIGH,
    ESCALATION_LOW,
    aggregate_panel,
    geometric_median_score,
    verify_evidence,
    weiszfeld,
    write_escalation_record,
)
from experiments.seam_bench.judge.seats import Evidence, Verdict


def make_verdict(seat_id, class_, vote, confidence, weight=1.0, evidence=None, discarded=False):
    return Verdict(
        vote=vote,
        confidence=confidence,
        evidence=evidence or [],
        missing=[],
        seat_id=seat_id,
        class_=class_,
        model_id="mock-model",
        temperature=0.3,
        weight=weight,
        discarded=discarded,
    )


# ---------------------------------------------------------------------------
# Weiszfeld / geometric median
# ---------------------------------------------------------------------------


def test_weiszfeld_matches_1d_weighted_median_on_clean_data():
    pts = [(0.2,), (0.5,), (0.8,)]
    w = [1, 1, 1]
    result = weiszfeld(pts, w)[0]
    assert abs(result - 0.5) < 1e-6


def test_geometric_median_beats_arithmetic_mean_under_one_poisoned_seat():
    """The plan's whole rationale for geometric-median aggregation:
    arithmetic vote-share has unbounded bias under a single biased judge.
    Three honest seats agree G is faithful (scores ~0.85-0.92); one seat
    is poisoned and votes confidently the opposite way (score ~0.03).
    The geometric median must sit close to the honest majority; the
    arithmetic mean gets dragged noticeably toward the poisoned seat."""
    honest_scores = [0.90, 0.85, 0.92]
    poisoned_score = 0.03

    verdicts = [make_verdict(f"honest-{i}", "fwd", "yes", s) for i, s in enumerate(honest_scores)]
    verdicts.append(make_verdict("poisoned", "back", "no", 1.0 - poisoned_score))  # score = poisoned_score

    arithmetic_mean = (sum(honest_scores) + poisoned_score) / 4
    geo_median = geometric_median_score(verdicts)

    honest_center = sum(honest_scores) / len(honest_scores)

    assert geo_median is not None
    # Geometric median stays close to the honest cluster...
    assert abs(geo_median - honest_center) < abs(arithmetic_mean - honest_center)
    # ...and specifically resists being dragged under the escalation
    # threshold the way the arithmetic mean would be at more extreme
    # poisoning ratios (documented property, checked directly here).
    assert geo_median > ESCALATION_HIGH
    assert arithmetic_mean < geo_median


def test_geometric_median_ignores_discarded_verdicts():
    verdicts = [
        make_verdict("a", "fwd", "yes", 0.9),
        make_verdict("b", "fwd", "no", 0.9, discarded=True),  # would drag score to ~0.1 if counted
    ]
    score = geometric_median_score(verdicts)
    assert score == pytest.approx(0.9)


def test_geometric_median_none_when_all_abstain():
    verdicts = [make_verdict("a", "fwd", "abstain", 0.0), make_verdict("b", "back", "abstain", 0.0)]
    assert geometric_median_score(verdicts) is None


# ---------------------------------------------------------------------------
# Evidence verification (lie detector)
# ---------------------------------------------------------------------------


def test_verify_evidence_passes_for_real_quotes():
    v = make_verdict(
        "s", "fwd", "yes", 0.8,
        evidence=[Evidence(quote="M1(String) from A to B;", source="protocol"), Evidence(quote="ship the order", source="intent")],
    )
    ok, fabricated = verify_evidence(v, "module m; global protocol P(role A, role B) { M1(String) from A to B; }", "please ship the order")
    assert ok
    assert fabricated == []


def test_verify_evidence_catches_fabricated_quotes():
    v = make_verdict("s", "fwd", "yes", 0.8, evidence=[Evidence(quote="this never appears anywhere", source="protocol")])
    ok, fabricated = verify_evidence(v, "module m; global protocol P(role A, role B) { M1(String) from A to B; }", "intent text")
    assert not ok
    assert fabricated == ["this never appears anywhere"]


def test_verify_evidence_normalizes_whitespace_and_case():
    v = make_verdict("s", "fwd", "yes", 0.8, evidence=[Evidence(quote="M1(String)   FROM a TO b;", source="protocol")])
    ok, _ = verify_evidence(v, "module m; M1(String) from a to b;", "")
    assert ok


# ---------------------------------------------------------------------------
# Panel aggregation
# ---------------------------------------------------------------------------


def test_probe_veto_forces_reject_even_when_fwd_back_all_vote_yes():
    verdicts = [
        make_verdict("fwd1", "fwd", "yes", 0.95),
        make_verdict("fwd2", "fwd", "yes", 0.9),
        make_verdict("back1", "back", "yes", 0.9),
        make_verdict("probe", "probe", "no", 1.0),  # deterministic counterexample found
    ]
    result = aggregate_panel(verdicts)
    assert result.vetoed
    assert result.verdict == "reject"


def test_gray_zone_aggregate_escalates():
    verdicts = [
        make_verdict("fwd1", "fwd", "yes", 0.5),
        make_verdict("fwd2", "fwd", "no", 0.5),
    ]
    result = aggregate_panel(verdicts)
    assert ESCALATION_LOW <= result.aggregate_score <= ESCALATION_HIGH
    assert result.escalate
    assert "aggregate_in_gray_zone" in result.escalation_reasons
    assert result.verdict == "escalate"


def test_any_abstention_escalates():
    verdicts = [
        make_verdict("fwd1", "fwd", "yes", 0.95),
        make_verdict("fwd2", "fwd", "yes", 0.95),
        make_verdict("back1", "back", "abstain", 0.0),
    ]
    result = aggregate_panel(verdicts)
    assert result.escalate
    assert "abstention" in result.escalation_reasons
    assert result.abstentions[0].seat_id == "back1"


def test_clear_accept_when_no_veto_no_escalation():
    verdicts = [
        make_verdict("fwd1", "fwd", "yes", 0.95),
        make_verdict("fwd2", "fwd", "yes", 0.9),
        make_verdict("back1", "back", "yes", 0.92),
        make_verdict("probe", "probe", "yes", 1.0),
    ]
    result = aggregate_panel(verdicts)
    assert not result.vetoed
    assert not result.escalate
    assert result.verdict == "accept"


def test_clear_reject_when_low_score_no_probe():
    verdicts = [
        make_verdict("fwd1", "fwd", "no", 0.95),
        make_verdict("fwd2", "fwd", "no", 0.9),
    ]
    result = aggregate_panel(verdicts)
    assert result.verdict == "reject"
    assert not result.vetoed  # rejected on score, not on a probe veto


def test_probe_vote_conflict_flagged_when_panel_disagrees_with_probe():
    verdicts = [
        make_verdict("fwd1", "fwd", "yes", 0.95),
        make_verdict("fwd2", "fwd", "yes", 0.95),
        make_verdict("back1", "back", "yes", 0.95),
        make_verdict("probe", "probe", "no", 1.0),
    ]
    result = aggregate_panel(verdicts)
    assert "probe_vote_conflict" in result.escalation_reasons
    # still vetoed to reject: a deterministic counterexample outranks votes
    assert result.verdict == "reject"


def test_write_escalation_record_appends_jsonl(tmp_path):
    import json

    verdicts = [make_verdict("fwd1", "fwd", "abstain", 0.0)]
    result = aggregate_panel(verdicts)
    path = tmp_path / "escalations.jsonl"
    write_escalation_record(path, "case-001", result)
    write_escalation_record(path, "case-002", result)

    lines = path.read_text().strip().splitlines()
    assert len(lines) == 2
    rec = json.loads(lines[0])
    assert rec["case_id"] == "case-001"
    assert rec["escalate"] is True
