#!/usr/bin/env python3
"""governed_push.py — execute a real `git push` THROUGH the typed channel
(Stage 4 increment 1 of docs/reference/SPEC_TO_GATE_PLAN.md).

The GovernedPush protocol (experiments/cases/governed_push/protocols/
v1.scr, Scribble-validated) makes "rules loaded before the first push" type
structure: Agent's local type is RulesAck -> RulesOk -> PushRequest, so a
push attempted without the rules step is refused before any git command
runs, and a forbidden branch name is refused by the same registry-derived
payload refinement as the publish_flow case.

Why the gate here is STRICT (in-order), not permutation-tolerant: the
session monitor rightly tolerates asynchronous reordering when *observing*
messages — an earlier message may still be in flight — and therefore only
reports an unfulfilled obligation at trace end (the same semantics recorded
in SESSION_RECORD_2026-07-25.md §8, and re-confirmed while grading P7:
sending PushRequest first yields no call-site violation, only
premature-termination at the end). But executing an irreversible side
effect is a synchronization point: "possibly still in flight" is not good
enough at the moment the effect fires. So this driver advances each role's
projected state machine strictly in delivery order and refuses any send
not enabled in the sender's CURRENT state — the effect-side analogue of
the ledger's blocking (gate) mode. Prediction P7's registered wording
assumed the monitor itself would block; that failed and is graded as
failed — this strict effect gate is the recorded amendment that achieves
the registered outcome (refusal before any git command).

Usage:
  python tools/governed_push.py                       # push current branch to origin
  python tools/governed_push.py --branch B --remote R
  python tools/governed_push.py --skip-rules          # demonstrate the P7 refusal
Exit 0 = push executed and trace conformant; 1 = refused or failed.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import yaml  # noqa: E402

from stjp_core.compiler.efsm_parser import get_all_efsms  # noqa: E402
from stjp_core.compiler.refinement_checker import (  # noqa: E402
    load_refinements_for_protocol)
from stjp_core.monitor.monitor import SessionMonitor, TraceEvent  # noqa: E402

CASE = REPO / "experiments" / "cases" / "governed_push"
SCR = CASE / "protocols" / "v1.scr"
ROLES = ["Agent", "Registry", "Repo"]
PROTOCOL = "GovernedPush"


class StrictChannel:
    """Delivers events only when the sender's projected EFSM has the send
    enabled in its current state AND the payload refinement passes. No
    commuting credit: state advances in delivery order for every role."""

    def __init__(self):
        self.efsms = get_all_efsms(SCR, PROTOCOL, ROLES)
        self.refn = load_refinements_for_protocol(SCR)
        self.state = {r: e.initial_state for r, e in self.efsms.items()}
        self.delivered: list[TraceEvent] = []
        self.refusals: list[str] = []

    def _advance(self, role: str, direction: str, peer: str, label: str) -> bool:
        for t in self.efsms[role].transitions_from(self.state[role]):
            if (t.direction, t.peer, t.label) == (direction, peer, label):
                self.state[role] = t.target
                return True
        return False

    def attempt(self, sender: str, receiver: str, label: str,
                payload: str) -> bool:
        enabled = [(t.label, t.peer) for t in
                   self.efsms[sender].transitions_from(self.state[sender])
                   if t.direction == "send"]
        if (label, receiver) not in enabled:
            self.refusals.append(
                f"off-order: {sender} may not send {label} to {receiver} "
                f"now; enabled sends in its current state: {enabled or '[]'}")
            return False
        r = self.refn.get((sender, receiver, label))
        if r is not None:
            ok, err = r.check(payload)
            if not ok:
                self.refusals.append(f"refinement: {err}")
                return False
        self._advance(sender, "send", receiver, label)
        self._advance(receiver, "receive", sender, label)
        self.delivered.append(TraceEvent(sender=sender, receiver=receiver,
                                         label=label, payload=payload,
                                         step=len(self.delivered)))
        return True


def rules_quote() -> str:
    """The Agent's proof-of-read: quote the git-identity section from the
    live AGENT.md (Registry re-verifies the quote against the file). The
    section HEADING is matched (a '## ' line), not the menu entry that
    merely links to it — quoting the menu would be proof of skimming."""
    import re
    text = (REPO / "AGENT.md").read_text(encoding="utf-8")
    m = re.search(r"^## .*Git identity.*$", text, re.MULTILINE)
    if m is None:
        raise SystemExit("AGENT.md git-identity section heading not found")
    return text[m.start():m.start() + 1800]


def remediation_for(subject: str) -> list[str]:
    doc = yaml.safe_load((REPO / "tools" / "rules" / "AGENT_RULES.yaml")
                         .read_text(encoding="utf-8"))
    return [r["remediation"] for r in doc["rules"]
            if r["subject"] == subject and r.get("remediation")]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--branch", default=None)
    ap.add_argument("--remote", default="origin")
    ap.add_argument("--repo", type=Path, default=REPO,
                    help="repository to push (fixtures use a temp repo)")
    ap.add_argument("--skip-rules", action="store_true",
                    help="skip the RulesAck step (demonstrates the refusal)")
    args = ap.parse_args()

    repo = args.repo.resolve()
    branch = args.branch or subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo,
        capture_output=True, text=True, check=True).stdout.strip()

    ch = StrictChannel()

    def refuse(why_subject: str | None = None) -> int:
        for r in ch.refusals:
            print(f"gate REFUSED pre-execution: {r}")
        off_order = any(r.startswith("off-order") for r in ch.refusals)
        if off_order or not why_subject:
            print("  remediation: load the rules first — AGENT.md "
                  "'Read this first' and 'Git identity' sections; the "
                  "channel requires RulesAck before PushRequest")
        else:
            for fix in remediation_for(why_subject):
                print(f"  remediation: {fix}")
        print("no git command was executed")
        return 1

    if not args.skip_rules:
        quote = rules_quote()
        if not ch.attempt("Agent", "Registry", "RulesAck", quote):
            return refuse()
        live = (REPO / "AGENT.md").read_text(encoding="utf-8")
        if quote not in live:
            print("Registry: quoted rules text does not match the live "
                  "AGENT.md — re-read the rules; no git command executed")
            return 1
        if not ch.attempt("Registry", "Agent", "RulesOk",
                          "verified against live AGENT.md"):
            return refuse()

    if not ch.attempt("Agent", "Repo", "PushRequest", branch):
        return refuse("branch_name")

    print(f"gate PASSED: executing real push of '{branch}' to "
          f"'{args.remote}'")
    r = subprocess.run(["git", "push", "-u", args.remote, branch],
                       cwd=repo, capture_output=True, text=True)
    if r.returncode == 0:
        ch.attempt("Repo", "Agent", "PushAck",
                   (r.stderr.strip().splitlines() or ["pushed"])[-1])
    else:
        ch.attempt("Repo", "Agent", "PushRejected",
                   (r.stderr.strip().splitlines() or ["push failed"])[-1])

    sm = SessionMonitor(ch.efsms, ch.refn)
    verdicts = sm.process_trace(ch.delivered)
    conformant = sm.is_globally_conformant(verdicts)

    log_dir = CASE / "runs"
    log_dir.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log = log_dir / f"trace_{stamp}.jsonl"
    with log.open("w", encoding="utf-8") as f:
        for e in ch.delivered:
            f.write(json.dumps({"step": e.step, "sender": e.sender,
                                "receiver": e.receiver, "label": e.label,
                                "payload": e.payload[:120]}) + "\n")

    ok = r.returncode == 0 and conformant
    print(f"push exit={r.returncode}; trace: {len(ch.delivered)} events, "
          f"globally conformant: {conformant}; log: "
          f"{log.relative_to(REPO)}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
