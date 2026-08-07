"""Reconcile historical MAF usage from exact run-owned OTel trace spans.

Usage:
  python experiments/scripts/reconcile_maf_usage.py <run_dir> <server.log>... --write

Only valid MAF cells are considered. Every persisted trace ID must resolve to
one or more ``chat <model>`` spans with positive token usage. Without
``--write`` the command prints the proposed corrections without changing data.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path


CHAT_BLOCK = re.compile(r"(?=\{\r?\n    \"name\":)")
NAME = re.compile(r'"name":\s*"([^"]+)"')
SPAN_ID = re.compile(r'"span_id":\s*"([^"]+)"')
INPUT_TOKENS = re.compile(r'"gen_ai\.usage\.input_tokens":\s*([0-9]+)')
OUTPUT_TOKENS = re.compile(r'"gen_ai\.usage\.output_tokens":\s*([0-9]+)')


def _atomic_write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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


def _load_trace_usage(log_paths: list[Path], trace_ids: set[str]) -> dict:
    spans = {trace_id: [] for trace_id in trace_ids}
    for log_path in log_paths:
        text = log_path.read_text(encoding="utf-8", errors="replace")
        present = {trace_id for trace_id in trace_ids if trace_id in text}
        if not present:
            continue
        for block in CHAT_BLOCK.split(text):
            block_ids = [trace_id for trace_id in present if trace_id in block]
            if not block_ids:
                continue
            name_match = NAME.search(block)
            span_id_match = SPAN_ID.search(block)
            input_match = INPUT_TOKENS.search(block)
            output_match = OUTPUT_TOKENS.search(block)
            if (not name_match or not name_match.group(1).startswith("chat ")
                    or not span_id_match or not input_match or not output_match):
                continue
            span = {
                "span_id": span_id_match.group(1),
                "name": name_match.group(1),
                "prompt_tokens": int(input_match.group(1)),
                "completion_tokens": int(output_match.group(1)),
                "log_file": log_path.name,
            }
            for trace_id in block_ids:
                spans[trace_id].append(span)
    return spans


def _usage_for_trace(spans: list[dict], expected_model: str) -> dict:
    if not spans:
        raise RuntimeError("trace has no chat spans")
    span_ids = [span["span_id"] for span in spans]
    if len(span_ids) != len(set(span_ids)):
        raise RuntimeError("trace contains duplicate chat span IDs")
    expected_name = f"chat {expected_model}"
    wrong_models = sorted({span["name"] for span in spans
                           if span["name"] != expected_name})
    if wrong_models:
        raise RuntimeError(
            f"trace contains wrong-model spans: {wrong_models}; "
            f"expected {expected_name!r}")
    prompt = sum(span["prompt_tokens"] for span in spans)
    completion = sum(span["completion_tokens"] for span in spans)
    if prompt <= 0 or completion <= 0:
        raise RuntimeError(
            f"trace has invalid usage: prompt={prompt}, completion={completion}")
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": prompt + completion,
        "calls": len(spans),
    }


def _update_events(path: Path, by_trace: dict[str, dict],
                   aggregate: dict, *, write: bool) -> None:
    rows = [json.loads(line) for line in path.read_text(
        encoding="utf-8").splitlines() if line.strip()]
    for row in rows:
        marker = row.get("marker")
        if marker == "attempt_end":
            trace_id = (row.get("extra") or {}).get("trace_id")
            if trace_id in by_trace:
                row["tokens"] = dict(by_trace[trace_id])
                row.setdefault("extra", {})["usage_source"] = "foundry_trace"
                row["extra"]["capture_scope"] = "all_chat_client_calls"
        elif marker == "trial_end":
            row["tokens"] = dict(aggregate)
            row["usage_source"] = "foundry_trace"
            row["capture_scope"] = "all_chat_client_calls"
    if write:
        path.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
            encoding="utf-8")


def reconcile(run_dir: Path, log_paths: list[Path], *, write: bool) -> None:
    manifest_path = run_dir / "campaign_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cells = {
        cell_id: cell for cell_id, cell in manifest["cells"].items()
        if cell.get("status") == "valid"
        and str(cell.get("arm", "")).startswith("maf_")
    }
    trace_ids = {
        trace_id for cell in cells.values()
        for trace_id in cell.get("trace_ids", [])
    }
    spans = _load_trace_usage(log_paths, trace_ids)
    missing = sorted(trace_id for trace_id in trace_ids if not spans[trace_id])
    if missing:
        raise RuntimeError(f"missing exact trace IDs: {missing}")

    reconciled_at = datetime.now().astimezone().isoformat()
    for cell_id, cell in sorted(cells.items()):
        result_path = run_dir / cell["result_file"]
        result = json.loads(result_path.read_text(encoding="utf-8"))
        expected_model = result["model"]
        by_trace = {
            trace_id: _usage_for_trace(spans[trace_id], expected_model)
            for trace_id in cell["trace_ids"]
        }
        aggregate = {
            key: sum(usage[key] for usage in by_trace.values())
            for key in ("prompt_tokens", "completion_tokens", "total_tokens", "calls")
        }
        aggregate["capture_scope"] = "all_chat_client_calls"
        previous = dict(result["usage"])
        provenance = {
            "usage_source": "foundry_trace",
            "usage_evidence": "server_otel_console_export",
            "reconciled_at": reconciled_at,
            "trace_ids": list(cell["trace_ids"]),
            "previous_usage": previous,
            "per_trace": by_trace,
            "log_files": sorted({
                span["log_file"] for trace_id in cell["trace_ids"]
                for span in spans[trace_id]
            }),
        }
        result["usage"] = dict(aggregate)
        result["record"]["usage"] = dict(aggregate)
        result["usage_reconciliation"] = provenance
        cell["usage"] = dict(aggregate)
        cell["usage_source"] = "foundry_trace"
        cell["usage_reconciled_at"] = reconciled_at
        _update_events(
            result_path.parent / result["events_file"], by_trace, aggregate,
            write=write)
        if write:
            _atomic_write_json(result_path, result)
        print(
            f"{cell_id}: calls={aggregate['calls']} "
            f"prompt={aggregate['prompt_tokens']} "
            f"completion={aggregate['completion_tokens']} "
            f"total={aggregate['total_tokens']}")

    if write:
        manifest["updated_at"] = reconciled_at
        _atomic_write_json(manifest_path, manifest)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("logs", nargs="+", type=Path)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    reconcile(
        args.run_dir.resolve(), [path.resolve() for path in args.logs],
        write=args.write)


if __name__ == "__main__":
    main()
