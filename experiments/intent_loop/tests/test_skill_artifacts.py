from experiments.intent_loop.skill import build_agent_markdown, build_skill


def _record() -> dict:
    return {
        "episode_id": "reviewed",
        "valid": True,
        "distilled": {
            "mission": "Deliver an approved report.",
            "roles": [
                {"name": "Analyst", "description": "prepares the report"},
                {"name": "Requester", "description": "receives it"}],
            "interactions": [{
                "iid": "I1", "sender": "Analyst", "receiver": "Requester",
                "what": "final report", "waits_for": [],
                "carries": [{"name": "report", "type": "string",
                             "constraint": "non-empty"}]}],
            "completion_signal": "Requester receives the report."},
        "faithfulness": {"scope": {"ranking": {
            "overall_coverage_pct": 100,
            "roles": {"score_pct": 100},
            "directions": {"score_pct": 100},
            "interaction_constraints": {"score_pct": 100}}},
            "recall": 1.0, "backtranslation": {"score": 90},
            "faithful": True, "rule": "all ranked gates pass"},
        "draft_attempts": [], "final_protocol": "global protocol P() {}"}


def test_learned_agent_markdown_contains_direction_and_rule():
    text = build_agent_markdown(
        _record(), ["Confirm the final recipient before drafting."])

    assert "Analyst -> Requester" in text
    assert "Confirm the final recipient" in text
    assert "report: non-empty" in text


def test_skill_renderer_includes_ranked_coverage():
    text = build_skill(_record())
    assert "ranked STJP coverage: 100%" in text