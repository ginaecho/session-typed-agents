"""build_hosted_artifacts.py — host-side artifact builder for the hosted-group
workflow (S4, docs/reference/SDLC_HOSTED_WORKFLOW_SPEC.md).

Runs on the workstation (has scribble/java) and writes the artifacts the
container's main.py loads at start-up:

    foundry_hosted_agents/agent-framework-agent-with-remote-mcp-tools-responses/
      agents/<case.case_id>/artifacts/
        case_meta.json
        efsm.json
        refinements.json
        prompts.json
        prompts_index.json
        goals.json

Every prompt is built with the EXISTING repaired builders in
experiments/baselines/instructions.py and experiments/baselines/maf_groupchat.py
— this script never re-implements prompt text. See spec §1(A) for the exact
builder-per-arm mapping.

Usage:
    python build_hosted_artifacts.py <case_id>
    python build_hosted_artifacts.py skills_safety/sdlc_release_gate
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Path wiring — mirrors experiments/scripts/case_runner.py exactly so the
# imported builders see the same sys.path / .env as a normal case_runner run.
# ---------------------------------------------------------------------------

HERE = Path(__file__).resolve().parent            # experiments/scripts
EXPERIMENTS_DIR = HERE.parent                      # experiments/
REPO_ROOT = EXPERIMENTS_DIR.parent                 # session-typed-agents/
STJP_CORE = REPO_ROOT / "stjp_core"
CASES_DIR = EXPERIMENTS_DIR / "cases"
FOUNDRY_AGENTS_ROOT = (REPO_ROOT / "foundry_hosted_agents" /
                       "agent-framework-agent-with-remote-mcp-tools-responses")

sys.path.insert(0, str(HERE))             # case_loader
sys.path.insert(0, str(EXPERIMENTS_DIR))  # baselines package
sys.path.insert(0, str(REPO_ROOT))        # stjp_core library modules
load_dotenv(STJP_CORE / ".env")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from case_loader import Case
from baselines.instructions import (
    build_unchecked_skills_instructions,
    build_spec_minimal_instructions,
    build_global_spec_fairintent_instructions,
    _paraphrase_global_protocol,
)
from baselines.maf_groupchat import _build_orchestrator_instructions
from stjp_core.compiler.efsm_parser import get_all_efsms, EFSM
from stjp_core.compiler.refinement_checker import (
    load_refinements_for_protocol, Refinement, ChoiceGuard)
from stjp_core.compiler.protocol_parser import parse_protocol_file

# The 9 core arms, in the SAME order as baselines/registry.py SCENARIOS.
# RENAMED 2026-08-05 (BENCHMARK_PLAN_V3 §10.8 "Final arm naming",
# project-owner directive): skills/maf_skills (real skill-file baselines)
# replace bare/maf_groupchat; global_decentralized -> globalvalid (promoted
# from ablation tier, added to the hosted group same day: completes the
# info-placement x runtime grid -- whole validated plan as text on the
# round-robin runtime, observe-only monitor); maf_groupchat_llmvalid ->
# maf_globalvalid; min_llmvalid -> localvalid; maf_groupchat_llmvalid_orch ->
# maf_localvalid; min_llmvalid_gate -> localvalid_gate; min_llmvalid_sched ->
# localvalid_sched; maf_localvalid_sched is genuinely new (EFSM-scheduled MAF
# GroupChat -- feasibility confirmed same day, see main.py's MafGroupChatLoop
# docstring). This container has no legacy-key aliasing -- it is rebuilt
# fresh from this script on every deploy.
CORE_ARMS = [
    "skills",
    "maf_skills",
    "globalvalid",
    "maf_globalvalid",
    "localvalid",
    "maf_localvalid",
    "localvalid_gate",
    "maf_localvalid_gate",
    "localvalid_sched",
    "maf_localvalid_sched",
]

PROMPTS_SCHEMA_VERSION = 2


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# efsm.json
# ---------------------------------------------------------------------------

def _serialize_efsm(efsm: EFSM) -> dict:
    return {
        "role": efsm.role,
        "protocol_name": efsm.protocol_name,
        "states": sorted(efsm.states, key=lambda s: (0, int(s)) if s.isdigit() else (1, s)),
        "initial": efsm.initial_state,
        "accepting": sorted(efsm.accepting_states,
                            key=lambda s: (0, int(s)) if s.isdigit() else (1, s)),
        "transitions": [
            {
                "source": t.source, "target": t.target,
                "direction": t.direction, "label": t.label,
                "peer": t.peer, "payload_type": t.payload_type,
            }
            for t in efsm.transitions
        ],
    }


def build_efsm_json(case: Case, llmvalid_path: Path) -> dict:
    efsms = get_all_efsms(llmvalid_path, case.protocol_name, case.roles)
    return {role: _serialize_efsm(e) for role, e in efsms.items()}


# ---------------------------------------------------------------------------
# refinements.json
# ---------------------------------------------------------------------------

def _serialize_refinements(refn: dict) -> list[dict]:
    """Flatten the {key: Refinement|ChoiceGuard|SessionLedger} dict into a
    JSON-friendly list. Predicates are kept as their original source strings
    (never pre-evaluated) so the container's eval-based walker matches
    stjp_core/monitor/monitor.py exactly."""
    out: list[dict] = []
    for key, val in refn.items():
        if isinstance(val, Refinement):
            out.append({
                "kind": "refinement",
                "sender": val.sender, "receiver": val.receiver,
                "label": val.label, "declared_type": val.declared_type,
                "predicates": list(val.predicates),
            })
        elif isinstance(val, ChoiceGuard):
            out.append({
                "kind": "choice_guard",
                "role": val.role, "when": val.when,
                "require": val.require, "over": list(val.over),
            })
        elif key == "__ledger__":
            # Session ledger (stateful invariants) — not used by any of the
            # 7 core arms' gate logic today; recorded for completeness so a
            # future case that has one is not silently dropped.
            out.append({"kind": "ledger", "raw": str(val)})
    return out


def build_refinements_json(llmvalid_path: Path) -> list[dict]:
    refn = load_refinements_for_protocol(llmvalid_path)
    return _serialize_refinements(refn)


# ---------------------------------------------------------------------------
# prompts.json + prompts_index.json
# ---------------------------------------------------------------------------

def build_prompts(case: Case, llmvalid_path: Path) -> dict[str, dict[str, str]]:
    """{arm: {role_or_special: system_prompt}} for the 10 core arms.

    Builder-per-arm mapping, RENAMED 2026-08-05 (BENCHMARK_PLAN_V3 §10.8):
      skills                 -> build_unchecked_skills_instructions (real
                                 published per-role skill file); ex `bare`
      maf_skills              -> build_unchecked_skills_instructions
                                 + __orchestrator__ (no protocol); NEW
      globalvalid              -> build_global_spec_fairintent_instructions(override);
                                 ex `global_decentralized`
      maf_globalvalid           -> build_global_spec_fairintent_instructions(override)
                                 + __orchestrator__ (no protocol); ex `maf_groupchat_llmvalid`
      localvalid/*_gate/*_sched  -> build_spec_minimal_instructions(override=llm-valid),
                                 identical string, ONE entry computed and reused;
                                 ex `min_llmvalid`/`min_llmvalid_gate`/`min_llmvalid_sched`
      maf_localvalid              -> build_spec_minimal_instructions(override)
                                 + __orchestrator__ WITH protocol_text
                                 (reuses MAFGroupChatRunner.setup()'s exact snippet);
                                 ex `maf_groupchat_llmvalid_orch`
      maf_localvalid_sched          -> build_spec_minimal_instructions(override),
                                 SAME string as localvalid* (one entry reused);
                                 NO __orchestrator__ entry -- speaker selection
                                 is the programmatic EFSM selection_func in
                                 main.py's MafGroupChatLoop, not an LLM
                                 orchestrator agent. NEW (feasibility confirmed
                                 2026-08-05).
    """
    prompts: dict[str, dict[str, str]] = {arm: {} for arm in CORE_ARMS}

    # -- skills / maf_skills: real published per-role skill files ---------
    skills_prompts = {role: build_unchecked_skills_instructions(case, role)
                      for role in case.roles}
    prompts["skills"] = dict(skills_prompts)
    prompts["maf_skills"] = dict(skills_prompts)
    prompts["maf_skills"]["__orchestrator__"] = _build_orchestrator_instructions(case)

    # -- localvalid / localvalid_gate / localvalid_sched / maf_localvalid_sched
    # "identical string, one entry reused": compute once per role, share
    # across the four arm keys (byte-identical by construction, and only
    # ONE Scribble-projection round-trip per role instead of four).
    min_prompts = {role: build_spec_minimal_instructions(
        case, role, protocol_path_override=llmvalid_path) for role in case.roles}
    prompts["localvalid"] = dict(min_prompts)
    prompts["localvalid_gate"] = dict(min_prompts)
    prompts["maf_localvalid_gate"] = dict(min_prompts)
    prompts["localvalid_sched"] = dict(min_prompts)
    prompts["maf_localvalid_sched"] = dict(min_prompts)  # NO __orchestrator__: EFSM selection_func picks the speaker

    # -- globalvalid / maf_globalvalid: global-text-fairintent participants
    global_prompts = {role: build_global_spec_fairintent_instructions(
        case, role, protocol_path_override=llmvalid_path) for role in case.roles}
    prompts["globalvalid"] = dict(global_prompts)         # decentralized: NO __orchestrator__
    prompts["maf_globalvalid"] = dict(global_prompts)
    prompts["maf_globalvalid"]["__orchestrator__"] = _build_orchestrator_instructions(case)  # intent only, no protocol

    # -- maf_localvalid: local-contract participants + orchestrator carrying
    #    the validated global protocol. Reuses MAFGroupChatRunner.setup()'s
    #    exact orch-protocol-text snippet (baselines/maf_groupchat.py)
    #    rather than re-deriving it. ---------------------------------------
    prompts["maf_localvalid"] = dict(min_prompts)
    parsed = parse_protocol_file(llmvalid_path)
    paraphrase = _paraphrase_global_protocol(case, protocol_path=llmvalid_path)
    orch_protocol_text = (f"{parsed.raw_content}\n\n"
                          f"Natural-language summary:\n{paraphrase}")
    prompts["maf_localvalid"]["__orchestrator__"] = (
        _build_orchestrator_instructions(case, protocol_text=orch_protocol_text))
    prompts["maf_localvalid_gate"]["__orchestrator__"] = (
        _build_orchestrator_instructions(case, protocol_text=orch_protocol_text))

    return prompts


def build_prompts_index(prompts: dict[str, dict[str, str]]) -> dict:
    index: dict[str, list[dict]] = {}
    for arm, role_map in prompts.items():
        entries = []
        for role, text in role_map.items():
            entries.append({
                "role": role,
                "chars": len(text),
                "sha256": _sha256(text),
            })
        index[arm] = entries
    return {"prompts_schema_version": PROMPTS_SCHEMA_VERSION, "arms": index}


# ---------------------------------------------------------------------------
# goals.json
# ---------------------------------------------------------------------------

def build_goals_json(case: Case, llmvalid_path: Path) -> dict:
    import yaml as _yaml

    canonical = [{
        "id": g.id, "description": g.description, "metric": g.metric,
        "predicate": g.predicate,
        "anchor": {"sender": g.anchor_sender, "receiver": g.anchor_receiver,
                   "label": g.anchor_label},
        "threshold": g.threshold, "branch": g.branch, "category": g.category,
    } for g in case.goals]

    llmvalid_goals_path = llmvalid_path.parent / "goals.yaml"
    llm_valid = []
    if llmvalid_goals_path.exists():
        data = _yaml.safe_load(llmvalid_goals_path.read_text(encoding="utf-8")) or {}
        llm_valid = data.get("goals") or []

    return {"canonical": canonical, "llm_valid": llm_valid}


# ---------------------------------------------------------------------------
# case_meta.json
# ---------------------------------------------------------------------------

def build_case_meta(case: Case, llmvalid_path: Path) -> dict:
    intent_text = case.intent_effective
    return {
        "case_id": case.case_id,
        "roles": list(case.roles),
        "terminal_label": case.terminal_label,
        "max_steps": case.max_steps,
        "branch_hints": list(case.branch_hints),
        "intent_scale": case.intent_scale,
        "intent_sha256": _sha256(intent_text),
        "intent_chars": len(intent_text),
        "protocol_name": case.protocol_name,
        "llmvalid_protocol_relpath": str(
            llmvalid_path.relative_to(case.case_dir)).replace("\\", "/"),
        "prompts_schema_version": PROMPTS_SCHEMA_VERSION,
    }


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def build(case_id: str) -> Path:
    case_dir = CASES_DIR / case_id
    case = Case.load(case_dir, intent_scale="doc")
    llmvalid_path = case.case_dir / "protocols" / "llm_drafts" / "valid" / "v1.scr"
    if not llmvalid_path.exists():
        raise FileNotFoundError(
            f"missing LLM-drafted valid protocol: {llmvalid_path}. Run "
            f"draft_llm_protocols.py {case_id} first.")

    out_dir = FOUNDRY_AGENTS_ROOT / "agents" / case.case_id / "artifacts"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[build_hosted_artifacts] case={case.case_id} roles={case.roles}")
    print(f"[build_hosted_artifacts] llmvalid protocol: {llmvalid_path}")
    print(f"[build_hosted_artifacts] out_dir: {out_dir}")

    case_meta = build_case_meta(case, llmvalid_path)
    efsm_json = build_efsm_json(case, llmvalid_path)
    refinements_json = build_refinements_json(llmvalid_path)
    prompts = build_prompts(case, llmvalid_path)
    prompts_index = build_prompts_index(prompts)
    goals_json = build_goals_json(case, llmvalid_path)

    (out_dir / "case_meta.json").write_text(
        json.dumps(case_meta, indent=2), encoding="utf-8")
    (out_dir / "efsm.json").write_text(
        json.dumps(efsm_json, indent=2), encoding="utf-8")
    (out_dir / "refinements.json").write_text(
        json.dumps(refinements_json, indent=2), encoding="utf-8")
    (out_dir / "prompts.json").write_text(
        json.dumps(prompts, indent=2), encoding="utf-8")
    (out_dir / "prompts_index.json").write_text(
        json.dumps(prompts_index, indent=2), encoding="utf-8")
    (out_dir / "goals.json").write_text(
        json.dumps(goals_json, indent=2), encoding="utf-8")

    print(f"[build_hosted_artifacts] wrote 6 files:")
    for f in ["case_meta.json", "efsm.json", "refinements.json",
              "prompts.json", "prompts_index.json", "goals.json"]:
        p = out_dir / f
        print(f"    {f}  ({p.stat().st_size} bytes)")

    return out_dir


def main():
    if len(sys.argv) < 2:
        print("usage: build_hosted_artifacts.py <case_id>")
        print("  e.g. build_hosted_artifacts.py skills_safety/sdlc_release_gate")
        sys.exit(2)
    build(sys.argv[1])


if __name__ == "__main__":
    main()
