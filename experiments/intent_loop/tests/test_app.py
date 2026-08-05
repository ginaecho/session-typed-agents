"""Flask API tests — the surface both humans and agents depend on.

Everything here runs offline against the scripted mock episode; no network,
no JVM, no Azure config.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

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
    r = client.post("/api/runs", json={"mock": True, **body})
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
