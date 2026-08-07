"""Turn a hosted-campaign run's token usage into dollars, per model and arm.

Usage:
  python experiments/scripts/cost_summary.py <run_dir> [--prices <prices.json>] [--write]

Why this exists: tokens are the benchmark's primary efficiency metric, but the
four campaign models differ in price by more than 15x, so a token total alone
misstates what an operator actually pays. This script prices each VALID cell's
stored usage (prompt/completion split) against the per-model rate table in
experiments/config/model_prices.json and emits:

  - a per-(model, arm) cost matrix  (the safe, matched-model view),
  - per-model and per-arm aggregates, with the per-arm rows carrying an
    explicit `comparable` flag that is False whenever the arm's valid model
    composition differs from the full model set (the paired-comparison rule:
    pooled dollars across different model mixes are as misleading as pooled
    tokens - see BENCHMARK_HANDOFF.md section 8),
  - a grand total, and the list of unpriced cells.

Honesty rules, enforced:
  - Deterministic and offline: reads only campaign_manifest.json + the price
    file; re-running it on a run directory reproduces the same numbers.
    Correcting a rate later = edit the price file, re-run this script.
  - Fail-closed on prices: a valid cell whose model has no price entry aborts
    the summary rather than silently dropping spend.
  - Invalid/pending cells burned real money too, but their usage was never
    validated, so they cannot be priced from local evidence; they are listed
    in `unpriced_cells` and the summary says so instead of pretending the
    total is complete.
  - Every dollar figure inherits the price file's `estimate` flag and
    `source` string, so placeholder analog rates can never be mistaken for
    verified Azure meter rates.

With --write, saves cost_summary.json into the run directory (atomic).
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_PRICES = HERE.parent / "config" / "model_prices.json"


def _atomic_write_json(path: Path, value: dict) -> None:
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def load_prices(path: Path) -> dict:
    table = json.loads(path.read_text(encoding="utf-8"))
    models = table.get("models")
    if not isinstance(models, dict) or not models:
        raise RuntimeError(f"price table {path} has no 'models' map")
    for name, entry in models.items():
        for key in ("input_usd_per_1m", "output_usd_per_1m"):
            value = entry.get(key)
            if not isinstance(value, (int, float)) or value < 0:
                raise RuntimeError(
                    f"price table {path}: model {name!r} field {key} must be "
                    f"a non-negative number, got {value!r}")
    return table


def cell_cost_usd(usage: dict, price_entry: dict) -> float:
    return (usage["prompt_tokens"] * price_entry["input_usd_per_1m"]
            + usage["completion_tokens"] * price_entry["output_usd_per_1m"]) / 1e6


def _model_full_name(manifest: dict, run_dir: Path, model_key: str,
                     cell: dict) -> str:
    """Resolve the short wave key (e.g. 'v4pro') to the deployment name the
    price table uses (e.g. 'DeepSeek-V4-Pro'): prefer the preflight record,
    fall back to the cell's result.json."""
    preflight = (manifest.get("preflight") or {}).get(model_key) or {}
    if preflight.get("model"):
        return preflight["model"]
    result_file = cell.get("result_file")
    if result_file:
        result_path = run_dir / result_file
        if result_path.exists():
            model = json.loads(
                result_path.read_text(encoding="utf-8")).get("model")
            if model:
                return model
    raise RuntimeError(
        f"cannot resolve deployment name for model key {model_key!r}")


