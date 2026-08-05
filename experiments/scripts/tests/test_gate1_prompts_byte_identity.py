"""Acceptance gate 1 (docs/reference/SDLC_HOSTED_WORKFLOW_SPEC.md §5.1).

RENAMED 2026-08-05 (BENCHMARK_PLAN_V3 §10.8 "Final arm naming") along with
the 10-arm hosted matrix: `skills` (ex `bare`) is now built from
`build_unchecked_skills_instructions`; the `min_llmvalid` family is now
`localvalid`/`localvalid_gate`/`localvalid_sched` (+ `maf_localvalid_sched`,
which shares the SAME prompt string -- "one entry reused").

  - prompts.json (written by build_hosted_artifacts.py) is sha-indexed:
    every (arm, role) entry's sha256 in prompts_index.json matches a fresh
    hash of the string actually stored in prompts.json.
  - The `skills` prompt for Author == build_unchecked_skills_instructions(case,
    "Author") byte-for-byte (the artifact must never diverge from the live
    builder it was generated from).

Run directly: python experiments/scripts/tests/test_gate1_prompts_byte_identity.py
Prerequisite: experiments/scripts/build_hosted_artifacts.py has been run for
skills_safety/sdlc_release_gate (writes
foundry_hosted_agents/.../agents/sdlc_release_gate/artifacts/).
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS_DIR = HERE.parent
EXPERIMENTS_DIR = SCRIPTS_DIR.parent
REPO_ROOT = EXPERIMENTS_DIR.parent
ARTIFACTS_DIR = (REPO_ROOT / "foundry_hosted_agents" /
                 "agent-framework-agent-with-remote-mcp-tools-responses" /
                 "agents" / "sdlc_release_gate" / "artifacts")

sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(EXPERIMENTS_DIR))
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv
load_dotenv(REPO_ROOT / "stjp_core" / ".env")

from case_loader import Case
from baselines.instructions import (build_unchecked_skills_instructions,
                                    build_spec_minimal_instructions,
                                    build_global_spec_fairintent_instructions)


def main() -> None:
    case = Case.load(EXPERIMENTS_DIR / "cases" / "skills_safety" / "sdlc_release_gate",
                     intent_scale="doc")
    llmvalid_path = (case.case_dir / "protocols" / "llm_drafts" / "valid" / "v1.scr")

    prompts = json.loads((ARTIFACTS_DIR / "prompts.json").read_text(encoding="utf-8"))
    prompts_index = json.loads(
        (ARTIFACTS_DIR / "prompts_index.json").read_text(encoding="utf-8"))

    expected_arms = {"skills", "maf_skills", "globalvalid", "maf_globalvalid",
                     "localvalid", "maf_localvalid", "localvalid_gate",
                     "maf_localvalid_gate", "localvalid_sched",
                     "maf_localvalid_sched"}
    assert set(prompts) == expected_arms, (
        f"prompts.json arm set mismatch: {set(prompts)} vs {expected_arms}")
    print("[gate1] arm-set check OK: exactly the 10 core arms are present")

    # Check 1: prompts.json is sha-indexed.
    n_checked = 0
    for arm, role_map in prompts.items():
        idx_entries = {e["role"]: e for e in prompts_index["arms"][arm]}
        assert set(idx_entries) == set(role_map), (
            f"prompts_index.json arm={arm} role set mismatch: "
            f"{set(idx_entries)} vs {set(role_map)}")
        for role, text in role_map.items():
            expected_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
            actual_sha = idx_entries[role]["sha256"]
            assert actual_sha == expected_sha, (
                f"sha mismatch arm={arm} role={role}: "
                f"index={actual_sha} recomputed={expected_sha}")
            assert idx_entries[role]["chars"] == len(text)
            n_checked += 1
    print(f"[gate1] sha-index check OK ({n_checked} (arm,role) prompt entries verified)")

    # Check 2: skills prompt for Author == build_unchecked_skills_instructions
    # output byte-for-byte (ex bare / build_bare_fairintent_instructions).
    live = build_unchecked_skills_instructions(case, "Author")
    artifact = prompts["skills"]["Author"]
    assert live == artifact, (
        "BYTE MISMATCH: build_unchecked_skills_instructions(case, 'Author') != "
        "artifacts/prompts.json['skills']['Author']")
    print(f"[gate1] byte-identity check OK: skills/Author prompt matches "
          f"build_unchecked_skills_instructions output exactly "
          f"({len(live)} chars, sha256={hashlib.sha256(live.encode()).hexdigest()})")

    # Bonus: same check for every role in skills / maf_skills (same builder),
    # globalvalid / maf_globalvalid (same builder), and every arm in the
    # localvalid* / maf_localvalid_sched quartet ("one entry reused").
    for role in case.roles:
        live_r = build_unchecked_skills_instructions(case, role)
        assert live_r == prompts["skills"][role], f"skills/{role} byte mismatch"
        assert live_r == prompts["maf_skills"][role], f"maf_skills/{role} byte mismatch"
    print(f"[gate1] byte-identity check OK for all {len(case.roles)} "
          f"skills/<role> and maf_skills/<role> prompts")

    for role in case.roles:
        live_r = build_global_spec_fairintent_instructions(
            case, role, protocol_path_override=llmvalid_path)
        assert live_r == prompts["globalvalid"][role], f"globalvalid/{role} byte mismatch"
        assert live_r == prompts["maf_globalvalid"][role], f"maf_globalvalid/{role} byte mismatch"
    print(f"[gate1] byte-identity check OK for all {len(case.roles)} "
          f"globalvalid/<role> and maf_globalvalid/<role> prompts")

    for role in case.roles:
        live_r = build_spec_minimal_instructions(
            case, role, protocol_path_override=llmvalid_path)
        a = prompts["localvalid"][role]
        b = prompts["localvalid_gate"][role]
        c = prompts["localvalid_sched"][role]
        d = prompts["maf_localvalid_sched"][role]
        e = prompts["maf_localvalid"][role]
        f = prompts["maf_localvalid_gate"][role]
        assert live_r == a == b == c == d == e == f, (
            f"localvalid*/maf_localvalid* "
            f"prompts differ for {role}")
    print("[gate1] localvalid / localvalid_gate / localvalid_sched / "
          "maf_localvalid_gate / maf_localvalid_sched / maf_localvalid "
          "prompts are byte-identical "
          "per role to build_spec_minimal_instructions (one entry reused), "
          "as required")

    # maf_skills / maf_globalvalid / maf_localvalid carry an __orchestrator__
    # prompt; maf_localvalid_sched deliberately does NOT (no LLM orchestrator
    # -- speaker selection is the EFSM selection_func).
    for arm in ("maf_skills", "maf_globalvalid", "maf_localvalid",
                "maf_localvalid_gate"):
        assert "__orchestrator__" in prompts[arm], f"{arm} missing __orchestrator__ prompt"
    assert "__orchestrator__" not in prompts["maf_localvalid_sched"], (
        "maf_localvalid_sched must NOT have an __orchestrator__ prompt "
        "(EFSM selection_func, no LLM orchestrator)")
    for arm in ("skills", "globalvalid", "localvalid", "localvalid_gate",
                "localvalid_sched"):
        assert "__orchestrator__" not in prompts[arm], (
            f"{arm} (round-robin arm) must not have an __orchestrator__ prompt")
    print("[gate1] __orchestrator__ presence/absence check OK for all 10 arms")

    print("\n[gate1] ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
