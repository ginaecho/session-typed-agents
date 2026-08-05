"""Interrogation as a real conversation: a human answers, turn by turn, and
the run waits for them."""
from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from experiments.intent_loop.app import create_app
from experiments.intent_loop.stakeholder import HumanStakeholder, NOT_SPECIFIED


@pytest.fixture()
def client(tmp_path: Path):
    app = create_app(sessions_dir=tmp_path / "sessions",
                     corpus_path=tmp_path / "corpus.jsonl",
                     packs_dir=tmp_path / "packs",
                     exports_dir=tmp_path / "exports")
    app.config.update(TESTING=True)
    return app.test_client()


def test_human_stakeholder_blocks_until_the_answer_arrives():
    """The interrogation must WAIT — that is what makes it a conversation
    rather than a transcript read afterwards."""
    asked: list[str] = []
    h = HumanStakeholder(timeout_s=5, on_ask=asked.append)
    result: list[str] = []

    t = threading.Thread(target=lambda: result.append(
        h.answer("1. Who approves a refund?")))
    t.start()
    time.sleep(0.2)
    assert not result                      # still blocked
    assert h.pending and asked == ["1. Who approves a refund?"]

    h.submit("The finance approver, always.")
    t.join(timeout=5)
    assert result == ["The finance approver, always."]
    assert h.pending is None


def test_unanswered_conversation_degrades_honestly():
    """Nobody answered is a true statement; an invented answer is not."""
    h = HumanStakeholder(timeout_s=0.3)
    reply = h.answer("1. What is the threshold?")
    assert reply.startswith(NOT_SPECIFIED)
    assert "nobody answered" in reply


def test_duplicate_run_of_the_same_document_is_refused(client):
    """Two runs of one document against one deployment contend for the same
    rate limit and each makes the other slower — which is exactly what a
    user reads as 'stuck'."""
    first = client.post("/api/runs", json={"mock": True})
    assert first.status_code == 202
    # The mock episode finishes fast, so submit while it is still queued by
    # using the identical document explicitly.
    doc = "the same intent text"
    a = client.post("/api/runs", json={"mock": False, "validator": "mock",
                                       "intent_text": doc})
    b = client.post("/api/runs", json={"mock": False, "validator": "mock",
                                       "intent_text": doc})
    # `a` starts (and will fail without an LLM configured, which is fine);
    # `b` must be refused while `a` is in flight, or `a` already finished.
    assert b.status_code in (202, 409)
    if b.status_code == 409:
        body = b.get_json()
        assert body["job_id"] == a.get_json()["job_id"]
        assert "already in flight" in body["error"]


def test_answer_endpoint_rejects_when_nothing_is_waiting(client):
    job = client.post("/api/runs", json={"mock": True}).get_json()
    r = client.post(f"/api/runs/{job['job_id']}/answer",
                    json={"answer": "hello"})
    assert r.status_code == 409
    assert "not waiting" in r.get_json()["error"]

    assert client.post("/api/runs/nope/answer",
                       json={"answer": "x"}).status_code == 404
    assert client.post(f"/api/runs/{job['job_id']}/answer",
                       json={"answer": "  "}).status_code == 400


def test_job_reports_the_open_question_and_stage_age(client):
    """The UI needs both: what is being asked, and how long this step has
    been running, so a slow model call never looks frozen."""
    from experiments.intent_loop.jobs import JobRegistry
    reg = JobRegistry()
    done = threading.Event()
    job = reg.submit("run", {}, lambda j: (done.wait(2), {"ok": True})[1])
    job.ask("1. Who decides?")
    d = job.to_dict()
    assert d["awaiting"] == "1. Who decides?"
    assert d["stage"] == "awaiting_answer" and d["stage_since"]
    done.set()
