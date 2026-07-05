"""
Refinement Checker

Parses .refn sidecar files and evaluates payload predicates at runtime.
Predicates are sandboxed Python expressions over a bound variable `x`.

Message-payload format:
  [Sender -> Receiver : Label]
  type: int
  require: x > 0
  require: x <= 1000000

Choice-point format (value-dependent internal choice — the rule that decides
WHICH branch a role must take, given values it has already seen). Predicates
range over previously observed message payloads, bound by their label name:
  [choice at RevenueAnalyst]
  when: float(RawRevenueData) > 50000
  require: HighRevenueNotification
  over: StandardRevenueNotification

Semantics (enforced by stjp_core/monitor/monitor.py with value tracking):
  - when TRUE  and the role sends a label in `over`    -> choice_guard_violation
  - when TRUE  and the role sends `require`            -> OK
  - when FALSE and the role sends `require`            -> choice_guard_violation
    (only if `over` is non-empty — i.e. an alternative existed)
  - predicate not yet evaluable (value not seen)       -> guard is skipped

Research basis:
  - Bocchi et al. CONCUR'10 (asserted MPST — assertions at choice points)
  - Bocchi, Chen, Demangeon, Honda, Yoshida FORTE'13 (monitored session types)
  - "Specifying Stateful Asynchronous Properties for Distributed Programs"
    (stateful assertions over previously received values)
  - Zhou et al. OOPSLA'20 (refinement-typed payloads)
  - Das & Pfenning CONCUR'20 (undecidability of full arithmetic refinements)
"""

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path


class RefinementViolation(Exception):
    """Raised when a payload fails the refinement predicate at the call site."""


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
    'matches': _matches,
    'startswith': _startswith,
    'endswith': _endswith,
    'contains': _contains,
}

# AST nodes allowed in predicates
_ALLOWED_NODES = (
    ast.Expression, ast.BoolOp, ast.BinOp, ast.UnaryOp, ast.Compare,
    ast.Call, ast.Constant, ast.Name, ast.Load, ast.IfExp,
    ast.Tuple, ast.List, ast.Attribute,
    # Operators
    ast.And, ast.Or, ast.Not,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.UAdd, ast.USub,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn,
    ast.Is, ast.IsNot,
)

# Safe string methods allowed on `x`
_SAFE_ATTRS = {'lower', 'upper', 'strip', 'lstrip', 'rstrip', 'startswith', 'endswith', 'replace'}


def _validate_ast(node: ast.AST) -> bool:
    """Reject anything outside the safe subset."""
    if isinstance(node, ast.Attribute):
        # Allow only safe string method calls on the bound variable
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
    """Refinement contract for one message."""
    sender: str
    receiver: str
    label: str
    declared_type: str = ""
    predicates: list[str] = field(default_factory=list)

    def check(self, payload_str: str) -> tuple[bool, str]:
        """Evaluate all predicates against a payload value. Returns (ok, error)."""
        # Type coercion
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

    def __str__(self):
        parts = [f"[{self.sender} -> {self.receiver} : {self.label}]"]
        if self.declared_type:
            parts.append(f"type: {self.declared_type}")
        for p in self.predicates:
            parts.append(f"require: {p}")
        return "\n".join(parts)


@dataclass
class ChoiceGuard:
    """Value-dependent choice rule for one role's internal choice.

    `when` is a sandboxed predicate over previously observed payloads,
    referenced by message label (e.g. ``float(RawRevenueData) > 50000``).
    If it evaluates True the role MUST take `require`; sending any label in
    `over` instead is a choice_guard_violation (and vice versa when False).
    """
    role: str
    when: str = ""
    require: str = ""
    over: list[str] = field(default_factory=list)

    def evaluate(self, values: dict[str, str]) -> bool | None:
        """Evaluate `when` against observed payloads. None = not evaluable yet
        (a referenced label has not been observed) or unsafe/failed predicate."""
        if not self.when:
            return None
        try:
            tree = ast.parse(self.when, mode='eval')
        except SyntaxError:
            return None
        if not _validate_ast(tree):
            return None
        # Which bare names does the predicate need (beyond builtins/helpers)?
        known = set(SAFE_BUILTINS) | set(SAFE_HELPERS)
        needed = {n.id for n in ast.walk(tree)
                  if isinstance(n, ast.Name) and n.id not in known}
        if not needed.issubset(values.keys()):
            return None  # value(s) not observed yet — guard not active
        env = {**SAFE_BUILTINS, **SAFE_HELPERS,
               **{k: values[k] for k in needed}, '__builtins__': {}}
        try:
            return bool(eval(compile(tree, '<refn-choice>', 'eval'), env))
        except Exception:
            return None

    def __str__(self):
        alt = f" (instead of {', '.join(self.over)})" if self.over else ""
        return (f"[choice at {self.role}] when {self.when} "
                f"require {self.require}{alt}")


