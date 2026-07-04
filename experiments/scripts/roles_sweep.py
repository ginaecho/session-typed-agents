"""roles_sweep.py — does it scale? (BENCHMARK_PLAN_V2 §7 / E6)

Grows the same pipeline shape from 2 to 10 roles and measures the STRUCTURAL
coordination overhead — a deterministic proxy for tokens-per-goal that needs no
LLM:

  global-text proxy  every role re-reads the WHOLE protocol on every turn, so
                     cost ~ (full protocol size) × (number of role-turns).
  STJP proxy         the EFSM scheduler polls only the ONE enabled sender per
                     step, and each role sees only its projected local
                     contract; cost ~ sum over scheduled steps of that step's
                     sender-contract size.

These are real numbers (chars, scheduled polls) from real Scribble projections;
the actual token-per-delivered-goal figure needs live runs and is MEASUREMENT
PENDING. The proxy predicts the SHAPE (global-text blows up ~quadratically,
STJP grows gently) that the token curve should confirm.

    python experiments/scripts/roles_sweep.py --max-roles 10 -o experiments/reports/e6
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))

from stjp_core.compiler.validator import ScribbleValidator          # noqa: E402
from stjp_core.compiler.efsm_parser import get_all_efsms            # noqa: E402
from gen_corpus import pipeline                                     # noqa: E402
import random


def _contract_chars(efsm) -> int:
    """Size of a role's projected local contract (one line per transition)."""
    return sum(len(f"{t.source}:{t.direction}:{t.peer}:{t.label}:{t.target}")
               for t in efsm.transitions) + 40  # header overhead


def measure(n_roles: int, workdir: Path, rng) -> dict:
    text = pipeline(f"sweep_{n_roles}", n_roles, rng)
    scr = workdir / f"sweep_{n_roles}.scr"
    scr.write_text(text, encoding="utf-8")
    ok, err = ScribbleValidator().validate_protocol(scr)
    if not ok:
        raise RuntimeError(f"n={n_roles} invalid: {err[:150]}")
    roles = [f"R{i}" for i in range(n_roles)]
    efsms = get_all_efsms(scr, "Pipe", roles)

    n_messages = sum(len(e.transitions) for e in efsms.values()) // 2  # each msg = 1 send+1 recv
    full_chars = len(text)
    # global-text: every role re-reads the whole protocol on each of its turns.
    # a role's #turns ~ its transition count; sum over roles.
    role_turns = {r: len(e.transitions) for r, e in efsms.items()}
    global_text_proxy = full_chars * sum(role_turns.values())
    # STJP: scheduler polls one enabled sender per SEND step; that sender reads
    # only its own contract.
    send_steps = sum(1 for e in efsms.values() for t in e.transitions
                     if t.direction == "send")
    stjp_proxy = sum(_contract_chars(efsms[r]) * sum(
        1 for t in efsms[r].transitions if t.direction == "send")
        for r in roles)
    return {
        "n_roles": n_roles,
        "n_messages": n_messages,
        "scheduled_send_polls": send_steps,
        "global_text_cost_proxy": global_text_proxy,
        "stjp_cost_proxy": stjp_proxy,
        "ratio_global_over_stjp": round(global_text_proxy / stjp_proxy, 1),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-roles", type=int, default=10)
    ap.add_argument("-o", "--out", default="experiments/reports/e6")
    args = ap.parse_args()
    rng = random.Random(1)

    rows = []
    with tempfile.TemporaryDirectory() as td:
        wd = Path(td)
        for n in range(2, args.max_roles + 1):
            rows.append(measure(n, wd, rng))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "roles_sweep.json").write_text(
        json.dumps({"rows": rows,
                    "note": "structural proxy (real); token-per-goal PENDING"},
                   indent=2), encoding="utf-8")

    print(f"\nE6 ROLES SWEEP — structural coordination-cost proxy "
          f"(token-per-goal MEASUREMENT PENDING)\n")
    print(f"{'roles':>5s} {'msgs':>5s} {'polls':>6s} {'global-text':>12s} "
          f"{'STJP':>8s} {'ratio':>7s}")
    print("-" * 48)
    for r in rows:
        print(f"{r['n_roles']:5d} {r['n_messages']:5d} {r['scheduled_send_polls']:6d} "
              f"{r['global_text_cost_proxy']:12d} {r['stjp_cost_proxy']:8d} "
              f"{r['ratio_global_over_stjp']:6.1f}x")
    print(f"\nWROTE {out}/roles_sweep.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
