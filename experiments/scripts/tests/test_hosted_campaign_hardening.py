"""Deterministic checks for hosted campaign evidence hardening."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

os.environ["STJP_DISABLE_TRACING"] = "1"

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent
REPO_ROOT = SCRIPTS.parent.parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(REPO_ROOT))

from hosted_campaign import (  # noqa: E402
    CampaignManifest,
    _atomic_write_json,
    _run_preflight,
    _validated_trace_id,
    _validated_usage,
)


class FakeInvoker:
    def __init__(self, record: dict):
        self.record = record
        self.last_trace_id = None

    def invoke(self, request: dict) -> dict:
        assert request == {"stjp_preflight": True}
        self.last_trace_id = self.record.get("trace_id")
        return self.record


def test_atomic_manifest_and_resume() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp)
        manifest = CampaignManifest.create_or_load(
            run_dir, case_id="case", arms=["skills", "maf_skills"], models=["mini"],
            n=2, endpoint_mode="local")
        manifest.update_cell(
            "mini", "skills", 0, status="valid", trace_ids=["a" * 32])
        loaded = CampaignManifest.create_or_load(
            run_dir, case_id="case", arms=["skills", "maf_skills"], models=["mini"],
            n=2, endpoint_mode="local")
        assert loaded.is_valid("mini", "skills", 0)
        assert not loaded.is_valid("mini", "skills", 1)
        maf_result = run_dir / "cells" / "mini" / "maf_skills" / "0000" / "result.json"
        _atomic_write_json(maf_result, {
            "record": {"usage": {"capture_scope": "participant_outputs_only"}}})
        loaded.update_cell(
            "mini", "maf_skills", 0, status="valid",
            result_file=str(maf_result.relative_to(run_dir)))
        assert not loaded.is_valid("mini", "maf_skills", 0)
        _atomic_write_json(maf_result, {
            "record": {"usage": {"capture_scope": "all_chat_client_calls"}}})
        assert loaded.is_valid("mini", "maf_skills", 0)
        leftovers = list(run_dir.glob(".*.tmp"))
        assert not leftovers, leftovers


def test_usage_and_trace_validation() -> None:
    record = {
        "usage": {
            "prompt_tokens": 12, "completion_tokens": 2,
            "total_tokens": 14, "calls": 1,
            "capture_scope": "all_chat_client_calls",
        },
        "trace_id": "0123456789abcdef0123456789abcdef",
    }
    # cached_tokens is optional (pre-2026-08-07 builds) and defaults to 0
    assert _validated_usage(record) == (12, 2, 1, 0)
    record_cached = {
        "usage": {
            "prompt_tokens": 12, "completion_tokens": 2, "cached_tokens": 8,
            "total_tokens": 14, "calls": 1,
            "capture_scope": "all_chat_client_calls",
        },
    }
    assert _validated_usage(record_cached) == (12, 2, 1, 8)
    assert _validated_trace_id(record, object()) == record["trace_id"]
    for bad in (
        {"usage": {"prompt_tokens": 0, "completion_tokens": 2, "calls": 1,
                   "capture_scope": "all_chat_client_calls"}},
        {"usage": {"prompt_tokens": 12, "completion_tokens": 0, "calls": 1,
                   "capture_scope": "all_chat_client_calls"}},
        {"usage": {"prompt_tokens": 12, "completion_tokens": 2, "calls": 0,
                   "capture_scope": "all_chat_client_calls"}},
        # cached_tokens must be a non-negative int no larger than prompt_tokens
        {"usage": {"prompt_tokens": 12, "completion_tokens": 2, "calls": 1,
                   "cached_tokens": -1,
                   "capture_scope": "all_chat_client_calls"}},
        {"usage": {"prompt_tokens": 12, "completion_tokens": 2, "calls": 1,
                   "cached_tokens": 13,
                   "capture_scope": "all_chat_client_calls"}},
    ):
        try:
            _validated_usage(bad)
        except RuntimeError:
            pass
        else:
            raise AssertionError(f"accepted invalid usage: {bad}")


def test_preflight_persistence() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp)
        manifest = CampaignManifest.create_or_load(
            run_dir, case_id="case", arms=["skills"], models=["v4flash"],
            n=1, endpoint_mode="local")
        record = {
            "preflight": True,
            "model": "DeepSeek-V4-Flash",
            "text": "OK",
            "usage": {
                "prompt_tokens": 10, "completion_tokens": 1,
                "total_tokens": 11, "calls": 1,
                "capture_scope": "all_chat_client_calls",
            },
            "trace_id": "fedcba9876543210fedcba9876543210",
            "error": None,
        }
        evidence = _run_preflight(
            FakeInvoker(record), expected_model="DeepSeek-V4-Flash",
            model_key="v4flash", run_dir=run_dir, manifest=manifest)
        assert evidence["status"] == "valid"
        persisted = json.loads(
            (run_dir / "preflight" / "v4flash.json").read_text("utf-8"))
        assert persisted["usage"]["total_tokens"] == 11
        assert manifest.payload["preflight"]["v4flash"]["status"] == "valid"


def test_atomic_write_replaces_complete_document() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "state.json"
        _atomic_write_json(path, {"version": 1})
        _atomic_write_json(path, {"version": 2, "complete": True})
        assert json.loads(path.read_text("utf-8")) == {
            "complete": True, "version": 2}


if __name__ == "__main__":
    test_atomic_manifest_and_resume()
    test_usage_and_trace_validation()
    test_preflight_persistence()
    test_atomic_write_replaces_complete_document()
    print("ALL PASS")
