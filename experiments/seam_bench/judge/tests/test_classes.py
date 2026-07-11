from __future__ import annotations

import json

import pytest

from experiments.seam_bench.judge.classes import (
    ProbeSpec,
    Probe,
    compile_probes_from_intent,
    evaluate_probe,
    reconstruct_intent,
    run_j_back,
    run_j_fwd,
    run_j_probe,
)
from experiments.seam_bench.judge.payloads import sanitize_protocol
from experiments.seam_bench.judge.seats import SeatConfig, default_panel
from experiments.seam_bench.judge.tests.conftest import MockAnthropic
from stjp_core.compiler.efsm_parser import parse_fsm_dot

FWD_SEAT = SeatConfig(seat_id="fwd-test", class_="fwd", model_id="m", temperature=0.3, rubric_emphasis="roles", paraphrase_slot=0)
BACK_SEAT = SeatConfig(seat_id="back-test", class_="back", model_id="m", temperature=0.3, rubric_emphasis="prohibitions")
PROBE_SEAT = SeatConfig(seat_id="probe", class_="probe", model_id="", temperature=0.0, rubric_emphasis="reachability")
COMPILER_SEAT = SeatConfig(seat_id="probe-compiler", class_="probe", model_id="m", temperature=0.0, rubric_emphasis="reachability")


def _good_verdict_json(quote_from_protocol="M1(String) from A to B;"):
    return json.dumps({
        "vote": "yes",
        "confidence": 0.85,
        "evidence": [{"quote": quote_from_protocol, "source": "protocol"}],
        "missing": [],
    })


# ---------------------------------------------------------------------------
# J-fwd
# ---------------------------------------------------------------------------


def test_j_fwd_paraphrases_then_judges_and_is_cache_pure_on_rerun(cache):
    payload = sanitize_protocol("module m;\nglobal protocol P(role A, role B) { M1(String) from A to B; }\n")

    def responder(kwargs):
        if "output_config" not in kwargs:
            return "a paraphrase of the intent"
        assert payload.text in kwargs["messages"][0]["content"]
        return _good_verdict_json()

    client = MockAnthropic(responder)
    v1 = run_j_fwd(client, cache, FWD_SEAT, "ship the widget from A to B", payload)
    calls_after_first = client.call_count
    v2 = run_j_fwd(client, cache, FWD_SEAT, "ship the widget from A to B", payload)

    assert v1.vote == "yes"
    assert v1.class_ == "fwd"
    assert client.call_count == calls_after_first, "rerun must be a pure cache hit (paraphrase + verdict both cached)"
    assert v2.vote == v1.vote


def test_j_fwd_never_sees_tools_or_a_session(cache):
    payload = sanitize_protocol("module m;\nglobal protocol P(role A, role B) { M1(String) from A to B; }\n")
    seen_kwargs = []

    def responder(kwargs):
        seen_kwargs.append(kwargs)
        return "paraphrase" if "output_config" not in kwargs else _good_verdict_json()

    client = MockAnthropic(responder)
    run_j_fwd(client, cache, FWD_SEAT, "intent", payload)
    for kwargs in seen_kwargs:
        assert "tools" not in kwargs
        assert "session" not in kwargs


def test_j_fwd_fabricated_evidence_is_resampled_then_recovers(cache):
    payload = sanitize_protocol("module m;\nglobal protocol P(role A, role B) { M1(String) from A to B; }\n")
    calls = {"structured": 0}

    def responder(kwargs):
        if "output_config" not in kwargs:
            return "paraphrase"
        calls["structured"] += 1
        if calls["structured"] == 1:
            return json.dumps({"vote": "yes", "confidence": 0.9, "evidence": [{"quote": "totally made up quote", "source": "protocol"}], "missing": []})
        return _good_verdict_json()

    client = MockAnthropic(responder)
    v = run_j_fwd(client, cache, FWD_SEAT, "intent", payload)
    assert calls["structured"] == 2, "first (fabricated) verdict must trigger exactly one resample"
    assert not v.discarded
    assert v.vote == "yes"


def test_j_fwd_double_fabrication_is_discarded(cache):
    payload = sanitize_protocol("module m;\nglobal protocol P(role A, role B) { M1(String) from A to B; }\n")

    def responder(kwargs):
        if "output_config" not in kwargs:
            return "paraphrase"
        return json.dumps({"vote": "yes", "confidence": 0.9, "evidence": [{"quote": "still made up", "source": "protocol"}], "missing": []})

    client = MockAnthropic(responder)
    v = run_j_fwd(client, cache, FWD_SEAT, "intent", payload)
    assert v.discarded
    assert "fabricated" in v.discard_reason


# ---------------------------------------------------------------------------
# J-back
# ---------------------------------------------------------------------------


