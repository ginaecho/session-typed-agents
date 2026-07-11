from __future__ import annotations

import json

from experiments.seam_bench.judge.seats import (
    VERDICT_SCHEMA,
    call_structured,
    call_text,
    default_panel,
    verdict_from_raw,
)
from experiments.seam_bench.judge.tests.conftest import MockAnthropic


def test_default_panel_matches_plan_v2_1_spec():
    panel = default_panel()
    classes = [s.class_ for s in panel]
    assert classes.count("fwd") == 2
    assert classes.count("back") == 2
    assert classes.count("probe") == 1

    fwd_models = {s.model_id for s in panel if s.class_ == "fwd"}
    assert fwd_models == {"claude-opus-4-8", "claude-sonnet-5"}

    fwd_slots = {s.paraphrase_slot for s in panel if s.class_ == "fwd"}
    assert fwd_slots == {0, 1}, "fwd seats must get distinct paraphrase slots"

    temps = {s.temperature for s in panel if s.class_ in ("fwd", "back")}
    assert temps <= {0.3, 0.7}

    rubric_emphases = {s.rubric_emphasis for s in panel if s.class_ in ("fwd", "back")}
    assert rubric_emphases == {"roles", "ordering", "prohibitions", "termination"}


def test_call_structured_is_one_stateless_call_no_tools_no_session():
    def responder(kwargs):
        assert "tools" not in kwargs
        assert "tool_choice" not in kwargs
        assert kwargs["output_config"]["format"]["type"] == "json_schema"
        return json.dumps({"vote": "yes", "confidence": 0.8, "evidence": [], "missing": []})

    client = MockAnthropic(responder)
    data = call_structured(client, "claude-opus-4-8", 0.3, "system", "user", VERDICT_SCHEMA, max_tokens=256)
    assert data["vote"] == "yes"
    assert client.call_count == 1
    assert client.messages.calls[0]["max_tokens"] == 256
    assert client.messages.calls[0]["model"] == "claude-opus-4-8"


def test_call_text_returns_plain_text():
    client = MockAnthropic(lambda kwargs: "a paraphrase")
    text = call_text(client, "claude-sonnet-5", 0.7, "sys", "usr")
    assert text == "a paraphrase"


def test_verdict_from_raw_clamps_confidence():
    from experiments.seam_bench.judge.seats import SeatConfig

    seat = SeatConfig(seat_id="s", class_="fwd", model_id="m", temperature=0.3, rubric_emphasis="roles")
    v = verdict_from_raw({"vote": "no", "confidence": 5.0, "evidence": [], "missing": []}, seat)
    assert v.confidence == 1.0
    v2 = verdict_from_raw({"vote": "no", "confidence": -3.0, "evidence": [], "missing": []}, seat)
    assert v2.confidence == 0.0
