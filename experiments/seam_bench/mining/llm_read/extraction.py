"""W16 LLM-read extraction driver.

Loads the 13 mined teams (same harvest as W8), applies MANUALLY DECIDED
(by the extraction model -- a Claude session reading each skill's full text,
not an automated heuristic) fenced ```localtype blocks per role, writes
block-annotated copies + an evidence sidecar per team, then runs each team's
(possibly role-reduced) annotated dir through the REAL deterministic
pipeline: skill_compactor.compact_and_synthesize(..., llm_client=None) ->
ScribbleValidator, exactly as formalize.py does.

Usage (from repo root, after staging the three remote checkouts -- see
docs/reference/reports/seam/W8_miner.md sec 1 for the clone commands and
docs/reference/reports/seam/W16_llm_read_extraction.md for this run's own
probe):

    python -m experiments.seam_bench.mining.llm_read.extraction \\
        --remote-root <dir containing awesome-copilot/, VoltAgent/, anthropic-skills/> \\
        --scratch-dir <scratch dir for annotated copies + .scr outputs>

Writes, under --scratch-dir: annotated/<team>/<Role>.md (block-annotated
copies), pipeline_out/<team>.scr (synthesized global protocols),
extraction_summary.json (per-team coverage + pipeline verdict),
evidence_sidecars/<team>.json (verbatim evidence quote per extracted edge +
exclusion reasons for every no-block role).
"""
from __future__ import annotations
import argparse
import sys, json, re, shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[3]
MINING = HERE.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(MINING))

from run_mining import harvest_all           # noqa: E402
from team_builder import build_teams          # noqa: E402
from stjp_core.generation.skill_compactor import compact_and_synthesize, CompactionError  # noqa: E402


