"""cost_summary.py: dollar math, paired-comparison flag, fail-closed prices."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cost_summary  # noqa: E402


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _make_run(tmp_path: Path) -> tuple[Path, Path]:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    manifest = {
        "preflight": {
            "a": {"model": "Model-A"},
            "b": {"model": "Model-B"},
        },
        "cells": {
            # Model-A: 1M prompt + 100k completion at $2/$10 -> $2 + $1 = $3
            "a/armX/0000": {"status": "valid", "usage": {
                "prompt_tokens": 1_000_000, "completion_tokens": 100_000,
                "total_tokens": 1_100_000, "calls": 10}},
            # Model-B: 1M prompt + 100k completion at $0.1/$0.4 -> $0.14
            "b/armX/0000": {"status": "valid", "usage": {
                "prompt_tokens": 1_000_000, "completion_tokens": 100_000,
                "total_tokens": 1_100_000, "calls": 10}},
            # armY exists only on Model-B -> pooled row not comparable
            "b/armY/0000": {"status": "valid", "usage": {
                "prompt_tokens": 500_000, "completion_tokens": 0,
                "total_tokens": 500_000, "calls": 5}},
            # invalid cell: spent real money but has no validated usage
            "a/armY/0000": {"status": "invalid", "usage": None},
        },
    }
    _write(run_dir / "campaign_manifest.json", manifest)
    prices = tmp_path / "prices.json"
    _write(prices, {"as_of": "2026-08-06", "currency": "USD", "models": {
        "Model-A": {"input_usd_per_1m": 2.0, "output_usd_per_1m": 10.0,
                    "estimate": True, "source": "test"},
        "Model-B": {"input_usd_per_1m": 0.1, "output_usd_per_1m": 0.4,
                    "estimate": False, "source": "test"},
    }})
    return run_dir, prices


def test_cost_math_and_aggregates(tmp_path):
    run_dir, prices = _make_run(tmp_path)
    summary = cost_summary.summarize(run_dir, prices)
    assert summary["cells"]["a/armX/0000"]["cost_usd"] == pytest.approx(3.0)
    assert summary["cells"]["b/armX/0000"]["cost_usd"] == pytest.approx(0.14)
    assert summary["per_model"]["Model-A"]["cost_usd"] == pytest.approx(3.0)
    assert summary["total_cost_usd"] == pytest.approx(3.0 + 0.14 + 0.05)
    assert summary["any_price_is_estimate"] is True


def test_paired_comparison_flag(tmp_path):
    run_dir, prices = _make_run(tmp_path)
    summary = cost_summary.summarize(run_dir, prices)
    # armX pools both models -> comparable; armY pools only Model-B -> not
    assert summary["per_arm"]["armX"]["comparable"] is True
    assert summary["per_arm"]["armY"]["comparable"] is False
    assert summary["per_arm"]["armY"]["models"] == ["Model-B"]


def test_invalid_cells_are_listed_not_priced(tmp_path):
    run_dir, prices = _make_run(tmp_path)
    summary = cost_summary.summarize(run_dir, prices)
    assert [row["cell"] for row in summary["unpriced_cells"]] == ["a/armY/0000"]
    assert "a/armY/0000" not in summary["cells"]


def test_cached_tokens_priced_at_cached_meter(tmp_path):
    run_dir = tmp_path / "run_cached"
    run_dir.mkdir()
    _write(run_dir / "campaign_manifest.json", {
        "preflight": {"c": {"model": "Model-C"}},
        "cells": {"c/armZ/0000": {"status": "valid", "usage": {
            "prompt_tokens": 1_000_000, "completion_tokens": 100_000,
            "cached_tokens": 500_000,
            "total_tokens": 1_100_000, "calls": 10}}},
    })
    prices = tmp_path / "prices_cached.json"
    _write(prices, {"models": {"Model-C": {
        "input_usd_per_1m": 2.0, "output_usd_per_1m": 10.0,
        "cached_input_usd_per_1m": 0.2, "source": "test"}}})
    summary = cost_summary.summarize(run_dir, prices)
    # 0.5M uncached x $2 + 0.5M cached x $0.2 + 0.1M out x $10 = 1.0+0.1+1.0
    assert summary["cells"]["c/armZ/0000"]["cost_usd"] == pytest.approx(2.1)
    assert summary["per_model"]["Model-C"]["cached_tokens"] == 500_000


def test_cached_tokens_absent_is_full_rate_upper_bound(tmp_path):
    # Same cell without cached_tokens: all prompt tokens at the full rate.
    run_dir, prices = _make_run(tmp_path)
    summary = cost_summary.summarize(run_dir, prices)
    assert summary["cells"]["a/armX/0000"]["usage"]["cached_tokens"] == 0
    assert summary["cells"]["a/armX/0000"]["cost_usd"] == pytest.approx(3.0)


def test_missing_price_entry_fails_closed(tmp_path):
    run_dir, prices = _make_run(tmp_path)
    table = json.loads(prices.read_text(encoding="utf-8"))
    del table["models"]["Model-B"]
    prices.write_text(json.dumps(table), encoding="utf-8")
    with pytest.raises(RuntimeError, match="no price entry"):
        cost_summary.summarize(run_dir, prices)
