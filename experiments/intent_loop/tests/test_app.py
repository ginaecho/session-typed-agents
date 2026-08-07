"""Flask API tests — the surface both humans and agents depend on.

Everything here runs offline against the scripted mock episode; no network,
no JVM, no Azure config.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from experiments.intent_loop import mockdata
from experiments.intent_loop.app import create_app


@pytest.fixture()
def client(tmp_path: Path):
    app = create_app(sessions_dir=tmp_path / "sessions",
                     corpus_path=tmp_path / "corpus.jsonl",
                     packs_dir=tmp_path / "packs",
                     exports_dir=tmp_path / "exports")
    app.config.update(TESTING=True)
    return app.test_client()


def _run_mock(client, **body) -> dict:
    r = client.post("/api/runs",
                    json={"mock": True, "stop_after": "all",
                          **body})
    assert r.status_code == 202, r.get_json()
    job_id = r.get_json()["job_id"]
    for _ in range(200):
        job = client.get(f"/api/runs/{job_id}").get_json()
        if job["state"] in ("succeeded", "failed"):
            return job
        time.sleep(0.05)
    pytest.fail("job did not finish")


def test_health_and_manifest(client):
    h = client.get("/api/health").get_json()
    assert h["ok"] and "validator" in h and "llm" in h
    m = client.get("/api/manifest").get_json()
    paths = {e["path"] for e in m["endpoints"]}
    # The manifest is an agent's only contract — it must name the endpoints
    # that actually exist.
    assert {"/api/runs", "/api/episodes", "/api/training/export"} <= paths


def test_run_episode_emits_stage_events(client):
    job = _run_mock(client)
    assert job["state"] == "succeeded", job.get("error")
    stages = [e["stage"] for e in job["events"]]

    # The five phases still occur, in order — but they are no longer the
    # only events: interrogation reports every round as it happens, because
    # a phase that only speaks when it finishes looks hung for minutes.
    phases = [s for s in stages
              if s in ("start", "interrogated", "drafted", "evaluated",
                       "done")]
    assert phases == ["start", "interrogated", "drafted", "evaluated", "done"]
    assert "asked" in stages and "answered" in stages

    interrogated = next(e for e in job["events"]
                        if e["stage"] == "interrogated")
    assert interrogated["requirements"] == 5
    assert interrogated["from_answers"] == 2      # recovered by asking
    assert job["result"]["valid"] and job["result"]["faithful"]


def test_transcript_is_flushed_during_interrogation(client, tmp_path):
    """The Q&A must be readable while the run is still going."""
    job = _run_mock(client)
    session = job["result"]["session"]
    partial = client.get(f"/api/episodes/{session}/partial").get_json()
    assert partial["complete"] is True          # finished by now
    # The per-round flush wrote the transcript file before the record.
    assert (tmp_path / "sessions" / session / "transcript.json").exists()


def test_episode_listing_and_detail(client):
    job = _run_mock(client)
    session = job["result"]["session"]

    eps = client.get("/api/episodes").get_json()["episodes"]
    assert [e["session"] for e in eps] == [session]
    assert eps[0]["validator"] == "mock"

    ep = client.get(f"/api/episodes/{session}").get_json()
    assert ep["valid"] and ep["document"]
    assert len(ep["transcript"]) == 1
    # Attempt texts are re-attached from disk, including the rejected one.
    assert [a["valid"] for a in ep["draft_attempts"]] == [False, True]
    assert "global protocol" in ep["draft_attempts"][1]["text"]


def test_unknown_episode_and_path_traversal_rejected(client):
    assert client.get("/api/episodes/nope").status_code == 404
    assert client.get("/api/episodes/..%2f..%2fsecret").status_code == 404


def test_live_run_requires_an_intent(client):
    r = client.post("/api/runs", json={"mock": False, "validator": "mock"})
    assert r.status_code == 400
    assert "intent_text" in r.get_json()["error"]


def test_real_validator_refused_when_toolchain_absent(client, monkeypatch):
    monkeypatch.setattr("experiments.intent_loop.app.toolchain_status",
                        lambda: {"available": False, "detail": "no jars"})
    r = client.post("/api/runs", json={"mock": True, "validator": "real"})
    assert r.status_code == 409
    assert "validator='mock'" in r.get_json()["hint"]


def test_pack_and_training_export_roundtrip(client):
    _run_mock(client)

    pack = client.post("/api/packs", json={"version": "v1"}).get_json()
    assert pack["exemplars"] == 1 and pack["rulebook"]
    assert client.get("/api/packs").get_json()["packs"][0]["version"] == "v1"

    stats = client.get("/api/training/stats").get_json()
    assert stats["drafting_examples"] == 1   # valid AND faithful
    assert stats["repair_examples"] == 1     # rejected -> accepted pair

    ex = client.post("/api/training/export", json={}).get_json()
    rows = [json.loads(l) for l in
            Path(ex["files"]["train"]).read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    for row in rows:
        assert [m["role"] for m in row["messages"]] == \
               ["system", "user", "assistant"]
        assert row["messages"][2]["content"].startswith("global protocol")


def test_run_with_a_pack_is_accepted(client):
    _run_mock(client)
    client.post("/api/packs", json={"version": "v1"})
    job = _run_mock(client, pack="v1")
    assert job["state"] == "succeeded"
    job2 = client.post("/api/runs", json={"mock": True, "pack": "nope"})
    assert job2.status_code == 400


def test_user_graph_critique_returns_learner_confirmation_questions(
        client, monkeypatch):
    job = _run_mock(client)
    session = job["result"]["session"]
    reply = json.dumps({
        "assessment": "The completion handover may be missing.",
        "questions": [{
            "q": "Who sends the completed report to the requester?",
            "because": "This confirms the missing direction.",
            "kind": "direction"}]})
    from experiments.intent_loop.llm import MockChat
    learner = MockChat([reply])
    monkeypatch.setattr("experiments.intent_loop.llm.build_chat",
                        lambda *args, **kwargs: learner)

    response = client.post(
        f"/api/episodes/{session}/review-questions",
        json={"critique": "The graph does not show final delivery."})

    assert response.status_code == 200
    body = response.get_json()
    assert body["reviewed_by"] == "user"
    assert body["questions"][0]["kind"] == "direction"
    assert "final delivery" in learner.calls[0][2]


def test_review_state_recovers_questions_and_interrupted_submission(
        client, tmp_path):
    job = _run_mock(client)
    session = job["result"]["session"]
    session_dir = tmp_path / "sessions" / session
    (session_dir / "review_questions.json").write_text(json.dumps({
        "assessment": "A delivery may be missing.",
        "critique": "The requester never receives the report.",
        "questions": [{"q": "Who sends the report?", "kind": "direction"}]
    }), encoding="utf-8")
    refine_dir = tmp_path / "sessions" / "refine_interrupted"
    refine_dir.mkdir()
    (refine_dir / "review_submission.json").write_text(json.dumps({
        "parent": session,
        "review_critique": "The requester never receives the report.",
        "answers": [{"question": "Who sends the report?",
                     "answer": "The Analyst sends it."}],
        "validator": "scribble-java",
        "submitted_at": "2026-08-06T09:00:00+00:00",
        "status": "submitted"
    }), encoding="utf-8")

    response = client.get(f"/api/episodes/{session}/review-state")

    assert response.status_code == 200
    body = response.get_json()
    assert body["questions"]["questions"][0]["kind"] == "direction"
    submission = body["latest_submission"]
    assert submission["completed"] is False
    assert submission["answers"][0]["answer"] == "The Analyst sends it."


def test_start_fresh_supersedes_same_intent_with_new_round_budget(
        client, monkeypatch):
    release = threading.Event()

    def slow_episode(_llm, _document, *, progress, max_rounds, **_kwargs):
        while not release.wait(0.01):
            progress("thinking", {"max_rounds": max_rounds})
        return SimpleNamespace(
            episode_id="ep", valid=False, faithfulness=None,
            draft_attempts=[])

    monkeypatch.setattr("experiments.intent_loop.app.loop_mod.run_episode",
                        slow_episode)
    body = {"mock": False, "validator": "mock",
            "intent_text": "same intent", "answered_by": "document"}
    first = client.post("/api/runs", json={**body, "max_rounds": 10})
    assert first.status_code == 202

    second = client.post("/api/runs", json={
        **body, "max_rounds": 3, "replace_existing": True})
    assert second.status_code == 202
    first_job = client.get(
        f"/api/runs/{first.get_json()['job_id']}").get_json()
    second_job = client.get(
        f"/api/runs/{second.get_json()['job_id']}").get_json()
    assert first_job["state"] == "cancelled"
    assert second_job["params"]["max_rounds"] == 3
    release.set()


def test_confirmed_review_creates_valid_redrawable_learned_episode(
        client, monkeypatch, tmp_path):
    original_job = _run_mock(client)
    parent = original_job["result"]["session"]
    parent_record = client.get(f"/api/episodes/{parent}").get_json()
    revised = parent_record["distilled"]
    revised["interactions"] = [{
        "iid": "I99", "sender": "Analyst", "receiver": "Requester",
        "what": "the corrected final report delivery", "carries": [],
        "cardinality": "exactly once", "waits_for": []}]
    revision_reply = json.dumps({
        "distilled": revised,
        "change_summary": ["Corrected final report delivery."],
        "lesson": "Confirm the final recipient before drafting."})
    from experiments.intent_loop.llm import MockChat
    chat = MockChat([revision_reply, mockdata.GUARDED_FIXED_DRAFT]
                    + mockdata.EVAL_SCRIPT)
    monkeypatch.setattr("experiments.intent_loop.llm.build_chat",
                        lambda *args, **kwargs: chat)
    monkeypatch.setattr(
        "experiments.intent_loop.refine.persist_review_lesson",
        lambda lesson, **kwargs: [lesson] if lesson else [])

    response = client.post(f"/api/episodes/{parent}/refine", json={
        "validator": "mock",
        "review_critique": "The final report delivery is wrong.",
        "answers": [{"question": "What correction did the user confirm?",
                     "answer": "Analyst sends the report to Requester."}]})
    assert response.status_code == 202
    body = response.get_json()
    queued = client.get(f"/api/runs/{body['job_id']}").get_json()
    assert queued["params"]["max_repair_rounds"] == 12
    for _ in range(200):
        job = client.get(f"/api/runs/{body['job_id']}").get_json()
        if job["state"] in ("succeeded", "failed"):
            break
        time.sleep(0.05)
    assert job["state"] == "succeeded", job.get("error")
    assert job["result"]["valid"] is True
    assert job["result"]["validation_failed"] is False
    assert job["result"]["attempts"] >= 1

    reviewed_session = job["result"]["session"]
    reviewed = client.get(
        f"/api/episodes/{reviewed_session}").get_json()
    assert reviewed["distilled"]["interactions"][0]["iid"] == "I99"
    assert reviewed["final_protocol"]
    graph = client.get(
        f"/api/episodes/{reviewed_session}/graph").get_json()
    assert graph["from_valid_draft"] is True
    output = tmp_path / "sessions" / reviewed_session
    assert (output / "review.json").exists()
    assert (output / "SKILL.md").exists()
    assert (output / "AGENT.md").exists()
