"""d2_backtranslate.py — mocked-client tests (no network, no API key
required; this is the "implement + unit-test with a mocked client" path
described in the module docstring and the W3 report)."""
from pathlib import Path

import d2_backtranslate as d2
from common import all_seeds
from signature import SignatureCache


CORPUS_000 = (Path(__file__).resolve().parents[4] / "experiments" / "cases"
             / "_corpus" / "corpus_000.scr")


def test_forbidden_vocab_filter():
    assert d2.forbidden_vocab_violations("please run this global protocol") != []
    assert d2.forbidden_vocab_violations("get the report reviewed and approved") == []


def test_mock_client_three_registers_differ():
    text = CORPUS_000.read_text(encoding="utf-8")
    client = d2.MockIntentClient()
    rows = d2.generate_intents_for_protocol(text, client, n_per_register=1)
    registers = {r["register"] for r in rows}
    assert registers == set(d2.REGISTERS)
    intents = {r["intent"] for r in rows}
    assert len(intents) == len(rows), "the three registers should read differently"


def test_build_end_to_end_mocked(tmp_path):
    seeds = all_seeds()[:3]
    client = d2.MockIntentClient()
    cache = SignatureCache(path=None)
    records, hard = d2.build([(s.seed_case, s.text) for s in seeds], client, cache,
                             n_per_register=1)
    assert records, "expected some (intent, protocol) pairs"
    for r in records:
        assert r.intent
        assert r.source == "synthetic"
        assert r.gen["operator"] == "backtranslate"
        assert r.gen["round_trip"]["status"] == "not_run"
        assert d2.forbidden_vocab_violations(r.intent) == []
    assert hard == []  # no translate_fn supplied -> nothing quarantined


def test_round_trip_probe_accepts_identity_translator():
    text = CORPUS_000.read_text(encoding="utf-8")
    result = d2.round_trip_probe("irrelevant intent text", text,
                                 translate_fn=lambda intent: text, best_of=1)
    assert result["accepted"] is True
    assert result["attempts"] == 1


def test_round_trip_probe_rejects_none_translator():
    text = CORPUS_000.read_text(encoding="utf-8")
    result = d2.round_trip_probe("irrelevant intent text", text,
                                 translate_fn=lambda intent: None, best_of=2)
    assert result["accepted"] is False
    assert result["attempts"] == 2
