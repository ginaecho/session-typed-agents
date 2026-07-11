"""Collusion/degeneration audits — plan v2.1 §5.5.

Runs entirely against an injected (mockable) client so the whole battery
executes in CI without hitting the real API:

- swapped pairs: intent_A with G_B must be rejected
- gold-vs-mutant separation: a behavior-changing mutant must score lower
  than gold
- duplicate probes: same payload, different seed — measures per-seat
  self-consistency
- rationale-overlap alarm: pairwise 5-gram Jaccard across the panel's
  free-text fields; identical votes are fine, verbatim rationale is not
- effective independent votes: estimated from canary inter-seat
  correlation (a panel whose effective count drops below 3 must
  diversify seats, not add more of the same)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from experiments.seam_bench.judge.aggregate import seat_score
from experiments.seam_bench.judge.seats import SeatConfig, Verdict

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def ngram_jaccard(text_a: str, text_b: str, n: int = 5) -> float:
    """Pairwise n-gram Jaccard similarity over free text — the direct
    guard against "they all say the same judgment" *verbatim*. Honest
    agreement on the vote is fine; identical phrasing in the rationale is
    the collusion signature."""
    toks_a = _tokens(text_a)
    toks_b = _tokens(text_b)
    if len(toks_a) < n or len(toks_b) < n:
        return 0.0
    grams_a = {tuple(toks_a[i:i + n]) for i in range(len(toks_a) - n + 1)}
    grams_b = {tuple(toks_b[i:i + n]) for i in range(len(toks_b) - n + 1)}
    union = grams_a | grams_b
    if not union:
        return 0.0
    return len(grams_a & grams_b) / len(union)


def verdict_free_text(v: Verdict) -> str:
    return " ".join([e.quote for e in v.evidence] + list(v.missing))


@dataclass
class RationaleOverlapAlarm:
    triggered: bool
    max_overlap: float
    offending_pair: tuple[str, str] | None = None


def rationale_overlap_alarm(verdicts: list[Verdict], threshold: float = 0.6, n: int = 5) -> RationaleOverlapAlarm:
    max_overlap = 0.0
    offending: tuple[str, str] | None = None
    for i in range(len(verdicts)):
        for j in range(i + 1, len(verdicts)):
            a, b = verdicts[i], verdicts[j]
            overlap = ngram_jaccard(verdict_free_text(a), verdict_free_text(b), n=n)
            if overlap > max_overlap:
                max_overlap = overlap
                offending = (a.seat_id, b.seat_id)
    return RationaleOverlapAlarm(triggered=max_overlap > threshold, max_overlap=max_overlap, offending_pair=offending)


# ---------------------------------------------------------------------------
# Effective independent votes (canary inter-seat correlation)
# ---------------------------------------------------------------------------


def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    denom = (var_x * var_y) ** 0.5
    if denom == 0:
        return 0.0
    return cov / denom


def effective_independent_votes(vote_matrix: list[list[float]]) -> float:
    """vote_matrix[i] is one canary item's per-seat scalar scores
    (seat_score), same seat order every row. Returns an "effective sample
    size" style estimate: k seats with average pairwise correlation r
    behave like k / (1 + (k-1)*r) independent votes — the standard
    design-effect correction, and exactly the quantity R1's scouting used
    to describe "a 9-judge panel can carry ~2 effective votes"."""
    if not vote_matrix or not vote_matrix[0]:
        return 0.0
    k = len(vote_matrix[0])
    if k <= 1:
        return float(k)
    columns = [[row[i] for row in vote_matrix] for i in range(k)]
    correlations = []
    for i in range(k):
        for j in range(i + 1, k):
            correlations.append(_pearson(columns[i], columns[j]))
    avg_r = sum(correlations) / len(correlations) if correlations else 0.0
    avg_r = max(-1.0, min(1.0, avg_r))
    denom = 1 + (k - 1) * avg_r
    if denom <= 0:
        return float(k)  # fully anti-correlated seats — treat as fully independent, not undefined
    return k / denom


# ---------------------------------------------------------------------------
# Canary battery
# ---------------------------------------------------------------------------


@dataclass
class CanaryCheckResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class CanaryReport:
    checks: list[CanaryCheckResult] = field(default_factory=list)
    effective_votes: float | None = None
    rationale_alarm: RationaleOverlapAlarm | None = None

    @property
    def all_passed(self) -> bool:
        return all(c.passed for c in self.checks)

    def to_dict(self) -> dict:
        return {
            "checks": [{"name": c.name, "passed": c.passed, "detail": c.detail} for c in self.checks],
            "effective_votes": self.effective_votes,
            "rationale_alarm": None if self.rationale_alarm is None else {
                "triggered": self.rationale_alarm.triggered,
                "max_overlap": self.rationale_alarm.max_overlap,
                "offending_pair": self.rationale_alarm.offending_pair,
            },
        }


def check_swapped_pair(judge_fn: Callable[[str, str], Verdict], intent_a: str, protocol_b: str) -> CanaryCheckResult:
    """intent_A judged against G_B (an unrelated protocol) must be
    rejected. A seat that accepts a mismatched pair is leniency-broken."""
    verdict = judge_fn(intent_a, protocol_b)
    score = seat_score(verdict)
    rejected = score is not None and score < 0.5
    return CanaryCheckResult(
        name="swapped_pair",
        passed=rejected,
        detail=f"vote={verdict.vote} confidence={verdict.confidence} score={score}",
    )


def check_gold_vs_mutant(
    judge_fn: Callable[[str, str], Verdict], intent: str, gold_protocol: str, mutant_protocol: str
) -> CanaryCheckResult:
    """Gold vs a behavior-changing mutant must separate: gold scores
    higher than the mutant."""
    gold_verdict = judge_fn(intent, gold_protocol)
    mutant_verdict = judge_fn(intent, mutant_protocol)
    gold_score = seat_score(gold_verdict)
    mutant_score = seat_score(mutant_verdict)
    if gold_score is None or mutant_score is None:
        return CanaryCheckResult(name="gold_vs_mutant", passed=False, detail="abstention on a canary item")
    separated = gold_score > mutant_score
    return CanaryCheckResult(
        name="gold_vs_mutant",
        passed=separated,
        detail=f"gold_score={gold_score} mutant_score={mutant_score}",
    )


def check_duplicate_self_consistency(
    judge_fn: Callable[[str, str], Verdict], intent: str, protocol: str, n_repeats: int = 3, min_consistency: float = 0.66
) -> CanaryCheckResult:
    """Same payload judged n_repeats times (mock varies the "seed" via
    call count) — measures whether a seat is stable on its own output."""
    votes = [judge_fn(intent, protocol).vote for _ in range(n_repeats)]
    most_common = max(set(votes), key=votes.count)
    consistency = votes.count(most_common) / len(votes)
    return CanaryCheckResult(
        name="duplicate_self_consistency",
        passed=consistency >= min_consistency,
        detail=f"votes={votes} consistency={consistency:.2f}",
    )


def naive_behavior_changing_mutation(sanitized_text: str) -> str:
    """A minimal textual mutation for canary purposes only (swap the
    first two message senders) — NOT a Scribble-validity-preserving
    mutation and not a substitute for D3's real mutation operators
    (integration_stress.py::s2_mutation). Good enough to give judges a
    behavior-changing decoy without re-running the real validator."""
    pattern = re.compile(r"(\w+)\((.*?)\) from (\w+) to (\w+);")
    matches = list(pattern.finditer(sanitized_text))
    if len(matches) < 2:
        return sanitized_text
    m0, m1 = matches[0], matches[1]
    mutated = sanitized_text[: m0.start()]
    mutated += f"{m0.group(1)}({m0.group(2)}) from {m0.group(4)} to {m0.group(3)};"
    mutated += sanitized_text[m0.end():m1.start()]
    mutated += f"{m1.group(1)}({m1.group(2)}) from {m1.group(4)} to {m1.group(3)};"
    mutated += sanitized_text[m1.end():]
    return mutated


def run_canary_battery(
    judge_fn: Callable[[str, str], Verdict],
    seats: list[SeatConfig],
    cases: list[tuple[str, str]],
    verdicts_for_overlap: list[Verdict] | None = None,
) -> CanaryReport:
    """Run the full §5.5 battery in CI mode. ``judge_fn(intent, protocol)
    -> Verdict`` is caller-supplied so the same battery runs against a
    single seat, a full panel aggregate, or (in tests) an entirely mocked
    scorer with no network calls at all.

    ``cases`` is a list of (intent, sanitized_protocol_text) pairs drawn
    from at least two independent protocols, used to build swapped pairs
    and mutants.
    """
    report = CanaryReport()
    if len(cases) < 2:
        report.checks.append(CanaryCheckResult(name="battery_setup", passed=False, detail="need >=2 cases"))
        return report

    (intent_a, protocol_a), (intent_b, protocol_b) = cases[0], cases[1]

    report.checks.append(check_swapped_pair(judge_fn, intent_a, protocol_b))

    mutant_a = naive_behavior_changing_mutation(protocol_a)
    report.checks.append(check_gold_vs_mutant(judge_fn, intent_a, protocol_a, mutant_a))

    report.checks.append(check_duplicate_self_consistency(judge_fn, intent_a, protocol_a))

    vote_matrix: list[list[float]] = []
    for intent, protocol in cases:
        row = []
        for seat in seats:
            v = judge_fn(intent, protocol)
            score = seat_score(v)
            row.append(0.5 if score is None else score)
        vote_matrix.append(row)
    if len(seats) > 1:
        report.effective_votes = effective_independent_votes(vote_matrix)

    if verdicts_for_overlap:
        report.rationale_alarm = rationale_overlap_alarm(verdicts_for_overlap)

    return report