def summarize(run_dir: Path, prices_path: Path) -> dict:
    manifest = json.loads(
        (run_dir / "campaign_manifest.json").read_text(encoding="utf-8"))
    prices = load_prices(prices_path)
    price_models = prices["models"]

    cells_out: dict[str, dict] = {}
    unpriced: list[dict] = []
    per_model: dict[str, dict] = {}
    per_arm_models: dict[str, set] = {}

    for cell_id, cell in sorted(manifest["cells"].items()):
        model_key, arm, _trial = cell_id.split("/")
        if cell.get("status") != "valid" or not cell.get("usage"):
            unpriced.append({
                "cell": cell_id, "status": cell.get("status"),
                "reason": "not a valid cell with validated usage; its real "
                          "spend is not recoverable from local evidence "
                          "(rerun the cell, or reconcile from traces)"})
            continue
        model_name = _model_full_name(manifest, run_dir, model_key, cell)
        entry = price_models.get(model_name)
        if entry is None:
            raise RuntimeError(
                f"no price entry for model {model_name!r} (cell {cell_id}); "
                f"add it to {prices_path} - refusing to silently drop spend")
        usage = cell["usage"]
        cost = cell_cost_usd(usage, entry)
        cells_out[cell_id] = {
            "model": model_name,
            "arm": arm,
            "usage": {k: usage[k] for k in
                      ("prompt_tokens", "completion_tokens",
                       "total_tokens", "calls")},
            "cost_usd": round(cost, 4),
            "price_estimate": bool(entry.get("estimate")),
        }
        bucket = per_model.setdefault(model_name, {
            "cells": 0, "total_tokens": 0, "calls": 0, "cost_usd": 0.0})
        bucket["cells"] += 1
        bucket["total_tokens"] += usage["total_tokens"]
        bucket["calls"] += usage["calls"]
        bucket["cost_usd"] += cost
        per_arm_models.setdefault(arm, set()).add(model_name)

    all_models = {c["model"] for c in cells_out.values()}
    per_arm: dict[str, dict] = {}
    for arm in sorted(per_arm_models):
        rows = [c for c in cells_out.values() if c["arm"] == arm]
        arm_models = per_arm_models[arm]
        per_arm[arm] = {
            "cells": len(rows),
            "models": sorted(arm_models),
            # The paired-comparison rule, applied to money: a pooled dollar
            # figure is only comparable across arms when every arm pools the
            # same models. Downstream tables must not compare rows where
            # this flag is False (BENCHMARK_HANDOFF.md section 8).
            "comparable": arm_models == all_models,
            "total_tokens": sum(c["usage"]["total_tokens"] for c in rows),
            "cost_usd": round(sum(c["cost_usd"] for c in rows), 4),
        }

    for bucket in per_model.values():
        bucket["cost_usd"] = round(bucket["cost_usd"], 4)

    return {
        "run_dir": str(run_dir),
        "generated_at": datetime.now().astimezone().isoformat(),
        "prices_file": str(prices_path),
        "prices_as_of": prices.get("as_of"),
        "currency": prices.get("currency", "USD"),
        "any_price_is_estimate": any(
            c["price_estimate"] for c in cells_out.values()),
        "price_sources": {name: entry.get("source")
                          for name, entry in price_models.items()
                          if name in all_models},
        "cells": cells_out,
        "per_model": per_model,
        "per_arm": per_arm,
        "total_cost_usd": round(
            sum(c["cost_usd"] for c in cells_out.values()), 4),
        "unpriced_cells": unpriced,
    }


def print_report(summary: dict) -> None:
    est = " (ESTIMATED prices - replace with Azure meter rates)" \
        if summary["any_price_is_estimate"] else ""
    print(f"Cost summary for {summary['run_dir']}{est}")
    print(f"\nPer model ({summary['currency']}):")
    for model, row in sorted(summary["per_model"].items()):
        print(f"  {model:20s} cells={row['cells']:3d} "
              f"tokens={row['total_tokens']:>12,} "
              f"calls={row['calls']:>6,} cost=${row['cost_usd']:>10,.2f}")
    print("\nPer arm (pooled - rows with comparable=False must NOT be "
          "compared to each other):")
    for arm, row in summary["per_arm"].items():
        flag = "" if row["comparable"] else "  [NOT comparable: models=" \
            + ",".join(row["models"]) + "]"
        print(f"  {arm:22s} cells={row['cells']:3d} "
              f"tokens={row['total_tokens']:>12,} "
              f"cost=${row['cost_usd']:>9,.2f}{flag}")
    print(f"\nTOTAL priced spend: ${summary['total_cost_usd']:,.2f}")
    if summary["unpriced_cells"]:
        print(f"UNPRICED cells (real spend NOT included above): "
              f"{len(summary['unpriced_cells'])}")
        for row in summary["unpriced_cells"]:
            print(f"  - {row['cell']} ({row['status']})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--prices", type=Path, default=DEFAULT_PRICES)
    parser.add_argument("--write", action="store_true",
                        help="save cost_summary.json into the run directory")
    args = parser.parse_args()
    summary = summarize(args.run_dir.resolve(), args.prices.resolve())
    print_report(summary)
    if args.write:
        out = args.run_dir.resolve() / "cost_summary.json"
        _atomic_write_json(out, summary)
        print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
