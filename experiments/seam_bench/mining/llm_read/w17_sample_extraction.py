"""W17 model-read extraction over a RANDOM SAMPLE of the newly-mined
coordination-requiring teams.

Context: `coordination_filter.py` judged all 110 candidate teams the W17
harvest produced (`docs/reference/reports/seam/W17_coordination_scale_up.md`).
32 were judged `requires_coordination: yes`. Of those, 9 are W16's own
already-extracted teams (8 `worked-example` teams + the `gem-orchestrator`
subset of the 15-role `explicit_ref` cluster — `llm_read/extraction.py`,
unchanged, still reproduces those results byte-for-byte, verified 2026-07-12).
The remaining 23 were NOT individually deep-extracted (time-boxed per the
task card: "the filter verdict on all candidates matters more than deep
extraction on every single one"). Instead, this file model-reads a RANDOM
SAMPLE of 8 of those 23 (`random.seed(1707); random.sample(remaining, 8)` —
reproduced in `docs/reference/reports/seam/W17_coordination_scale_up.md`),
plus 2 additional teams checked because they are the only two remaining
MIT-licensed candidates from `crewAIInc/crewAI` (crewAI-examples' 12 "yes"
teams are all license-quarantined — see `ledger.py` — so they cannot yield
`test-real` records regardless of extraction outcome; these two were worth
checking directly rather than leaving the only license-clean new source
unexamined). The 2 bonus teams are flagged `via_random_sample=False` in the
summary so they are never miscounted as part of the n=8 statistical sample.

Extraction discipline is IDENTICAL to W16's (`llm_read/extraction.py`
module docstring): only write a `Peer!Label(Type);` / `Peer?Label(Type);`
line when the role's own text, or a teammate's text naming this role, states
or clearly implies it — never invent an edge from plausibility alone.

Two corrections this pass made to `coordination_filter` batch verdicts,
found only by reading the full source files (not just the dossier's short
descriptions) — recorded here AND cross-referenced in the verdicts JSONL's
`extra.corrected_from` field so the correction is auditable, not silent:

  - `same_dir:github/awesome-copilot:skills/quality-playbook/agents`: the
    batch judge read "each in its own context window via sub-agents" as
    inter-file coordination; the full text says the opposite — one file
    explicitly instructs the reader NOT to invoke the other file as a
    sub-agent ("Do not spawn a separate `quality-playbook` sub-agent from
    another session"). Corrected yes -> no.
  - `same_dir:rohitg00/awesome-claude-code-toolkit:plugins/visual-regression/commands`:
    the batch judge read `/compare`'s dependency on `/capture-baseline`'s
    output file as coordination; both are generic slash-commands invoked by
    the SAME single actor (a developer's own two CLI invocations), not two
    interacting parties handing work to each other. Corrected yes -> no.
  - `same_dir:VoltAgent/awesome-claude-code-subagents:categories/09-meta-orchestration`
    (this specific 3-role residual grouping: agent-installer,
    it-ops-orchestrator, knowledge-synthesizer): it-ops-orchestrator's OWN
    task genuinely needs a specialist counterpart ("dispatch the work to the
    most appropriate specialists"), but neither of its two actual teammates
    in THIS heuristically-formed trio is that counterpart (agent-installer
    only assists a human browsing a catalog; knowledge-synthesizer's real
    named collaborators are six OTHER files already claimed by an earlier
    heuristic pass, not the two present here). Corrected yes -> unclear.

Usage:
    python -m experiments.seam_bench.mining.llm_read.w17_sample_extraction \\
        --remote-root <dir with awesome-copilot/, VoltAgent/, anthropic-skills/,
                        crewAI-core/, crewAI-examples/, rohitg00-toolkit/>
        --scratch-dir <scratch dir>
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[3]
MINING = HERE.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(MINING))

from run_mining import harvest_all                                       # noqa: E402
from team_builder import build_teams                                     # noqa: E402
from ledger import build_ledger                                          # noqa: E402
from intent_extract import extract_intent                                # noqa: E402
from schema import DatasetRecord, write_jsonl                            # noqa: E402
from stjp_core.generation.skill_compactor import compact_and_synthesize, CompactionError  # noqa: E402

RANDOM_SAMPLE_TEAM_IDS = [
    "same_dir:rohitg00/awesome-claude-code-toolkit:plugins/visual-regression/commands",
    "same_dir:VoltAgent/awesome-claude-code-subagents:categories/09-meta-orchestration",
    "named_counterpart:VoltAgent/awesome-claude-code-subagents:incident-responder+devops-incident-responder",
    "crewai_config:crewAIInc/crewAI-examples:flows/write_a_book_with_flows/src/write_a_book_with_flows/crews/outline_book_crew",
    "crewai_config:crewAIInc/crewAI-examples:crews/surprise_trip/src/surprise_travel",
    "crewai_config:crewAIInc/crewAI-examples:crews/screenplay_writer",
    "named_counterpart:VoltAgent/awesome-claude-code-subagents:codebase-orchestrator+readme-generator",
    "same_dir:github/awesome-copilot:skills/quality-playbook/agents",
]
BONUS_LICENSED_TEAM_IDS = [
    "crewai_config:crewAIInc/crewAI:lib/cli/src/crewai_cli/templates/crew",
    "crewai_config:crewAIInc/crewAI:lib/cli/src/crewai_cli/templates/flow/crews/content_crew",
]

# team_id -> dict(blocks: {role_hint: block_body}, evidence: {...}, excluded: {...},
#                 corrected_verdict: str|None, notes: str)
EXTRACTIONS = {
    "same_dir:rohitg00/awesome-claude-code-toolkit:plugins/visual-regression/commands": dict(
        blocks={}, evidence={},
        excluded={
            "capture-baseline": {"category": "pure-solo-task", "reason":
                "A generic CLI slash-command; its steps ('Save screenshots to the baselines directory') "
                "produce a file artifact, not a message to another named party."},
            "compare": {"category": "pure-solo-task", "reason":
                "Step 1 ('Verify that baseline screenshots exist') reads capture-baseline's output FILE, "
                "but both commands are run by the SAME single actor (a developer's own sequential CLI "
                "invocations) — that is a data dependency across two steps of one workflow, not two "
                "interacting parties."},
        },
        corrected_verdict="no",
        notes="coordination_filter batch verdict corrected yes->no after reading full command text: "
              "a shared file across two sequential single-actor commands is not multi-party coordination "
              "(same failure mode W16 found for VoltAgent's fetch/invalidate/list/search cache-file commands).",
    ),
    "same_dir:VoltAgent/awesome-claude-code-subagents:categories/09-meta-orchestration": dict(
        blocks={}, evidence={},
        excluded={
            "agent-installer": {"category": "pure-solo-task", "reason":
                "Helps a human user browse/install agents from the repo; its 'Usage Example' addresses the "
                "user directly, never another team role."},
            "it-ops-orchestrator": {"category": "ambiguous", "reason":
                "Its own task genuinely needs a specialist counterpart ('dispatch the work to the most "
                "appropriate specialists—especially PowerShell or .NET agents'), but neither teammate "
                "actually present in this specific 3-file grouping (agent-installer, knowledge-synthesizer) "
                "is that counterpart — the real specialists it means are elsewhere in the repo, unclaimed "
                "by this heuristic instance."},
            "knowledge-synthesizer": {"category": "ambiguous", "reason":
                "Has a real 'Integration with other agents:' section, but every name in it (performance-monitor, "
                "error-coordinator, agent-organizer, workflow-orchestrator, context-manager, "
                "multi-agent-coordinator) was already claimed by an earlier named-counterpart pass — none is "
                "agent-installer or it-ops-orchestrator, its actual teammates here."},
        },
        corrected_verdict="unclear",
        notes="coordination_filter batch verdict corrected yes->unclear: it-ops-orchestrator's task is real "
              "and coordination-shaped, but this specific residual 3-file grouping does not represent that "
              "dependency — its true counterparts were claimed by team_builder's earlier heuristic pass.",
    ),
    "named_counterpart:VoltAgent/awesome-claude-code-subagents:incident-responder+devops-incident-responder": dict(
        blocks={}, evidence={},
        excluded={
            "incident-responder": {"category": "no-ordering-stated", "reason":
                "Its own text ('requires immediate response, evidence preservation, and coordinated recovery') "
                "and its collaboration bullet ('Support devops-incident-responder on operational issues') "
                "confirm a REAL, correctly-matched need for coordination with this exact teammate — but neither "
                "file names a specific message/artifact exchanged, only a generic supervisory verb ('Support "
                "... on'). No labeled interaction can be written without inventing one."},
            "devops-incident-responder": {"category": "no-ordering-stated", "reason":
                "Mirror of incident-responder's finding: 'Support sre-engineer on reliability' etc. are real "
                "but generic collaboration bullets with no specific payload to extract."},
        },
        corrected_verdict=None,
        notes="coordination_filter verdict CONFIRMED yes on reread (this is the control case in the sample: "
              "not every 'yes' turned out to be a batch-judging error) — 'Support devops-incident-responder on "
              "operational issues' correctly names the actual teammate, unlike the other VoltAgent samples in "
              "this batch. Structure genuinely needed, but not extractable: generic 'support/coordinate' verbs "
              "carry no message label, unlike CrewAI's 'based on the research findings' phrasing.",
    ),
    "crewai_config:crewAIInc/crewAI-examples:flows/write_a_book_with_flows/src/write_a_book_with_flows/crews/outline_book_crew": dict(
        blocks={
            "researcher": "outliner!ResearchFindings(String);",
            "outliner": "researcher?ResearchFindings(String);",
        },
        evidence={
            "researcher": [{"edge": "researcher->outliner: ResearchFindings", "quote":
                "generate_outline: Create a book outline with chapters in sequential order based on the "
                "research findings.", "source_role": "outliner (task description names the dependency)"}],
            "outliner": [{"edge": "researcher->outliner: ResearchFindings", "quote":
                "Create a book outline with chapters in sequential order based on the research findings.",
                "source_role": "outliner"}],
        },
        excluded={},
        corrected_verdict=None,
        notes="LICENSE-BLOCKED: crewAIInc/crewAI-examples has no LICENSE file anywhere in the repo tree "
              "(verified 2026-07-12, see ledger.py) — this team reaches validator_passed (recovered structure, "
              "real Scribble-valid protocol) but CANNOT be emitted as a test-real DatasetRecord under this "
              "project's license discipline. Recorded as 'recovered, license-blocked'.",
    ),
    "crewai_config:crewAIInc/crewAI-examples:crews/surprise_trip/src/surprise_travel": dict(
        blocks={
            "personalized_activity_planner": "itinerary_compiler!ActivityPlan(String);",
            "restaurant_scout": "itinerary_compiler!DiningPlan(String);",
            "itinerary_compiler": "personalized_activity_planner?ActivityPlan(String);\n"
                                  "restaurant_scout?DiningPlan(String);",
        },
        evidence={
            "personalized_activity_planner": [{"edge": "personalized_activity_planner->itinerary_compiler: ActivityPlan",
                "quote": "Compile all researched information into a comprehensive day-by-day itinerary for the "
                         "trip ... Ensure the itinerary integrates flights, hotel information, and all planned "
                         "activities and dining experiences.", "source_role": "itinerary_compiler"}],
            "restaurant_scout": [{"edge": "restaurant_scout->itinerary_compiler: DiningPlan",
                "quote": "Ensure the itinerary integrates flights, hotel information, and all planned "
                         "activities and dining experiences.", "source_role": "itinerary_compiler"}],
            "itinerary_compiler": [{"edge": "both predecessors -> itinerary_compiler", "quote":
                "Compile all researched information into a comprehensive day-by-day itinerary for the trip",
                "source_role": "itinerary_compiler (own task description)"}],
        },
        excluded={},
        corrected_verdict=None,
        notes="LICENSE-BLOCKED (same crewAI-examples repo, see above): reaches validator_passed with a genuine "
              "fan-in pattern (two producers, one consumer) — the strongest-structured recovery in this whole "
              "sample, still not emittable as test-real.",
    ),
    "crewai_config:crewAIInc/crewAI-examples:crews/screenplay_writer": dict(
        blocks={}, evidence={},
        excluded={
            "spamfilter": {"category": "pure-solo-task", "reason":
                "Reads the ORIGINAL input ('the following newsgroup post'), not another role's output."},
            "analyst": {"category": "no-counterpart-named", "reason":
                "'Analyse ... the following discussion' operates on the original input; no agent field or "
                "named recipient in tasks.yaml for this task."},
            "scriptwriter": {"category": "ambiguous", "reason":
                "'Create a dialogue heavy screenplay from the discussion' — 'the discussion' is ambiguous "
                "between the raw input and analyst's reworded output; no explicit dependency phrase like "
                "CrewAI's other crews ('based on the research findings') is used here."},
            "formatter": {"category": "ambiguous", "reason":
                "'Format the script exactly like this' — 'the script' plausibly means scriptwriter's output, "
                "but the task text never says so explicitly, and no per-task `agent:`/`context:` field in "
                "tasks.yaml states it either."},
            "scorer": {"category": "ambiguous", "reason":
                "'Score the following script: {{script}}' — a templated variable, not a named-role dependency "
                "statement."},
        },
        corrected_verdict=None,
        notes="coordination_filter's 'yes' rests on the GENRE (filter->analyze->script->format->score reads "
              "as an obvious pipeline) rather than on any specific quoted dependency — every task here is "
              "connected to 'the discussion'/'the script' as generic template variables, never to a named "
              "predecessor role or task, unlike every other crewAI-examples crew sampled. Per the evidence-only "
              "discipline, nothing was extractable without inventing which task produces {{script}}.",
    ),
    "named_counterpart:VoltAgent/awesome-claude-code-subagents:codebase-orchestrator+readme-generator": dict(
        blocks={}, evidence={},
        excluded={
            "codebase-orchestrator": {"category": "no-ordering-stated", "reason":
                "'Guide readme-generator on documentation updates after approved refactors' correctly names "
                "the actual teammate — a real, confirmed edge — but names no specific message/label, only a "
                "generic supervisory verb."},
            "readme-generator": {"category": "no-counterpart-named", "reason":
                "Its own 'Integration with other agents:' list names six different roles (documentation-engineer, "
                "product-manager, backend-developer, qa-expert, devops-engineer, security-auditor, "
                "license-engineer, open-source-maintainers) — none is codebase-orchestrator, so no reciprocal "
                "send/receive action can be attributed to this role for this specific pairing."},
        },
        corrected_verdict=None,
        notes="coordination_filter verdict CONFIRMED yes (correctly-matched edge, real coordination need) but "
              "not extractable — same generic-verb-no-label pattern as incident-responder/devops-incident-responder.",
    ),
    "same_dir:github/awesome-copilot:skills/quality-playbook/agents": dict(
        blocks={}, evidence={},
        excluded={
            "quality-playbook-claude": {"category": "pure-solo-task", "reason":
                "Full text read directly (not just the dossier description): 'If you are reading this file, "
                "your Claude Code session IS the orchestrator. Do not spawn a separate `quality-playbook` "
                "sub-agent from another session' — this file explicitly forbids treating quality-playbook.md "
                "as an invokable counterpart. The two files are mutually-exclusive alternate entry points into "
                "the SAME one-role skill (a Claude-Code-specific variant and a generic-tool variant), not two "
                "interacting roles."},
            "quality-playbook": {"category": "pure-solo-task", "reason":
                "Same skill, generic-tool variant of quality-playbook-claude.agent.md; the 'six phases ... via "
                "sub-agents' language describes ONE orchestrator's internal use of ephemeral phase sub-agents "
                "in fresh context windows, not a relationship between these two specific harvested files."},
        },
        corrected_verdict="no",
        notes="coordination_filter batch verdict corrected yes->no after reading the full quality-playbook-claude "
              "text: the 'six phases via sub-agents' language the batch judge cited as coordination evidence is "
              "explicitly single-orchestrator internal execution, and the file explicitly forbids nesting the "
              "OTHER team member as a sub-agent. Exact same failure mode W16 already found for this same "
              "quality-playbook pair (then sourced from a different same-directory listing) — see "
              "llm_read/extraction.py team 12.",
    ),
}

BONUS_EXTRACTIONS = {
    "crewai_config:crewAIInc/crewAI:lib/cli/src/crewai_cli/templates/crew": dict(
        blocks={
            "researcher": "reporting_analyst!ResearchNotes(String);",
            "reporting_analyst": "researcher?ResearchNotes(String);",
        },
        evidence={
            "researcher": [{"edge": "researcher->reporting_analyst: ResearchNotes", "quote":
                "reporting_task: Review the context you got and expand each topic into a full section for a "
                "report.", "source_role": "reporting_analyst"}],
            "reporting_analyst": [{"edge": "researcher->reporting_analyst: ResearchNotes", "quote":
                "Review the context you got and expand each topic into a full section for a report.",
                "source_role": "reporting_analyst"}],
        },
        excluded={},
    ),
    "crewai_config:crewAIInc/crewAI:lib/cli/src/crewai_cli/templates/flow/crews/content_crew": dict(
        blocks={
            "planner": "writer!Outline(String);",
            "writer": "planner?Outline(String);\neditor!Draft(String);",
            "editor": "writer?Draft(String);",
        },
        evidence={
            "planner": [{"edge": "planner->writer: Outline", "quote":
                "writing_task: Using the outline provided, write a full blog post about {topic}.",
                "source_role": "writer"}],
            "writer": [
                {"edge": "planner->writer: Outline", "quote":
                 "Using the outline provided, write a full blog post about {topic}.", "source_role": "writer"},
                {"edge": "writer->editor: Draft", "quote":
                 "editing_task: Review and edit the blog post about {topic}.", "source_role": "editor"},
            ],
            "editor": [{"edge": "writer->editor: Draft", "quote":
                "Review and edit the blog post about {topic}. ... Do not rewrite the post — refine and polish it.",
                "source_role": "editor"}],
        },
        excluded={},
    ),
}


def _annotate(text: str, block_body: str) -> str:
    return text.rstrip() + "\n\n```localtype\n" + block_body + "\n```\n"


def _run_one(team, by_id, ext, out_dir, sanitize_name):
    import re
    n_total = len(team.role_names)
    n_blocked = len(ext["blocks"])
    rec = {"team_id": team.team_id, "source_repo": team.source_repo,
           "heuristic": team.heuristic, "n_roles_total": n_total,
           "n_roles_blocked": n_blocked,
           "coverage": round(n_blocked / n_total, 3) if n_total else 0.0,
           "excluded": ext["excluded"], "notes": ext.get("notes", ""),
           "corrected_verdict": ext.get("corrected_verdict")}
    if n_blocked < 2:
        rec["stage_reached"] = "extraction" if n_blocked == 0 else "extraction_insufficient_roles"
        rec["ok"] = False
        rec["pipeline_error"] = "fewer than 2 roles had evidence-backed blocks; deterministic compaction not attempted."
        return rec, None
    team_dir = out_dir / "annotated" / re.sub(r"[^A-Za-z0-9_]", "_", team.team_id)[:80]
    team_dir.mkdir(parents=True, exist_ok=True)
    by_role = {}
    for aid in team.artifact_ids:
        a = by_id[aid]
        by_role[a.role_hint] = a
    for role_hint, block_body in ext["blocks"].items():
        a = by_role[role_hint]
        san = re.sub(r"[^A-Za-z0-9_]", "_", role_hint)
        (team_dir / f"{san}.md").write_text(_annotate(a.text, block_body), encoding="utf-8")
    out_scr = out_dir / "pipeline_out" / (re.sub(r"[^A-Za-z0-9_]", "_", team.team_id)[:80] + ".scr")
    out_scr.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = compact_and_synthesize(team_dir, out_scr,
                                        protocol_name=sanitize_name(team.team_id), llm_client=None)
        rec["stage_reached"] = "validator_passed" if result.valid else (
            "synthesis_failed" if result.error and "compatible" not in result.error else
            "compatibility_failed" if result.error else "unknown")
        rec["ok"] = result.valid
        rec["pipeline_error"] = result.error
        rec["synthesis_mode"] = result.synthesis_mode
        rec["protocol_text"] = result.protocol_text if result.valid else ""
        return rec, (result if result.valid else None)
    except CompactionError as e:
        rec["stage_reached"] = "compactor_failed"
        rec["ok"] = False
        rec["pipeline_error"] = str(e)
        return rec, None


def main():
    import re
    ap = argparse.ArgumentParser()
    ap.add_argument("--remote-root", type=Path, required=True)
    ap.add_argument("--scratch-dir", type=Path, required=True)
    args = ap.parse_args()

    def sanitize_name(team_id):
        parts = re.split(r"[^A-Za-z0-9]+", team_id)
        return "".join(p.capitalize() for p in parts if p)[:40] or "Team"

    artifacts = harvest_all(args.remote_root)
    by_id = {a.artifact_id: a for a in artifacts}
    ledger = build_ledger(artifacts)
    intents = {aid: extract_intent(a) for aid, a in by_id.items()}
    team_result = build_teams(artifacts)
    teams_by_id = {t.team_id: t for t in team_result.teams}

    summary = []
    records = []
    args.scratch_dir.mkdir(parents=True, exist_ok=True)
    for tid in RANDOM_SAMPLE_TEAM_IDS + BONUS_LICENSED_TEAM_IDS:
        team = teams_by_id[tid]
        ext = EXTRACTIONS.get(tid) or BONUS_EXTRACTIONS.get(tid)
        rec, result = _run_one(team, by_id, ext, args.scratch_dir, sanitize_name)
        rec["via_random_sample"] = tid in RANDOM_SAMPLE_TEAM_IDS
        summary.append(rec)
        if result is not None:
            lic_ok = all(not ledger[aid].quarantined for aid in team.artifact_ids)
            rec["license_ok"] = lic_ok
            if lic_ok:
                import hashlib
                fam = hashlib.sha256(result.protocol_text.encode("utf-8")).hexdigest()[:16]
                intent_parts = [intents[aid].text for aid in team.artifact_ids if intents[aid].text]
                records.append(DatasetRecord(
                    id=f"mined:llm_read:w17:{tid}", family=fam, split="test-real",
                    intent=" ".join(intent_parts) if intent_parts else None,
                    protocol=result.protocol_text, refn=None, source="mined", seed_case=tid,
                    gen={"family_placeholder": True, "synthesis_mode": result.synthesis_mode,
                         "compactor_mode": "llm-read-annotated", "team_heuristic": team.heuristic,
                         "extraction_pass": "W17-sample"},
                    provenance={"team_id": tid, "source_repo": team.source_repo,
                               "roles": team.role_names,
                               "artifacts": [{"artifact_id": aid, "path": by_id[aid].path,
                                              "source_repo": ledger[aid].source_repo,
                                              "license_spdx": ledger[aid].license_spdx,
                                              "commit_sha": ledger[aid].commit_sha}
                                             for aid in team.artifact_ids]}))

    (args.scratch_dir / "w17_sample_extraction_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    n = write_jsonl(args.scratch_dir / "w17_sample_dataset_records.jsonl", records)
    for r in summary:
        tag = "SAMPLE" if r["via_random_sample"] else "BONUS-LICENSED"
        print(f"[{tag}] {r['team_id']}: {r['stage_reached']} ok={r['ok']}",
              f"license_ok={r.get('license_ok')}" if 'license_ok' in r else "")
    print(f"wrote {n} new DatasetRecords")


if __name__ == "__main__":
    main()
