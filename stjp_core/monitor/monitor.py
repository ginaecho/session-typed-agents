"""
Runtime Monitor

Walks a per-role EFSM against a trace of events, detecting:
  - Off-protocol messages (label not in current state's transitions)
  - Premature termination (stopped in non-accepting state)
  - Capability escalation (sent to/received from unexpected peer)

Based on: Bocchi, Chen, Demangeon, Honda, Yoshida — FORTE'13 / TCS'17
  "If every endpoint's local monitor enforces its projected local type,
   the global protocol is observably satisfied."

Each monitor only knows its own role's EFSM. Global compliance falls out
of local compliance — no central observer needed.
"""

from dataclasses import dataclass, field
from enum import Enum
from stjp_core.compiler.efsm_parser import EFSM, Transition


class ViolationType(Enum):
    OFF_PROTOCOL = "off_protocol"
    REFINEMENT_FAILED = "refinement_failed"
    PREMATURE_TERMINATION = "premature_termination"
    UNEXPECTED_PEER = "unexpected_peer"
    CHOICE_GUARD = "choice_guard_violation"
    STATEFUL_INVARIANT = "stateful_invariant_violation"


@dataclass
class TraceEvent:
    """A single observable event in an agent execution trace."""
    sender: str          # role that sent
    receiver: str        # role that received
    label: str           # message label e.g. "HighRevenue"
    payload: str = ""    # payload value (for refinement checking)
    payload_type: str = ""  # declared type
    step: int = 0        # sequence number in trace


@dataclass
class Violation:
    """A monitor-detected violation."""
    role: str
    violation_type: ViolationType
    step: int
    event: TraceEvent | None
    state: str
    expected: list[str]
    message: str


@dataclass
class MonitorVerdict:
    """Result of monitoring one role against a complete trace."""
    role: str
    conformant: bool
    violations: list[Violation] = field(default_factory=list)
    steps_checked: int = 0
    final_state: str = ""
    trace_length: int = 0


