"""mutate_protocol.py — inject one specific defect into a valid Scribble protocol.

Used by mutation_bench.py (BENCHMARK_PLAN_V2 §2 / E1) to test the CHECKER:
break known-good protocols on purpose, one defect at a time, and measure how
many the validator catches (soundness) and how many good ones it wrongly
rejects (completeness / false positives).

Each operator takes (protocol_text, rng) and returns a mutated protocol string,
or None if the operator does not apply to this protocol. Operators are
syntactic transforms chosen so that a *typical* application produces a
protocol the type system should reject; a small fraction may yield a
semantically-equivalent (harmless) mutant — standard mutation-testing practice
— which shows up as a "surviving mutant" and is reported honestly.

Defect classes (mapped to the plan's names):
  circular_wait   reverse one message direction -> a role must send before it
                  is enabled / a wait-for cycle appears (Scribble core).
  swap_order      swap two adjacent top-level messages -> unenabled sender /
                  safety violation (Scribble core).
  drop_message    delete one top-level message -> a downstream role is stranded
                  or a later sender is never enabled (Scribble core).
  rewire_peer     redirect one message to a different declared role -> broken
                  causal enablement (Scribble core).
  undeclare_role  drop a used role from the header -> "role not declared"
                  (Scribble core; ~always caught).
  branch_asymmetry delete a message from ONE branch of a choice -> a role
                  present in some branches only / inconsistent choice
                  (Scribble core, our external-choice discipline).
"""
from __future__ import annotations

import re

_MSG_RE = re.compile(r'^(\s*)(\w+)\(([^)]*)\)\s+from\s+(\w+)\s+to\s+(\w+)\s*;\s*$')
_HEADER_RE = re.compile(r'(global\s+protocol\s+\w+\s*\()([^)]*)(\)\s*\{)', re.DOTALL)

# Well-formedness defects: constructive transforms that produce protocols the
# type system SHOULD reject (undeclared role, choice-knowledge / enabling
# errors). These carry the soundness claim — expect high detection.
WELLFORMED_DEFECTS = ["undeclare_role", "branch_asymmetry", "flip_branch_subject"]

# Reordering transforms: local edits to message order/peers. On an ACYCLIC
# protocol these usually yield ANOTHER well-formed protocol, which Scribble
# correctly accepts — so low "detection" here is not a checker failure, it is
# the checker declining to reject a genuinely-safe protocol. Reported
# separately; catching intent drift is the job of goals/refinements, not the
# well-formedness checker.
REORDER_OPS = ["circular_wait", "swap_order", "drop_message", "rewire_peer"]

CLASSES = WELLFORMED_DEFECTS + REORDER_OPS


def _lines_with_depth(text: str):
    """Yield (index, line, brace_depth_before_line) for each line."""
    depth = 0
    out = []
    for i, line in enumerate(text.splitlines()):
        out.append((i, line, depth))
        depth += line.count("{") - line.count("}")
    return out


def _message_line_indices(text: str, top_level_only: bool):
    """Indices of lines that are a single message interaction.
    top_level_only: brace depth == 1 (inside the protocol body, not a choice)."""
    idxs = []
    for i, line, depth in _lines_with_depth(text):
        if _MSG_RE.match(line):
            if not top_level_only or depth == 1:
                idxs.append(i)
    return idxs


def _declared_roles(text: str):
    m = _HEADER_RE.search(text)
    return re.findall(r'role\s+(\w+)', m.group(2)) if m else []


