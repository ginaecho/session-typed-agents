"""efsm_walker.py — vendored EFSM + refinement walker for the hosted container.

Ports stjp_core/compiler/efsm_parser.py's EFSM/Transition dataclasses and
stjp_core/monitor/monitor.py's RoleMonitor/SessionMonitor gate semantics
(choice guards + refinement predicates, the SAME `eval` sandbox as
stjp_core/compiler/refinement_checker.py) so the container can reproduce the
SAME gate decisions WITHOUT importing stjp_core — the Docker build context
for this service is this directory only (see Dockerfile: ``COPY . user_agent/``),
so stjp_core (which lives three levels up, and pulls in azure-ai-agents /
scribble-java paths) is not available at image-build time. This module reads
the pre-computed artifacts/efsm.json + artifacts/refinements.json written by
experiments/scripts/build_hosted_artifacts.py instead of parsing Scribble
output directly.

Asynchronous subtyping (2026-08-05 orchestrator-mandated port): this walker
carries the FULL commuting-reorder acceptance logic of
stjp_core/monitor/monitor.py::RoleMonitor — `_match_commuting` (BFS past
different-channel actions; a "channel" from this role's local view is
(peer, direction), so a send to peer A and a receive from peer B commute,
while same-channel actions are FIFO heads that block), the `_skipped`
deferred-obligation multiset (an action commuted past becomes a debt the
role must still pay later in the trace, consumed WITHOUT advancing state
when it arrives), and `check_termination`'s unfulfilled-deferred-obligation
check (a trace ending with unpaid debt = premature_termination even from an
accepting EFSM state — stjp_core's 2026-07-19 audit fix). Ported
line-for-line from stjp_core/monitor/monitor.py; no semantic invention.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# EFSM (ported from stjp_core/compiler/efsm_parser.py — dataclass shapes only)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Transition:
    source: str
    target: str
    direction: str        # "send" or "receive"
    peer: str
    label: str
    payload_type: str = ""


@dataclass
class EFSM:
    role: str
    protocol_name: str = ""
    states: set = field(default_factory=set)
    initial_state: str = ""
    accepting_states: set = field(default_factory=set)
    transitions: list = field(default_factory=list)

    def transitions_from(self, state: str) -> list:
        return [t for t in self.transitions if t.source == state]

    def is_accepting(self, state: str) -> bool:
        return state in self.accepting_states

    def expected_labels(self, state: str) -> list:
        return [f"{t.peer}{'!' if t.direction == 'send' else '?'}{t.label}"
                for t in self.transitions_from(state)]


def efsm_from_json(d: dict) -> EFSM:
    return EFSM(
        role=d["role"], protocol_name=d.get("protocol_name", ""),
        states=set(d["states"]), initial_state=d["initial"],
        accepting_states=set(d["accepting"]),
        transitions=[Transition(source=t["source"], target=t["target"],
                                direction=t["direction"], peer=t["peer"],
                                label=t["label"],
                                payload_type=t.get("payload_type", ""))
                    for t in d["transitions"]],
    )


def efsms_from_json(efsm_json: dict) -> dict[str, EFSM]:
    """{role: EFSM} from a decoded artifacts/efsm.json."""
    return {role: efsm_from_json(d) for role, d in efsm_json.items()}


# ---------------------------------------------------------------------------
# Refinements (ported from stjp_core/compiler/refinement_checker.py)
# ---------------------------------------------------------------------------

SAFE_BUILTINS = {
    'len': len, 'abs': abs, 'min': min, 'max': max,
    'int': int, 'float': float, 'str': str, 'bool': bool,
    'isinstance': isinstance, 'True': True, 'False': False, 'None': None,
}


def _matches(pattern: str, s: str) -> bool:
    return re.fullmatch(pattern, s) is not None


def _startswith(s: str, prefix: str) -> bool:
    return isinstance(s, str) and s.startswith(prefix)


def _endswith(s: str, suffix: str) -> bool:
    return isinstance(s, str) and s.endswith(suffix)


def _contains(s: str, sub: str) -> bool:
    return isinstance(s, str) and sub in s


SAFE_HELPERS = {
    'matches': _matches, 'startswith': _startswith,
    'endswith': _endswith, 'contains': _contains,
}

_ALLOWED_NODES = (
    ast.Expression, ast.BoolOp, ast.BinOp, ast.UnaryOp, ast.Compare,
    ast.Call, ast.Constant, ast.Name, ast.Load, ast.IfExp,
    ast.Tuple, ast.List, ast.Attribute,
    ast.And, ast.Or, ast.Not,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.UAdd, ast.USub,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn,
    ast.Is, ast.IsNot,
)

_SAFE_ATTRS = {'lower', 'upper', 'strip', 'lstrip', 'rstrip', 'startswith',
              'endswith', 'replace'}


def _validate_ast(node: ast.AST) -> bool:
    """Reject anything outside the safe subset (byte-identical logic to
    stjp_core/compiler/refinement_checker.py::_validate_ast)."""
    if isinstance(node, ast.Attribute):
        if node.attr not in _SAFE_ATTRS:
            return False
    elif not isinstance(node, _ALLOWED_NODES):
        return False
    for child in ast.iter_child_nodes(node):
        if not _validate_ast(child):
            return False
    return True


@dataclass
class Refinement:
    sender: str
    receiver: str
    label: str
    declared_type: str = ""
    predicates: list = field(default_factory=list)

    def check(self, payload_str: str) -> tuple[bool, str]:
        try:
            if self.declared_type == 'int':
                x = int(payload_str)
            elif self.declared_type == 'float':
                x = float(payload_str)
            elif self.declared_type == 'bool':
                x = payload_str.lower() in ('true', '1', 'yes')
            else:
                x = payload_str
        except (ValueError, TypeError) as e:
            return False, f"type error: expected {self.declared_type}, got {payload_str!r}: {e}"

        env = {'x': x, **SAFE_BUILTINS, **SAFE_HELPERS, '__builtins__': {}}
        for pred in self.predicates:
            try:
                tree = ast.parse(pred, mode='eval')
                if not _validate_ast(tree):
                    return False, f"unsafe predicate: {pred}"
                result = eval(compile(tree, '<refn>', 'eval'), env)
                if not result:
                    return False, f"predicate failed: {pred} (x={x!r})"
            except Exception as e:
                return False, f"predicate error: {pred}: {e}"
        return True, ""


@dataclass
class ChoiceGuard:
    role: str
    when: str = ""
    require: str = ""
    over: list = field(default_factory=list)

    def evaluate(self, values: dict) -> Optional[bool]:
        """None = not evaluable yet (unseen value) or unsafe/failed predicate
        — the walker then ALLOWS the send and flags nothing (matching
        stjp_core monitor behavior: unevaluable == allow + no verdict)."""
        if not self.when:
            return None
        try:
            tree = ast.parse(self.when, mode='eval')
        except SyntaxError:
            return None
        if not _validate_ast(tree):
            return None
        known = set(SAFE_BUILTINS) | set(SAFE_HELPERS)
        needed = {n.id for n in ast.walk(tree)
                  if isinstance(n, ast.Name) and n.id not in known}
        if not needed.issubset(values.keys()):
            return None
        env = {**SAFE_BUILTINS, **SAFE_HELPERS,
               **{k: values[k] for k in needed}, '__builtins__': {}}
        try:
            return bool(eval(compile(tree, '<refn-choice>', 'eval'), env))
        except Exception:
            return None


def refinements_from_json(entries: list) -> tuple[dict, list]:
    """artifacts/refinements.json -> ({(sender,receiver,label): Refinement}, [ChoiceGuard,...])."""
    payload_guards: dict = {}
    choice_guards: list = []
    for e in entries:
        kind = e.get("kind")
        if kind == "refinement":
            r = Refinement(sender=e["sender"], receiver=e["receiver"],
                           label=e["label"], declared_type=e.get("declared_type", ""),
                           predicates=list(e.get("predicates", [])))
            payload_guards[(r.sender, r.receiver, r.label)] = r
        elif kind == "choice_guard":
            choice_guards.append(ChoiceGuard(
                role=e["role"], when=e.get("when", ""),
                require=e.get("require", ""), over=list(e.get("over", []))))
        # "ledger" entries: not used by the current gated arms
        # for the cases seen so far (no case ships a session ledger yet
        # alongside its llm-valid draft); ignored here rather than silently
        # mis-enforced.
    return payload_guards, choice_guards


# ---------------------------------------------------------------------------
# Violations + RoleMonitor / SessionMonitor
# (ported from stjp_core/monitor/monitor.py; direct-match only, see the
#  module docstring's KNOWN DEVIATION note)
# ---------------------------------------------------------------------------

@dataclass
class TraceEvent:
    sender: str
    receiver: str
    label: str
    payload: str = ""
    payload_type: str = ""
    step: int = 0


@dataclass
class Violation:
    role: str
    violation_type: str     # off_protocol | refinement_failed | unexpected_peer |
                            # choice_guard_violation | premature_termination
    step: int
    event: Optional[TraceEvent]
    state: str
    expected: list
    message: str


def _normalize_label(label: str) -> str:
    """Strip trailing type annotation, e.g. 'HighRevenue(Double)' -> 'HighRevenue'."""
    idx = label.find("(")
    return label[:idx] if idx > 0 else label


class RoleMonitor:
    """Single-role EFSM walker with asynchronous-subtyping reorder tolerance,
    ported line-for-line from stjp_core/monitor/monitor.py::RoleMonitor."""

    def __init__(self, efsm: EFSM, payload_guards: dict, choice_guards: list):
        self.efsm = efsm
        self.current_state = efsm.initial_state
        self.violations: list[Violation] = []
        self.steps_checked = 0
        self.payload_guards = payload_guards
        self.choice_guards = [g for g in choice_guards if g.role == efsm.role]
        self.observed_values: dict[str, str] = {}
        # Deferred-obligation multiset (stjp_core lazily creates this via a
        # hasattr check in process_event; initializing here is semantically
        # identical and deepcopy-safe). A multiset (list) because the same
        # (direction, label, peer) obligation can legitimately be owed more
        # than once under recursion.
        self._skipped: list[tuple[str, str, str]] = []  # (direction, label, peer)

    # ------------------------------------------------------------------
    # Async message reordering (asynchronous subtyping) — verbatim port of
    # stjp_core/monitor/monitor.py::RoleMonitor._match_commuting.
    #
    # In an async system, receives from *different* peers may arrive in any
    # order and sends to *different* peers may be emitted in any order. The
    # projected EFSM linearises them; the monitor must tolerate reordering
    # when messages go to/from distinct channels.
    # ------------------------------------------------------------------

    def _match_commuting(self, direction: str, norm_label: str, peer: str):
        """Find a transition matching (direction, norm_label, peer) from the
        current state, commuting past actions on DIFFERENT channels.

        Multiparty session types are asynchronous: two actions commute iff
        they are on different channels. From this role's local view a
        "channel" is (peer, direction) — so a send to peer A and a receive
        from peer B commute, and so do a pending send and an incoming receive
        on different peers. Only actions on the SAME channel (same peer AND
        same direction) are FIFO-ordered and must not be reordered.

        So to accept an observed event we may "defer" any different-channel
        transition the local type still owes, and look for the matching one
        underneath. The deferred transitions become obligations the role must
        still fulfil later (tracked in self._skipped).

        Returns (matched_transition, [deferred_transitions]) or (None, []).
        """
        from collections import deque
        queue = deque([(self.current_state, [])])
        seen: set = set()
        while queue:
            st, deferred = queue.popleft()
            if st in seen:
                continue
            seen.add(st)
            for t in self.efsm.transitions_from(st):
                if (t.direction == direction and t.peer == peer
                        and t.label == norm_label):
                    return t, deferred
                same_channel = (t.peer == peer and t.direction == direction)
                # Commute past t only if it is on a DIFFERENT channel. A
                # same-channel transition is a FIFO head that must be consumed
                # in order, so it blocks this path.
                if not same_channel and len(deferred) < 24:
                    queue.append((t.target, deferred + [t]))
        return None, []

    def process_event(self, event: TraceEvent) -> Optional[Violation]:
        role = self.efsm.role
        if event.sender == role:
            direction, peer = "send", event.receiver
        elif event.receiver == role:
            direction, peer = "receive", event.sender
        else:
            return None  # not relevant to this role

        self.steps_checked += 1
        norm_label = _normalize_label(event.label)

        choice_v: Optional[Violation] = None
        if direction == "send" and self.choice_guards:
            choice_v = self._check_choice_guards(event, norm_label)

        # Record AFTER guard evaluation, matching stjp_core (a guard never
        # ranges over the very message being judged).
        if event.payload:
            self.observed_values[norm_label] = event.payload

        # --- Was this event a previously-deferred obligation? consume it ---
        # Don't advance state — it was already advanced when we deferred it.
        if (direction, norm_label, peer) in self._skipped:
            self._skipped.remove((direction, norm_label, peer))
            v = self._check_refinement(event, None)
            return choice_v or v

        candidates = self.efsm.transitions_from(self.current_state)
        matching = [t for t in candidates
                    if t.label == norm_label and t.direction == direction
                    and t.peer == peer]

        # No direct match: try matching by commuting past different-channel
        # actions (asynchronous MPST concurrency). Any different-channel
        # transition we step over becomes a deferred obligation.
        if not matching:
            matched, deferred = self._match_commuting(direction, norm_label, peer)
            if matched is not None:
                for d in deferred:
                    self._skipped.append((d.direction, d.label, d.peer))
                matching = [matched]

        if not matching:
            label_matches = [t for t in candidates if t.label == norm_label]
            if label_matches:
                v = Violation(
                    role=role, violation_type="unexpected_peer",
                    step=event.step, event=event, state=self.current_state,
                    expected=[f"{t.peer}{'!' if t.direction == 'send' else '?'}{t.label}"
                              for t in candidates],
                    message=f"Role {role}: message {event.label} sent to/from wrong "
                            f"peer ({peer}), expected {label_matches[0].peer}")
            else:
                v = Violation(
                    role=role, violation_type="off_protocol",
                    step=event.step, event=event, state=self.current_state,
                    expected=self.efsm.expected_labels(self.current_state),
                    message=f"Role {role} at state {self.current_state}: got "
                            f"{direction} {peer}{'!' if direction == 'send' else '?'}"
                            f"{event.label}, expected one of "
                            f"{self.efsm.expected_labels(self.current_state)}")
            self.violations.append(v)
            return v

        v = self._check_refinement(event, matching[0])
        if v:
            return v

        # Advance state. A choice-guard violation does NOT block the advance
        # (the message was protocol-legal and did happen) — matches
        # stjp_core/monitor/monitor.py exactly.
        self.current_state = matching[0].target
        return choice_v

    def _check_choice_guards(self, event: TraceEvent,
                             norm_label: str) -> Optional[Violation]:
        for g in self.choice_guards:
            verdict = g.evaluate(self.observed_values)
            if verdict is None:
                continue  # unevaluable == allow + no verdict
            wrong = ((verdict and norm_label in g.over) or
                     (not verdict and g.over and norm_label == g.require))
            if wrong:
                must = g.require if verdict else " / ".join(g.over)
                v = Violation(
                    role=self.efsm.role, violation_type="choice_guard_violation",
                    step=event.step, event=event, state=self.current_state,
                    expected=[must],
                    message=(f"Role {self.efsm.role}: choice guard [when {g.when}] "
                             f"= {verdict} requires {must}, but sent {event.label}"))
                self.violations.append(v)
                return v
        return None

    def _check_refinement(self, event: TraceEvent,
                          trans: Optional[Transition]) -> Optional[Violation]:
        norm_label = _normalize_label(event.label)
        for key in [(event.sender, event.receiver, event.label),
                    (event.sender, event.receiver, norm_label)]:
            refn = self.payload_guards.get(key)
            if refn and event.payload:
                ok, err = refn.check(event.payload)
                if not ok:
                    v = Violation(
                        role=self.efsm.role, violation_type="refinement_failed",
                        step=event.step, event=event, state=self.current_state,
                        expected=[str(refn.predicates)],
                        message=f"Role {self.efsm.role}: refinement failed for "
                                f"{event.label}: {err}")
                    self.violations.append(v)
                    return v
        return None

    def check_termination(self) -> Optional[Violation]:
        """Check if the monitor ended in an accepting state.

        Also flags UNFULFILLED DEFERRED OBLIGATIONS (verbatim port of
        stjp_core/monitor/monitor.py::RoleMonitor.check_termination): when
        the monitor commutes past a different-channel action, that action
        becomes a debt the role must still pay later in the trace. If the
        trace ends with the debt unpaid, the session is incomplete even
        though the EFSM state may already be accepting (bug found in
        stjp_core's 2026-07-19 code audit).
        """
        owed = self._skipped
        if owed:
            v = Violation(
                role=self.efsm.role, violation_type="premature_termination",
                step=self.steps_checked, event=None, state=self.current_state,
                expected=[f"{peer}{'!' if d == 'send' else '?'}{label}"
                          for (d, label, peer) in owed],
                message=f"Role {self.efsm.role}: trace ended with unfulfilled "
                        f"deferred obligation(s) "
                        f"{[(d, label, peer) for (d, label, peer) in owed]} — "
                        f"actions the role commuted past but never performed")
            self.violations.append(v)
            return v
        if not self.efsm.is_accepting(self.current_state):
            v = Violation(
                role=self.efsm.role, violation_type="premature_termination",
                step=self.steps_checked, event=None, state=self.current_state,
                expected=self.efsm.expected_labels(self.current_state),
                message=f"Role {self.efsm.role}: terminated in non-accepting "
                        f"state {self.current_state}, expected one of "
                        f"{self.efsm.expected_labels(self.current_state)}")
            self.violations.append(v)
            return v
        return None

    def enabled_sends(self) -> list[Transition]:
        """Transitions this role could SEND right now — the EFSM scheduler's
        claim predicate (localvalid_sched / maf_localvalid_sched)."""
        return [t for t in self.efsm.transitions_from(self.current_state)
                if t.direction == "send"]


class SessionMonitor:
    """All roles' RoleMonitors, stepped together — mirrors
    stjp_core/monitor/monitor.py::SessionMonitor (minus the central session
    ledger, which no arm of this case uses)."""

    def __init__(self, efsms: dict[str, EFSM], payload_guards: dict,
                 choice_guards: list):
        self.monitors = {role: RoleMonitor(efsm, payload_guards, choice_guards)
                         for role, efsm in efsms.items()}

    def process_event(self, event: TraceEvent) -> Optional[Violation]:
        """Advance every role's monitor; return the FIRST violation seen —
        matches stjp_core/monitor/stjp_live_emitter.py::LiveEventEmitter.emit."""
        first: Optional[Violation] = None
        for mon in self.monitors.values():
            v = mon.process_event(event)
            if v is not None and first is None:
                first = v
        return first

    def all_accepting(self) -> bool:
        return all(m.efsm.is_accepting(m.current_state)
                   for m in self.monitors.values())

    def is_globally_conformant(self) -> bool:
        return all(len(m.violations) == 0 for m in self.monitors.values())
