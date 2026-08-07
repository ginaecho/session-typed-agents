from __future__ import annotations

import json

from experiments.intent_loop import mockdata
from experiments.intent_loop.llm import MockChat
from experiments.intent_loop.refine import (persist_review_lesson,
                                             review_questions,
                                             refine_episode,
                                             revise_intent_from_review)
from experiments.intent_loop.schema import DistilledIntent


def _distilled() -> DistilledIntent:
    raw = json.loads(mockdata.INTERROGATOR_DONE)["distilled"]
    return DistilledIntent.from_dict(raw)


def test_user_graph_critique_becomes_confirmation_questions():
    reply = json.dumps({
        "assessment": "The final report direction may be reversed.",
        "questions": [{
            "q": "Who sends the final report to whom?",
            "because": "This confirms the final handover direction.",
            "kind": "direction"}]})
    chat = MockChat([reply])

    result = review_questions(
        chat, _distilled(), "The requester must receive the report.",
        mockdata.FIXED_DRAFT,
        "The final report arrow looks backwards.")

    assert result["questions"][0]["kind"] == "direction"
    prompt = chat.calls[0][2]
    assert "ORIGINAL USER INTENT" in prompt
    assert "REVIEWER'S CRITIQUE" in prompt
    assert "final report arrow looks backwards" in prompt


def test_review_always_requires_user_confirmation():
    chat = MockChat([json.dumps({
        "assessment": "Add a final delivery from Analyst to Requester.",
        "questions": []})])

    result = review_questions(
        chat, _distilled(), "intent", mockdata.FIXED_DRAFT,
        "The final delivery is missing.")

    assert len(result["questions"]) == 1
    assert "accurate" in result["questions"][0]["q"]


def test_confirmed_review_revises_full_interaction_graph():
    original = _distilled()
    revised_raw = original.to_dict()
    revised_raw["interactions"] = [{
        "iid": "I1", "sender": "Analyst", "receiver": "Requester",
        "what": "the final report", "carries": [{
            "name": "report", "type": "string", "constraint": "non-empty"}],
        "cardinality": "exactly once", "waits_for": []}]
    reply = json.dumps({
        "distilled": revised_raw,
        "change_summary": ["Added Analyst to Requester final handover."],
        "lesson": "Model completion as a directed handover to its recipient."
    })

    revised, changes, lesson = revise_intent_from_review(
        MockChat([reply]), original, "intent", mockdata.FIXED_DRAFT,
        "The graph is missing delivery.", [{
            "question": "Who sends it?", "answer": "Analyst to Requester."}])

    assert [(item.sender, item.receiver) for item in revised.interactions] == [
        ("Analyst", "Requester")]
    assert changes == ["Added Analyst to Requester final handover."]
    assert "directed handover" in lesson


def test_confirmed_review_lesson_is_bounded_and_deduplicated(tmp_path):
    path = tmp_path / "lessons.json"
    lesson = "Check the intended sender and receiver before drafting."
    persist_review_lesson(lesson, path=path, max_lessons=2)
    learned = persist_review_lesson(lesson, path=path, max_lessons=2)

    assert learned == [lesson]


def test_review_refinement_writes_revised_graph_and_learning_artifacts(
        tmp_path):
    original = _distilled()
    revised_raw = original.to_dict()
    revised_raw["interactions"] = [{
        "iid": "I1", "sender": "Analyst", "receiver": "Requester",
        "what": "final report", "carries": [], "cardinality": "exactly once",
        "waits_for": []}]
    revision = json.dumps({
        "distilled": revised_raw,
        "change_summary": ["Added final report delivery."],
        "lesson": "Model completion as a handover to the final recipient."})
    chat = MockChat([revision, mockdata.GUARDED_FIXED_DRAFT]
                    + mockdata.EVAL_SCRIPT)
    parent = tmp_path / "parent"
    parent.mkdir()
    (parent / "document.md").write_text("intent", encoding="utf-8")
    output = tmp_path / "reviewed"

    stages = []
    record = refine_episode(
        chat, parent_record={
            "episode_id": "ep", "intent_sha256": "x", "intent_chars": 6,
            "distilled": original.to_dict(), "transcript": [],
            "final_protocol": mockdata.FIXED_DRAFT},
        parent_dir=parent, out_dir=output,
        answers=[{"question": "Who receives it?",
                  "answer": "The Requester."}],
        validate_fn=lambda _text: (True, ""), validator_label="mock",
        corpus_path=tmp_path / "corpus.jsonl",
        review_critique="The graph omits final delivery.",
        lessons_path=tmp_path / "lessons.json",
        progress=lambda stage, _detail: stages.append(stage))

    assert record.distilled["interactions"][0]["receiver"] == "Requester"
    assert (output / "review.json").exists()
    assert "Analyst -> Requester" in (output / "AGENT.md").read_text(
        encoding="utf-8")
    assert (output / "SKILL.md").exists()
    assert "intent_revision_started" in stages
    assert "draft_started" in stages
    assert "validation_started" in stages
    assert "validation_result" in stages
    assert "faithfulness_started" in stages
    assert stages[-1] == "done"