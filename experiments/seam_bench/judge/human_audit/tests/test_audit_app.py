"""Tests for audit_app.py's pure (non-Streamlit-runtime) helpers:
resumability, append-only writes, and idempotent submission. These do not
drive the Streamlit UI itself (no browser) — that is covered by the
`streamlit run ... --server.headless true` boot smoke test the human
worker ran manually (see the task's PR notes), which this suite cannot
reproduce offline.

streamlit must be importable for this module to load (see
requirements.txt) — that's a real dependency of the tool being tested, not
an accident of the test environment.
"""
from __future__ import annotations

import json

import pytest

streamlit = pytest.importorskip("streamlit")

from experiments.seam_bench.judge.human_audit import audit_app as app


def _write_jsonl(path, records):
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def test_labeled_ids_empty_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "LABELS_PATH", tmp_path / "labels.jsonl")
    assert app.labeled_ids() == set()


def test_next_unlabeled_index_resumes_after_partial_labels():
    packet = [{"item_id": "a"}, {"item_id": "b"}, {"item_id": "c"}]
    done = {"a"}
    assert app.next_unlabeled_index(packet, done) == 1


def test_next_unlabeled_index_none_when_all_done():
    packet = [{"item_id": "a"}, {"item_id": "b"}]
    done = {"a", "b"}
    assert app.next_unlabeled_index(packet, done) is None


def test_submit_label_appends_one_line(tmp_path, monkeypatch):
    labels_path = tmp_path / "labels.jsonl"
    monkeypatch.setattr(app, "LABELS_PATH", labels_path)
    app.submit_label("item-0001", "fit", "looks fine", 12.3)
    records = app.read_jsonl(labels_path)
    assert len(records) == 1
    assert records[0]["item_id"] == "item-0001"
    assert records[0]["label"] == "fit"
    assert records[0]["note"] == "looks fine"
    assert records[0]["seconds_spent"] == 12.3
    assert "ts" in records[0]


def test_submit_label_is_idempotent_never_overwrites(tmp_path, monkeypatch):
    labels_path = tmp_path / "labels.jsonl"
    monkeypatch.setattr(app, "LABELS_PATH", labels_path)
    app.submit_label("item-0001", "fit", "", 5.0)
    app.submit_label("item-0001", "no_fit", "changed my mind", 9.0)  # ignored
    records = app.read_jsonl(labels_path)
    assert len(records) == 1
    assert records[0]["label"] == "fit"  # first write wins, never overwritten


def test_append_only_preserves_prior_lines_across_process_restarts(tmp_path, monkeypatch):
    """Simulates a resumed session: labels.jsonl already has entries from an
    earlier sitting; a fresh call must APPEND, not truncate."""
    labels_path = tmp_path / "labels.jsonl"
    monkeypatch.setattr(app, "LABELS_PATH", labels_path)
    _write_jsonl(labels_path, [
        {"item_id": "item-0001", "label": "fit", "note": "", "seconds_spent": 4.0,
         "ts": "2026-07-11T00:00:00Z"},
        {"item_id": "item-0002", "label": "no_fit", "note": "", "seconds_spent": 6.0,
         "ts": "2026-07-11T00:01:00Z"},
    ])
    app.submit_label("item-0003", "unsure", "", 3.0)
    records = app.read_jsonl(labels_path)
    assert [r["item_id"] for r in records] == ["item-0001", "item-0002", "item-0003"]


def test_resumability_full_cycle(tmp_path, monkeypatch):
    labels_path = tmp_path / "labels.jsonl"
    monkeypatch.setattr(app, "LABELS_PATH", labels_path)
    packet = [{"item_id": f"item-{i:04d}"} for i in range(1, 6)]

    # "first sitting": label the first two items
    app.submit_label("item-0001", "fit", "", 1.0)
    app.submit_label("item-0002", "no_fit", "", 1.0)

    # "restart": resume must land on item-0003
    done = app.labeled_ids()
    idx = app.next_unlabeled_index(packet, done)
    assert packet[idx]["item_id"] == "item-0003"


def test_session_stats():
    done_records = [
        {"seconds_spent": 4.0}, {"seconds_spent": 6.0}, {"seconds_spent": 5.0},
    ]
    n, mean = app.session_stats(done_records)
    assert n == 3
    assert mean == pytest.approx(5.0)


def test_session_stats_empty():
    n, mean = app.session_stats([])
    assert n == 0
    assert mean == 0.0
