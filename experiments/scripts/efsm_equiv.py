"""efsm_equiv.py — do two protocols mean the same thing? (BENCHMARK_PLAN_V2 §6 / E5)

Translation fidelity (English -> protocol) must compare a DRAFTED protocol to a
GOLD one by MEANING, not text. Two protocols mean the same iff they accept
exactly the same conversations. This module provides that check three ways:

  efsm_bisimilar(e1, e2)        bisimulation on two single-role EFSMs (product
                                BFS; exact for the deterministic transition
                                systems Scribble projects).
  protocol_language(text)       the set of accepted message sequences (paths)
                                of a global protocol, loops unrolled once.
  protocols_equivalent(a, b)    the paper's check: same role set, per-role
                                projected EFSMs bisimilar, AND identical global
                                conversation language. Returns (bool, reason).

No LLM. Used by the translation-fidelity harness (translation_fidelity.py) to
score "EFSM-equivalent to gold" among validated drafts.
"""
from __future__ import annotations

import sys
import tempfile
from collections import deque
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

from stjp_core.compiler.efsm_parser import EFSM, get_all_efsms      # noqa: E402
from stjp_core.compiler.validator import ScribbleValidator          # noqa: E402
from stjp_core.critic.protocol_paths import paths_for_protocol      # noqa: E402
import re


def _edge_key(t):
    """Canonical label of an EFSM transition (ignores state numbering)."""
    return (t.direction, t.peer, t.label, t.payload_type)


def efsm_bisimilar(e1: EFSM, e2: EFSM) -> tuple[bool, str]:
    """Product-BFS bisimulation. Exact for deterministic transition systems
    (Scribble EFSMs are deterministic on (direction,peer,label))."""
    if not e1.initial_state or not e2.initial_state:
        # both empty behaviour -> equivalent; one empty -> not
        return (e1.transitions == [] and e2.transitions == []), "empty"

    start = (e1.initial_state, e2.initial_state)
    seen = {start}
    queue = deque([start])
    while queue:
        s1, s2 = queue.popleft()
        acc1, acc2 = e1.is_accepting(s1), e2.is_accepting(s2)
        if acc1 != acc2:
            return False, f"accepting mismatch at {(s1, s2)}: {acc1} vs {acc2}"
        out1 = {_edge_key(t): t.target for t in e1.transitions_from(s1)}
        out2 = {_edge_key(t): t.target for t in e2.transitions_from(s2)}
        if set(out1) != set(out2):
            only1 = set(out1) - set(out2)
            only2 = set(out2) - set(out1)
            return False, f"edge mismatch at {(s1, s2)}: only-A={only1} only-B={only2}"
        for k in out1:
            nxt = (out1[k], out2[k])
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return True, "bisimilar"


def _module_stem(text: str) -> str:
    m = re.search(r"module\s+(\w+)\s*;", text)
    return m.group(1) if m else "proto"


def _protocol_name(text: str) -> str:
    m = re.search(r"global\s+protocol\s+(\w+)", text)
    return m.group(1) if m else ""


def _roles(text: str) -> list[str]:
    m = re.search(r"global\s+protocol\s+\w+\s*\(([^)]*)\)", text, re.DOTALL)
    return re.findall(r"role\s+(\w+)", m.group(1)) if m else []


def protocol_language(text: str) -> frozenset:
    """Set of accepted conversations (each a tuple of (sender,receiver,label))."""
    ps = paths_for_protocol(text)
    return frozenset(
        tuple((e.sender, e.receiver, e.label) for e in path)
        for path in ps.paths)


def _project_all(text: str, workdir: Path) -> dict[str, EFSM]:
    stem = _module_stem(text)
    p = workdir / f"{stem}.scr"
    p.write_text(text, encoding="utf-8")
    ok, err = ScribbleValidator().validate_protocol(p)
    if not ok:
        raise ValueError(f"protocol {stem} invalid: {err[:200]}")
    return get_all_efsms(p, _protocol_name(text), _roles(text))


def protocols_equivalent(text_a: str, text_b: str) -> tuple[bool, str]:
    """Same role set + per-role EFSM bisimilar + identical conversation language."""
    ra, rb = sorted(_roles(text_a)), sorted(_roles(text_b))
    if ra != rb:
        return False, f"role sets differ: {ra} vs {rb}"
    with tempfile.TemporaryDirectory() as td:
        wd = Path(td)
        ea = _project_all(text_a, wd)
        eb = _project_all(text_b, wd)
    for role in ra:
        ok, why = efsm_bisimilar(ea[role], eb[role])
        if not ok:
            return False, f"role {role}: {why}"
    la, lb = protocol_language(text_a), protocol_language(text_b)
    if la != lb:
        return False, (f"conversation language differs "
                       f"(|A|={len(la)} |B|={len(lb)}, "
                       f"only-A={len(la - lb)} only-B={len(lb - la)})")
    return True, "equivalent"


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(
        description="Check two Scribble protocols are conversation-equivalent")
    ap.add_argument("a")
    ap.add_argument("b")
    args = ap.parse_args()
    a = Path(args.a).read_text(encoding="utf-8")
    b = Path(args.b).read_text(encoding="utf-8")
    ok, why = protocols_equivalent(a, b)
    print(f"{'EQUIVALENT' if ok else 'DIFFERENT'} — {why}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