class RoleMonitor:
    """
    Runtime monitor for a single role.
    Interprets the projected EFSM against a stream of trace events.
    """

    def __init__(self, efsm: EFSM, refinements: dict | None = None):
        self.efsm = efsm
        self.current_state = efsm.initial_state
        self.violations: list[Violation] = []
        self.steps_checked = 0
        self.refinements = refinements or {}
        # Value tracking for stateful assertions (choice guards): every
        # payload this role observes (send or receive), keyed by normalized
        # label. Later guards reference these by label name.
        self.observed_values: dict[str, str] = {}
        from stjp_core.compiler.refinement_checker import choice_guards_for
        self.choice_guards = choice_guards_for(self.refinements, efsm.role)

    @staticmethod
    def _normalize_label(label: str) -> str:
        """Strip type annotations from labels.

        Agents may emit labels like ``HighRevenue(Double)`` or ``HighNotice()``
        whereas the EFSM stores just ``HighRevenue`` / ``HighNotice``.  Strip
        any trailing ``(...)`` so that comparison succeeds.
        """
        idx = label.find("(")
        return label[:idx] if idx > 0 else label

    # ------------------------------------------------------------------
    # Async message reordering (asynchronous subtyping)
    # ------------------------------------------------------------------
    # In an async system:
    #   - Receives from *different* peers may arrive in any order.
    #   - Sends to *different* peers may be emitted in any order.
    # The projected EFSM linearises them, but the monitor must tolerate
    # reordering when messages go to/from distinct peers.
    #
    # Approach: BFS through same-direction transitions from the current
    # state.  If the incoming event matches any transition on that
    # frontier, consume it and advance to the target state.  Any
    # intermediate transitions that were "skipped" are remembered so they
    # can be matched later without the EFSM state blocking them.
    # ------------------------------------------------------------------

    def _match_commuting(self, direction: str, norm_label: str, peer: str):
        """Find a transition matching (direction, norm_label, peer) from the
        current state, commuting past actions on DIFFERENT channels.

        Multiparty session types are asynchronous: two actions commute iff they
        are on different channels. From this role's local view a "channel" is
        (peer, direction) — so a send to peer A and a receive from peer B
        commute, and so do a pending send and an incoming receive on different
        peers. Only actions on the SAME channel (same peer AND same direction)
        are FIFO-ordered and must not be reordered.

        So to accept an observed event we may "defer" any different-channel
        transition the local type still owes, and look for the matching one
        underneath. The deferred transitions become obligations the role must
        still fulfil later (tracked in self._skipped).

        Returns (matched_transition, [deferred_transitions]) or (None, []).
        """
        from collections import deque
        queue = deque([(self.current_state, [])])
        seen: set[str] = set()
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

    def process_event(self, event: TraceEvent) -> Violation | None:
        """
        Process a single trace event relevant to this role.

        Supports asynchronous subtyping: receives from different peers
        may arrive out of the EFSM's sequential order.
        """
        role = self.efsm.role

        # Determine if this event is relevant to this role
        if event.sender == role:
            direction = "send"
            peer = event.receiver
        elif event.receiver == role:
            direction = "receive"
            peer = event.sender
        else:
            return None  # not relevant to this role

        self.steps_checked += 1
        norm_label = self._normalize_label(event.label)

        # --- Choice-point guards (value-dependent internal choice) -------
        # Checked on SENDS only, BEFORE the EFSM match: the message may be
        # perfectly protocol-legal (both branches type-check) and still be
        # the wrong branch for the values this role has already seen.
        choice_v: Violation | None = None
        if direction == "send" and self.choice_guards:
            choice_v = self._check_choice_guards(event, norm_label)

        # Record the observed payload AFTER guard evaluation so a guard
        # never ranges over the very message being judged.
        if event.payload:
            self.observed_values[norm_label] = event.payload

        # Initialise the skipped (deferred-obligation) multiset if needed.
        # A multiset (list) because the same (direction,label,peer) obligation
        # can legitimately be owed more than once under recursion.
        if not hasattr(self, "_skipped"):
            self._skipped: list[tuple[str, str, str]] = []  # (direction, label, peer)

        # --- Was this event a previously-deferred obligation? consume it ---
        if (direction, norm_label, peer) in self._skipped:
            self._skipped.remove((direction, norm_label, peer))
            # Don't advance state — it was already advanced when we deferred it.
            v = self._check_refinement(event, None)
            return choice_v or v

        # Direct match from the current state.
        candidates = self.efsm.transitions_from(self.current_state)
        matching = [t for t in candidates
                    if t.label == norm_label
                    and t.direction == direction
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
            # Check if the label exists but with wrong peer
            label_matches = [t for t in candidates if t.label == norm_label]
            if label_matches:
                v = Violation(
                    role=role,
                    violation_type=ViolationType.UNEXPECTED_PEER,
                    step=event.step,
                    event=event,
                    state=self.current_state,
                    expected=[f"{t.peer}{'!' if t.direction == 'send' else '?'}{t.label}"
                              for t in candidates],
                    message=f"Role {role}: message {event.label} sent to/from wrong peer "
                            f"({peer}), expected {label_matches[0].peer}"
                )
            else:
                v = Violation(
                    role=role,
                    violation_type=ViolationType.OFF_PROTOCOL,
                    step=event.step,
                    event=event,
                    state=self.current_state,
                    expected=self.efsm.expected_labels(self.current_state),
                    message=f"Role {role} at state {self.current_state}: "
                            f"got {direction} {peer}{'!' if direction == 'send' else '?'}"
                            f"{event.label}, expected one of "
                            f"{self.efsm.expected_labels(self.current_state)}"
                )
            self.violations.append(v)
            return v

        # Check refinement predicates if available
        v = self._check_refinement(event, matching[0])
        if v:
            return v

        # Advance state. A choice-guard violation does NOT block the
        # advance — the message was protocol-legal and did happen; the
        # monitor stays aligned with reality and reports the wrong branch.
        self.current_state = matching[0].target
        return choice_v

    def _check_choice_guards(self, event: TraceEvent,
                             norm_label: str) -> Violation | None:
        """Evaluate value-dependent choice guards against this send."""
        for g in self.choice_guards:
            verdict = g.evaluate(self.observed_values)
            if verdict is None:
                continue  # not evaluable yet (referenced value unseen)
            wrong = ((verdict and norm_label in g.over) or
                     (not verdict and g.over and norm_label == g.require))
            if wrong:
                must = g.require if verdict else " / ".join(g.over)
                v = Violation(
                    role=self.efsm.role,
                    violation_type=ViolationType.CHOICE_GUARD,
                    step=event.step,
                    event=event,
                    state=self.current_state,
                    expected=[must],
                    message=(f"Role {self.efsm.role}: choice guard "
                             f"[when {g.when}] = {verdict} with observed "
                             f"values { {k: v[:24] for k, v in self.observed_values.items()} } "
                             f"requires {must}, but sent {event.label}"),
                )
                self.violations.append(v)
                return v
        return None

    def _check_refinement(self, event: TraceEvent,
                          trans: Transition | None) -> Violation | None:
        """Check refinement predicates for a matched transition."""
        norm_label = self._normalize_label(event.label)
        for key in [(event.sender, event.receiver, event.label),
                    (event.sender, event.receiver, norm_label)]:
            refn = self.refinements.get(key)
            if refn and event.payload:
                ok, err = refn.check(event.payload)
                if not ok:
                    v = Violation(
                        role=self.efsm.role,
                        violation_type=ViolationType.REFINEMENT_FAILED,
                        step=event.step,
                        event=event,
                        state=self.current_state,
                        expected=[str(refn)],
                        message=f"Role {self.efsm.role}: refinement failed "
                                f"for {event.label}: {err}"
                    )
                    self.violations.append(v)
                    return v
        return None

    def check_termination(self) -> Violation | None:
        """Check if the monitor ended in an accepting state."""
        if not self.efsm.is_accepting(self.current_state):
            v = Violation(
                role=self.efsm.role,
                violation_type=ViolationType.PREMATURE_TERMINATION,
                step=self.steps_checked,
                event=None,
                state=self.current_state,
                expected=self.efsm.expected_labels(self.current_state),
                message=f"Role {self.efsm.role}: terminated in non-accepting state "
                        f"{self.current_state}, expected one of "
                        f"{self.efsm.expected_labels(self.current_state)}"
            )
            self.violations.append(v)
            return v
        return None

    def get_verdict(self, trace_length: int) -> MonitorVerdict:
        """Return the final verdict for this role."""
        return MonitorVerdict(
            role=self.efsm.role,
            conformant=len(self.violations) == 0,
            violations=list(self.violations),
            steps_checked=self.steps_checked,
            final_state=self.current_state,
            trace_length=trace_length,
        )


class SessionMonitor:
    """
    Monitors all roles in a session simultaneously.
    Each role has its own RoleMonitor with its own EFSM.
    Global compliance = all local monitors pass (FORTE'13 theorem).
    """

    def __init__(self, efsms: dict[str, EFSM], refinements: dict | None = None,
                 gate: bool = False):
        self.monitors = {
            role: RoleMonitor(efsm, refinements)
            for role, efsm in efsms.items()
        }
        # Prototype 1: the session ledger is CENTRAL (it sees the ordered stream,
        # unlike the per-role monitors). `gate` selects observe vs enforce mode.
        self.ledger = (refinements or {}).get('__ledger__')
        self.gate = gate
        self.ledger_violations: list[Violation] = []
        if self.ledger is not None:
            self.ledger.reset()

    @staticmethod
    def _norm(label: str) -> str:
        idx = label.find("(")
        return label[:idx] if idx > 0 else label

    def process_trace(self, events: list[TraceEvent]) -> dict[str, MonitorVerdict]:
        """Run all monitors against a complete trace.

        The central session ledger is stepped on each event in stream order,
        after the per-role monitors, and any stateful-invariant breach is
        attributed to the message's sender at the exact crossing message.
        """
        for event in events:
            for monitor in self.monitors.values():
                monitor.process_event(event)
            if self.ledger is not None:
                for lv in self.ledger.step(self._norm(event.label), event.payload,
                                           step_no=event.step, gate=self.gate):
                    v = Violation(
                        role=event.sender,
                        violation_type=ViolationType.STATEFUL_INVARIANT,
                        step=event.step, event=event, state="",
                        expected=[lv.invariant],
                        message=(f"stateful invariant `{lv.invariant}` breached at "
                                 f"{event.label} (step {event.step}); virtual state "
                                 f"{ {k: round(v, 2) if isinstance(v, float) else v for k, v in lv.values.items()} }"
                                 + ("; REJECTED pre-delivery" if lv.blocked else "")),
                    )
                    self.ledger_violations.append(v)
                    if event.sender in self.monitors:
                        self.monitors[event.sender].violations.append(v)

        # Check termination for all roles
        for monitor in self.monitors.values():
            monitor.check_termination()

        return {role: m.get_verdict(len(events))
                for role, m in self.monitors.items()}

    def is_globally_conformant(self, verdicts: dict[str, MonitorVerdict]) -> bool:
        """Global conformance = all local monitors pass."""
        return all(v.conformant for v in verdicts.values())
