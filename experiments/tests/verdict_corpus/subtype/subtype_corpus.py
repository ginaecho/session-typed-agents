"""Subtype + anticipation verdict corpus — 14 hand-built cases (Prototype 2).

Discipline (E0): the new checker's behaviour is pinned by a hand-written corpus
that must pass 14/14 BEFORE the E9 benchmark trusts it. EFSMs are built directly
(no Scribble needed) so the cases are self-contained and fast. Half exercise the
compile-time subtype check `is_subtype` (2a), half the runtime anticipation
fragment `anticipable` (2b), including the LMCS'17-style negative cases that
must be REJECTED.

Run:  python experiments/tests/verdict_corpus/subtype/subtype_corpus.py
Exit 0 iff 14/14.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from stjp_core.compiler.efsm_parser import EFSM, Transition          # noqa: E402
from stjp_core.compiler.check_subtype import is_subtype, anticipable  # noqa: E402


def efsm(role, trans, init="0"):
    """Build an EFSM from (src, dir, peer, label, target[, payload]) tuples."""
    e = EFSM(role=role, protocol_name="T")
    for t in trans:
        src, d, peer, label, tgt = t[0], t[1], t[2], t[3], t[4]
        pay = t[5] if len(t) > 5 else ""
        e.transitions.append(Transition(source=src, target=tgt, direction=d,
                                         peer=peer, label=label, payload_type=pay))
        e.states.add(src); e.states.add(tgt)
    srcs = {t.source for t in e.transitions}
    e.initial_state = init
    e.accepting_states = e.states - srcs
    return e


S, R = "send", "receive"

# ── (2a) SUBTYPE cases: (id, T'(sub), T(sup), expect_subtype) ────────────────
SUB_CASES = []

# S1 identical → subtype
_t = [("0", S, "P", "a", "1")]
SUB_CASES.append(("S1_identical", efsm("A", _t), efsm("A", _t), True))

# S2 output covariance: T' selects a SUBSET of T's sends → subtype
sup = efsm("A", [("0", S, "P", "a", "1"), ("0", S, "P", "b", "2")])
sub = efsm("A", [("0", S, "P", "a", "1")])
SUB_CASES.append(("S2_output_subset", sub, sup, True))

# S3 output SUPERSET: T' offers a send T does not → NOT subtype
sup = efsm("A", [("0", S, "P", "a", "1")])
sub = efsm("A", [("0", S, "P", "a", "1"), ("0", S, "P", "b", "2")])
SUB_CASES.append(("S3_output_superset", sub, sup, False))

# S4 input contravariance: T' offers a SUPERSET of T's receives → subtype
sup = efsm("A", [("0", R, "P", "a", "1")])
sub = efsm("A", [("0", R, "P", "a", "1"), ("0", R, "P", "b", "2")])
SUB_CASES.append(("S4_input_superset", sub, sup, True))

# S5 input SUBSET: T' drops a receive T requires → NOT subtype
sup = efsm("A", [("0", R, "P", "a", "1"), ("0", R, "P", "b", "2")])
sub = efsm("A", [("0", R, "P", "a", "1")])
SUB_CASES.append(("S5_input_subset", sub, sup, False))

# S6 drop the ONLY send (T' terminal where T must send) → NOT subtype
sup = efsm("A", [("0", S, "P", "settle", "1")])
sub = efsm("A", [])          # terminal at 0
sub.initial_state = "0"; sub.states = {"0"}; sub.accepting_states = {"0"}
SUB_CASES.append(("S6_drop_only_send", sub, sup, False))

# S7 payload mismatch on a matched send → NOT subtype (exact-sort v1)
sup = efsm("A", [("0", S, "P", "a", "1", "String")])
sub = efsm("A", [("0", S, "P", "a", "1", "Double")])
SUB_CASES.append(("S7_payload_mismatch", sub, sup, False))

# ── (2b) ANTICIPATION cases: (id, EFSM, state, peer, label, expect) ──────────
ANT_CASES = []

# A1 safe single-receive anticipation: ?x then !y, y independent of x → admit
e = efsm("A", [("0", R, "P", "x", "1"), ("1", S, "Q", "y", "2")])
ANT_CASES.append(("A1_safe_single", e, "0", "Q", "y", True))

# A2 dependent branch: after ?x the type BRANCHES; y only on one branch → reject
e = efsm("A", [("0", R, "P", "x1", "1"), ("0", R, "P", "x2", "2"),
               ("1", S, "Q", "y", "3"), ("2", S, "Q", "z", "4")])
ANT_CASES.append(("A2_dependent_branch", e, "0", "Q", "y", False))

# A3 anticipate PAST a pending send → reject (fragment is receives-only)
e = efsm("A", [("0", S, "Q", "a", "1"), ("1", S, "Q", "y", "2")])
ANT_CASES.append(("A3_past_pending_send", e, "0", "Q", "y", False))

# A4 strictly enabled here → NOT an anticipation (reject; strict gate handles it)
e = efsm("A", [("0", S, "Q", "y", "1")])
ANT_CASES.append(("A4_strictly_enabled", e, "0", "Q", "y", False))

# A5 two INDEPENDENT receives before y, single path → admit (bounded depth 2)
e = efsm("A", [("0", R, "P", "x", "1"), ("1", R, "P2", "w", "2"),
               ("2", S, "Q", "y", "3")])
ANT_CASES.append(("A5_two_receive_chain", e, "0", "Q", "y", True))

# A6 KEY positive: after ?x the type branches but BOTH branches enable y → admit
e = efsm("A", [("0", R, "P", "x1", "1"), ("0", R, "P", "x2", "2"),
               ("1", S, "Q", "y", "3"), ("2", S, "Q", "y", "4")])
ANT_CASES.append(("A6_all_branches_enable", e, "0", "Q", "y", True))

# A7 receive loop that NEVER enables y → reject (bounded search terminates)
e = efsm("A", [("0", R, "P", "x", "0")])   # self-loop on receive, y never appears
ANT_CASES.append(("A7_loop_no_enable", e, "0", "Q", "y", False))


def main() -> int:
    passed, failed = 0, []
    print("── SUBTYPE + ANTICIPATION verdict corpus (Prototype 2) ──")
    print("  · compile-time subtype (2a):")
    for cid, sub, sup, exp in SUB_CASES:
        got, why = is_subtype(sub, sup)
        ok = (got == exp)
        print(f"    {'PASS' if ok else 'FAIL'}  {cid}"
              + ("" if ok else f"  — got {got} exp {exp} ({why})"))
        passed += ok
        if not ok:
            failed.append(cid)
    print("  · runtime anticipation fragment (2b):")
    for cid, e, st, peer, label, exp in ANT_CASES:
        got = anticipable(e, st, peer, label)
        ok = (got == exp)
        print(f"    {'PASS' if ok else 'FAIL'}  {cid}"
              + ("" if ok else f"  — got {got} exp {exp}"))
        passed += ok
        if not ok:
            failed.append(cid)
    total = len(SUB_CASES) + len(ANT_CASES)
    print(f"\nSUBTYPE CORPUS: {passed}/{total} passed"
          + (f" — FAILURES: {failed}" if failed else "  ✓ checker trustworthy"))
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
