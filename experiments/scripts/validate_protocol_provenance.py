"""Validate a case protocol with nuscr and Scribble and persist provenance."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPERIMENTS_DIR = HERE.parent
REPO_ROOT = EXPERIMENTS_DIR.parent
CASES_DIR = EXPERIMENTS_DIR / "cases"
sys.path.insert(0, str(REPO_ROOT))

from experiments.scripts.case_loader import Case
from stjp_core.compiler.compiler_iface import get_compiler


def _atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_path = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    os.close(fd)
    tmp = Path(raw_path)
    try:
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True),
                       encoding="utf-8")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def _classify_nuscr_failure(message: str) -> str:
    text = message.lower()
    unsupported = (
        "not implemented", "unsupported", "not supported",
        "unimplemented", "cannot project",
    )
    return "not-implemented" if any(term in text for term in unsupported) else "fail"


def validate_case(case_id: str) -> tuple[dict, Path]:
    case = Case.load(CASES_DIR / case_id, intent_scale="doc")
    protocol = (case.case_dir / "protocols" / "llm_drafts" /
                "valid" / "v1.scr")
    if not protocol.is_file():
        raise FileNotFoundError(f"protocol not found: {protocol}")

    protocol_bytes = protocol.read_bytes()
    result = {
        "schema_version": 1,
        "case_id": case.case_id,
        "protocol_name": case.protocol_name,
        "protocol_path": str(protocol.relative_to(case.case_dir)),
        "protocol_sha256": hashlib.sha256(protocol_bytes).hexdigest(),
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "roles": list(case.roles),
    }

    nuscr = get_compiler("nuscr")
    nuscr_ok, nuscr_message = nuscr.validate(protocol)
    nuscr_result: dict = {
        "verdict": "pass" if nuscr_ok else _classify_nuscr_failure(nuscr_message),
        "message": nuscr_message,
        "projection_mode": "coinductive-full",
        "projections": {},
    }
    if nuscr_ok:
        try:
            for role in case.roles:
                local_type = nuscr.project_local_type(
                    protocol, case.protocol_name, role,
                    mode="coinductive-full")
                nuscr_result["projections"][role] = {
                    "chars": len(local_type),
                    "sha256": hashlib.sha256(
                        local_type.encode("utf-8")).hexdigest(),
                }
        except RuntimeError as exc:
            message = str(exc)
            nuscr_result["verdict"] = _classify_nuscr_failure(message)
            nuscr_result["message"] = message
    result["nuscr"] = nuscr_result

    scribble = get_compiler("scribble")
    scribble_ok, scribble_message = scribble.validate(protocol)
    scribble_result: dict = {
        "verdict": "pass" if scribble_ok else "fail",
        "message": scribble_message,
        "projections": {},
    }
    if scribble_ok:
        try:
            for role in case.roles:
                efsm = scribble.project_efsm(
                    protocol, case.protocol_name, role)
                scribble_result["projections"][role] = {
                    "states": len(efsm.states),
                    "transitions": len(efsm.transitions),
                }
        except RuntimeError as exc:
            scribble_result["verdict"] = "fail"
            scribble_result["message"] = str(exc)
    result["scribble"] = scribble_result

    out_path = protocol.parent / "protocol_validation.json"
    _atomic_write_json(out_path, result)

    provenance_path = case.case_dir / "intent" / "provenance.json"
    provenance = (
        json.loads(provenance_path.read_text(encoding="utf-8"))
        if provenance_path.exists() else {}
    )
    provenance["protocol_validation"] = {
        "artifact": str(out_path.relative_to(case.case_dir)),
        "protocol_sha256": result["protocol_sha256"],
        "nuscr_verdict": nuscr_result["verdict"],
        "scribble_verdict": scribble_result["verdict"],
        "validated_at": result["validated_at"],
    }
    _atomic_write_json(provenance_path, provenance)
    return result, out_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "case_id", nargs="?",
        default="skills_safety/sdlc_release_gate")
    args = parser.parse_args()

    result, out_path = validate_case(args.case_id)
    print(json.dumps({
        "protocol_sha256": result["protocol_sha256"],
        "nuscr_verdict": result["nuscr"]["verdict"],
        "scribble_verdict": result["scribble"]["verdict"],
        "artifact": str(out_path),
    }, indent=2))
    if result["scribble"]["verdict"] != "pass":
        return 1
    if result["nuscr"]["verdict"] == "fail":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