def circular_wait(text: str, rng) -> str | None:
    idxs = _message_line_indices(text, top_level_only=True)
    if not idxs:
        return None
    lines = text.splitlines()
    i = rng.choice(idxs)
    m = _MSG_RE.match(lines[i])
    ind, lbl, ty, a, b = m.groups()
    lines[i] = f"{ind}{lbl}({ty}) from {b} to {a};"   # reverse direction
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def swap_order(text: str, rng) -> str | None:
    idxs = _message_line_indices(text, top_level_only=True)
    # need two ADJACENT top-level message lines
    adj = [(idxs[k], idxs[k + 1]) for k in range(len(idxs) - 1)
           if idxs[k + 1] == idxs[k] + 1]
    if not adj:
        return None
    lines = text.splitlines()
    i, j = rng.choice(adj)
    lines[i], lines[j] = lines[j], lines[i]
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def drop_message(text: str, rng) -> str | None:
    idxs = _message_line_indices(text, top_level_only=True)
    if len(idxs) < 2:                     # keep at least one interaction
        return None
    lines = text.splitlines()
    i = rng.choice(idxs)
    del lines[i]
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def rewire_peer(text: str, rng) -> str | None:
    idxs = _message_line_indices(text, top_level_only=True)
    roles = _declared_roles(text)
    if not idxs or len(roles) < 3:
        return None
    lines = text.splitlines()
    i = rng.choice(idxs)
    m = _MSG_RE.match(lines[i])
    ind, lbl, ty, a, b = m.groups()
    others = [r for r in roles if r not in (a, b)]
    if not others:
        return None
    new_b = rng.choice(others)
    lines[i] = f"{ind}{lbl}({ty}) from {a} to {new_b};"
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def undeclare_role(text: str, rng) -> str | None:
    roles = _declared_roles(text)
    if len(roles) < 2:
        return None
    m = _HEADER_RE.search(text)
    # drop a role that is USED in the body (so the omission is a real error)
    body = text[m.end():]
    used = [r for r in roles if re.search(rf'\b{r}\b', body)]
    victim = rng.choice(used or roles)
    kept = [r for r in roles if r != victim]
    new_header = ", ".join(f"role {r}" for r in kept)
    return text[:m.start(2)] + new_header + text[m.end(2):]


def branch_asymmetry(text: str, rng) -> str | None:
    # delete one message line that sits INSIDE a choice (depth >= 2)
    inner = [i for i, line, depth in _lines_with_depth(text)
             if _MSG_RE.match(line) and depth >= 2]
    if not inner:
        return None
    lines = text.splitlines()
    i = rng.choice(inner)
    del lines[i]
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def flip_branch_subject(text: str, rng) -> str | None:
    """In a choice, reverse the FIRST message of a branch so its subject (the
    sending role) is no longer the chooser. Scribble rejects this as an
    inconsistent external-choice subject / an unenabled sender — the canonical
    MPST knowledge-of-choice defect."""
    lines = text.splitlines()
    depths = _lines_with_depth(text)
    # locate a `choice at <Chooser> {` and the first message line strictly
    # inside it (depth increased). Reverse that message's direction.
    for i, line, depth in depths:
        cm = re.search(r'choice\s+at\s+(\w+)', line)
        if not cm:
            continue
        chooser = cm.group(1)
        for j in range(i + 1, len(lines)):
            mm = _MSG_RE.match(lines[j])
            if mm:
                ind, lbl, ty, a, b = mm.groups()
                if a == chooser:                 # reverse so chooser no longer sends
                    lines[j] = f"{ind}{lbl}({ty}) from {b} to {a};"
                    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")
            if "}" in lines[j]:                  # left this branch without a hit
                break
    return None


OPERATORS = {
    "flip_branch_subject": flip_branch_subject,
    "circular_wait": circular_wait,
    "swap_order": swap_order,
    "drop_message": drop_message,
    "rewire_peer": rewire_peer,
    "undeclare_role": undeclare_role,
    "branch_asymmetry": branch_asymmetry,
}


def mutate(text: str, defect_class: str, rng) -> str | None:
    """Apply one mutation of `defect_class`. Returns mutated text or None."""
    op = OPERATORS.get(defect_class)
    if op is None:
        raise ValueError(f"unknown defect class {defect_class!r}; "
                         f"choices: {list(OPERATORS)}")
    return op(text, rng)
