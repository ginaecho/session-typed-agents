#!/usr/bin/env python3
"""sweep_driver.py — one driver loop for BOTH arms of the agent_lit_sweep case.

Why this exists instead of `scripts/case_runner.py`: the canonical harness has
no tool calling ("There is no data source. No tool calling." —
experiments/CLAUDE.md) and drives Azure Foundry agents. A literature sweep needs
role-players that can actually search, so this case is driven by an operator
loop over search-capable agents instead. Everything downstream of a message —
the monitor, the ledger, the metrics — is the repo's own code.

The point of a single driver: the two arms must differ ONLY in configuration,
never in how much operator attention they get. So both arms run through the same
three commands, and the arm flag decides three things and nothing else:

    arm                    turn order        enforcement   instruction to role
    bare                   fixed rotation    observe only  prose intent
    min_llmvalid_sched     EFSM enabled set  gate (block)  projected local type

In `bare` the monitor and ledger still WATCH (so budget overrun and off-contract
messages can be measured) but never block. That mirrors the canonical harness,
which monitors bare arms against the protocol whose labels they were never shown
— the violations are the measurement, not a failure of the agents.

Commands
--------
    init   --arm ARM --trial N --assignment "..."   start a trial
    next   --arm ARM --trial N                      whose turn, and what to tell them
    submit --arm ARM --trial N --sender S --label L --payload P [--searches K]
    status --arm ARM --trial N
    metrics --arm ARM --trial N                     the four pre-registered metrics

State and traces live in runs/<arm>/trial<N>/ next to this file.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import fields
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "experiments" / "baselines"))

from stjp_core.compiler.efsm_parser import get_all_efsms                  # noqa: E402
from stjp_core.compiler.refinement_checker import (                       # noqa: E402
    load_refinements_for_protocol)
from stjp_core.monitor.monitor import SessionMonitor, TraceEvent, Violation  # noqa: E402

PROTO = HERE / "protocols" / "v1.scr"
NAME = "LiteratureSweep"
ROLES = ["Coordinator", "Scout", "Verifier"]
ARMS = ("bare", "min_llmvalid_sched")
TERMINAL = "Report"
MAX_STEPS = 40


# ── case text ────────────────────────────────────────────────────────────────

def _case() -> dict:
    import yaml
    return yaml.safe_load((HERE / "case.yaml").read_text())


def _roles_block(case: dict) -> str:
    rd = case.get("role_descriptions") or {}
    return "Roles on this team:\n" + "\n".join(
        f"  {r}: {d}" for r, d in rd.items())


def instruction_for(role: str, arm: str, assignment: str) -> str:
    """What this role is told. The ONLY prompt difference between the arms.

    Both arms get the intent and the role descriptions, so the measured variable
    is purely "what protocol information comes on top" — the same fairness rule
    the finance case uses.
    """
    case = _case()
    head = (f"You are {role} on a literature-sweep team.\n\n"
            f"{_roles_block(case)}\n\nTask:\n{case['intent'].strip()}\n\n"
            f"Search assignment:\n{assignment.strip()}\n")

    if arm == "bare":
        return head + (
            "\nCoordinate with the others however you judge best. Reply with ONE "
            'JSON object: {"send_to":"<Role|null>","label":"<a label you choose>",'
            '"payload":"<value>","searches":<how many search calls you just made>,'
            '"rationale":"<1 line>"}. Use send_to=null and label="WAIT" if you '
            "have nothing to send.\n")

    # Compiled arm: the projected local type, built by the repo's own builder.
    from instructions import build_spec_minimal_instructions

    class _C:                       # the shape build_spec_minimal_instructions needs
        protocol_path = PROTO
        protocol_name = NAME
        roles = ROLES
        terminal_label = TERMINAL

        def __init__(self, c):
            self._c = c

        def __getattr__(self, k):
            return self._c.get(k)

    contract = build_spec_minimal_instructions(_C(case), role)
    return head + "\nYour contract (derived from the validated protocol):\n" + contract


# ── trial state ──────────────────────────────────────────────────────────────

def _dir(arm: str, trial: int) -> Path:
    return HERE / "runs" / arm / f"trial{trial}"


def _load(arm: str, trial: int) -> dict:
    p = _dir(arm, trial) / "state.json"
    if not p.exists():
        sys.exit(f"no trial at {p} — run `init` first")
    return json.loads(p.read_text())


def _save(arm: str, trial: int, st: dict) -> None:
    d = _dir(arm, trial)
    d.mkdir(parents=True, exist_ok=True)
    (d / "state.json").write_text(json.dumps(st, indent=2))
    with (d / "events.jsonl").open("w") as f:
        for e in st["events"]:
            f.write(json.dumps(e) + "\n")


def _fresh_monitor(arm: str) -> SessionMonitor:
    """A monitor over the accepted trace. Rebuilt from the trace each time
    rather than persisted, so the trace stays the only state that matters.

    What the gate blocks, measured (see the probe in this case's notes):
    a message to a peer the protocol has no edge to (`unexpected_peer`), a
    label the protocol does not contain or that belongs to another role
    (`off_protocol`), a payload failing its refinement (`refinement_failed`),
    and a spend that would overdraw the budget ledger.

    What it deliberately does NOT block: a message that merely arrives before
    something it could legally follow. The monitor records the missing message
    as a *deferred obligation* and only reports it unfulfilled at trace end,
    because in an asynchronous setting that message may still be in flight.
    Multiparty session types permit permutation of causally independent
    actions, so blocking on arrival order would be wrong, not stricter.
    """
    efsms = get_all_efsms(PROTO, NAME, ROLES)
    refn = load_refinements_for_protocol(PROTO)
    return SessionMonitor(efsms, refn, gate=(arm == "min_llmvalid_sched"))


def _accepted_events(st: dict) -> list[TraceEvent]:
    return [TraceEvent(sender=e["sender"], receiver=e["receiver"],
                       label=e["label"], payload=str(e.get("payload", "")),
                       step=e["step"])
            for e in st["events"] if not e.get("rejected")]


# ── commands ─────────────────────────────────────────────────────────────────

def cmd_init(a) -> int:
    st = {"arm": a.arm, "trial": a.trial, "assignment": a.assignment,
          "events": [], "searches_spent": 0, "rr_index": 0, "closed": False}
    _save(a.arm, a.trial, st)
    d = _dir(a.arm, a.trial)
    for role in ROLES:
        (d / f"{role}.instruction.md").write_text(
            instruction_for(role, a.arm, a.assignment))
    print(f"initialised {a.arm} trial{a.trial} at {d}")
    print(f"instructions written for {', '.join(ROLES)}")
    return 0


def cmd_next(a) -> int:
    st = _load(a.arm, a.trial)
    if st["closed"]:
        print("TRIAL CLOSED"); return 0
    if len(st["events"]) >= MAX_STEPS:
        print("STEP CAP REACHED — close the trial as incomplete"); return 0

    sm = _fresh_monitor(a.arm)
    sm.process_trace(_accepted_events(st))

    if a.arm == "min_llmvalid_sched":
        # EFSM claim predicate: only roles with an enabled SEND may act.
        enabled = []
        for role, mon in sm.monitors.items():
            if any(t.direction == "send"
                   for t in mon.efsm.transitions_from(mon.current_state)):
                enabled.append(role)
        if not enabled:
            print("NO ENABLED SENDER — deadlock (cannot happen for a valid type)")
            return 1
        turn = enabled[0]
        print(f"ENABLED SET: {enabled}   (taking {turn})")
    else:
        turn = ROLES[st["rr_index"] % len(ROLES)]
        print(f"FIXED ROTATION: taking {turn}")

    print(f"TURN: {turn}")
    print(f"STEP: {len(st['events']) + 1} of {MAX_STEPS}")
    print(f"SEARCHES SPENT: {st['searches_spent']}")
    print(f"\n--- HISTORY (as {turn} sees it) ---")
    if not st["events"]:
        print("(nothing yet)")
    for e in st["events"]:
        if e.get("rejected"):
            if e["sender"] == turn:
                print(f"  [step {e['step']}] YOUR MESSAGE WAS REJECTED: "
                      f"{e['label']} -> {e['receiver']} :: {e['reject_reason']}")
            continue
        if turn in (e["sender"], e["receiver"]):
            who = "you ->" if e["sender"] == turn else f"{e['sender']} ->"
            print(f"  [step {e['step']}] {who} {e['receiver']}: "
                  f"{e['label']}({e.get('payload','')})")
    return 0


def cmd_submit(a) -> int:
    st = _load(a.arm, a.trial)
    if st["closed"]:
        sys.exit("trial already closed")

    step = len(st["events"]) + 1
    receiver = a.receiver
    ev = TraceEvent(sender=a.sender, receiver=receiver, label=a.label,
                    payload=str(a.payload), step=step)

    sm = _fresh_monitor(a.arm)
    sm.process_trace(_accepted_events(st))
    before = len(sm.ledger_violations) if sm.ledger else 0

    verdicts = sm.process_trace(_accepted_events(st) + [ev])
    viols = [v for v in verdicts.values() if getattr(v, "violations", None)]
    new_ledger = (sm.ledger_violations[before:] if sm.ledger else [])

    # Which problems does this message have?
    problems: list[str] = []
    for vd in verdicts.values():
        for v in getattr(vd, "violations", []) or []:
            if v.event is not None and v.event.step == step:
                problems.append(f"{v.violation_type.value}: {v.message}")
    for lv in new_ledger:
        problems.append(lv.message)

    gate = (a.arm == "min_llmvalid_sched")
    rejected = bool(problems) and gate

    rec = {"step": step, "sender": a.sender, "receiver": receiver,
           "label": a.label, "payload": a.payload,
           "searches": a.searches, "problems": problems,
           "rejected": rejected}
    if rejected:
        rec["reject_reason"] = " | ".join(problems)
    st["events"].append(rec)

    # Searches are spent whether or not the message was accepted ONLY in bare:
    # in the compiled arm a rejected SearchSpend never authorises the calls.
    if not rejected:
        st["searches_spent"] += int(a.searches or 0)
    elif not gate:
        st["searches_spent"] += int(a.searches or 0)

    if not rejected:
        st["rr_index"] += 1
    if a.label == TERMINAL and not rejected:
        st["closed"] = True

    _save(a.arm, a.trial, st)
    print("REJECTED (not delivered)" if rejected else "ACCEPTED")
    for p in problems:
        print(f"  ! {p}")
    if st["closed"]:
        print("TRIAL CLOSED (terminal message)")
    return 0


def cmd_status(a) -> int:
    st = _load(a.arm, a.trial)
    print(json.dumps({k: v for k, v in st.items() if k != "events"}, indent=2))
    print(f"events: {len(st['events'])} "
          f"({sum(1 for e in st['events'] if e.get('rejected'))} rejected)")
    return 0


def cmd_metrics(a) -> int:
    """The four pre-registered metrics, computed from the trace only."""
    st = _load(a.arm, a.trial)
    acc = [e for e in st["events"] if not e.get("rejected")]

    # M1 duplicate-claim rate: a Candidate (or, in bare, any message whose
    # payload names an already-claimed identifier) submitted more than once.
    seen: set[str] = set()
    subs = dups = 0
    for e in acc:
        key = str(e.get("payload", "")).strip().lower()
        if not key:
            continue
        is_claim = e["label"] in ("Candidate",) or (
            a.arm == "bare" and e["receiver"] != e["sender"] and len(key) > 8)
        if not is_claim:
            continue
        subs += 1
        if key in seen:
            dups += 1
        seen.add(key)
    m1 = (dups / subs) if subs else None

    # M2 budget overrun: lowest the budget reached, and any spend past zero.
    sm = _fresh_monitor(a.arm)
    sm.process_trace(_accepted_events(st))
    left = sm.ledger.values["searches_left"] if sm.ledger else None
    declared = sum(int(e.get("searches") or 0) for e in acc)
    m2 = {"searches_left_by_ledger": left,
          "declared_searches_total": declared,
          "overran": (left is not None and left < 0) or declared > 12}

    # M3 unverified-claim rate: claims recorded without a Confirmed verdict.
    confirmed = {str(e.get("payload", "")).strip().lower()
                 for e in acc if e["label"] == "Confirmed"}
    reported = [e for e in acc if e["label"] == TERMINAL]
    m3 = {"confirmed_count": len(confirmed),
          "report_present": bool(reported),
          "note": "identifier resolution is graded by hand against the report text"}

    print(json.dumps({
        "arm": a.arm, "trial": a.trial,
        "steps": len(st["events"]),
        "rejected": sum(1 for e in st["events"] if e.get("rejected")),
        "closed": st["closed"],
        "M1_duplicate_claim_rate": m1,
        "M1_submissions": subs, "M1_duplicates": dups,
        "M2_budget": m2,
        "M3_verification": m3,
        "M4_tokens": "supplied externally per trial",
    }, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--arm", required=True, choices=ARMS)
        p.add_argument("--trial", required=True, type=int)

    p = sub.add_parser("init"); common(p); p.add_argument("--assignment", required=True)
    p = sub.add_parser("next"); common(p)
    p = sub.add_parser("status"); common(p)
    p = sub.add_parser("metrics"); common(p)
    p = sub.add_parser("submit"); common(p)
    p.add_argument("--sender", required=True, choices=ROLES)
    p.add_argument("--receiver", required=True, choices=ROLES)
    p.add_argument("--label", required=True)
    p.add_argument("--payload", default="")
    p.add_argument("--searches", type=int, default=0)

    a = ap.parse_args()
    return {"init": cmd_init, "next": cmd_next, "submit": cmd_submit,
            "status": cmd_status, "metrics": cmd_metrics}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
