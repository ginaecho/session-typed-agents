"""E9 (deterministic parts) — deadlock replay + safety non-regression.

Prototype 2's tolerant gate admits ONE decidable, provably-safe relaxation:
independent-receive output anticipation (`check_subtype.anticipable`). This
script measures, WITHOUT any LLM:

  1. DEADLOCK REPLAY — of the 19 genuine gated-arm deadlocks (17 escrow C+min,
     2 STJP), how many of the sends the gate REJECTED would have been admitted
     as safe anticipations? This decomposes the deadlocks into "gate too strict"
     (rescuable) vs "agent gave up" (an absent send the gate never saw).

  2. SAFETY NON-REGRESSION — an illegal-send corpus (off-protocol labels / wrong
     peers) must be admitted by the tolerant gate exactly ZERO times: the
     fragment is provably inside the precise relation, so any admission is a bug.

Run:  python experiments/subagent_trials/e9_analysis.py --out experiments/reports/n100/e9
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.pop("JAVA_TOOL_OPTIONS", None)
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from stjp_core.compiler.efsm_parser import get_all_efsms                # noqa: E402
from stjp_core.compiler.check_subtype import anticipable               # noqa: E402
from cases import CASES                                                # noqa: E402


def _escrow_efsms():
    c = CASES["escrow_trade"]
    td = tempfile.mkdtemp()
    scr = Path(td) / f"{c['module']}.scr"
    scr.write_text(c["protocol"], encoding="utf-8")
    return get_all_efsms(scr, c["protocol_name"], c["roles"])


def _state_at(efsm, role, trace, upto_round):
    """Reconstruct `role`'s EFSM cursor from delivered messages before a round."""
    st = efsm.initial_state
    for e in trace:
        if not e["delivered"] or e["round"] >= upto_round:
            continue
        if e["sender"] == role:
            direction, peer = "send", e["receiver"]
        elif e["receiver"] == role:
            direction, peer = "receive", e["sender"]
        else:
            continue
        for t in efsm.transitions_from(st):
            if t.direction == direction and t.peer == peer and t.label == e["label"]:
                st = t.target
                break
    return st


def deadlock_replay(efsms) -> dict:
    trials = []
    for arm in ["min_gate", "stjp"]:
        for d in sorted(Path(".trial_state/ladder_run/escrow_trade").glob(f"{arm}__trial_*")):
            t = json.loads((d / "state.json").read_text())["trials"][0]
            if t["status"] == "success":
                continue
            rescuable = 0
            rej_detail = []
            for rj in t["rejections"]:
                role = rj["role"]
                efsm = efsms.get(role)
                if efsm is None:
                    continue
                st = _state_at(efsm, role, t["trace"], rj["round"])
                anticip = anticipable(efsm, st, rj["to"], rj["label"])
                rescuable += int(anticip)
                rej_detail.append({"role": role, "to": rj["to"], "label": rj["label"],
                                   "state": st, "anticipable": anticip})
            trials.append({
                "trial": f"{arm}/{d.name}", "status": t["status"],
                "delivered": len([e for e in t["trace"] if e["delivered"]]),
                "n_rejections": len(t["rejections"]),
                "rescuable_rejections": rescuable,
                "rejections": rej_detail,
            })
    # Honest labels: "has_anticipable_rejection" is a mechanical type-level fact
    # (the gate rejected a send that precise subtyping would admit). It does NOT
    # mean the session would reach goal — the root cause may be an ABSENT send
    # elsewhere (agent give-up), and admitting the anticipation may relax a
    # business ordering (e.g. escrow's pay-before-ship). The E9 report
    # interprets; the JSON only records the mechanical measurement.
    for tr in trials:
        tr["has_anticipable_rejection"] = tr["rescuable_rejections"] > 0
    with_anticip = sum(1 for tr in trials if tr["has_anticipable_rejection"])
    return {"n_deadlocks": len(trials),
            "deadlocks_with_anticipable_rejection": with_anticip,
            "deadlocks_gate_correctly_held": len(trials) - with_anticip,
            "trials": trials}


def safety_nonregression(efsms) -> dict:
    """Illegal sends (off-protocol label, or a legal label to the WRONG peer)
    must NEVER be anticipable. 0 admitted = non-regression holds."""
    roles = list(efsms)
    illegal = []
    # off-protocol labels at each role's initial state
    for role, e in efsms.items():
        for bogus in ["Hack", "Leak", "Bypass"]:
            for peer in roles:
                if peer != role:
                    illegal.append((role, e.initial_state, peer, bogus))
    # legal labels sent to the WRONG peer (peer-swap)
    for role, e in efsms.items():
        for t in e.transitions:
            if t.direction == "send":
                for peer in roles:
                    if peer != role and peer != t.peer:
                        illegal.append((role, t.source, peer, t.label))
    admitted = sum(1 for (role, st, peer, label) in illegal
                   if anticipable(efsms[role], st, peer, label))
    return {"illegal_sends_tested": len(illegal), "admitted_by_tolerant_gate": admitted,
            "non_regression_holds": admitted == 0}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="experiments/reports/n100/e9")
    args = ap.parse_args()
    efsms = _escrow_efsms()

    replay = deadlock_replay(efsms)
    safety = safety_nonregression(efsms)
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    summary = {"benchmark": "E9 deterministic — deadlock replay + safety non-regression",
               "generated": "2026-07-05", "deadlock_replay": replay, "safety": safety}
    (out / "e9_deterministic.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("DEADLOCK REPLAY:")
    print(f"  {replay['n_deadlocks']} genuine deadlocks; "
          f"with_anticipable_rejection={replay['deadlocks_with_anticipable_rejection']}, "
          f"gate_correctly_held={replay['deadlocks_gate_correctly_held']}")
    for tr in replay["trials"]:
        print(f"    {tr['trial']}: delivered={tr['delivered']} rej={tr['n_rejections']} "
              f"anticipable={tr['rescuable_rejections']} "
              f"-> {'anticipable-rejection' if tr['has_anticipable_rejection'] else 'gate-correctly-held'}")
    print("SAFETY NON-REGRESSION:")
    print(f"  illegal sends tested={safety['illegal_sends_tested']}, "
          f"admitted={safety['admitted_by_tolerant_gate']}, "
          f"holds={safety['non_regression_holds']}")
    print(f"\nwrote {out}/e9_deterministic.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
