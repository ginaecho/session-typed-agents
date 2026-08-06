"""repair_loop.py — the T0 T+R production loop.

SEAM_TRAINING_EXECUTION_PLAN.md §2 "System under training": "At inference
the pair runs the production loop: T drafts -> validate -> on reject, R
patches, <= 3 rounds (mirrors the live 4-reject->pass trace)." §4 T0 runs
"the repair loop with the same API model" as one of its baseline arms.

`run_repair_chain` is the whole loop for ONE item: draft (or reuse a
caller-supplied initial draft, e.g. the k=1 slot of a best-of-k batch) ->
validate through the REAL Scribble-java CLI (validity.py, never a weaker
approximation) -> on reject, hand the validator's own counterexample text
back to `Drafter.repair()` -> validate again -> repeat up to
`max_rounds` (default 3, the plan's cap) repairs. Every attempt in the
chain becomes one RunRecord (W1's schema): `k` counts attempts 1-indexed
(k=1 is the initial draft, k=2..max_rounds+1 are repair attempts);
`repair_rounds` on EVERY record in the chain is set to the chain's final
total-rounds-used (capped at `max_rounds`) — metrics.repair_rounds_mean
reads it off the highest-k record, so this is redundant-but-consistent by
construction rather than requiring the reader to know which row is "the"
final one.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Optional

from experiments.seam_bench.eval import validity
from experiments.seam_bench.eval.schema import RunRecord
from experiments.seam_bench.t0.drafter import (Drafter,
                                                GUARD_SIDECAR_SENTINEL,
                                                estimate_usage,
                                                split_guard_sidecar)

ValidateFn = Callable[[str], tuple[bool, str]]
BisimFn = Callable[[str, str], tuple[bool, str]]
ProgressFn = Callable[[str, dict], None]

#: SEAM_TRAINING_EXECUTION_PLAN.md §2/§4: repair loop caps at 3 rounds.
MAX_REPAIR_ROUNDS = 3


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run_repair_chain(
    drafter: Drafter, *, system: str, item_id: str, split: str, intent: str,
    gold: Optional[str] = None, initial_draft: Optional[str] = None,
    max_rounds: int = MAX_REPAIR_ROUNDS,
    validate_fn: ValidateFn = validity.validate,
    bisim_fn: BisimFn = validity.bisim_equivalent,
    require_guard_sidecar: bool = False,
    progress: Optional[ProgressFn] = None,
) -> list[RunRecord]:
    """Run the T+R loop for one item, return one RunRecord per attempt.

    `initial_draft`, if given, is used as the k=1 attempt instead of calling
    `drafter.draft(intent, 1)` — lets a caller reuse the k=1 slot of an
    already-drawn best-of-k batch instead of spending a second draft call
    (run_t0.py does this: best-of-k phase draws k candidates, the repair
    phase starts the chain from candidate #1).

    Terminates as soon as an attempt validates, or after `max_rounds`
    repair attempts, whichever comes first — never more than
    `1 + max_rounds` RunRecords are returned.

    Every attempt text may embed a `.refn` guard sidecar after the
    `split_guard_sidecar` sentinel (SEAM_TRAINING_EXECUTION_PLAN.md §2:
    "Scribble `.scr` + `.refn` guard sidecar when the intent implies value
    constraints") — `validate_fn`/`bisim_fn` always run against the
    protocol-only half (real Scribble has no notion of the sidecar); the
    RunRecord's `draft` field keeps the FULL text (protocol + sidecar, if
    any) so guard-co-emission can be measured downstream from the JSONL
    without re-deriving it (see run_t0.py's `guard_co_emission_rate`).
    """
    if initial_draft is not None:
        current = initial_draft
    else:
        drafted = drafter.draft(intent, 1)
        if len(drafted) != 1:
            raise ValueError(
                f"drafter.draft(intent, 1) returned {len(drafted)} texts, "
                f"expected exactly 1")
        current = drafted[0]

    def emit(stage: str, **detail) -> None:
        if progress is not None:
            progress(stage, detail)

    def validate_attempt(text: str, attempt: int) -> tuple[bool, str]:
        protocol_text, refn = split_guard_sidecar(text)
        emit("validation_started", attempt=attempt,
             protocol_chars=len(protocol_text), guards=bool(refn))
        valid, msg = validate_fn(protocol_text)
        if valid and require_guard_sidecar and not refn:
            valid, msg = False, (
                "intent-loop: missing required refinement-guard sidecar; "
                f"append {GUARD_SIDECAR_SENTINEL} and at least one "
                "<MessageLabel>.<field> :: <predicate> guard")
        emit("validation_result", attempt=attempt, valid=valid,
             verdict=("accepted" if valid else "rejected"),
             validator_message=msg[:500])
        return valid, msg

    valid, msg = validate_attempt(current, 1)
    attempts: list[tuple[str, bool, str]] = [(current, valid, msg)]
    rounds_used = 0
    while not valid and rounds_used < max_rounds:
        emit("repair_started", attempt=rounds_used + 2,
             previous_error=msg[:500])
        current = drafter.repair(intent, current, msg)
        emit("repair_completed", attempt=rounds_used + 2,
             draft_chars=len(current))
        valid, msg = validate_attempt(current, rounds_used + 2)
        rounds_used += 1
        attempts.append((current, valid, msg))

    final_rounds = min(rounds_used, max_rounds)
    ts = _now()
    records: list[RunRecord] = []
    for i, (text, ok, vmsg) in enumerate(attempts, start=1):
        bisim: Optional[bool] = None
        if ok and gold is not None:
            proto_only, _r = split_guard_sidecar(text)
            bisim, _reason = bisim_fn(proto_only, gold)
        usage = estimate_usage(drafter, intent, text)
        records.append(RunRecord(
            system=system, model=usage.model, item_id=item_id, split=split,
            k=i, draft=text, valid=ok, validator_msg=vmsg, bisim=bisim,
            repair_rounds=final_rounds, tokens_in=usage.tokens_in,
            tokens_out=usage.tokens_out, usd=usage.usd, ts=ts))
    return records
