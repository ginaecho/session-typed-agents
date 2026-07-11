from __future__ import annotations

from experiments.seam_bench.judge.canaries import (
    effective_independent_votes,
    naive_behavior_changing_mutation,
    ngram_jaccard,
    rationale_overlap_alarm,
    run_canary_battery,
)
from experiments.seam_bench.judge.payloads import sanitize_protocol
from experiments.seam_bench.judge.seats import Evidence, Verdict, default_panel


def make_verdict(seat_id, evidence_text, vote="yes", confidence=0.9):
    return Verdict(
        vote=vote, confidence=confidence,
        evidence=[Evidence(quote=evidence_text, source="protocol")], missing=[],
        seat_id=seat_id, class_="fwd", model_id="m", temperature=0.3,
    )


def test_ngram_jaccard_identical_text_is_one():
    text = "the roles are Buyer and Seller and they exchange three messages in order"
    assert ngram_jaccard(text, text) == 1.0


def test_ngram_jaccard_disjoint_text_is_zero():
    a = "the roles are Buyer and Seller exchanging an order confirmation"
    b = "completely unrelated sentence about weather forecasts in Tokyo today"
    assert ngram_jaccard(a, b) == 0.0


def test_ngram_jaccard_short_text_is_zero_not_error():
    assert ngram_jaccard("short", "text") == 0.0


def test_rationale_overlap_alarm_triggers_on_verbatim_rationale():
    verdicts = [
        make_verdict("s1", "the protocol correctly routes every rejected order back to the customer immediately"),
        make_verdict("s2", "the protocol correctly routes every rejected order back to the customer immediately"),
    ]
    alarm = rationale_overlap_alarm(verdicts, threshold=0.5)
    assert alarm.triggered
    assert alarm.max_overlap == 1.0


def test_rationale_overlap_alarm_does_not_trigger_on_agreeing_but_differently_worded_rationale():
    verdicts = [
        make_verdict("s1", "Buyer sends Order then Seller replies with Confirm in strict sequence"),
        make_verdict("s2", "Seller only issues Confirm once Buyer has already transmitted an Order message"),
    ]
    alarm = rationale_overlap_alarm(verdicts, threshold=0.5)
    assert not alarm.triggered


def test_effective_votes_near_k_for_independent_seats():
    # Four seats whose scores vary in an uncorrelated pattern across items.
    vote_matrix = [
        [0.9, 0.1, 0.9, 0.1],
        [0.1, 0.9, 0.1, 0.9],
        [0.9, 0.9, 0.1, 0.1],
        [0.1, 0.1, 0.9, 0.9],
        [0.9, 0.1, 0.1, 0.9],
        [0.1, 0.9, 0.9, 0.1],
    ]
    votes = effective_independent_votes(vote_matrix)
    assert votes > 3.0, "near-uncorrelated seats should carry close to k=4 effective votes"


def test_effective_votes_near_one_for_identical_seats():
    # A 9-seat panel that all move in lockstep — R1's "9 judges, ~2
    # effective votes" finding, taken to its extreme (perfect correlation).
    vote_matrix = [[s] * 9 for s in [0.9, 0.2, 0.8, 0.1, 0.95, 0.3]]
    votes = effective_independent_votes(vote_matrix)
    assert votes < 2.0, "perfectly-correlated seats must not be counted as independent"


def test_naive_mutation_swaps_first_two_message_directions():
    payload = sanitize_protocol("module m;\nglobal protocol P(role A, role B) { M1(String) from A to B; M2(String) from A to B; }\n")
    mutant = naive_behavior_changing_mutation(payload.text)
    assert mutant != payload.text
    assert "from B to A" in mutant


def test_run_canary_battery_end_to_end_mocked_judge_reports_effective_votes(corpus_000, corpus_001):
    payload_a = sanitize_protocol(corpus_000)
    payload_b = sanitize_protocol(corpus_001)
    panel = default_panel()

    def mocked_judge_fn(intent, protocol_text):
        """A fully deterministic mock scorer: high score only for the
        exact pristine gold pairing — this is exactly what a real panel
        is supposed to do (reject swapped pairs, separate gold from
        mutants) without any network call."""
        is_gold = intent == payload_a.protocol_name and protocol_text == payload_a.text
        vote = "yes" if is_gold else "no"
        return make_verdict("mock-seat", protocol_text[:40], vote=vote, confidence=0.9)

    cases = [
        (payload_a.protocol_name, payload_a.text),  # intent_a = "Gen", found in its own G
        (payload_b.protocol_name, payload_b.text),  # intent_b = "Nego"
    ]

    report = run_canary_battery(mocked_judge_fn, panel, cases)
    by_name = {c.name: c for c in report.checks}

    assert by_name["swapped_pair"].passed, "intent_A judged against G_B must be rejected"
    assert by_name["gold_vs_mutant"].passed, "gold must separate from a behavior-changing mutant"
    assert by_name["duplicate_self_consistency"].passed
    assert report.effective_votes is not None
    assert report.effective_votes > 0
