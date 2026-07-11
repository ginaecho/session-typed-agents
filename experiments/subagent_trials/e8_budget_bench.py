"""E8 — cumulative-violation detection (Prototype 1, deterministic portion).

Seeded, reproducible trace corpus for the `budget_run` case: per-message limit
$5,000 (a normal payload guard), session budget $10,000 (a STATEFUL ledger
invariant). Every debit is individually legal (<= $5k); an overrun is only
visible in the cumulative total.

Three arms, exactly as pre-registered:
  (a) current STJP — per-message payload guard only (this is the shipped system)
  (b) +stateful invariants, OBSERVE — the ledger flags the crossing message
  (c) +stateful invariants, GATE   — the ledger rejects the crossing pre-delivery

Metrics: detection rate on overrun traces, false positives on legal traces,
crossing-exactness (does the flag land at the exact crossing message?), and for
the gate arm the number of post-budget debits delivered (must be 0).

Deterministic: a fixed-seed PRNG generates the corpus, so re-runs are identical
(no wall-clock / no unseeded randomness).

Run:  python experiments/subagent_trials/e8_budget_bench.py --n 50 --out experiments/reports/n100/e8
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from stjp_core.compiler.refinement_checker import (   # noqa: E402
    parse_session_ledger, Refinement)
from cases import CASES                                # noqa: E402

PER_MSG_LIMIT = 5000.0
BUDGET = 10000.0


def _debits_overrun(rng) -> tuple[list[float], int]:
    """A sequence of individually-legal debits (<= limit) whose cumulative sum
    crosses BUDGET. Returns (debits, crossing_index 1-based)."""
    debits: list[float] = []
    total = 0.0
    while True:
        d = float(rng.randrange(1000, int(PER_MSG_LIMIT) + 1, 500))  # 1000..5000
        debits.append(d)
        total += d
        if total > BUDGET:
            return debits, len(debits)


def _debits_legal(rng) -> list[float]:
    """A sequence of individually-legal debits whose cumulative sum stays <=
    BUDGET (a genuine legal run, of random length)."""
    debits: list[float] = []
    total = 0.0
    # random target length 1..4 debits, sized to stay under budget
    k = rng.randint(1, 4)
    remaining = BUDGET
    for _ in range(k):
        hi = min(PER_MSG_LIMIT, remaining)
        if hi < 1000:
            break
        d = float(rng.randrange(1000, int(hi) + 1, 500))
        debits.append(d)
        remaining -= d
    return debits or [1000.0]


def _per_message_guard():
    r = Refinement(sender="Requester", receiver="Approver", label="Debit",
                   declared_type="float", predicates=[f"x <= {int(PER_MSG_LIMIT)}"])
    return r


def eval_arm_a(debits) -> tuple[bool, int]:
    """Arm (a): per-message guard only. Flags iff some single debit > limit.
    Returns (flagged, crossing_step_or_-1)."""
    g = _per_message_guard()
    for i, d in enumerate(debits, 1):
        ok, _ = g.check(str(d))
        if not ok:
            return True, i
    return False, -1


def eval_arm_ledger(debits, gate: bool):
    """Arms (b)/(c): the stateful ledger. Returns (flagged, crossing_step,
    delivered_post_budget_count)."""
    ledger = parse_session_ledger(CASES["budget_run"]["refn"])
    ledger.reset()
    flagged_step = -1
    delivered_post_budget = 0
    committed_before_flag = 0.0
    for i, d in enumerate(debits, 1):
        pre = ledger.values["total_debited"]
        breaches = ledger.step("Debit", str(d), step_no=i, gate=gate)
        if breaches and flagged_step == -1:
            flagged_step = i
        # a debit is "delivered post-budget" if it was actually committed
        # (ledger advanced) despite pushing total over budget
        post = ledger.values["total_debited"]
        if post > BUDGET and post != pre:
            delivered_post_budget += 1
    return (flagged_step != -1), flagged_step, delivered_post_budget


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50, help="traces per class (overrun / legal)")
    ap.add_argument("--seed", type=int, default=20260705)
    ap.add_argument("--out", default="experiments/reports/n100/e8")
    args = ap.parse_args()
    rng = random.Random(args.seed)

    overruns = [_debits_overrun(rng) for _ in range(args.n)]   # (debits, crossing)
    legals = [_debits_legal(rng) for _ in range(args.n)]

    arms = {"a_per_message": {}, "b_ledger_observe": {}, "c_ledger_gate": {}}

    # detection on overrun traces + crossing exactness
    for key, is_gate, is_ledger in [("a_per_message", False, False),
                                    ("b_ledger_observe", False, True),
                                    ("c_ledger_gate", True, True)]:
        detected = exact = post_budget = 0
        for debits, crossing in overruns:
            if is_ledger:
                flagged, step, delivered = eval_arm_ledger(debits, gate=is_gate)
                post_budget += delivered
            else:
                flagged, step = eval_arm_a(debits)
            if flagged:
                detected += 1
                if step == crossing:
                    exact += 1
        # false positives on legal traces
        fp = 0
        for debits in legals:
            if is_ledger:
                flagged, _, _ = eval_arm_ledger(debits, gate=is_gate)
            else:
                flagged, _ = eval_arm_a(debits)
            fp += int(flagged)
        arms[key] = {
            "detected_overruns": f"{detected}/{args.n}",
            "detection_rate": round(detected / args.n, 3),
            "crossing_exact": f"{exact}/{detected}" if detected else "0/0",
            "false_positives": f"{fp}/{args.n}",
            "post_budget_debits_delivered": post_budget,
        }

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    summary = {
        "benchmark": "E8 — cumulative-violation detection (budget_run)",
        "seed": args.seed, "n_per_class": args.n,
        "per_message_limit": PER_MSG_LIMIT, "session_budget": BUDGET,
        "arms": arms,
        "note": ("Every debit is individually <= the per-message limit, so the "
                 "overrun is invisible to any per-message guard by construction. "
                 "Arm (a) is the shipped STJP; its 0 detections are the motivation."),
    }
    (out / "e8_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"\nwrote {out}/e8_summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
