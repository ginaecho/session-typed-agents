"""Acceptance gate 2 (docs/reference/SDLC_HOSTED_WORKFLOW_SPEC.md §5.2):
container logic UNIT-smoke without any LLM.

RENAMED 2026-08-05 (BENCHMARK_PLAN_V3 §10.8 "Final arm naming") along with
the rest of the hosted matrix: the arm formerly called `min_llmvalid_gate`
is now `localvalid_gate`, and `min_llmvalid_sched` is now `localvalid_sched`
(same builder/config, new key).

A FakeChatClient (scripted replies) drives ONE trial of localvalid_gate and
ONE trial of localvalid_sched through main.py's loop classes directly
(run_trial_with_agents), with NO ResponsesHostServer, NO Azure, NO network.

  - localvalid_gate: Author's first reply is a scripted OFF-CONTRACT send
    (wrong label). Assert the gate REJECTS it pre-delivery (it lands in
    blocked_attempts, NOT in events).
  - localvalid_sched: only Author's EFSM state has an enabled SEND at the
    start of the protocol. Assert the scheduler polls ONLY Author while that
    holds (QualityReviewer..DevOps get ZERO calls), then correctly advances
    to QualityReviewer once Author's Submit is delivered.
  - REORDER (async-subtyping port, orchestrator-mandated 2026-08-05): the
    Merger's approve-branch notification block (6 sends to 6 different
    peers) is driven through localvalid_gate in BOTH the EFSM-literal
    order AND a commuted order (StopQuality before ApprovedAuthor). The
    walker must ACCEPT both orderings end-to-end (zero blocked attempts,
    trial reaches the Deployed terminal) while the WrongLabel smoke above
    keeps proving genuinely off-protocol sends are still rejected. NOTE:
    in this llm-valid draft the four-review fan-in is realized as a baton
    chain — the Merger has exactly ONE reviewer-verdict RECV (ToMerger),
    so "two verdicts arriving at Merger out of RECV order" cannot be
    constructed from this protocol; the Merger send-block reorder is the
    protocol's realizable analogue and exercises the identical
    _match_commuting/_skipped code path (which is direction-agnostic).
  - RECV-side reorder at walker level: QualityReviewer's monitor accepts
    StopQuality (from Merger) arriving BEFORE Submit (from Author) — the
    literal receives-from-different-peers-commute case — with the commuted
    actions tracked as deferred obligations, debt flagged at termination if
    the trace ends early, and cleared when the owed messages appear later.

Per spec §6 (REAL-API rule): this FakeChatClient output is NEVER written to
any runs/ directory and is not counted in any table. It exists solely to
unit-test the deterministic EFSM-walker enforcement code in main.py /
efsm_walker.py.

Run directly:
    python experiments/scripts/tests/test_gate2_loop_smoke.py
Prerequisite: build_hosted_artifacts.py has been run (main.load_artifacts()
reads artifacts/{case_meta,efsm,refinements,prompts}.json).
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
AGENT_DIR = (REPO_ROOT / "foundry_hosted_agents" /
            "agent-framework-agent-with-remote-mcp-tools-responses" /
            "agents" / "sdlc_release_gate")
sys.path.insert(0, str(AGENT_DIR))

import agent_framework as af  # noqa: E402
import main  # noqa: E402  (the container's main.py)

WAIT_JSON = '{"send_to": null, "label": "WAIT", "payload": "", "rationale": "nothing yet"}'


class ScriptedChatClient:
    """FakeChatClient: pops one scripted reply per call (repeats the last
    entry once exhausted). Tracks call_count so the test can assert exactly
    which roles the scheduler touched."""

    def __init__(self, replies: list[str]):
        self.replies = list(replies) or [WAIT_JSON]
        self.call_count = 0

    async def get_response(self, *args, **kwargs):
        from agent_framework import ChatResponse, Message, UsageDetails
        idx = min(self.call_count, len(self.replies) - 1)
        text = self.replies[idx]
        self.call_count += 1
        return ChatResponse(
            messages=Message(role="assistant", contents=[text]),
            usage_details=UsageDetails(input_token_count=11, output_token_count=4),
        )


def _build_role_agents(case_meta, prompts_for_arm, scripts: dict[str, list[str]]):
    role_clients = {}
    role_agents = {}
    for role in case_meta["roles"]:
        client = ScriptedChatClient(scripts.get(role, [WAIT_JSON]))
        role_clients[role] = client
        role_agents[role] = af.Agent(client, prompts_for_arm[role], name=role)
    return role_clients, role_agents


async def smoke_gate_rejects_off_contract():
    print("=" * 72)
    print("SMOKE 1: localvalid_gate rejects a scripted off-contract send")
    print("=" * 72)
    case_meta, efsms, payload_guards, choice_guards, prompts = main.load_artifacts()
    arm = "localvalid_gate"
    scripts = {
        # Off-contract: Author's initial EFSM state only allows SEND
        # Submit(...) to QualityReviewer. This sends the WRONG LABEL to the
        # RIGHT peer -> off_protocol violation -> must be REJECTED.
        "Author": ['{"send_to": "QualityReviewer", "label": "WrongLabel", '
                  '"payload": "x", "rationale": "deliberately off-contract"}'],
    }
    role_clients, role_agents = _build_role_agents(case_meta, prompts[arm], scripts)

    events_log = []
    result = await main.run_trial_with_agents(
        arm, role_agents, None,
        roles=case_meta["roles"], terminal_label=case_meta["terminal_label"],
        max_steps=2, efsms=efsms, payload_guards=payload_guards,
        choice_guards=choice_guards, branch_hint=None,
        log_fn=lambda event, **kw: events_log.append((event, kw)))

    print(f"  terminated_by = {result.terminated_by}")
    print(f"  events        = {result.events}")
    print(f"  blocked_attempts = {result.blocked_attempts}")
    print(f"  Author calls made: {role_clients['Author'].call_count}")
    gated_logs = [kw for ev, kw in events_log if ev == "gated"]

    assert len(result.blocked_attempts) >= 1, "expected at least one blocked attempt"
    b = result.blocked_attempts[0]
    assert b["sender"] == "Author"
    assert b["label"] == "WrongLabel"
    assert b["gate_verdict"] == "rejected"
    assert b["reject_reason"], "reject_reason must be populated"
    assert len(result.events) == 0, (
        "the off-contract send must NOT have been delivered as an event")
    assert len(gated_logs) >= 1 and gated_logs[0]["violation_type"] == "off_protocol"
    print("  PASS: off-contract send was rejected pre-delivery, not delivered, "
          "and logged as a 'gated' event.\n")
    return main.build_trial_record(arm, "FAKE-MODEL-NOT-FOR-EVIDENCE", 0, case_meta, result)


async def smoke_sched_enabled_roles_only():
    print("=" * 72)
    print("SMOKE 2: localvalid_sched polls ONLY enabled-SEND roles")
    print("=" * 72)
    case_meta, efsms, payload_guards, choice_guards, prompts = main.load_artifacts()
    arm = "localvalid_sched"
    scripts = {
        # Author WAITs twice (no progress) before finally sending Submit. If
        # the scheduler were round-robin it would ALSO poll
        # QualityReviewer..DevOps during those two idle turns; the EFSM
        # scheduler must not, because none of them has an enabled SEND yet
        # (their local state is "receive Submit from Author").
        "Author": [WAIT_JSON, WAIT_JSON,
                  '{"send_to": "QualityReviewer", "label": "Submit", '
                  '"payload": "v1", "rationale": "go"}'],
        "QualityReviewer": ['{"send_to": "SecurityReviewer", "label": "ToSecurity", '
                            '"payload": "v1", "rationale": "go"}'],
    }
    role_clients, role_agents = _build_role_agents(case_meta, prompts[arm], scripts)

    result = await main.run_trial_with_agents(
        arm, role_agents, None,
        roles=case_meta["roles"], terminal_label=case_meta["terminal_label"],
        # Cap at 2 delivered events: Author's Submit, QualityReviewer's
        # ToSecurity. The loop must stop there without EVER calling
        # SecurityReviewer/ArchReviewer/ResponsibleAIReviewer/Merger/DevOps,
        # none of which has an enabled SEND within this window.
        max_steps=2, efsms=efsms, payload_guards=payload_guards,
        choice_guards=choice_guards, branch_hint=None, log_fn=None)

    print(f"  terminated_by = {result.terminated_by}")
    print(f"  events        = {result.events}")
    call_counts = {r: c.call_count for r, c in role_clients.items()}
    print(f"  call_count per role = {call_counts}")

    assert result.terminated_by == "max_steps"
    assert [e["label"] for e in result.events] == ["Submit", "ToSecurity"], (
        "expected exactly Author->QualityReviewer Submit, then "
        "QualityReviewer->SecurityReviewer ToSecurity, in that order")
    assert call_counts["Author"] == 3, "Author should be polled 3x (2 WAIT + 1 SEND)"
    assert call_counts["QualityReviewer"] == 1
    for r in ("SecurityReviewer", "ArchReviewer", "ResponsibleAIReviewer",
             "Merger", "DevOps"):
        assert call_counts[r] == 0, (
            f"scheduler must NEVER poll {r} while it has no enabled SEND "
            f"(got {call_counts[r]} calls)")
    print("  PASS: scheduler polled Author repeatedly while it was the only "
          "enabled-SEND role, advanced to QualityReviewer once Author's "
          "Submit was delivered, and NEVER polled the five roles with no "
          "enabled SEND in this window.\n")
    return main.build_trial_record(arm, "FAKE-MODEL-NOT-FOR-EVIDENCE", 0, case_meta, result)


# ---------------------------------------------------------------------------
# Reorder smokes (async-subtyping port; orchestrator directive 2026-08-05)
# ---------------------------------------------------------------------------

def _act(to: str, label: str) -> str:
    return json.dumps({"send_to": to, "label": label, "payload": "v1",
                       "rationale": "go"})


# EFSM-literal linearization of the Merger's approve branch (verified against
# artifacts/efsm.json: 71->77 ApprovedAuthor, 77->78 StopQuality,
# 78->79 StopSecurity, 79->80 StopArch, 80->81 StopRai, 81->82 Deploy).
MERGER_LITERAL_ORDER = ["ApprovedAuthor", "StopQuality", "StopSecurity",
                        "StopArch", "StopRai", "Deploy"]
# Commuted order: StopQuality emitted BEFORE ApprovedAuthor — two sends to
# DIFFERENT peers, which asynchronous MPST says commute. A strict-order
# walker would falsely reject StopQuality here.
MERGER_REORDERED = ["StopQuality", "ApprovedAuthor", "StopSecurity",
                    "StopArch", "StopRai", "Deploy"]
_MERGER_RECEIVER = {"ApprovedAuthor": "Author", "StopQuality": "QualityReviewer",
                    "StopSecurity": "SecurityReviewer", "StopArch": "ArchReviewer",
                    "StopRai": "ResponsibleAIReviewer", "Deploy": "DevOps"}


async def _run_happy_trial_with_merger_order(merger_order: list[str]):
    """One full localvalid_gate trial: happy review chain, then the Merger
    emits its 6-peer notification block in ``merger_order``, then DevOps
    deploys. Returns (result, gated_log_lines)."""
    case_meta, efsms, payload_guards, choice_guards, prompts = main.load_artifacts()
    arm = "localvalid_gate"
    scripts = {
        "Author": [_act("QualityReviewer", "Submit"), WAIT_JSON],
        "QualityReviewer": [_act("SecurityReviewer", "ToSecurity"), WAIT_JSON],
        "SecurityReviewer": [_act("ArchReviewer", "ToArch"), WAIT_JSON],
        "ArchReviewer": [_act("ResponsibleAIReviewer", "ToRai"), WAIT_JSON],
        "ResponsibleAIReviewer": [_act("Merger", "ToMerger"), WAIT_JSON],
        "Merger": [_act(_MERGER_RECEIVER[l], l) for l in merger_order] + [WAIT_JSON],
        # DevOps is polled once per round-robin cycle; Deploy (the Merger's
        # 6th send) lands in cycle 6, so DevOps WAITs 5 times then deploys.
        "DevOps": [WAIT_JSON] * 5 + [_act("Merger", "Deployed")],
    }
    role_clients, role_agents = _build_role_agents(case_meta, prompts[arm], scripts)

    events_log = []
    result = await main.run_trial_with_agents(
        arm, role_agents, None,
        roles=case_meta["roles"], terminal_label=case_meta["terminal_label"],
        max_steps=20, efsms=efsms, payload_guards=payload_guards,
        choice_guards=choice_guards, branch_hint=None,
        log_fn=lambda event, **kw: events_log.append((event, kw)))
    gated = [kw for ev, kw in events_log if ev == "gated"]
    return result, gated


async def smoke_reorder_merger_block():
    print("=" * 72)
    print("SMOKE 3: localvalid_gate accepts the Merger notification block in")
    print("         BOTH the EFSM-literal order and a commuted order")
    print("=" * 72)
    chain = ["Submit", "ToSecurity", "ToArch", "ToRai", "ToMerger"]

    for name, order in (("EFSM-literal", MERGER_LITERAL_ORDER),
                        ("REORDERED (StopQuality before ApprovedAuthor)",
                         MERGER_REORDERED)):
        result, gated = await _run_happy_trial_with_merger_order(order)
        labels = [e["label"] for e in result.events]
        print(f"  [{name}] terminated_by = {result.terminated_by}")
        print(f"  [{name}] delivered labels = {labels}")
        print(f"  [{name}] blocked_attempts = {result.blocked_attempts}")
        assert result.terminated_by == "terminal_label", (
            f"{name}: trial must reach the Deployed terminal, "
            f"got {result.terminated_by} (error={result.error})")
        assert labels == chain + order + ["Deployed"], (
            f"{name}: unexpected delivered-event sequence: {labels}")
        assert result.blocked_attempts == [], (
            f"{name}: gate must not reject any send in this trial "
            f"(all are protocol-legal under async subtyping); "
            f"got {result.blocked_attempts}")
        assert gated == [], f"{name}: no 'gated' log lines expected, got {gated}"
        print(f"  [{name}] PASS: all 12 events delivered, zero gate rejections.")

    print("  PASS: both orderings accepted end-to-end. Under the pre-port\n"
          "  strict-order walker the REORDERED variant would have false-\n"
          "  rejected StopQuality at Merger state 71 (expected ReviseAuthor/\n"
          "  ApprovedAuthor) — that false rejection is now gone, while the\n"
          "  WrongLabel smoke (SMOKE 1) still rejects genuinely off-protocol\n"
          "  sends.\n")


def smoke_recv_side_reorder_walker_level():
    print("=" * 72)
    print("SMOKE 4: walker-level RECV-side reorder tolerance (QualityReviewer)")
    print("=" * 72)
    import copy
    import efsm_walker as walker

    case_meta, efsms, payload_guards, choice_guards, prompts = main.load_artifacts()

    # StopQuality (receive from Merger) arrives BEFORE Submit (receive from
    # Author) and before QR's own ToSecurity send — receives from different
    # peers commute; the strict EFSM order is Submit -> ToSecurity -> Stop.
    mon = walker.RoleMonitor(efsms["QualityReviewer"], payload_guards, choice_guards)
    v = mon.process_event(walker.TraceEvent(
        sender="Merger", receiver="QualityReviewer", label="StopQuality",
        payload="ok", step=1))
    print(f"  StopQuality-first verdict: {v}")
    print(f"  deferred obligations now owed: {mon._skipped}")
    assert v is None, "RECV-side commuted arrival must be accepted"
    assert ("receive", "Submit", "Author") in mon._skipped
    assert ("send", "ToSecurity", "SecurityReviewer") in mon._skipped

    # If the trace ended HERE, the debt must flag premature_termination even
    # though the EFSM state is already accepting (stjp_core 2026-07-19 audit
    # semantics).
    early = copy.deepcopy(mon)
    tv = early.check_termination()
    print(f"  termination-with-debt verdict: "
          f"{tv.violation_type if tv else None}: {(tv.message if tv else '')[:100]}")
    assert tv is not None and tv.violation_type == "premature_termination"
    assert "unfulfilled deferred obligation" in tv.message

    # The owed actions then appear later in the trace: consumed WITHOUT
    # advancing state, debt cleared, clean termination.
    assert mon.process_event(walker.TraceEvent(
        sender="Author", receiver="QualityReviewer", label="Submit",
        payload="v1", step=2)) is None
    assert mon.process_event(walker.TraceEvent(
        sender="QualityReviewer", receiver="SecurityReviewer", label="ToSecurity",
        payload="v1", step=3)) is None
    assert mon._skipped == [], f"debt must be cleared, still owed: {mon._skipped}"
    assert mon.check_termination() is None
    print("  late-arriving owed messages consumed; debt cleared; clean termination")

    # And a genuinely off-protocol event is STILL rejected on a fresh monitor
    # (commuting must not become accept-everything).
    fresh = walker.RoleMonitor(efsms["QualityReviewer"], payload_guards, choice_guards)
    v2 = fresh.process_event(walker.TraceEvent(
        sender="QualityReviewer", receiver="Author", label="Bogus",
        payload="", step=1))
    print(f"  off-protocol control: {v2.violation_type if v2 else None}")
    assert v2 is not None and v2.violation_type == "off_protocol"
    print("  PASS: RECV-side reorder accepted with deferred-obligation "
          "tracking;\n  off-protocol event still rejected.\n")


async def smoke_maf_sched_enabled_roles_only():
    """maf_localvalid_sched (NEW, 2026-08-05): MAF GroupChat with NO
    orchestrator agent -- speaker selection is the programmatic EFSM
    selection_func (main.py's MafGroupChatLoop._build_efsm_selection_func).
    Same claim as SMOKE 2 (only enabled-SEND roles get polled), ported to
    the MAF runtime: Author is the only role with an enabled SEND at round
    0, so it must be selected first; QualityReviewer next once Author's
    Submit lands."""
    print("=" * 72)
    print("SMOKE 5: maf_localvalid_sched -- MAF GroupChat, EFSM selection_func,")
    print("         NO orchestrator agent/LLM call for speaker selection")
    print("=" * 72)
    case_meta, efsms, payload_guards, choice_guards, prompts = main.load_artifacts()
    arm = "maf_localvalid_sched"
    assert "__orchestrator__" not in prompts[arm], (
        "maf_localvalid_sched must have no __orchestrator__ prompt")
    scripts = {
        "Author": [_act("QualityReviewer", "Submit")],
        "QualityReviewer": [_act("SecurityReviewer", "ToSecurity")],
    }
    role_clients, role_agents = _build_role_agents(case_meta, prompts[arm], scripts)

    result = await main.run_trial_with_agents(
        arm, role_agents, None,
        roles=case_meta["roles"], terminal_label=case_meta["terminal_label"],
        max_steps=2, efsms=efsms, payload_guards=payload_guards,
        choice_guards=choice_guards, branch_hint=None, log_fn=None)

    print(f"  terminated_by = {result.terminated_by}")
    print(f"  events        = {result.events}")
    call_counts = {r: c.call_count for r, c in role_clients.items()}
    print(f"  call_count per role = {call_counts}")

    labels = [e["label"] for e in result.events]
    assert labels[:2] == ["Submit", "ToSecurity"], (
        f"expected the EFSM scheduler to pick Author then QualityReviewer "
        f"first, got labels={labels}")
    assert call_counts["Author"] >= 1 and call_counts["QualityReviewer"] >= 1
    # SecurityReviewer legitimately becomes enabled once ToSecurity is
    # delivered (it must now reply), so it's scripted to WAIT and IS polled
    # repeatedly -- that's correct EFSM-driven behaviour, not a leak. The
    # four roles still downstream of it (never yet enabled in this window)
    # must never be touched.
    assert call_counts["SecurityReviewer"] >= 1, (
        "SecurityReviewer should become enabled (and get polled) once "
        "ToSecurity is delivered")
    for r in ("ArchReviewer", "ResponsibleAIReviewer", "Merger", "DevOps"):
        assert call_counts[r] == 0, (
            f"MAF EFSM scheduler must never poll {r} while it has no "
            f"enabled SEND (got {call_counts[r]} calls)")
    print("  PASS: MAF GroupChat with the EFSM selection_func picked Author "
          "then QualityReviewer (the only enabled-SEND roles), let "
          "SecurityReviewer be polled once it became enabled, with zero "
          "orchestrator LLM calls and zero calls to the four still-"
          "not-yet-enabled roles.\n")
    return main.build_trial_record(arm, "FAKE-MODEL-NOT-FOR-EVIDENCE", 0, case_meta, result)


async def smoke_maf_gate_rejects_pre_broadcast():
    print("=" * 72)
    print("SMOKE 6: maf_localvalid_gate rejects before MAF broadcast")
    print("=" * 72)
    case_meta, efsms, payload_guards, choice_guards, prompts = main.load_artifacts()
    arm = "maf_localvalid_gate"
    scripts = {
        "Author": [
            _act("QualityReviewer", "WrongLabel"),
            _act("QualityReviewer", "Submit"),
        ],
    }
    role_clients, role_agents = _build_role_agents(case_meta, prompts[arm], scripts)
    orchestrator_client = ScriptedChatClient([
        json.dumps({"terminate": False, "reason": "start",
                    "next_speaker": "Author", "final_message": None}),
        json.dumps({"terminate": True, "reason": "gate verified",
                    "next_speaker": None, "final_message": "done"}),
    ])
    orchestrator = af.Agent(
        orchestrator_client, prompts[arm]["__orchestrator__"],
        name="Orchestrator")

    result = await main.run_trial_with_agents(
        arm, role_agents, orchestrator,
        roles=case_meta["roles"], terminal_label=case_meta["terminal_label"],
        max_steps=2, efsms=efsms, payload_guards=payload_guards,
        choice_guards=choice_guards, branch_hint=None, log_fn=None)

    labels = [event["label"] for event in result.events]
    print(f"  delivered labels = {labels}")
    print(f"  blocked_attempts = {result.blocked_attempts}")
    assert labels == ["Submit"], (
        "only the corrected Submit may enter MAF's shared transcript")
    assert len(result.blocked_attempts) == 1
    assert result.blocked_attempts[0]["label"] == "WrongLabel"
    assert result.blocked_attempts[0]["gate_verdict"] == "rejected"
    assert role_clients["Author"].call_count == 2, (
        "the gate must re-prompt the same participant after rejection")
    print("  PASS: off-contract output was rejected and the same MAF "
          "participant was re-prompted before broadcast.\n")


async def smoke_usage_interceptor_counts_internal_calls():
    inner = ScriptedChatClient(["one", "two"])
    client = main.RetryingChatClient(inner)
    await client.get_response([])
    await client.get_response([])
    # 4th element: cached_tokens (0 — ScriptedChatClient reports no cache)
    assert client.captured_usage() == (22, 8, 2, 0)

    class CachedChatClient(ScriptedChatClient):
        async def get_response(self, *args, **kwargs):
            from agent_framework import ChatResponse, Message, UsageDetails
            self.call_count += 1
            return ChatResponse(
                messages=Message(role="assistant", contents=["ok"]),
                usage_details=UsageDetails(input_token_count=11,
                                           output_token_count=4,
                                           cache_read_input_token_count=7),
            )

    cached_client = main.RetryingChatClient(CachedChatClient(["ok"]))
    await cached_client.get_response([])
    assert cached_client.captured_usage() == (11, 4, 1, 7)
    print("  PASS: chat-client interceptor counts calls hidden inside MAF "
          "and captures cached-input tokens.\n")


async def _run() -> None:
    r1 = await smoke_gate_rejects_off_contract()
    r2 = await smoke_sched_enabled_roles_only()
    await smoke_reorder_merger_block()
    smoke_recv_side_reorder_walker_level()
    r5 = await smoke_maf_sched_enabled_roles_only()
    await smoke_maf_gate_rejects_pre_broadcast()
    await smoke_usage_interceptor_counts_internal_calls()
    print("=" * 72)
    print("ALL GATE-2 SMOKES PASSED (1: gate reject, 2: sched, "
          "3: reorder both orders, 4: RECV-side reorder, "
          "5: maf_localvalid_sched EFSM selection_func, "
          "6: maf_localvalid_gate pre-broadcast enforcement, "
          "7: complete MAF usage interception)")
    print("=" * 72)
    print("\n(FakeChatClient trial records shown for transcript purposes ONLY -")
    print(" per spec §6 these are NEVER persisted to runs/ and count in no table.)")
    print("\n--- smoke 1 (localvalid_gate) record ---")
    print(json.dumps(r1, indent=2)[:1500])
    print("\n--- smoke 2 (localvalid_sched) record ---")
    print(json.dumps(r2, indent=2)[:1500])


def main_cli() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main_cli()