def test_j_back_reconstruction_step_never_receives_the_original_intent(cache):
    payload = sanitize_protocol("module m;\nglobal protocol P(role A, role B) { M1(String) from A to B; }\n")
    secret_marker = "XYZZY_SECRET_ORIGINAL_INTENT_MARKER_12345"
    seen_prompts = []

    def responder(kwargs):
        seen_prompts.append(json.dumps(kwargs))
        return "reconstructed intent text, no secrets here"

    client = MockAnthropic(responder)
    # reconstruct_intent's signature has no `intent` parameter at all —
    # this call is what proves the isolation, not a docstring promise.
    reconstruct_intent(client, cache, BACK_SEAT, payload)
    for prompt in seen_prompts:
        assert secret_marker not in prompt


def test_j_back_full_flow_compares_reconstruction_to_original(cache):
    payload = sanitize_protocol("module m;\nglobal protocol P(role A, role B) { M1(String) from A to B; }\n")

    def responder(kwargs):
        if "output_config" not in kwargs:
            return "A sends a message to B."
        assert "ORIGINAL" in kwargs["messages"][0]["content"]
        assert "RECONSTRUCTION" in kwargs["messages"][0]["content"]
        return json.dumps({"vote": "yes", "confidence": 0.8, "evidence": [{"quote": "A sends a message to B.", "source": "intent"}], "missing": []})

    client = MockAnthropic(responder)
    v = run_j_back(client, cache, BACK_SEAT, "A should send B a message", payload)
    assert v.vote == "yes"
    assert v.class_ == "back"


def test_j_back_protocol_sourced_evidence_is_always_fabricated(cache):
    """The comparator never saw G — if it cites a "protocol" quote, that
    is definitionally fabricated, and the fabrication guard must catch it
    on every retry (not just flag it once)."""
    payload = sanitize_protocol("module m;\nglobal protocol P(role A, role B) { M1(String) from A to B; }\n")

    def responder(kwargs):
        if "output_config" not in kwargs:
            return "reconstruction text"
        return json.dumps({"vote": "yes", "confidence": 0.8, "evidence": [{"quote": "M1(String) from A to B;", "source": "protocol"}], "missing": []})

    client = MockAnthropic(responder)
    v = run_j_back(client, cache, BACK_SEAT, "intent", payload)
    assert v.discarded


# ---------------------------------------------------------------------------
# J-probe — deterministic checker (offline, hand-built EFSMs; no Scribble needed)
# ---------------------------------------------------------------------------

APPROVE_FSM_DOT = '''
"0" [label="0: "];
"1" [label="1: "];
"2" [label="2: "];
"0" -> "1" [ label="Buyer?Request(String)" ];
"1" -> "2" [ label="Buyer!Approve(Bool)" ];
'''

REJECT_NO_NOTIFY_DOT = '''
"0" [label="0: "];
"1" [label="1: "];
"0" -> "1" [ label="Buyer?Reject(String)" ];
'''

REJECT_WITH_NOTIFY_DOT = '''
"0" [label="0: "];
"1" [label="1: "];
"2" [label="2: "];
"0" -> "1" [ label="Buyer?Reject(String)" ];
"1" -> "2" [ label="Customer!Notify(String)" ];
'''


def test_evaluate_probe_reachable_and_never():
    efsm = parse_fsm_dot(APPROVE_FSM_DOT, role="Seller")
    reachable_probe = Probe("can Seller approve?", ProbeSpec(kind="reachable", role="Seller", label="Approve", direction="send", peer="Buyer"))
    result = evaluate_probe({"Seller": efsm}, reachable_probe)
    assert result.passed

    never_probe = Probe("Seller must never reject", ProbeSpec(kind="never", role="Seller", label="Reject", direction="send", peer="Buyer"))
    result2 = evaluate_probe({"Seller": efsm}, never_probe)
    assert result2.passed  # Reject never appears in this EFSM


def test_evaluate_probe_never_fails_when_prohibited_label_reachable():
    efsm = parse_fsm_dot(APPROVE_FSM_DOT, role="Seller")
    never_probe = Probe("Seller must never approve", ProbeSpec(kind="never", role="Seller", label="Approve", direction="send", peer="Buyer"))
    result = evaluate_probe({"Seller": efsm}, never_probe)
    assert not result.passed


def test_evaluate_probe_response_passes_when_notification_follows():
    efsm = parse_fsm_dot(REJECT_WITH_NOTIFY_DOT, role="Seller")
    probe = Probe(
        "every rejection ends in a customer notification",
        ProbeSpec(
            kind="response", role="Seller", label="Reject", direction="receive", peer="Buyer",
            response_role="Seller", response_label="Notify", response_direction="send", response_peer="Customer",
        ),
    )
    result = evaluate_probe({"Seller": efsm}, probe)
    assert result.passed


def test_evaluate_probe_response_fails_with_counterexample_when_notification_missing():
    efsm = parse_fsm_dot(REJECT_NO_NOTIFY_DOT, role="Seller")
    probe = Probe(
        "every rejection ends in a customer notification",
        ProbeSpec(
            kind="response", role="Seller", label="Reject", direction="receive", peer="Buyer",
            response_role="Seller", response_label="Notify", response_direction="send", response_peer="Customer",
        ),
    )
    result = evaluate_probe({"Seller": efsm}, probe)
    assert not result.passed
    assert result.counterexample  # a concrete deterministic trace, not an LLM opinion
    assert "Buyer?Reject" in result.counterexample[0]