def choice_guards_for(refinements: dict, role: str) -> list["ChoiceGuard"]:
    """Extract the ChoiceGuards for one role from a parsed .refn dict."""
    return [g for k, g in refinements.items()
            if isinstance(g, ChoiceGuard) and g.role == role]


# Parser for .refn files
_HEADER_RE = re.compile(r'\[\s*(\w+)\s*->\s*(\w+)\s*:\s*(\w+)\s*\]')
_CHOICE_HEADER_RE = re.compile(r'\[\s*choice\s+at\s+(\w+)\s*\]', re.IGNORECASE)


def parse_refn_file(path: Path) -> dict[tuple[str, str, str], Refinement]:
    """Parse a .refn file. Returns dict keyed by (sender, receiver, label)."""
    text = path.read_text(encoding='utf-8')
    return parse_refn_text(text)


def parse_refn_text(text: str) -> dict:
    """Parse refinement text content.

    Returns a dict containing both kinds of entries:
      (sender, receiver, label) -> Refinement          (payload guards)
      ('__choice__', role, idx) -> ChoiceGuard          (choice-point guards)
    The special first element '__choice__' can never collide with a real
    sender role name, so existing ``refinements.get((s, r, label))`` callers
    are unaffected. Use ``choice_guards_for(refinements, role)`` to extract
    the guards for one role.
    """
    refinements: dict = {}
    current: Refinement | None = None
    current_choice: ChoiceGuard | None = None
    n_choice = 0

    def _flush():
        nonlocal current, current_choice, n_choice
        if current:
            refinements[(current.sender, current.receiver, current.label)] = current
            current = None
        if current_choice:
            refinements[('__choice__', current_choice.role, n_choice)] = current_choice
            n_choice += 1
            current_choice = None

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        choice_header = _CHOICE_HEADER_RE.match(line)
        if choice_header:
            _flush()
            current_choice = ChoiceGuard(role=choice_header.group(1))
            continue

        header = _HEADER_RE.match(line)
        if header:
            _flush()
            current = Refinement(
                sender=header.group(1),
                receiver=header.group(2),
                label=header.group(3),
            )
            continue

        if current_choice is not None:
            if line.startswith('when:'):
                current_choice.when = line.split(':', 1)[1].strip()
            elif line.startswith('require:'):
                current_choice.require = line.split(':', 1)[1].strip()
            elif line.startswith('over:'):
                current_choice.over = [s.strip() for s in
                                       line.split(':', 1)[1].split(',') if s.strip()]
            continue

        if current is None:
            continue

        if line.startswith('type:'):
            current.declared_type = line.split(':', 1)[1].strip()
        elif line.startswith('require:'):
            current.predicates.append(line.split(':', 1)[1].strip())

    _flush()

    # Prototype 1: attach a session ledger (state/on/invariant clauses) under a
    # string key that can never collide with the tuple keys used above.
    ledger = parse_session_ledger(text)
    if not ledger.is_empty():
        refinements['__ledger__'] = ledger
    return refinements


def load_refinements_for_protocol(protocol_path: Path) -> dict[tuple[str, str, str], Refinement]:
    """Auto-discover sibling .refn file for a .scr file."""
    refn_path = protocol_path.with_suffix('.refn')
    if refn_path.exists():
        return parse_refn_file(refn_path)
    return {}


