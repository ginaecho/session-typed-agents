"""Unit tests for efsm_equiv.py (E5 checker): a protocol is equivalent to
itself and to a benign reformat, but NOT to a relabeled, reordered, or
role-renamed variant. Uses real Scribble projection.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE.parent / "scripts"))

from efsm_equiv import protocols_equivalent, protocol_language      # noqa: E402

GOLD = """module gold;
data <java> "java.lang.String" from "rt.jar" as String;
data <java> "java.lang.Double" from "rt.jar" as Double;
global protocol P(role A, role B, role C) {
    choice at A {
        Hi(Double) from A to B;
        HiN(String) from A to C;
    } or {
        Lo(Double) from A to B;
        LoN(String) from A to C;
    }
    R(String) from B to A;
    D(String) from C to A;
}
"""

# same meaning, reformatted whitespace + reordered the two INDEPENDENT tail
# messages R and D — but R (B->A) and D (C->A) are on different channels, so is
# this the same conversation LANGUAGE? The path sets differ in order, so the
# language check treats them as different sequences. We therefore test the
# IDENTICAL-order reformat for equivalence, and the reordered one for
# difference (documents that the language check is order-sensitive on the
# linearised paths).
SAME = """module same;
data <java> "java.lang.String" from "rt.jar" as String;
data <java> "java.lang.Double" from "rt.jar" as Double;

global protocol P(role A, role B, role C) {
    choice at A {
        Hi(Double)   from A to B;
        HiN(String)  from A to C;
    } or {
        Lo(Double)   from A to B;
        LoN(String)  from A to C;
    }
    R(String) from B to A;
    D(String) from C to A;
}
"""

RELABELED = GOLD.replace("Hi(", "Hello(").replace("module gold", "module relabeled")

REORDERED_TAIL = GOLD.replace(
    "    R(String) from B to A;\n    D(String) from C to A;",
    "    D(String) from C to A;\n    R(String) from B to A;"
).replace("module gold", "module reordered")

ROLE_RENAMED = GOLD.replace("role C", "role Z").replace(" to C;", " to Z;") \
    .replace("from C ", "from Z ").replace("module gold", "module renamed")


def test_self_equivalent():
    ok, why = protocols_equivalent(GOLD, GOLD)
    assert ok, why
    print("[equiv] protocol equivalent to itself")


def test_reformat_equivalent():
    ok, why = protocols_equivalent(GOLD, SAME)
    assert ok, why
    print("[equiv] whitespace/format reformat is equivalent")


def test_relabel_differs():
    ok, why = protocols_equivalent(GOLD, RELABELED)
    assert not ok, "relabeled protocol must not be equivalent"
    print(f"[equiv] relabeled differs — {why[:60]}")


def test_reorder_differs():
    ok, why = protocols_equivalent(GOLD, REORDERED_TAIL)
    assert not ok, "reordered conversation must not be equivalent"
    print(f"[equiv] reordered tail differs — {why[:60]}")


def test_role_rename_differs():
    ok, why = protocols_equivalent(GOLD, ROLE_RENAMED)
    assert not ok, "role-renamed protocol must not be equivalent"
    print(f"[equiv] role rename differs — {why[:60]}")


def test_language_counts():
    lang = protocol_language(GOLD)
    assert len(lang) == 2, f"gold has two branches -> two conversations, got {len(lang)}"
    print(f"[equiv] language enumerates {len(lang)} conversations")


if __name__ == "__main__":
    test_self_equivalent()
    test_reformat_equivalent()
    test_relabel_differs()
    test_reorder_differs()
    test_role_rename_differs()
    test_language_counts()
    print("ALL PASS")
