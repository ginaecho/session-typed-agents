"""Generate per-case hosted-group specs for the unified MAF-orchestrator design.

Each case becomes ONE hosted Foundry agent group: a MAF GroupChat whose
orchestrator HOLDS the validated protocol (it picks the speaker each round)
and whose participants hold only their projected local contract. The prompts
are rendered HERE (scribble-java projection runs on this machine) and baked
into a group_spec.json; the container needs no Java, only the pre-rendered
prompts. This is the hosted-surface twin of the maf_groupchat_llmvalid_orch
benchmark arm.

Output per case: <hosted_root>/agents/<case_id>/group_spec.json
"""
import json
import sys
from pathlib import Path

STJP = Path(r"c:/Users/tzuchunchen/Documents/05_Research/EAG/eag-innovation/agentic-governance/stjp")
sys.path.insert(0, str(STJP))
sys.path.insert(0, str(STJP / "experiments"))

from scripts.case_loader import Case
from baselines.instructions import build_spec_minimal_instructions
from baselines.maf_groupchat import _build_orchestrator_instructions

HOSTED_ROOT = STJP / "foundry_hosted_agents" / "agent-framework-agent-with-remote-mcp-tools-responses"

CASES = [
    "skills_safety/code_execution", "skills_safety/airline_seat",
    "skills_safety/booking_saga", "skills_safety/content_pipeline",
    "finance", "agenticpay_settlement", "skills_safety/pr_review_merge",
    "agenticpay_multi_buyer", "agenticpay_multi_seller",
    "skills_safety/react18_migration", "skills_safety/sdlc_release_gate",
    "skills_safety/gem_dev_team", "memory_race",
]


def valid_protocol_path(case_dir: Path, canonical: Path) -> Path:
    """Use the LLM-drafted validated protocol if present (matches the
    maf_groupchat_llmvalid_orch arm), else the canonical protocol."""
    draft = case_dir / "protocols" / "llm_drafts" / "valid" / "v1.scr"
    return draft if draft.exists() else canonical


def main():
    summary = []
    for rel in CASES:
        case_dir = STJP / "experiments" / "cases" / rel
        case = Case.load(case_dir)
        proto = valid_protocol_path(case_dir, case.protocol_path)
        proto_text = proto.read_text(encoding="utf-8")

        participants = {}
        for role in case.roles:
            # projected local contract (scribble-java runs here)
            participants[role] = build_spec_minimal_instructions(
                case, role, protocol_path_override=proto)
        orch_prompt = _build_orchestrator_instructions(case, proto_text)

        group_name = "stjp-" + case.case_id.replace("_", "-") + "-group"
        spec = {
            "case_id": case.case_id,
            "group_name": group_name,
            "roles": case.roles,
            "terminal_label": case.terminal_label,
            "max_rounds": case.max_steps + 4,
            "orchestrator_prompt": orch_prompt,
            "participants": participants,
            "protocol_source": str(proto.relative_to(STJP)),
        }
        out_dir = HOSTED_ROOT / "agents" / case.case_id
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "group_spec.json").write_text(
            json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")
        summary.append((case.case_id, group_name, len(case.roles),
                        len(orch_prompt), sum(len(p) for p in participants.values())))
        print(f"  {case.case_id:24s} {group_name:34s} roles={len(case.roles)} "
              f"orch={len(orch_prompt)}c participants={sum(len(p) for p in participants.values())}c")
    print(f"\nGenerated {len(summary)} group_spec.json files under {HOSTED_ROOT/'agents'}")


if __name__ == "__main__":
    main()