# ─────────────────────────────────────────────────────────────────────────────
# Prototype 1 — Stateful session invariants ("the session ledger")
#
# Theory: Chen & Honda, CONCUR'12 — stateful asynchronous properties are
# assertions over *virtual state* that evolves across the whole conversation.
# STJP's structural advantage: the gate sits at delivery and sees the ordered
# message stream, so v1 checks these invariants centrally at the gate (the
# per-endpoint distribution question that CONCUR'12's machinery solves is
# deferred to v2).
#
# What it catches that per-message guards cannot: a violation spread across many
# individually-legal messages. Canonical case: budget $10k, per-debit limit $5k,
# three debits of $4k — every message passes every per-message guard, the
# cumulative total is a violation no per-decision predicate can see.
#
# Sidecar grammar (scribble-java untouched), three top-level clause kinds:
#     state total_debited : money = 0                  # virtual state decl
#     state budget        : money = 10000              # a never-updated decl acts as a constant
#     on Debit(amount)    : total_debited += amount    # update bound to a label
#     invariant total_debited <= budget                # checked after every update
# Optional loop-reset:
#     state window_spend : money = 0 reset on WindowOpen   # reset to init when WindowOpen is seen
# ─────────────────────────────────────────────────────────────────────────────

_STATE_RE = re.compile(
    r'^state\s+(\w+)\s*:\s*(\w+)\s*=\s*(-?\d+(?:\.\d+)?)'
    r'(?:\s+reset\s+on\s+(\w+))?\s*$')
_ON_RE = re.compile(r'^on\s+(\w+)\s*\(\s*(\w+)\s*\)\s*:\s*(\w+)\s*(\+=|-=|\*=|/=|=)\s*(.+)$')
_INVARIANT_RE = re.compile(r'^invariant\s+(.+)$')

# S-class default for a stateful-invariant breach (configurable per-invariant to
# S4 for irreversible-resource invariants via a trailing "  @S4" annotation).
_INV_SEV_RE = re.compile(r'^(.*?)\s*@S([0-4])\s*$')


@dataclass
class LedgerViolation:
    """A stateful-invariant breach, located at the exact crossing message."""
    invariant: str
    label: str
    step: int
    severity: str            # "S2".."S4"
    values: dict             # snapshot of virtual state at the breach
    blocked: bool = False    # True when the gate rejected the message pre-delivery


@dataclass
class SessionLedger:
    """Central virtual-state ledger checked over the ordered message stream.

    decls:      name -> (type, init_value, reset_on_label|None)
    updates:    label -> (field_name, [(state_name, op, expr_str), ...])
    invariants: [(expr_str, severity), ...]
    """
    decls: dict = field(default_factory=dict)
    updates: dict = field(default_factory=dict)
    invariants: list = field(default_factory=list)
    # runtime state (populated by reset())
    values: dict | None = None
    unevaluable: list = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (self.decls or self.updates or self.invariants)

    def reset(self):
        self.values = {n: init for n, (ty, init, r) in self.decls.items()}
        self.unevaluable = []

    def _eval(self, expr: str, extra: dict):
        tree = ast.parse(expr, mode='eval')
        if not _validate_ast(tree):
            raise RefinementViolation(f"unsafe ledger expression: {expr}")
        env = {**SAFE_BUILTINS, **SAFE_HELPERS, **self.values, **extra,
               '__builtins__': {}}
        return eval(compile(tree, '<refn-ledger>', 'eval'), env)

    def step(self, norm_label: str, payload: str, step_no: int = 0,
             gate: bool = False) -> list[LedgerViolation]:
        """Apply the label's updates, then check invariants touching changed
        state. Returns any breaches located at THIS message.

        Determinism: updates are applied only on accepted messages, so replays
        are bit-reproducible. In gate mode a breaching message is rolled back
        (rejected pre-delivery) and reported blocked; the ledger keeps the
        pre-message values so later messages are judged against reality.
        An unevaluable update (missing/nonnumeric payload field) is skipped and
        logged — never a false block.
        """
        if self.values is None:
            self.reset()

        # reset-on: any state whose reset trigger is this label resets to init
        # BEFORE this message's own updates are applied (loop-entry semantics).
        for n, (ty, init, r) in self.decls.items():
            if r == norm_label:
                self.values[n] = init

        spec = self.updates.get(norm_label)
        if not spec:
            return []
        field_name, ups = spec

        num = _coerce_num(payload)
        if num is None:
            self.unevaluable.append({"label": norm_label, "step": step_no,
                                     "reason": "guard_unevaluable: nonnumeric payload"})
            return []  # never a false block

        snapshot = dict(self.values)
        extra = {field_name: num}
        try:
            for (name, op, expr) in ups:
                val = self._eval(expr, extra)
                if op == '=':
                    self.values[name] = val
                elif op == '+=':
                    self.values[name] = self.values[name] + val
                elif op == '-=':
                    self.values[name] = self.values[name] - val
                elif op == '*=':
                    self.values[name] = self.values[name] * val
                elif op == '/=':
                    self.values[name] = self.values[name] / val
        except Exception:
            self.values = snapshot
            self.unevaluable.append({"label": norm_label, "step": step_no,
                                     "reason": "guard_unevaluable: update error"})
            return []

        touched = {u[0] for u in ups}
        breaches: list[LedgerViolation] = []
        for (expr, sev) in self.invariants:
            names = {n.id for n in ast.walk(ast.parse(expr, mode='eval'))
                     if isinstance(n, ast.Name)}
            if not (names & touched):
                continue  # invariant does not mention any state this message changed
            try:
                ok = bool(self._eval(expr, {}))
            except Exception:
                continue
            if not ok:
                breaches.append(LedgerViolation(
                    invariant=expr, label=norm_label, step=step_no,
                    severity=sev, values=dict(self.values), blocked=gate))

        if breaches and gate:
            # reject pre-delivery: roll the virtual state back so the breaching
            # resource is never committed.
            self.values = snapshot
        return breaches


