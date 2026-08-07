"""Phase 2: an endorsed understanding becomes a checked protocol.

This file exists because phase 2 shipped with NO test and crashed on the
user's first click with `NameError: DistilledIntent is not defined` — the
function read its inputs from disk and constructed schema objects that were
never imported. A single offline call would have caught it.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.intent_loop import mockdata
from experiments.intent_loop.llm import MockChat
from experiments.intent_loop.loop import formalize_episode, mock_validate

UNDERSTANDING = {
    "distilled": {
        "mission": "Produce an approved quarterly report.",
        "roles": [{"name": "Requester", "kind": "user", "description": "asks"},
                  {"name": "Analyst", "kind": "agent", "description": "works"},
                  {"name": "Approver", "kind": "agent", "description": "signs"}],
        "requirements": [
            {"rid": "R1", "kind": "ordering", "who": ["Requester", "Analyst"],
             "text": "The request reaches the Analyst first.",
             "source": "document"},
            {"rid": "R2", "kind": "authorization", "who": ["Approver"],
             "text": "The Approver approves before release.",
             "source": "answer"}],
        "goals": [{"gid": "G1", "text": "The Requester holds the report.",
                   "evidence": "report received", "final": True}],
        "interactions": [
            {"iid": "I1", "sender": "Requester", "receiver": "Analyst",
             "what": "the data request", "cardinality": "exactly once"},
            {"iid": "I2", "sender": "Analyst", "receiver": "Approver",
             "what": "the analysis for sign-off"}],
        "completion_signal": "The Requester holds the report.",
        "open_questions": [],
    },
    "transcript": [{"round": 1, "question": "Who approves?",
                    "answer": "The Approver."}],
}


def _session(tmp_path: Path) -> Path:
    d = tmp_path / "sessions" / "live_understood"
    d.mkdir(parents=True)
    (d / "document.md").write_text(
        "<!-- episode: ep-x | sha256: y | chars: 9 -->\nan intent",
        encoding="utf-8")
    (d / "understanding.json").write_text(json.dumps(UNDERSTANDING),
                                          encoding="utf-8")
    (d / "record.json").write_text(json.dumps({
        **UNDERSTANDING, "episode_id": "ep-x", "intent_sha256": "y" * 64,
        "intent_chars": 9, "draft_attempts": [], "final_protocol": None,
        "valid": False, "faithfulness": None,
        "meter": {"phase": "understood"},
        "ts": "2026-08-05T00:00:00+00:00"}), encoding="utf-8")
    return d


def test_formalize_reads_the_understanding_and_drafts(tmp_path: Path):
    """The regression: this raised NameError before the schema imports were
    added, so the very first click on 'Formalise' died."""
    d = _session(tmp_path)
    stages: list[str] = []
    record = formalize_episode(
        MockChat(mockdata.DRAFTER_SCRIPT + mockdata.EVAL_SCRIPT),
        d, validate_fn=mock_validate, validator_label="mock",
        faithfulness_rounds=0, corpus_path=tmp_path / "corpus.jsonl",
        progress=lambda s, _d: stages.append(s))

    assert record.valid, "the scripted draft should validate"
    assert record.final_protocol and "global protocol" in record.final_protocol
    # It must NOT re-interrogate: the understanding was already endorsed.
    assert "asked" not in stages and "interrogated" not in stages
    assert "drafted" in stages
    # Identity and history carry over from the endorsed episode.
    assert record.episode_id == "ep-x"
    assert len(record.transcript) == 1
    assert (d / "protocol.scr").exists()


def test_formalize_refuses_a_session_with_no_understanding(tmp_path: Path):
    empty = tmp_path / "sessions" / "nothing"
    empty.mkdir(parents=True)
    with pytest.raises(FileNotFoundError, match="no understanding"):
        formalize_episode(MockChat([]), empty, validate_fn=mock_validate)


def test_formalize_honours_a_hand_edited_understanding(tmp_path: Path):
    """A human may correct understanding.json between the phases; phase 2
    must read the edit rather than a stale copy in record.json."""
    d = _session(tmp_path)
    edited = json.loads((d / "understanding.json").read_text(encoding="utf-8"))
    edited["distilled"]["requirements"].append(
        {"rid": "R3", "kind": "termination", "who": ["Analyst"],
         "text": "The Analyst sends the final report.", "source": "answer"})
    (d / "understanding.json").write_text(json.dumps(edited), encoding="utf-8")

    record = formalize_episode(
        MockChat(mockdata.DRAFTER_SCRIPT + mockdata.EVAL_SCRIPT),
        d, validate_fn=mock_validate, validator_label="mock",
        faithfulness_rounds=0, corpus_path=tmp_path / "corpus.jsonl")
    rids = [r["rid"] for r in record.distilled["requirements"]]
    assert "R3" in rids


def test_formalize_grades_the_emitted_guard_sidecar(tmp_path: Path):
    d = _session(tmp_path)
    edited = json.loads((d / "understanding.json").read_text(encoding="utf-8"))
    edited["distilled"]["requirements"].append(
        {"rid": "R3", "kind": "value", "priority": "must",
         "who": ["Analyst"], "text": "The amount must exceed 500.",
         "source": "document"})
    edited["distilled"]["interactions"][1]["carries"] = [
        {"name": "amount", "type": "double", "constraint": "amount > 500"}]
    (d / "understanding.json").write_text(json.dumps(edited), encoding="utf-8")
    guarded = mockdata.FIXED_DRAFT + \
        "\n=== REFN ===\nAnalysisSubmitted.amount :: amount > 500\n"
    chat = MockChat([guarded] + mockdata.EVAL_SCRIPT)

    record = formalize_episode(
        chat, d, validate_fn=mock_validate, validator_label="mock",
        faithfulness_rounds=0, corpus_path=tmp_path / "corpus.jsonl")

    assert record.valid
    coverage_call = next(call for call in chat.calls if call[0] == "coverage")
    assert "AnalysisSubmitted.amount :: amount > 500" in coverage_call[2]
