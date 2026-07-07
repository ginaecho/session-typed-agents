"""
Tests for the nuscr protocol-compiler backend + the common ProtocolCompiler
interface.

Run:  python stjp_core/tests/test_nuscr_backend.py

Offline tests (syntax adapter, FSM-dot parser, backend factory) always run.
Docker-dependent tests (validate / project via the nuscr-coind image) are
skipped with a clear notice if Docker or the image is unavailable.
"""
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from stjp_core.compiler.nuscr_syntax import scr_to_nuscr
from stjp_core.compiler.efsm_parser import parse_nuscr_fsm_dot
from stjp_core.compiler.compiler_iface import (
    get_compiler,
    ScribbleCompiler,
)

LINEAR_SCR = """module v1;

data <java> "java.lang.String" from "rt.jar" as String;
data <java> "java.lang.Double" from "rt.jar" as Double;

global protocol Trade(role Buyer, role Seller) {
    Order(Double) from Buyer to Seller;
    Confirm(String) from Seller to Buyer;
}
"""

RECURSIVE_SCR = """module v1;

data <java> "java.lang.String" from "rt.jar" as String;

global protocol Stream(role P, role C) {
    rec LOOP {
        Data(String) from P to C;
        choice at C {
            More() from C to P;
            continue LOOP;
        } or {
            Stop() from C to P;
        }
    }
}
"""

SAMPLE_NUSCR_DOT = """digraph G {
  0;
  1;
  2;


  0 -> 1 [label="Seller!Order(int)", ];
  1 -> 2 [label="Seller?Confirm(String)", ];

  }
"""


def _docker_ok() -> bool:
    # A native binary (STJP_NUSCR_BIN) makes the runtime tests runnable
    # without Docker — see nuscr_compiler.py.
    from stjp_core.config import NUSCR_BIN
    if NUSCR_BIN and shutil.which(NUSCR_BIN):
        return True
    if shutil.which("docker") is None:
        return False
    try:
        r = subprocess.run(
            ["docker", "image", "inspect", "nuscr-coind:latest"],
            capture_output=True, text=True,
        )
        return r.returncode == 0
    except Exception:
        return False


def test_scr_to_nuscr_strips_preamble_and_maps_types():
    out = scr_to_nuscr(LINEAR_SCR)
    assert "module" not in out, "module line should be stripped"
    assert "data <java>" not in out, "data declarations should be stripped"
    assert "global protocol Trade" in out, "protocol body should survive"
    assert "Order(int)" in out, f"Double should map to int, got:\n{out}"
    assert "Confirm(String)" in out, "String payload should survive"
    print("  [ok] scr_to_nuscr strips preamble + maps Double->int")


def test_parse_nuscr_fsm_dot():
    efsm = parse_nuscr_fsm_dot(SAMPLE_NUSCR_DOT, role="Buyer", protocol_name="Trade")
    assert efsm.states == {"0", "1", "2"}, efsm.states
    assert efsm.initial_state == "0", efsm.initial_state
    assert efsm.accepting_states == {"2"}, efsm.accepting_states
    assert len(efsm.transitions) == 2, efsm.transitions
    t0 = efsm.transitions[0]
    assert (t0.source, t0.target) == ("0", "1")
    assert t0.direction == "send" and t0.peer == "Seller" and t0.label == "Order"
    assert t0.payload_type == "int", t0.payload_type
    t1 = efsm.transitions[1]
    assert t1.direction == "receive" and t1.label == "Confirm"
    print("  [ok] parse_nuscr_fsm_dot handles unquoted ids + trailing comma")


def test_backend_factory():
    assert isinstance(get_compiler("scribble"), ScribbleCompiler)
    assert get_compiler("scribble").name == "scribble"
    nu = get_compiler("nuscr")
    assert nu.name == "nuscr"
    try:
        get_compiler("bogus")
    except ValueError:
        pass
    else:
        raise AssertionError("unknown backend should raise ValueError")
    print("  [ok] get_compiler returns the right backend + rejects bad names")


def _write_tmp(scr_text: str, stem: str) -> Path:
    from stjp_core.config import NUSCR_DIR
    p = NUSCR_DIR / "_stjp_tmp" / f"{stem}.src.scr"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(scr_text, encoding="utf-8")
    return p


def test_nuscr_validate_and_project_linear():
    nu = get_compiler("nuscr")
    scr = _write_tmp(LINEAR_SCR, "trade_lin")
    ok, msg = nu.validate(scr)
    assert ok, f"linear protocol should validate, got: {msg}"
    efsm = nu.project_efsm(scr, "Trade", "Buyer")
    labels = {(t.direction, t.label) for t in efsm.transitions}
    assert ("send", "Order") in labels, labels
    assert ("receive", "Confirm") in labels, labels
    print("  [ok] nuscr validate + project_efsm on linear protocol")


def test_nuscr_coinductive_projection_recursive():
    nu = get_compiler("nuscr")
    scr = _write_tmp(RECURSIVE_SCR, "stream_rec")
    ok, msg = nu.validate(scr)
    assert ok, f"recursive protocol should validate, got: {msg}"
    lt = nu.project_local_type(scr, "Stream", "P", mode="coinductive-full")
    assert lt.strip(), "coinductive projection should be non-empty"
    assert "Data" in lt, f"projection should mention Data, got:\n{lt}"
    print("  [ok] nuscr coinductive-full projects a recursive protocol")


def main():
    print("test_nuscr_backend:")
    # offline
    test_scr_to_nuscr_strips_preamble_and_maps_types()
    test_parse_nuscr_fsm_dot()
    test_backend_factory()
    # docker-dependent
    if _docker_ok():
        test_nuscr_validate_and_project_linear()
        test_nuscr_coinductive_projection_recursive()
    else:
        print("  [skip] Docker/nuscr-coind image unavailable -> skipped nuscr runtime tests")
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
