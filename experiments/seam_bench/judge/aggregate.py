"""Deterministic aggregation — plan v2.1 §5.3/§5.5.

"No LLM anywhere in aggregation." Everything in this module is plain
Python operating on already-produced ``Verdict`` objects:

- per-seat calibration weights (config, default 1.0 — carried on
  ``Verdict.weight``, set from ``SeatConfig.weight``)
- geometric-median aggregation over seat scores (Weiszfeld's algorithm,
  no numpy/scipy)
- J-probe failures veto regardless of vote share
- abstentions route out with dissent attached
- evidence verification (the lie-detector): every evidence quote must
  string-match the payload after normalization, or the verdict is
  discarded
- the escalation rule (aggregate in [0.4, 0.6], probe-vote conflict, or
  any abstention) emits a JSONL record for the human gate
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from experiments.seam_bench.judge.seats import Verdict


# ---------------------------------------------------------------------------
# Evidence verification (§5.4 lie detector)
# ---------------------------------------------------------------------------

_WHITESPACE_RE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip().lower()


def verify_evidence(verdict: Verdict, protocol_text: str, intent_text: str) -> tuple[bool, list[str]]:
    """Check every evidence quote actually occurs in its claimed source
    (string match after whitespace/case normalization). Returns
    (all_verified, [fabricated_quotes]).

    J-probe verdicts carry deterministic trace/counterexample "evidence",
    not LLM-authored prose quoted from the payload — they are exempt from
    this check by construction (there is nothing for them to hallucinate;
    the counterexample IS the computation). Callers should only invoke
    this for J-fwd / J-back verdicts.
    """
    norm_protocol = _normalize(protocol_text)
    norm_intent = _normalize(intent_text)
    fabricated: list[str] = []
    for item in verdict.evidence:
        haystack = norm_protocol if item.source == "protocol" else norm_intent
        if _normalize(item.quote) not in haystack:
            fabricated.append(item.quote)
    return (len(fabricated) == 0, fabricated)


# ---------------------------------------------------------------------------
# Geometric median (Weiszfeld's algorithm) — dependency-free, arbitrary dim
# ---------------------------------------------------------------------------


def weiszfeld(points: list[tuple[float, ...]], weights: list[float], max_iter: int = 200, tol: float = 1e-9) -> tuple[float, ...]:
    """Weighted geometric median via Weiszfeld's algorithm. Works for any
    dimension; we use it in 1-D (scalar per-seat scores), where it
    converges to the weighted median — the tuning-free robust aggregate
    the plan calls for (arithmetic vote-share has unbounded bias under a
    single biased judge; the geometric median does not)."""
    if not points:
        raise ValueError("weiszfeld requires at least one point")
    if len(points) == 1:
        return points[0]

    dim = len(points[0])
    total_w = sum(weights)
    guess = tuple(sum(w * p[d] for w, p in zip(weights, points)) / total_w for d in range(dim))

    for _ in range(max_iter):
        num = [0.0] * dim
        den = 0.0
        exact_hit: tuple[float, ...] | None = None
        for w, p in zip(weights, points):
            dist = math.sqrt(sum((p[d] - guess[d]) ** 2 for d in range(dim)))
            if dist < 1e-12:
                exact_hit = p
                continue
            inv = w / dist
            for d in range(dim):
                num[d] += p[d] * inv
            den += inv
        if den == 0.0:
            return exact_hit if exact_hit is not None else guess
        new_guess = tuple(num[d] / den for d in range(dim))
        shift = math.sqrt(sum((new_guess[d] - guess[d]) ** 2 for d in range(dim)))
        guess = new_guess
        if shift < tol:
            break
    return guess


def seat_score(verdict: Verdict) -> float | None:
    """Map a verdict to a scalar "faithfulness" score in [0, 1].
    Abstentions have no score (they route to escalation, not aggregation)."""
    if verdict.vote == "yes":
        return verdict.confidence
    if verdict.vote == "no":
        return 1.0 - verdict.confidence
    return None  # abstain


def geometric_median_score(verdicts: Iterable[Verdict]) -> float | None:
    scored = [(v, seat_score(v)) for v in verdicts if not v.discarded]
    points = [(s,) for v, s in scored if s is not None]
    weights = [v.weight for v, s in scored if s is not None]
    if not points:
        return None
    return weiszfeld(points, weights)[0]


# ---------------------------------------------------------------------------
# Panel-level aggregation
# ---------------------------------------------------------------------------


@dataclass
class PanelResult:
    aggregate_score: float | None
    verdict: str  # "accept" | "reject" | "escalate"
    vetoed: bool
    probe_verdicts: list[Verdict]
    voting_verdicts: list[Verdict]
    abstentions: list[Verdict]
    discarded: list[Verdict]
    escalate: bool
    escalation_reasons: list[str]

    def to_dict(self) -> dict:
        return {
            "aggregate_score": self.aggregate_score,
            "verdict": self.verdict,
            "vetoed": self.vetoed,
            "probe_verdicts": [v.to_dict() for v in self.probe_verdicts],
            "voting_verdicts": [v.to_dict() for v in self.voting_verdicts],
            "abstentions": [v.to_dict() for v in self.abstentions],
            "discarded": [v.to_dict() for v in self.discarded],
            "escalate": self.escalate,
            "escalation_reasons": self.escalation_reasons,
        }


ESCALATION_LOW = 0.4
ESCALATION_HIGH = 0.6


def aggregate_panel(verdicts: list[Verdict]) -> PanelResult:
    probe_verdicts = [v for v in verdicts if v.class_ == "probe"]
    other_verdicts = [v for v in verdicts if v.class_ != "probe"]

    discarded = [v for v in other_verdicts if v.discarded]
    live = [v for v in other_verdicts if not v.discarded]
    abstentions = [v for v in live if v.vote == "abstain"]
    voting_verdicts = [v for v in live if v.vote != "abstain"]

    aggregate_score = geometric_median_score(voting_verdicts)

    probe_failed = any(v.vote == "no" for v in probe_verdicts)
    probe_passed = any(v.vote == "yes" for v in probe_verdicts) and not probe_failed

    escalation_reasons: list[str] = []

    if abstentions:
        escalation_reasons.append("abstention")

    probe_vote_conflict = False
    if aggregate_score is not None:
        if probe_failed and aggregate_score >= ESCALATION_HIGH:
            probe_vote_conflict = True
        elif probe_passed and aggregate_score <= ESCALATION_LOW:
            probe_vote_conflict = True
    if probe_vote_conflict:
        escalation_reasons.append("probe_vote_conflict")

    if aggregate_score is not None and ESCALATION_LOW <= aggregate_score <= ESCALATION_HIGH:
        escalation_reasons.append("aggregate_in_gray_zone")

    escalate = len(escalation_reasons) > 0

    if probe_failed:
        verdict = "reject"
    elif escalate:
        verdict = "escalate"
    elif aggregate_score is not None and aggregate_score > ESCALATION_HIGH:
        verdict = "accept"
    elif aggregate_score is not None and aggregate_score < ESCALATION_LOW:
        verdict = "reject"
    else:
        # No voting verdicts at all (e.g. everything abstained/discarded).
        verdict = "escalate"
        if "no_voting_verdicts" not in escalation_reasons:
            escalation_reasons.append("no_voting_verdicts")
        escalate = True

    return PanelResult(
        aggregate_score=aggregate_score,
        verdict=verdict,
        vetoed=probe_failed,
        probe_verdicts=probe_verdicts,
        voting_verdicts=voting_verdicts,
        abstentions=abstentions,
        discarded=discarded,
        escalate=escalate,
        escalation_reasons=escalation_reasons,
    )


def write_escalation_record(path: str | Path, case_id: str, result: PanelResult) -> None:
    """Append one JSONL record for the human gate (§5.3 escalation tier).

    Per plan §5.3, a stateless Fable-5 seat + a planner-written analysis
    are routed WITH the case to the human, but the planner's analysis is
    advisory and never a counted vote — this function only ever writes
    the panel's own deterministic output; nothing here fabricates or
    stands in for that advisory layer.
    """
    record = {"case_id": case_id, **result.to_dict()}
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")
