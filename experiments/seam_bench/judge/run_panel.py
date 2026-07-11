"""End-to-end orchestration: run the default panel on one (intent, G) case.

Not a separate architectural layer — this is the glue that ties
payloads/seats/classes/aggregate/cache together the way a real caller
would, and doubles as the entry point for the conditional real-API smoke
test (W6 task card item 8). Requires ``ANTHROPIC_API_KEY`` in the
environment; prints a clear skip message and exits 0 if it's absent
rather than failing noisily.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from experiments.seam_bench.judge.aggregate import PanelResult, aggregate_panel, write_escalation_record
from experiments.seam_bench.judge.cache import VerdictCache
from experiments.seam_bench.judge.classes import build_efsms_from_source, run_j_back, run_j_fwd, run_j_probe
from experiments.seam_bench.judge.payloads import SanitizedPayload, sanitize_protocol
from experiments.seam_bench.judge.seats import Verdict, default_panel


def judge_case(client, cache: VerdictCache, intent: str, protocol_source: str, panel=None) -> tuple[PanelResult, list[Verdict], SanitizedPayload]:
    panel = panel or default_panel()
    payload = sanitize_protocol(protocol_source)

    verdicts: list[Verdict] = []
    for seat in panel:
        if seat.class_ == "fwd":
            verdicts.append(run_j_fwd(client, cache, seat, intent, payload))
        elif seat.class_ == "back":
            verdicts.append(run_j_back(client, cache, seat, intent, payload))
        elif seat.class_ == "probe":
            probe_seat = seat
            compiler_seat = seat.__class__(**{**seat.__dict__, "model_id": "claude-sonnet-5", "max_tokens": 1024})
            efsms = build_efsms_from_source(protocol_source, payload.protocol_name, payload.roles)
            verdict, _results = run_j_probe(client, cache, probe_seat, compiler_seat, intent, payload, efsms)
            verdicts.append(verdict)

    result = aggregate_panel(verdicts)
    return result, verdicts, payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=Path("experiments/cases/_corpus/corpus_000.scr"))
    parser.add_argument("--intent", type=str, required=False)
    parser.add_argument("--cache-dir", type=Path, default=Path("experiments/seam_bench/judge/.cache_smoke"))
    parser.add_argument("--escalation-log", type=Path, default=Path("experiments/seam_bench/judge/.escalations_smoke.jsonl"))
    args = parser.parse_args(argv)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY not set — skipping real panel smoke run.")
        return 0

    import anthropic

    protocol_source = args.protocol.read_text(encoding="utf-8")
    intent = args.intent or (
        "Four roles (R0, R1, R2, R3) coordinate a short handshake. R0 first "
        "confirms two boolean flags with R1, then R0 notifies R2 of a "
        "boolean flag and R2 acknowledges back to R0. R1 then either "
        "requests an integer count from R3 (which replies with a string) "
        "or simply signals R3 with a boolean, and afterwards R3 sends "
        "several follow-up strings, booleans and doubles to R0, R1 and R2 "
        "to close out the exchange."
    )

    client = anthropic.Anthropic()
    cache = VerdictCache(args.cache_dir)
    result, verdicts, payload = judge_case(client, cache, intent, protocol_source)

    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    if result.escalate:
        write_escalation_record(args.escalation_log, args.protocol.stem, result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
