from __future__ import annotations

import json

from experiments.intent_loop import mockdata
from experiments.intent_loop.faithfulness import (back_translate,
                                                  evaluate_faithfulness)
from experiments.intent_loop.llm import MockChat
from experiments.intent_loop.schema import DistilledIntent


def _distilled() -> DistilledIntent:
    raw = json.loads(mockdata.INTERROGATOR_DONE)["distilled"]
    return DistilledIntent.from_dict(raw)


def test_faithful_episode_aggregates_true():
    llm = MockChat(mockdata.EVAL_SCRIPT)
    report = evaluate_faithfulness(llm, _distilled(), mockdata.FIXED_DRAFT)
    assert report.recall == 1.0
    assert report.ungrounded == []
    assert report.backtranslation["score"] == 92
    assert report.faithful
    assert report.gold_equivalent is None


def test_missing_requirement_fails_verdict():
    coverage = json.loads(mockdata.COVERAGE_REPLY)
    coverage["verdicts"] = coverage["verdicts"][:-1]  # drop R5's verdict
    llm = MockChat([json.dumps(coverage), mockdata.BACKTRANSLATION_REPLY,
                    mockdata.COMPARE_REPLY])
    report = evaluate_faithfulness(llm, _distilled(), mockdata.FIXED_DRAFT)
    # Unverdicted requirement counts as a miss, never a free pass.
    r5 = next(v for v in report.coverage if v.rid == "R5")
    assert r5.covered == "no"
    assert report.recall == 0.8
    assert not report.faithful


def test_low_backtranslation_score_fails_verdict():
    llm = MockChat([mockdata.COVERAGE_REPLY, mockdata.BACKTRANSLATION_REPLY,
                    json.dumps({"score": 40, "missing": ["the audit rule"],
                                "added": []})])
    report = evaluate_faithfulness(llm, _distilled(), mockdata.FIXED_DRAFT)
    assert report.recall == 1.0
    assert not report.faithful


def test_back_translator_never_sees_the_intent():
    llm = MockChat([mockdata.BACKTRANSLATION_REPLY])
    back_translate(llm, mockdata.FIXED_DRAFT)
    stage, system, user = llm.calls[0]
    assert stage == "backtranslate"
    combined = system + user
    # The intent/mission text must be absent from everything the
    # back-translator was shown (the J-back isolation property).
    assert "quarterly report workflow" not in combined.lower()
    assert "mission" not in combined.lower()


def test_gold_equivalence_uses_injected_bisim():
    calls = []
    def fake_bisim(a, b):
        calls.append((a, b))
        return True, "structurally equivalent"
    llm = MockChat(mockdata.EVAL_SCRIPT)
    report = evaluate_faithfulness(llm, _distilled(), mockdata.FIXED_DRAFT,
                                   gold_protocol="gold text",
                                   bisim_fn=fake_bisim)
    assert report.gold_equivalent is True
    assert calls == [(mockdata.FIXED_DRAFT, "gold text")]
