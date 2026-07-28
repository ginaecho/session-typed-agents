#!/usr/bin/env python3
"""check_publish_flow.py — deterministic demo of the typed publish channel:
the fence-to-field move for one irreversible outward act (a git push).

What it shows, with no agents and no statistics: when the only path to
`git push` is a protocol message, the branch-name rules from the registry
(tools/rules/AGENT_RULES.yaml) are checked at the call site as a payload
refinement — the forbidden push is refused BEFORE delivery, with the
registry's remediation shown, and the corrected push completes the session
to its accepting state. Compare .githooks/pre-push, which protects only
clones that enabled it: the 2026-07-25 session ran under a global hooks
path a repo-local fence never touches
(docs/reference/SESSION_RECORD_2026-07-25.md §7).

Predictions for this script were registered before it ran:
docs/predictions/SPEC_TO_GATE_PREREGISTRATION.md P4 and P5.

Usage: python experiments/cases/publish_flow/check_publish_flow.py
Exit 0 = all registered expectations hold, 1 = any failed.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

import yaml  # noqa: E402

from stjp_core.compiler.efsm_parser import get_all_efsms  # noqa: E402
from stjp_core.compiler.refinement_checker import (  # noqa: E402
    load_refinements_for_protocol)
from stjp_core.monitor.monitor import SessionMonitor, TraceEvent  # noqa: E402

CASE = Path(__file__).resolve().parent
SCR = CASE / "protocols" / "v1.scr"
ROLES = ["Agent", "Repo"]
PROTOCOL = "PublishFlow"


def remediation_for(subject: str) -> list[str]:
    doc = yaml.safe_load((REPO / "tools" / "rules" / "AGENT_RULES.yaml")
                         .read_text(encoding="utf-8"))
    return [r["remediation"] for r in doc["rules"]
            if r["subject"] == subject and r.get("remediation")]


def main() -> int:
    failures: list[str] = []

    # 1. Static validation with the real Scribble compiler (P4).
    scribble_dir = REPO / "scribble-java" / "scribble-dist" / "target"
    if scribble_dir.exists():
        from stjp_core.compiler.validator import ScribbleValidator
        ok, err = ScribbleValidator().validate_protocol(SCR)
        print(f"[P4] Scribble validation: {'PASSED' if ok else 'FAILED: ' + err}")
        if not ok:
            failures.append("P4: protocol did not validate")
    else:
        print("[P4] Scribble compiler not built here — build scribble-java "
              "with Maven and unzip scribble-dist (see stjp_core/CLAUDE.md); "
              "validation SKIPPED, not passed")
        failures.append("P4: compiler unavailable (skipped is not passed)")

    # 2. Project and load the gate pieces (pure Python).
    efsms = get_all_efsms(SCR, PROTOCOL, ROLES)
    refn = load_refinements_for_protocol(SCR)
    delivered: list[TraceEvent] = []
    refusals: list[str] = []

    def attempt_send(sender: str, receiver: str, label: str, payload: str):
        """The call-site gate: the refinement decides BEFORE delivery, the
        same placement GAP_CLOSED.md compiles into projected send tools."""
        r = refn.get((sender, receiver, label))
        if r is not None:
            ok, err = r.check(payload)
            if not ok:
                refusals.append(err)
                print(f"  gate REFUSED pre-delivery: {label}({payload!r}) — {err}")
                for fix in remediation_for("branch_name"):
                    print(f"    remediation: {fix}")
                return False
        delivered.append(TraceEvent(sender=sender, receiver=receiver,
                                    label=label, payload=payload,
                                    step=len(delivered)))
        print(f"  delivered: {label}({payload!r}) {sender} -> {receiver}")
        return True

    # 3. The scenario: forbidden push refused, corrected push completes.
    print("\nAttempt 1 — the platform-assigned branch name:")
    sent = attempt_send("Agent", "Repo", "PushRequest",
                        "claude/stjp-opus5-improvements-1qri4e")
    print("\nAttempt 2 — the corrected branch name:")
    attempt_send("Agent", "Repo", "PushRequest", "gc/stjp-opus5-improvements")
    attempt_send("Repo", "Agent", "PushAck", "pushed")

    # 4. Conformance of the delivered trace.
    sm = SessionMonitor(efsms, refn)
    verdicts = sm.process_trace(delivered)
    conformant = sm.is_globally_conformant(verdicts)
    final_states = {r: v.final_state for r, v in verdicts.items()}
    print(f"\ndelivered trace: {len(delivered)} events; "
          f"globally conformant: {conformant}; final states: {final_states}")

    # 5. Grade P5.
    if sent:
        failures.append("P5: the forbidden push was delivered")
    if len(refusals) != 1:
        failures.append(f"P5: expected exactly 1 refusal, got {len(refusals)}")
    if not conformant:
        failures.append("P5: corrected session not conformant")
    if any(not v.conformant for v in verdicts.values()):
        failures.append("P5: violations recorded in the delivered trace")

    print()
    if failures:
        for f in failures:
            print(f"FAIL {f}")
    else:
        print("PASS P5: forbidden push refused pre-delivery (1 refusal, "
              "with remediation); corrected push conformant to the "
              "accepting state")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