def sanitize(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", name)


# ── Manual extraction decisions ─────────────────────────────────────────────
# Each entry: team_index -> dict(
#   reduced_id, blocks: {orig_role: (sanitized_name, block_text)},
#   evidence: {orig_role: [ {edge, quote, source_role} ]},
#   excluded: {orig_role: {"category":..., "reason":...}},
# )

EXTRACTIONS = {
0: dict(  # worked_example:pr_merge
  reduced_id="pr_merge__reduced_Author_Merger",
  blocks={
    "Author": "Merger?MergeDone(String);",
    "Merger": "Author!MergeDone(String);",
  },
  evidence={
    "Author": [{"edge": "Merger->Author: MergeDone", "quote":
      "merge it and confirm to the author (send `MergeDone`).",
      "source_role": "Merger", "note": "dual of Merger's explicit send; Author's own text ('You are done when your change has been merged') corroborates but does not itself name the message."}],
    "Merger": [{"edge": "Merger->Author: MergeDone", "quote":
      "merge it and confirm to the author (send `MergeDone`).",
      "source_role": "Merger"}],
  },
  excluded={
    "CodeReviewer": {"category": "no-counterpart-named", "reason":
      "'pass it on with your verdict (send `ReviewPassed`)' names no recipient role."},
    "SecurityReviewer": {"category": "no-counterpart-named", "reason":
      "'report it as cleared (send `SecurityPassed`)' names no recipient role."},
  },
),
1: dict(  # worked_example:content_pipeline -- FULL coverage
  reduced_id="content_pipeline__full",
  blocks={
    "Researcher": "Writer!ResearchBrief(String);",
    "Writer": "Researcher?ResearchBrief(String);\nEditor!SubmitDraft(String);",
    "Editor": "Writer?SubmitDraft(String);\nPublisher!Approve(String);",
    "Publisher": "Editor?Approve(String);",
  },
  evidence={
    "Researcher": [{"edge": "Researcher->Writer: ResearchBrief", "quote":
      "Hand a concise research brief to the Writer (send `ResearchBrief` to Writer).",
      "source_role": "Researcher"}],
    "Writer": [
      {"edge": "Researcher->Writer: ResearchBrief", "quote":
       "Hand a concise research brief to the Writer (send `ResearchBrief` to Writer).",
       "source_role": "Researcher"},
      {"edge": "Writer->Editor: SubmitDraft", "quote":
       "submit it so it can go out (send `SubmitDraft`).", "source_role": "Writer",
       "note": "Writer's own text does not name the recipient; peer supplied by Editor's text ('Review the Writer's draft')."},
    ],
    "Editor": [
      {"edge": "Writer->Editor: SubmitDraft", "quote":
       "Review the Writer's draft for accuracy, clarity, and compliance.",
       "source_role": "Editor", "note": "names Writer as source; clearly implies receipt, though the label 'SubmitDraft' is only named in Writer's own text."},
      {"edge": "Editor->Publisher: Approve", "quote":
       "approve it for publication (send `Approve` to the Publisher).",
       "source_role": "Editor"},
    ],
    "Publisher": [{"edge": "Editor->Publisher: Approve", "quote":
      "approve it for publication (send `Approve` to the Publisher). / Publish as soon as you receive the article",
      "source_role": "Editor + Publisher"}],
  },
  excluded={},
  notes="Publisher's own 'send `Published`' is dropped: its target is 'the live site', not a named team role (no-counterpart-named).",
),
2: dict(  # worked_example:airline_seat -- FULL coverage
  reduced_id="airline_seat__full",
  blocks={
    "Triage": "SeatBooking!AssignFlight(String);",
    "SeatBooking": "Triage?AssignFlight(String);\nFlightSystem!UpdateSeat(String);\nFlightSystem?SeatConfirmed(String);",
    "FlightSystem": "SeatBooking?UpdateSeat(String);\nSeatBooking!SeatConfirmed(String);",
  },
  evidence={
    "Triage": [{"edge": "Triage->SeatBooking: AssignFlight", "quote":
      "you assign the flight for this booking (send `AssignFlight` with the flight number to Seat Booking).",
      "source_role": "Triage"}],
    "SeatBooking": [
      {"edge": "Triage->SeatBooking: AssignFlight", "quote":
       "you assign the flight for this booking (send `AssignFlight` with the flight number to Seat Booking).",
       "source_role": "Triage"},
      {"edge": "SeatBooking->FlightSystem: UpdateSeat", "quote":
       "Use the update seat tool to update the seat on the flight (send `UpdateSeat` to the Flight System).",
       "source_role": "SeatBooking"},
      {"edge": "FlightSystem->SeatBooking: SeatConfirmed", "quote":
       "You receive `UpdateSeat` from the Seat Booking agent and apply the seat change, then send `SeatConfirmed` back.",
       "source_role": "FlightSystem"},
    ],
    "FlightSystem": [{"edge": "SeatBooking->FlightSystem: UpdateSeat / FlightSystem->SeatBooking: SeatConfirmed",
      "quote": "You receive `UpdateSeat` from the Seat Booking agent and apply the seat change, then send `SeatConfirmed` back.",
      "source_role": "FlightSystem"}],
  },
  excluded={},
),
3: dict(  # worked_example:booking_saga -- FULL coverage, deliberate deadlock
  reduced_id="booking_saga__full",
  blocks={
    "Traveler": "Hotel!RequestBooking(String);\nHotel?BookingConfirmed(String);",
    "Hotel": "Traveler?RequestBooking(String);\nPayment?PaymentCaptured(String);\nTraveler!BookingConfirmed(String);",
    "Payment": "Hotel?RoomHeld(String);\nHotel!PaymentCaptured(String);",
  },
  evidence={
    "Traveler": [
      {"edge": "Traveler->Hotel: RequestBooking", "quote":
       "Request a hotel booking for the trip (send `RequestBooking` to the Hotel).", "source_role": "Traveler"},
      {"edge": "Hotel->Traveler: BookingConfirmed", "quote":
       "Wait for the final booking confirmation.", "source_role": "Traveler",
       "note": "label BookingConfirmed supplied by Hotel's own text."},
    ],
    "Hotel": [
      {"edge": "Traveler->Hotel: RequestBooking", "quote":
       "Request a hotel booking for the trip (send `RequestBooking` to the Hotel).", "source_role": "Traveler"},
      {"edge": "Payment->Hotel: PaymentCaptured", "quote":
       "wait until you receive `PaymentCaptured` from the Payment service.", "source_role": "Hotel"},
      {"edge": "Hotel->Traveler: BookingConfirmed", "quote":
       "ONLY THEN confirm the booking (send `BookingConfirmed` to the Traveler).", "source_role": "Hotel"},
    ],
    "Payment": [
      {"edge": "Hotel->Payment: RoomHeld", "quote":
       "wait until you receive `RoomHeld` from the Hotel service.", "source_role": "Payment",
       "note": "DELIBERATELY NOT mirrored in Hotel's block: Hotel.md never states it sends RoomHeld anywhere. This is not an omission on my part -- Hotel's text simply does not make that claim. Recording the asymmetry as-is is the point of this case."},
      {"edge": "Payment->Hotel: PaymentCaptured", "quote":
       "ONLY THEN capture the charge (send `PaymentCaptured` to the Hotel).", "source_role": "Payment"},
    ],
  },
  excluded={},
  notes="Hotel's block has no RoomHeld send by design -- Payment's local type waits for a message Hotel's own skill text never promises to send. Expected to fail multiparty compatibility, not synthesis/validator.",
),
4: dict(  # worked_example:code_execution
  reduced_id="code_execution__reduced_Reviewer_Executor",
  blocks={
    "Reviewer": "Coder?SubmitCode(String);\nExecutor!Approve(String);",
    "Executor": "Reviewer?Approve(String);",
  },
  evidence={
    "Reviewer": [
      {"edge": "Coder->Reviewer: SubmitCode", "quote":
       "Inspect the Coder's submitted code for safety and correctness.", "source_role": "Reviewer",
       "note": "names Coder as source; label SubmitCode supplied by Coder's own text ('submit it so it can be run (send `SubmitCode`)'), whose own text names no recipient."},
      {"edge": "Reviewer->Executor: Approve", "quote":
       "approve it for execution (send `Approve` to the Executor).", "source_role": "Reviewer"},
    ],
    "Executor": [{"edge": "Reviewer->Executor: Approve", "quote":
      "approve it for execution (send `Approve` to the Executor).", "source_role": "Reviewer"}],
  },
  excluded={
    "Coder": {"category": "no-counterpart-named", "reason":
      "'submit it so it can be run (send `SubmitCode`)' names no recipient; Coder's role is only named as a *source* in Reviewer's text, never as a recipient of anything, so no LocalType action can be attributed to Coder without inventing one."},
  },
),
5: dict(  # worked_example:doc_pipeline -- nothing extractable
  reduced_id=None,
  blocks={}, evidence={},
  excluded={
    "Requester": {"category": "ambiguous", "reason":
      "'Ask the writing team for the internal announcement' names a vague collective ('the writing team'), not a single team-role peer; 'send `DocRequest`' names no recipient."},
    "Writer": {"category": "no-counterpart-named", "reason":
      "'hand it off so it can go out (send `DraftComms`)' names no recipient."},
    "BrandReviewer": {"category": "no-counterpart-named", "reason":
      "'When content comes to you' names no sender; 'pass it along as brand-approved (send `BrandApproved`)' names no recipient."},
    "DocLead": {"category": "no-counterpart-named", "reason":
      "'distribute the finished document company-wide (send `DocShipped`)' names no recipient role (Requester is never named here even though Requester's own text expects to receive it)."},
  },
  notes="Unlike pr_merge/content_pipeline/airline_seat/booking_saga, this worked example's paraphrase never names a directional peer for any send. 0/4 roles extractable.",
),
6: dict(  # worked_example:pr_merge_upstream -- real upstream text, solo docs
  reduced_id=None, blocks={}, evidence={},
  excluded={
    "address-comments": {"category": "pure-solo-task", "reason":
      "Real address-comments.agent.md never names another agent or role; describes one agent's own comment-fixing loop with the human user only."},
    "code-review-generic": {"category": "pure-solo-task", "reason":
      "Real code-review-generic.instructions.md is a solo severity-triage checklist ('Block merge' is a self-directed verdict label, not a message to a named Merger role)."},
    "se-security-reviewer": {"category": "pure-solo-task", "reason":
      "Real se-security-reviewer.agent.md is a solo OWASP-review checklist with no named counterpart."},
    "principal-software-engineer": {"category": "pure-solo-task", "reason":
      "Real principal-software-engineer.agent.md is a solo engineering-judgment guide with no named counterpart."},
  },
  notes="The skills_safety worked example (team 0) got its send/receive vocabulary from the STJP author's paraphrase, not from these real upstream files -- none of the 4 real files name another team role at all.",
),
7: dict(  # worked_example:doc_pipeline_upstream -- real upstream text, solo docs
  reduced_id=None, blocks={}, evidence={},
  excluded={
    "internal-comms": {"category": "pure-solo-task", "reason":
      "Real internal-comms/SKILL.md addresses the invoking user directly ('Identify the communication type from the request'); no other named skill/agent."},
    "brand-guidelines": {"category": "pure-solo-task", "reason":
      "Real brand-guidelines/SKILL.md is a standalone style-application reference; no named counterpart."},
    "doc-coauthoring": {"category": "pure-solo-task", "reason":
      "Real doc-coauthoring/SKILL.md invokes generic 'a sub-agent' for ambiguity checks -- no named team-role peer, and the sub-agent is not one of the 3 harvested files."},
  },
),
8: dict(  # explicit_ref: gem-implementer + r  -- heuristic false positive
  reduced_id=None, blocks={}, evidence={},
  excluded={
    "r": {"category": "ambiguous", "reason":
      "Team formation itself is a team_builder regex artifact: the only 'invoke the' match in gem-implementer.md is followed within 80 chars by the letter 'R' from 'TDD Cycle (Red -> Green -> R[efactor])', which the word-boundary regex for role name 'r' matched. No genuine cross-reference between the R style-guide and gem-implementer exists in either file's text."},
    "gem-implementer": {"category": "ambiguous", "reason":
      "Same false-positive match as 'r' -- gem-implementer.md never mentions an 'r' role/skill."},
  },
),
9: dict(  # explicit_ref: 15-role awesome-copilot cluster -- genuine gem-team subset + 8 false positives
  reduced_id="gem_team_subset__gem_orchestrator_and_6_workers",
  blocks={
    "gem-orchestrator": (
      "choice {\n"
      "    gem_planner!Delegate(String);\n"
      "} or {\n"
      "    gem_reviewer!Delegate(String);\n"
      "} or {\n"
      "    gem_debugger!Delegate(String);\n"
      "} or {\n"
      "    gem_documentation_writer!Delegate(String);\n"
      "} or {\n"
      "    gem_skill_creator!Delegate(String);\n"
      "} or {\n"
      "    gem_critic!Delegate(String);\n"
      "}"
    ),
    "gem-planner": "gem_orchestrator?Delegate(String);",
    "gem-reviewer": "gem_orchestrator?Delegate(String);",
    "gem-debugger": "gem_orchestrator?Delegate(String);",
    "gem-documentation-writer": "gem_orchestrator?Delegate(String);",
    "gem-skill-creator": "gem_orchestrator?Delegate(String);",
    "gem-critic": "gem_orchestrator?Delegate(String);",
  },
  evidence={
    "gem-orchestrator": [
      {"edge": "gem-orchestrator->gem-planner: Delegate", "quote":
       "Delegate to `gem-planner` with `task_clarifications`, relevant context, `memory_seed`, and `config_snapshot`.", "source_role": "gem-orchestrator"},
      {"edge": "gem-orchestrator->gem-reviewer: Delegate", "quote":
       "Delegate to `gem-reviewer(plan)`.", "source_role": "gem-orchestrator"},
      {"edge": "gem-orchestrator->gem-debugger: Delegate", "quote":
       "first delegate to `gem-debugger` for diagnosis (wave 1)", "source_role": "gem-orchestrator"},
      {"edge": "gem-orchestrator->gem-documentation-writer: Delegate", "quote":
       "delegate to `gem-documentation-writer` -> PRD", "source_role": "gem-orchestrator"},
      {"edge": "gem-orchestrator->gem-skill-creator: Delegate", "quote":
       "delegate to `gem-skill-creator` -> skills", "source_role": "gem-orchestrator"},
      {"edge": "gem-orchestrator->gem-critic: Delegate", "quote":
       "delegate to `gem-critic(plan)`, only if: High-risk signal exists", "source_role": "gem-orchestrator"},
    ],
    "gem-planner": [{"edge": "gem-orchestrator->gem-planner: Delegate", "quote":
      "Delegate to `gem-planner` with `task_clarifications`...", "source_role": "gem-orchestrator",
      "note": "receive side is dual-inferred; gem-planner.md itself never names gem-orchestrator, only 'Return minimal JSON per output_format' with no named recipient (so no send action extracted for gem-planner)."}],
    "gem-reviewer": [{"edge": "gem-orchestrator->gem-reviewer: Delegate", "quote":
      "Delegate to `gem-reviewer(plan)`.", "source_role": "gem-orchestrator", "note": "same dual-inference; no send extracted (return target unnamed in gem-reviewer.md)."}],
    "gem-debugger": [{"edge": "gem-orchestrator->gem-debugger: Delegate", "quote":
      "first delegate to `gem-debugger` for diagnosis (wave 1)", "source_role": "gem-orchestrator", "note": "same dual-inference; no send extracted."}],
    "gem-documentation-writer": [{"edge": "gem-orchestrator->gem-documentation-writer: Delegate", "quote":
      "delegate to `gem-documentation-writer` -> PRD", "source_role": "gem-orchestrator", "note": "same dual-inference; no send extracted."}],
    "gem-skill-creator": [{"edge": "gem-orchestrator->gem-skill-creator: Delegate", "quote":
      "delegate to `gem-skill-creator` -> skills", "source_role": "gem-orchestrator",
      "note": "gem-skill-creator.md does name 'orchestrator' once ('Query orchestrator memory for pattern frequency') but that is a memory read, not a message send, so no additional send action was extracted."}],
    "gem-critic": [{"edge": "gem-orchestrator->gem-critic: Delegate", "quote":
      "delegate to `gem-critic(plan)`, only if: High-risk signal exists", "source_role": "gem-orchestrator", "note": "same dual-inference; no send extracted."}],
  },
  excluded={
    "prompt": {"category": "ambiguous", "reason": "team_builder matched this file via a generic 'invoke the sub-agent' phrase in a different file (agents.md); prompt.md itself never names another team role."},
    "prd": {"category": "no-counterpart-named", "reason": "prd.md/prd.agent.md is a solo PRD-writing guide; no cross-reference found."},
    "planner": {"category": "ambiguous", "reason": "distinct from gem-planner; the only nearby match (devbox-image-definition.md's 'Customization YAML Generation Planner' tool) is an unrelated Azure DevBox tool, not this 'planner' agent."},
    "agent-safety": {"category": "ambiguous", "reason": "'When agents delegate to other agents, apply the most restrictive policy from either' is a generic security rule about delegation in general, not a specific edge naming another harvested role."},
    "devbox-image-definition": {"category": "ambiguous", "reason": "'Customization YAML Generation Planner' is a specific unrelated Azure DevBox tool name, not the 'planner' role in this team."},
    "gem-documentation-writer__unused": {"category": "n/a", "reason": "placeholder, not used"},
    "debug": {"category": "no-counterpart-named", "reason": "debug.md contains zero handoff-verb matches; solo debugging checklist."},
    "plan": {"category": "no-counterpart-named", "reason": "plan.md contains zero handoff-verb matches; solo planning checklist."},
    "agents": {"category": "ambiguous", "reason": "agents.md is a meta-guide on how to write agent definitions; its 'Hand off to the Implementer agent'/'Hand off to the Reviewer agent' lines are a generic worked EXAMPLE inside documentation prose, not agents.md's own behavior, and 'Implementer'/'Reviewer' do not match any role in this harvested team."},
  },
  notes="team_builder's explicit-reference heuristic swept 15 awesome-copilot files into one 'team' via short/generic role-name collisions (regex false positives, same failure mode as team 8's 'r'). Within it, gem-orchestrator.agent.md is a genuine, hand-written multi-agent orchestration spec that explicitly names 6 of the other 14 files as delegation targets -- a real recoverable 7-role subset. The other 8 files were never actually part of a described team; excluded and reported as their own no-block artifacts, not folded into the reduced run's coverage denominator ambiguity.",
),
10: dict(  # explicit_ref: markdown + se-ux-ui-designer -- false positive
  reduced_id=None, blocks={}, evidence={},
  excluded={
    "markdown": {"category": "ambiguous", "reason":
      "team_builder matched se-ux-ui-designer.md's own fenced-code-block language tag ('```markdown') as if it named the 'markdown' instructions role -- a regex artifact, not a reference to markdown.instructions.md."},
    "se-ux-ui-designer": {"category": "ambiguous", "reason": "same false-positive match; se-ux-ui-designer.md never discusses the markdown formatting-instructions file."},
  },
),
11: dict(  # same_dir: VoltAgent subagent-catalog (fetch/invalidate/list/search)
  reduced_id=None, blocks={}, evidence={},
  excluded={
    "fetch": {"category": "pure-solo-task", "reason": "Independent user-invoked slash command; touches a shared cache FILE, never messages another command."},
    "invalidate": {"category": "pure-solo-task", "reason": "Independent user-invoked slash command over the same shared cache file; no agent-to-agent messaging."},
    "list": {"category": "pure-solo-task", "reason": "Independent user-invoked slash command; only cross-reference is a usage TIP pointing the human user at /search and /fetch, not a message to them."},
    "search": {"category": "pure-solo-task", "reason": "Independent user-invoked slash command; same shared-cache-file pattern, no messaging to fetch/list/invalidate."},
  },
  notes="Same-directory grouping found 4 sibling slash-commands that share a cache file, not an interacting multi-agent team; this is exactly the failure mode R3 flagged for directory-shaped sources.",
),
12: dict(  # same_dir: quality-playbook (2 variants)
  reduced_id=None, blocks={}, evidence={},
  excluded={
    "quality-playbook-claude": {"category": "pure-solo-task", "reason":
      "Self-describes as a single orchestrator ('your Claude Code session IS the orchestrator'). Its only cross-file relationship to quality-playbook.agent.md is that both are tool-specific variants of the same single-role skill (Claude Code vs. generic), not two interacting roles."},
    "quality-playbook": {"category": "pure-solo-task", "reason": "Same skill, generic-tool variant of quality-playbook-claude.agent.md; not a second interacting role."},
  },
),
}


def main():
    global ANNOT, OUT, SCRATCH
    ap = argparse.ArgumentParser()
    ap.add_argument("--remote-root", type=Path, default=None,
                    help="dir containing awesome-copilot/, VoltAgent/, anthropic-skills/ "
                         "checkouts; omit to run local-vendored-only (worked-example "
                         "teams 0-5 only, all remote-repo teams 6-12 skipped)")
    ap.add_argument("--scratch-dir", type=Path, required=True,
                    help="scratch dir for annotated copies + .scr outputs + summary/sidecars")
    args = ap.parse_args()
    SCRATCH = args.scratch_dir
    ANNOT = SCRATCH / "annotated"
    OUT = SCRATCH / "pipeline_out"
    SCRATCH.mkdir(parents=True, exist_ok=True)

    artifacts = harvest_all(args.remote_root)
    by_id = {a.artifact_id: a for a in artifacts}
    team_result = build_teams(artifacts)

    # W17 note (2026-07-12): `harvest_all`/`build_teams` now also pull in
    # crewAI + rohitg00-toolkit sources and two new team-formation
    # heuristics (`coordination_filter.py`'s harvest expansion,
    # `docs/reference/reports/seam/W17_coordination_scale_up.md`) — a fresh
    # `build_teams(artifacts)` call today returns ~110 teams, not W16's
    # original 13, and NOT in the same list order (the new
    # named-counterpart/crewai-config heuristics run before
    # same-directory, shifting where teams 11/12 land). This script's
    # EXTRACTIONS dict is keyed by POSITION in the ORIGINAL 13-team list,
    # so we filter down to exactly those 13 team_ids (order preserved by
    # this explicit whitelist, not by list position in the larger result)
    # rather than assert-failing or silently misindexing into the wrong
    # teams. See W17_coordination_scale_up.md for the fresh, superseding
    # judgment over the full ~110-team pool (`coordination_filter.py`
    # verdicts + `w17_extraction.py` for the newly-sampled teams).
    ORIGINAL_13_TEAM_IDS = [
        "worked_example:pr_merge", "worked_example:content_pipeline",
        "worked_example:airline_seat", "worked_example:booking_saga",
        "worked_example:code_execution", "worked_example:doc_pipeline",
        "worked_example:pr_merge_upstream", "worked_example:doc_pipeline_upstream",
        "explicit_ref:github/awesome-copilot:gem-implementer+r",
        "explicit_ref:github/awesome-copilot:agent-safety+agents+debug+devbox-image-definition+"
        "gem-critic+gem-debugger+gem-documentation-writer+gem-orchestrator+gem-planner+gem-reviewer+"
        "gem-skill-creator+plan+planner+prd+prompt",
        "explicit_ref:github/awesome-copilot:markdown+se-ux-ui-designer",
        "same_dir:VoltAgent/awesome-claude-code-subagents:tools/subagent-catalog",
        "same_dir:github/awesome-copilot:skills/quality-playbook/agents",
    ]
    by_team_id = {t.team_id: t for t in team_result.teams}
    if all(tid in by_team_id for tid in ORIGINAL_13_TEAM_IDS):
        teams = [by_team_id[tid] for tid in ORIGINAL_13_TEAM_IDS]
    else:
        # exact historical shape unavailable (e.g. a source repo changed
        # upstream) — fail loudly rather than silently indexing into the
        # wrong teams.
        missing = [tid for tid in ORIGINAL_13_TEAM_IDS if tid not in by_team_id]
        raise AssertionError(f"expected 13 original W16 team_ids, missing: {missing}")
    assert len(teams) == 13, len(teams)

    summary = []
    for i, t in enumerate(teams):
        ext = EXTRACTIONS[i]
        by_role = {a.role_hint: a for aid in t.artifact_ids for a in [by_id[aid]]}
        n_total_roles = len(t.role_names)
        n_blocked = len(ext["blocks"])
        coverage = n_blocked / n_total_roles if n_total_roles else 0.0

        rec = {
            "team_index": i, "team_id": t.team_id, "source_repo": t.source_repo,
            "heuristic": t.heuristic, "n_roles_total": n_total_roles,
            "n_roles_blocked": n_blocked, "coverage": round(coverage, 3),
            "excluded": ext["excluded"], "notes": ext.get("notes", ""),
            "reduced_id": ext["reduced_id"],
        }

        if ext["reduced_id"] is None or n_blocked < 2:
            rec["stage_reached"] = "extraction" if n_blocked == 0 else "extraction_insufficient_roles"
            rec["ok"] = False
            rec["pipeline_error"] = "fewer than 2 roles had evidence-backed blocks; deterministic compaction was not attempted for this team."
            summary.append(rec)
            continue

        team_dir = ANNOT / sanitize(t.team_id)
        if team_dir.exists():
            shutil.rmtree(team_dir)
        team_dir.mkdir(parents=True)

        for orig_role, block_body in ext["blocks"].items():
            a = by_role[orig_role]
            san = sanitize(orig_role)
            fname = f"{san}.md"
            annotated_text = a.text.rstrip() + "\n\n```localtype\n" + block_body + "\n```\n"
            (team_dir / fname).write_text(annotated_text, encoding="utf-8")

        out_scr = OUT / f"{i:02d}_{sanitize(t.team_id)}.scr"
        (OUT).mkdir(parents=True, exist_ok=True)
        try:
            result = compact_and_synthesize(team_dir, out_scr, protocol_name="Team%d" % i,
                                            llm_client=None, save_local_types=True)
            rec["stage_reached"] = "validator_passed" if result.valid else (
                "synthesis_failed" if result.error and "compatible" not in result.error else
                "compatibility_failed" if result.error else "unknown")
            rec["ok"] = result.valid
            rec["pipeline_error"] = result.error
            rec["synthesis_mode"] = result.synthesis_mode
            rec["protocol_text"] = result.protocol_text if result.valid else ""
        except CompactionError as e:
            rec["stage_reached"] = "compactor_failed"
            rec["ok"] = False
            rec["pipeline_error"] = str(e)
        except Exception as e:
            rec["stage_reached"] = "exception"
            rec["ok"] = False
            rec["pipeline_error"] = f"{type(e).__name__}: {e}"
        summary.append(rec)

    (SCRATCH / "extraction_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # evidence sidecars
    sidecar_dir = SCRATCH / "evidence_sidecars"
    sidecar_dir.mkdir(exist_ok=True)
    for i, t in enumerate(teams):
        ext = EXTRACTIONS[i]
        (sidecar_dir / f"{i:02d}_{sanitize(t.team_id)}.json").write_text(
            json.dumps({"team_id": t.team_id, "evidence": ext["evidence"],
                        "excluded": ext["excluded"], "notes": ext.get("notes", "")}, indent=2),
            encoding="utf-8")

    for r in summary:
        print(r["team_index"], r["team_id"], "coverage=%.2f" % r["coverage"], r["stage_reached"], r.get("ok"))
        if r.get("pipeline_error"):
            print("    ", r["pipeline_error"][:200].replace("\n", " | "))


if __name__ == "__main__":
    main()