def _coerce_num(s: str):
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def parse_session_ledger(text: str) -> SessionLedger:
    """Parse the state/on/invariant clauses of a .refn file into a SessionLedger."""
    ledger = SessionLedger()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        m = _STATE_RE.match(line)
        if m:
            name, ty, init, reset_on = m.groups()
            init_v = float(init) if ('.' in init or ty in ('money', 'float')) else int(init)
            ledger.decls[name] = (ty, init_v, reset_on)
            continue
        m = _ON_RE.match(line)
        if m:
            label, field_name, state_name, op, expr = m.groups()
            fn, ups = ledger.updates.get(label, (field_name, []))
            ups.append((state_name, op, expr.strip()))
            ledger.updates[label] = (field_name, ups)
            continue
        m = _INVARIANT_RE.match(line)
        if m:
            body = m.group(1).strip()
            sev_m = _INV_SEV_RE.match(body)
            if sev_m:
                body, sev_digit = sev_m.group(1).strip(), sev_m.group(2)
                sev = f"S{sev_digit}"
            else:
                sev = "S2"   # default; S4 for irreversible-resource invariants via @S4
            ledger.invariants.append((body, sev))
            continue
    return ledger


def validate_session_ledger(ledger: SessionLedger, protocol_labels: set) -> tuple[bool, list]:
    """Static dischargeability / well-formedness check (v1: dynamic invariants,
    this only checks the sidecar is coherent — no SMT proof).

    Rules:
      1. every `on` label exists in the protocol G;
      2. update expressions reference only declared state + that label's field;
      3. invariants reference only declared state (protocol constants are
         modelled as never-updated `state` decls).
    Returns (ok, [error, ...]).
    """
    errors: list = []
    declared = set(ledger.decls)
    for label, (field_name, ups) in ledger.updates.items():
        if protocol_labels and label not in protocol_labels:
            errors.append(f"on {label}: label not in protocol")
        for (name, op, expr) in ups:
            if name not in declared:
                errors.append(f"on {label}: updates undeclared state '{name}'")
            try:
                names = {n.id for n in ast.walk(ast.parse(expr, mode='eval'))
                         if isinstance(n, ast.Name)}
            except SyntaxError:
                errors.append(f"on {label}: unparseable expression '{expr}'")
                continue
            allowed = declared | {field_name} | set(SAFE_BUILTINS) | set(SAFE_HELPERS)
            for nm in names - allowed:
                errors.append(f"on {label}: expression references unknown '{nm}'")
    for (expr, sev) in ledger.invariants:
        try:
            names = {n.id for n in ast.walk(ast.parse(expr, mode='eval'))
                     if isinstance(n, ast.Name)}
        except SyntaxError:
            errors.append(f"invariant: unparseable '{expr}'")
            continue
        allowed = declared | set(SAFE_BUILTINS) | set(SAFE_HELPERS)
        for nm in names - allowed:
            errors.append(f"invariant '{expr}': references undeclared '{nm}'")
    return (len(errors) == 0, errors)
