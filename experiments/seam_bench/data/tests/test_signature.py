"""signature.py — deterministic, whitespace-insensitive, behaviour-sensitive.

These tests hit the real Scribble validator (as does everything in this
package — there is no shortcut around it), so they are a handful of slow
subprocess calls rather than pure unit tests. Kept small on purpose.
"""
from pathlib import Path

from common import all_seeds
from signature import protocol_signature, SignatureCache, SignatureError


CORPUS_000 = (Path(__file__).resolve().parents[4] / "experiments" / "cases"
             / "_corpus" / "corpus_000.scr")


def test_signature_deterministic():
    text = CORPUS_000.read_text(encoding="utf-8")
    a = protocol_signature(text)
    b = protocol_signature(text)
    assert a == b
    assert a.startswith("efsmv1:")


def test_signature_whitespace_insensitive_via_cache():
    text = CORPUS_000.read_text(encoding="utf-8")
    reformatted = text.replace(" from ", "  from ").replace(" to ", "  to ")
    cache = SignatureCache(path=None)
    assert cache.signature(text) == cache.signature(reformatted)


def test_signature_differs_for_different_seeds():
    seeds = all_seeds()
    sigs = {s.seed_case: protocol_signature(s.text) for s in seeds[:6]}
    # not a strict guarantee across ALL seeds, but these are structurally
    # distinct corpus shapes and must not collide
    assert len(set(sigs.values())) == len(sigs)


def test_invalid_protocol_raises():
    broken = "module x;\n\nglobal protocol P(role A) {\n  Foo(String) from A to B;\n}\n"
    try:
        protocol_signature(broken)
        assert False, "expected SignatureError"
    except SignatureError:
        pass
