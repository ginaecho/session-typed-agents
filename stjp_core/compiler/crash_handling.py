"""crash_handling.py — Prototype 3 ("no session left in limbo").

Theory: Viering–Chen–Eugster–Hu–Ziarek, ESOP 2018. Failure-aware local types
with typed try/handle regions and a robust coordinator: a crash of any role
inside a region routes every live role into a statically-checked handler
continuation, and the type system proves the handlers themselves are safe.

STJP's mapping is unusually direct: the scheduler is the coordinator (it already
tracks who must act), the monitors already hold per-role EFSMs (handlers are more
generated states), and the audit's 22 non-terminal trials are precisely the
untyped version of the problem.

Sidecar grammar (scribble-java untouched) — a `.fail` file over G:

    region Trade covers ALL              # or: covers states {8,27,39}
    on crash Buyer   : Escrow->Seller:AbortTrade ; goal := Refunded
    on crash Escrow  : ESCALATE          # no safe automated recovery -> typed abort to human
    timeout * = 3 polls                  # crash detector: k enabled polls, no legal action

Four STATIC validator checks (all in `validate_fail`):
  1. Coverage      — every crashable role has a handler or explicit ESCALATE.
  2. Projectability — each handler body is a well-formed mini global type over the
                     live roles (deadlock-free; Scribble-checked when available).
  3. Recoverability — every handler reaches a typed terminal (`goal :=`) or
                     ESCALATE: "no crash leaves the session in limbo."
  4. No-authorization-bypass — a handler must not emit a trace that violates a
                     Critic safety policy (e.g. settle before confirm). The
                     adversarial recovery-shortcut handler is rejected here.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Handler:
    role: str                                  # the crashed role this handles
    escalate: bool = False
    messages: list = field(default_factory=list)   # [(sender, receiver, label), ...]
    goal: str = ""                             # typed-degraded terminal marker


@dataclass
class FailSpec:
    region_name: str = ""
    covers_all: bool = True
    covered_states: set = field(default_factory=set)
    handlers: dict = field(default_factory=dict)   # role -> Handler
    timeouts: dict = field(default_factory=dict)   # role ('*' = all) -> k polls

    def handler_for(self, role: str) -> "Handler | None":
        return self.handlers.get(role)

    def timeout_for(self, role: str) -> int | None:
        return self.timeouts.get(role, self.timeouts.get("*"))


_REGION_RE = re.compile(r'^region\s+(\w+)\s+covers\s+(ALL|states\s*\{([^}]*)\})\s*$')
_ON_RE = re.compile(r'^on\s+crash\s+(\w+)\s*:\s*(.+)$')
_TIMEOUT_RE = re.compile(r'^timeout\s+([\w*]+)\s*=\s*(\d+)\s*polls?\s*$')
_MSG_RE = re.compile(r'^(\w+)\s*->\s*(\w+)\s*:\s*(\w+)$')


def parse_fail_text(text: str) -> FailSpec:
    spec = FailSpec()
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        m = _REGION_RE.match(line)
        if m:
            spec.region_name = m.group(1)
            if m.group(2) == "ALL":
                spec.covers_all = True
            else:
                spec.covers_all = False
                spec.covered_states = {s.strip() for s in (m.group(3) or "").split(",") if s.strip()}
            continue
        m = _TIMEOUT_RE.match(line)
        if m:
            spec.timeouts[m.group(1)] = int(m.group(2))
            continue
        m = _ON_RE.match(line)
        if m:
            role, body = m.group(1), m.group(2).strip()
            h = Handler(role=role)
            if body.upper().startswith("ESCALATE"):
                h.escalate = True
            else:
                for part in body.split(";"):
                    part = part.strip()
                    gm = re.match(r'goal\s*:=\s*(\w+)', part)
                    if gm:
                        h.goal = gm.group(1)
                        continue
                    mm = _MSG_RE.match(part)
                    if mm:
                        h.messages.append((mm.group(1), mm.group(2), mm.group(3)))
            spec.handlers[role] = h
            continue
    return spec


# ── the four static checks ───────────────────────────────────────────────────

def _handler_projectable(handler: Handler, live_roles: set) -> tuple[bool, str]:
    """Check 2: the handler body is a well-formed mini protocol over live roles.

    A linear point-to-point message sequence is deadlock-free iff every message's
    sender and receiver are distinct LIVE roles. (A Scribble round-trip is a
    faithful superset; for these linear handlers the structural check is
    equivalent and avoids a JVM call per handler.)"""
    for (s, r, label) in handler.messages:
        if s not in live_roles:
            return False, f"handler for {handler.role}: sender {s} is not a live role"
        if r not in live_roles:
            return False, f"handler for {handler.role}: receiver {r} is not a live role"
        if s == r:
            return False, f"handler for {handler.role}: {label} has sender==receiver"
    return True, ""


def validate_fail(spec: FailSpec, roles: list, policies=None,
                  pre_crash_trace=None) -> tuple[bool, list]:
    """Run all four static checks. `policies` (parsed Critic policies) enables
    check 4; `pre_crash_trace` is an optional list of (sender,receiver,label)
    dicts representing a worst-case in-region history to prepend when checking
    that a handler cannot cause a safety violation."""
    errors = []
    roles_set = set(roles)

    # 1. Coverage — every crashable role has a handler or ESCALATE.
    for role in roles:
        if role not in spec.handlers:
            errors.append(f"coverage: no handler or ESCALATE for crash of {role}")

    for role, h in spec.handlers.items():
        if role not in roles_set:
            errors.append(f"handler names unknown role {role}")
            continue
        live = roles_set - {role}
        if h.escalate:
            continue
        # 2. Projectability
        ok, why = _handler_projectable(h, live)
        if not ok:
            errors.append(why)
        # 3. Recoverability — reaches a typed terminal.
        if not h.goal:
            errors.append(f"recoverability: handler for {role} reaches no typed "
                          f"terminal (missing `goal :=`) and is not ESCALATE")
        # 4. No-authorization-bypass — the handler's resulting trace must not
        #    trigger a Critic safety finding.
        if policies:
            from stjp_core.critic.critic import run_runtime_critic
            trace = list(pre_crash_trace or []) + [
                {"sender": s, "receiver": r, "label": lab} for (s, r, lab) in h.messages]
            rt = run_runtime_critic(trace, policies)
            if rt.findings:
                errors.append(f"authorization-bypass: handler for {role} would "
                              f"violate a safety policy: "
                              f"{rt.findings[0].policy_id} ({rt.findings[0].policy_kind})")
    return (len(errors) == 0, errors)


# ── runtime: crash detection (timeout) ───────────────────────────────────────

def detect_crashes(spec: FailSpec, idle_poll_counts: dict) -> list:
    """A role that has been polled with an enabled action but produced no legal
    action for >= its timeout budget is declared crashed. Returns the crashed
    roles in a DETERMINISTIC order (lexicographic) so that two roles timing out
    in the same round have a stable tie-break.
    """
    crashed = []
    for role, idle in idle_poll_counts.items():
        k = spec.timeout_for(role)
        if k is not None and idle >= k:
            crashed.append(role)
    return sorted(crashed)


# ── runtime: resolve a crash to a typed outcome ──────────────────────────────

def resolve_crash(spec: FailSpec, crashed_role: str, at_state: str = "",
                  has_cf: bool = True) -> dict:
    """Return the typed outcome of a crash.

    Without crash-handling (`has_cf=False`) the session is stuck: `limbo`.
    With CF, fire the handler: ESCALATE -> `typed_abort`; otherwise emit the
    handler messages and reach the `goal` terminal -> `typed_degraded`.
    """
    if not has_cf:
        return {"outcome": "limbo", "goal": None, "messages": []}
    h = spec.handler_for(crashed_role)
    if h is None:
        return {"outcome": "limbo", "goal": None, "messages": []}   # uncovered
    if h.escalate:
        return {"outcome": "typed_abort", "goal": "ESCALATE", "messages": []}
    return {"outcome": "typed_degraded", "goal": h.goal,
            "messages": [{"sender": s, "receiver": r, "label": lab}
                         for (s, r, lab) in h.messages]}
