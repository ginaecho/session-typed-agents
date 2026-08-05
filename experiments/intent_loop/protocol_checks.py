"""protocol_checks.py — the two properties this framework exists to get:
nobody waits forever, and each role fires when it is its turn.

WHAT THIS IS AND IS NOT. The authority on deadlock-freedom is the real
Scribble checker (`eval/validity.validate`), which decides projectability
and circular waits properly. These checks do NOT replace it and must never
be reported as if they had: they run on the drafted IR to give fast,
readable, *pre-validator* answers to two questions a reviewer asks out
loud —

    "can anyone end up waiting for something that never comes?"
    "whose turn is it, at each step?"

They are deliberately conservative. Every finding names the exact
interaction; nothing is inferred beyond what the structure states. When
they and Scribble disagree, Scribble wins — and `TURN` output is a
simulation of the protocol as written, not proof that a runtime will
schedule it that way.

Why bother, given Scribble exists: Scribble answers yes/no about a whole
protocol. It does not tell you WHICH join can starve, or show a reviewer
the turn order to argue with. These do, and they run with no JVM, so they
work while a draft is still being written.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from experiments.intent_loop.protocol_graph import (Choice, Continue, Message,
                                                    ProtocolIR, Recursion,
                                                    parse_protocol)

SEVERITY = ("blocker", "warning", "note")


@dataclass
class Finding:
    severity: str
    kind: str
    where: str                  # message label / branch / loop name
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"severity": self.severity, "kind": self.kind,
                "where": self.where, "detail": self.detail}


# ---------------------------------------------------------------------------
# 1. Deadlock precursors
# ---------------------------------------------------------------------------

def _branch_role_sets(node: Choice) -> list[tuple[str, set[str], set[str]]]:
    """Per branch: (label, roles that send, roles that receive)."""
    out = []
    for label, body in node.branches:
        senders: set[str] = set()
        receivers: set[str] = set()
        for m in _messages(body):
            senders.add(m.sender)
            receivers.update(m.receivers)
        out.append((label, senders, receivers))
    return out


def _messages(body: list[Any]) -> list[Message]:
    found: list[Message] = []
    for node in body:
        if isinstance(node, Message):
            found.append(node)
        elif isinstance(node, Choice):
            for _l, sub in node.branches:
                found.extend(_messages(sub))
        elif isinstance(node, Recursion):
            found.extend(_messages(node.body))
    return found


#: A label that is an identifier rather than a name — `I1`, `R3`,
#: `I3Score`, `M12`. Observed on a protocol that PASSED the real checker:
#: the drafter satisfied Scribble by transcribing interaction ids, and the
#: result says nothing about what the messages mean. Scribble cannot object
#: — it type-checks structure, not meaning — which is exactly why
#: acceptance is a floor and not the goal.
_ID_LABEL = re.compile(r"^(?:[IRGM]\d+|[A-Z]\d+)([A-Z][a-z]+)?$")


def check_label_quality(ir: ProtocolIR) -> list[Finding]:
    """Do the message names say what the messages mean?

    This is the cheapest possible faithfulness signal and it needs no LLM:
    a protocol whose labels are `I1, I2, I3` is structurally fine and
    semantically empty. Reported as a warning per label plus one blocker
    when it is the dominant style, because at that point the protocol has
    stopped describing the user's intent altogether.
    """
    findings: list[Finding] = []
    labels = [m.label for m in ir.messages()]
    if not labels:
        return findings
    idish = [l for l in labels if _ID_LABEL.match(l)]
    for lab in sorted(set(idish)):
        findings.append(Finding(
            "warning", "id-as-label", lab,
            f"`{lab}` is an identifier, not a name. The checker accepts it, "
            f"but a reader cannot tell what is being sent. Name the message "
            f"after the thing it carries (e.g. PreflightVerdict, "
            f"ApprovalGranted)."))
    if len(idish) >= max(2, len(labels) // 2):
        findings.append(Finding(
            "blocker", "meaningless-vocabulary", "protocol",
            f"{len(idish)} of {len(labels)} message labels are identifiers "
            f"({', '.join(sorted(set(idish))[:6])}…). This protocol passes "
            f"the type checker while saying nothing about the user's "
            f"intent — valid is not the same as faithful."))
    return findings


def _norm_role(name: str) -> str:
    """Compare role names the way a reader would, not byte-for-byte.

    The distilled intent names roles in prose ("EDA Notebook Runner",
    "Preflight Checker") but a Scribble identifier cannot contain spaces,
    so the drafter MUST rename them (`EDARunner`, `PreflightChecker`). A
    literal comparison therefore reported every single handover as dropped
    — seven false blockers on a real run. Normalising to alphanumerics
    fixes the common case; a genuine rename to a different word still shows
    up, which is what we want.
    """
    return re.sub(r"[^a-z0-9]", "", name.lower())


def check_grounding(ir: ProtocolIR, interactions: list[dict]) -> list[Finding]:
    """Every message should trace to a declared interaction, and every
    declared interaction should appear as a message.

    Mechanical, no LLM: match on the (sender, receiver) pair, compared by
    normalised role name. A message between a pair the intent never
    mentions is invented structure; a declared handover with no message is
    a requirement silently dropped — and Scribble cannot see either,
    because both protocols type-check equally well.
    """
    findings: list[Finding] = []
    if not interactions:
        return findings
    declared: dict[tuple[str, str], tuple[str, str]] = {}
    for i in interactions:
        s = str(i.get("sender") or i.get("from") or "")
        t = str(i.get("receiver") or i.get("to") or "")
        if not s or not t:
            continue
        # A self-handover is intra-role work, not a message; the protocol
        # is right to omit it (see the interior/boundary distinction).
        if _norm_role(s) == _norm_role(t):
            continue
        declared[(_norm_role(s), _norm_role(t))] = (s, t)

    seen: set[tuple[str, str]] = set()
    for m in ir.messages():
        for rcv in m.receivers:
            pair = (_norm_role(m.sender), _norm_role(rcv))
            seen.add(pair)
            if pair not in declared:
                findings.append(Finding(
                    "warning", "ungrounded-message", m.label,
                    f"{m.sender} → {rcv} is not a handover the intent "
                    f"declares. Either it is invented, or an interaction "
                    f"was missed during interrogation."))
    for pair in sorted(set(declared) - seen):
        s, t = declared[pair]
        findings.append(Finding(
            "blocker", "dropped-interaction", f"{s} → {t}",
            f"the intent declares this handover but the protocol has no "
            f"message for it — a requirement silently dropped. The type "
            f"checker cannot see this: the protocol without it validates "
            f"just as well."))
    return findings


def check_deadlock_precursors(ir: ProtocolIR) -> list[Finding]:
    """Structural patterns that make a role wait for something that may
    never arrive. Each is a *precursor*: a reason to look, and for the
    strongest one, a reason for Scribble to reject."""
    findings: list[Finding] = []
    all_msgs = list(ir.messages())

    # (a) UNINFORMED BRANCH — the classic MPST rejection, and the one the
    # repo's own "unsafe" fixture is built from: a role acts differently
    # per branch but is never told which branch was taken, so it blocks
    # waiting for a message the other side will not send on this path.
    for node in _choices(ir.body):
        per_branch = _branch_role_sets(node)
        active: set[str] = set()
        for _l, s, r in per_branch:
            active |= (s | r)
        for role in sorted(active - {node.at}):
            involved = [(lbl, role in s or role in r)
                        for lbl, s, r in per_branch]
            if not all(x for _lbl, x in involved) and any(
                    x for _lbl, x in involved):
                missing = [lbl or f"branch {i + 1}"
                           for i, (lbl, x) in enumerate(involved) if not x]
                findings.append(Finding(
                    "blocker", "uninformed-branch", f"choice at {node.at}",
                    f"{role} participates in some branches but not in "
                    f"{', '.join(missing)} — on that path it is never told "
                    f"the decision, so it can block waiting for a message "
                    f"that is never sent. Send {role} a message in every "
                    f"branch (even a bare notification)."))

    # (b) UNGUARDED / UNBOUNDED LOOP — a `rec` whose body can reach
    # `continue` without any message, or which has no exit at all, never
    # terminates.
    for rec in _recursions(ir.body):
        body_msgs = _messages(rec.body)
        if not body_msgs:
            findings.append(Finding(
                "blocker", "unguarded-loop", f"rec {rec.name}",
                "the loop body sends no message before continuing — it "
                "spins without progress."))
        elif not _has_exit(rec):
            findings.append(Finding(
                "blocker", "no-loop-exit", f"rec {rec.name}",
                "every path through the loop reaches `continue` — there is "
                "no branch that leaves it, so the session cannot end."))

    # (c) SELF-SEND — a role sending to itself is not a coordination step
    # and usually means intra-role work leaked into the protocol.
    for m in all_msgs:
        if m.sender in m.receivers:
            findings.append(Finding(
                "warning", "self-send", m.label,
                f"{m.sender} sends to itself — that is intra-role work, not "
                f"an interaction; it belongs in the role's interior."))

    # (d) NEVER HEARS / NEVER SPEAKS — a declared role that only sends or
    # only receives is not automatically wrong, but a role that does
    # neither is dead weight in the protocol.
    speaks = {m.sender for m in all_msgs}
    hears = {r for m in all_msgs for r in m.receivers}
    for role in ir.roles:
        if role not in speaks and role not in hears:
            findings.append(Finding(
                "warning", "inert-role", role,
                "declared but never sends or receives anything."))
    return findings


def _choices(body: list[Any]) -> list[Choice]:
    out: list[Choice] = []
    for node in body:
        if isinstance(node, Choice):
            out.append(node)
            for _l, sub in node.branches:
                out.extend(_choices(sub))
        elif isinstance(node, Recursion):
            out.extend(_choices(node.body))
    return out


def _recursions(body: list[Any]) -> list[Recursion]:
    out: list[Recursion] = []
    for node in body:
        if isinstance(node, Recursion):
            out.append(node)
            out.extend(_recursions(node.body))
        elif isinstance(node, Choice):
            for _l, sub in node.branches:
                out.extend(_recursions(sub))
    return out


def _has_exit(rec: Recursion) -> bool:
    """True if some path through the loop body avoids `continue`."""
    def walk(body: list[Any]) -> bool:
        # returns True if this straight-line body ALWAYS continues
        for node in body:
            if isinstance(node, Continue) and node.name == rec.name:
                return True
            if isinstance(node, Choice):
                # the loop only always-continues if EVERY branch does
                if node.branches and all(walk(sub) for _l, sub in node.branches):
                    return True
        return False
    return not walk(rec.body)


# ---------------------------------------------------------------------------
# 2. Turn taking — whose move is it?
# ---------------------------------------------------------------------------

@dataclass
class Turn:
    step: int
    role: str                   # who is enabled to act
    action: str                 # "send Label to X"
    waiting: list[str] = field(default_factory=list)   # who is blocked
    branch: str = ""            # enclosing branch/loop context

    def to_dict(self) -> dict[str, Any]:
        return {"step": self.step, "role": self.role, "action": self.action,
                "waiting": self.waiting, "branch": self.branch}


def turn_order(ir: ProtocolIR, max_steps: int = 120) -> dict[str, Any]:
    """Walk the protocol and report, at each step, exactly one enabled
    sender — the scheduler's view.

    This is the property the framework is for: at any point the protocol
    names WHO may act, so a runtime never has to poll roles whose answer
    cannot advance anything. Everyone else is listed as waiting, which is
    what makes an idle poll visibly wasteful.

    At a `choice`, the deciding role is enabled and the branches are shown
    as alternatives; the walk follows the first branch so the trace stays a
    single readable path, and says so.
    """
    turns: list[Turn] = []
    truncated = False
    branch_points: list[dict] = []

    def walk(body: list[Any], ctx: str) -> None:
        nonlocal truncated
        for node in body:
            if truncated or len(turns) >= max_steps:
                truncated = True
                return
            if isinstance(node, Message):
                waiting = [r for r in ir.roles if r != node.sender]
                turns.append(Turn(len(turns) + 1, node.sender,
                                  f"send {node.label} to "
                                  f"{', '.join(node.receivers)}",
                                  waiting, ctx))
            elif isinstance(node, Choice):
                labels = [lbl or f"branch {i + 1}"
                          for i, (lbl, _b) in enumerate(node.branches)]
                branch_points.append({"at": node.at, "step": len(turns) + 1,
                                      "alternatives": labels})
                turns.append(Turn(len(turns) + 1, node.at,
                                  f"decide: {' | '.join(labels)}",
                                  [r for r in ir.roles if r != node.at], ctx))
                if node.branches:
                    first = labels[0]
                    walk(node.branches[0][1],
                         f"{ctx} / {first}" if ctx else first)
            elif isinstance(node, Recursion):
                walk(node.body, f"{ctx} / loop {node.name}" if ctx
                     else f"loop {node.name}")
            elif isinstance(node, Continue):
                turns.append(Turn(len(turns) + 1, "—",
                                  f"↺ back to loop {node.name}", [], ctx))

    walk(ir.body, "")

    # Idle-poll arithmetic: round-robin asks every role at every step; the
    # protocol names exactly one. This is the scheduling dividend, counted
    # rather than asserted.
    n_roles = max(1, len(ir.roles))
    useful = len([t for t in turns if t.role != "—"])
    round_robin_polls = useful * n_roles
    return {
        "turns": [t.to_dict() for t in turns],
        "branch_points": branch_points,
        "truncated": truncated,
        "roles": ir.roles,
        "polling": {
            "enabled_polls": useful,
            "round_robin_polls": round_robin_polls,
            "wasted_polls": round_robin_polls - useful,
            "note": "one enabled sender per step vs asking every role every "
                    "step; the difference is the calls a protocol-driven "
                    "scheduler never has to make (first branch only when "
                    "the protocol branches)",
        },
    }


# ---------------------------------------------------------------------------
# Combined report
# ---------------------------------------------------------------------------

def check_protocol(protocol_text: str,
                   declared_joins: Optional[list[dict]] = None,
                   interactions: Optional[list[dict]] = None
                   ) -> dict[str, Any]:
    """Structure AND meaning, in one payload for the UI/API.

    Passing the type checker is a floor, not the goal: a protocol of
    `I1, I2, I3` between the right roles is accepted by Scribble and tells
    the user nothing. So the label-quality and grounding checks sit beside
    the deadlock ones, and both can raise blockers.
    """
    ir = parse_protocol(protocol_text)
    findings = check_deadlock_precursors(ir)
    findings += check_label_quality(ir)
    findings += check_grounding(ir, interactions or [])

    # Declared joins (from the distilled checklist) must actually appear as
    # an ordering in the protocol. A join the drafter dropped is precisely
    # the "prose said after both finish, nobody implemented the wait" bug.
    labels = [m.label for m in ir.messages()]
    for j in declared_joins or []:
        iid = str(j.get("iid", "?"))
        waits = [str(w) for w in j.get("waits_for", [])]
        what = str(j.get("what", ""))[:60]
        findings.append(Finding(
            "note", "declared-join", iid,
            f"declared to wait for ALL of {', '.join(waits)} ({what}). "
            f"Confirm the protocol orders it after every one of them — a "
            f"join that exists only in prose is where these documents "
            f"deadlock."))

    blockers = [f for f in findings if f.severity == "blocker"]
    return {
        "findings": [f.to_dict() for f in findings],
        "blockers": len(blockers),
        "warnings": len([f for f in findings if f.severity == "warning"]),
        "verdict": "structural blockers found" if blockers
                   else "no structural blocker found",
        "authority_note": "Deadlock-freedom is decided by the real Scribble "
                          "checker, not here. These are fast pre-validator "
                          "signals: a blocker is a strong reason Scribble "
                          "will reject; their absence proves nothing.",
        "turn_order": turn_order(ir),
        "stats": ir.stats(),
    }