def test_evaluate_probe_unknown_role_fails_loudly():
    efsm = parse_fsm_dot(APPROVE_FSM_DOT, role="Seller")
    probe = Probe("bogus", ProbeSpec(kind="reachable", role="Nonexistent", label="X", direction="send"))
    result = evaluate_probe({"Seller": efsm}, probe)
    assert not result.passed


# ---------------------------------------------------------------------------
# J-probe — LLM-compiled queries grounded to real vocabulary, then evaluated
# ---------------------------------------------------------------------------


def test_compile_probes_from_intent_drops_ungrounded_probes(cache):
    def responder(kwargs):
        return json.dumps({
            "probes": [
                {
                    "query_text": "can Seller approve the request?",
                    "kind": "reachable", "role": "Seller", "label": "Approve", "direction": "send", "peer": "Buyer",
                    "response_role": "", "response_label": "", "response_direction": "", "response_peer": "",
                },
                {
                    # hallucinated role/label not in the allowed vocabulary — must be dropped
                    "query_text": "does the Auditor sign off?",
                    "kind": "reachable", "role": "Auditor", "label": "SignOff", "direction": "send", "peer": "Seller",
                    "response_role": "", "response_label": "", "response_direction": "", "response_peer": "",
                },
            ],
        })

    client = MockAnthropic(responder)
    probes = compile_probes_from_intent(client, cache, COMPILER_SEAT, "intent", ["Seller", "Buyer"], ["Approve", "Reject"])
    assert len(probes) == 1
    assert probes[0].compiled_check.role == "Seller"


def test_compile_probes_from_intent_never_receives_the_protocol_text(cache):
    secret_marker = "SUPER_SECRET_PROTOCOL_BODY_MARKER"

    def responder(kwargs):
        assert secret_marker not in json.dumps(kwargs)
        return json.dumps({"probes": []})

    client = MockAnthropic(responder)
    compile_probes_from_intent(client, cache, COMPILER_SEAT, "intent mentioning nothing secret", ["Seller"], ["Approve"])


def test_run_j_probe_vetoes_on_a_failed_deterministic_check(cache):
    efsm = parse_fsm_dot(REJECT_NO_NOTIFY_DOT, role="Seller")
    # message_labels must include "Notify" too so the compiled probe's
    # response half survives grounding against the allowed vocabulary.
    payload = sanitize_protocol(
        "module m;\nglobal protocol P(role Seller, role Buyer, role Customer) {\n"
        "  Reject(String) from Buyer to Seller;\n"
        "  Notify(String) from Seller to Customer;\n"
        "}\n"
    )

    def responder(kwargs):
        return json.dumps({
            "probes": [{
                "query_text": "every rejection must notify the customer",
                "kind": "response", "role": "Seller", "label": "Reject", "direction": "receive", "peer": "Buyer",
                "response_role": "Seller", "response_label": "Notify", "response_direction": "send", "response_peer": "Customer",
            }],
        })

    client = MockAnthropic(responder)
    verdict, results = run_j_probe(client, cache, PROBE_SEAT, COMPILER_SEAT, "intent", payload, {"Seller": efsm})
    assert verdict.vote == "no"
    assert verdict.class_ == "probe"
    assert verdict.confidence == 1.0
    assert not results[0].passed


def test_run_j_probe_abstains_when_nothing_compiles(cache):
    payload = sanitize_protocol("module m;\nglobal protocol P(role A, role B) { M1(String) from A to B; }\n")
    client = MockAnthropic(lambda kwargs: json.dumps({"probes": []}))
    verdict, results = run_j_probe(client, cache, PROBE_SEAT, COMPILER_SEAT, "intent", payload, {})
    assert verdict.vote == "abstain"
    assert results == []


# ---------------------------------------------------------------------------
# One worked example against the REAL Scribble toolchain (skipped if absent)
# ---------------------------------------------------------------------------


def test_build_efsms_from_source_real_toolchain_worked_example(corpus_000):
    from stjp_core.config import SCRIBBLE_PATH
    from experiments.seam_bench.judge.classes import build_efsms_from_source

    if not SCRIBBLE_PATH.exists():
        pytest.skip("real Scribble toolchain not installed in this environment")

    efsms = build_efsms_from_source(corpus_000, "Gen", ["R0", "R1", "R2", "R3"])
    assert set(efsms) == {"R0", "R1", "R2", "R3"}
    r0 = efsms["R0"]
    assert r0.transitions, "R0's EFSM must have at least one real transition from the real Scribble compiler"

    # A concrete, grounded probe against the real EFSM: R0 sends M1 to R1.
    probe = Probe("does R0 send M1 to R1?", ProbeSpec(kind="reachable", role="R0", label="M1", direction="send", peer="R1"))
    result = evaluate_probe(efsms, probe)
    assert result.passed
