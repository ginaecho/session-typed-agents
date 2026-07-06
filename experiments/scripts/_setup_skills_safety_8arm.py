"""One-shot: wire skills_safety cases into the 8-arm harness layout.

For each case: copy skills_original/ -> unchecked_skills/, install the validated
synthesized protocol as protocols/v1.scr (+ llm_drafts/valid/v1.scr), emit a
minimal v1.refn, and derive llm_drafts/valid/goals.yaml from case.yaml.
"""
import shutil
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1] / "cases" / "skills_safety"
CASES = {
    "airline_seat": "AirlineSeat",
    "content_pipeline": "ContentPipeline",
    "code_execution": "CodeExecution",
    "booking_saga": "BookingSaga",
}

for case_id, proto in CASES.items():
    cdir = ROOT / case_id
    # 1. unchecked_skills/ <- skills_original/
    dst = cdir / "unchecked_skills"
    dst.mkdir(exist_ok=True)
    for f in (cdir / "skills_original").glob("*.md"):
        shutil.copy(f, dst / f.name)
    # 2. canonical protocol
    validated = cdir / "protocols" / f"{proto}.scr"
    (cdir / "protocols" / "v1.scr").write_text(validated.read_text(encoding="utf-8"), encoding="utf-8")
    refn = f"# Refinement contracts for {proto} (v1.scr)\n# (no value-level guards required for this case)\n"
    (cdir / "protocols" / "v1.refn").write_text(refn, encoding="utf-8")
    # 3. llm_drafts/valid
    vdir = cdir / "protocols" / "llm_drafts" / "valid"
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / "v1.scr").write_text(validated.read_text(encoding="utf-8"), encoding="utf-8")
    (vdir / "v1.refn").write_text(refn, encoding="utf-8")
    # 4. goals.yaml derived from case.yaml
    cfg = yaml.safe_load((cdir / "case.yaml").read_text(encoding="utf-8"))
    goals_doc = {"source_protocol": str(validated), "intent": cfg.get("intent", ""), "goals": cfg.get("goals", [])}
    (vdir / "goals.yaml").write_text(yaml.safe_dump(goals_doc, sort_keys=False), encoding="utf-8")
    print(f"[ok] {case_id}: unchecked_skills({len(list(dst.glob('*.md')))}) + v1.scr + valid/ + goals.yaml")

print("DONE")
