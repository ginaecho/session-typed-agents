"""MAFGroupChatRunner — MAF's true emergent-orchestration baseline.

Unlike the recipient-addressed `maf_native`/`maf_foundry` arms (where each
agent's JSON.send_to picks the next speaker), this arm uses MAF's
`GroupChatBuilder` with an LLM-based **orchestrator_agent** that decides
who speaks each round. This is the spirit-of-AutoGen / spirit-of-MAF
baseline: the agents themselves design the conversation flow.

How it differs from the other WITHOUT arms:

  - bare         : Foundry, manual round-robin (we drive turns)
  - maf_native   : MAF Agent, recipient-addressed (agent.send_to picks next)
  - maf_foundry  : MAF + Foundry chat, recipient-addressed
  - maf_groupchat: MAF GroupChat, **LLM orchestrator picks next speaker each round**

This is the "fairest" comparison vs WITH-spec arms: agents share a single
chat transcript, an LLM picks the next speaker emergently, and we measure
the cost (orchestrator + participant LLM calls) + success rate.

NOTE on termination: we use `max_rounds = case.max_steps + 4` and rely on
events to tell us if terminal_label was reached. A custom TerminationCondition
would let us stop early; first-cut keeps the loop simple.
"""
from __future__ import annotations

import asyncio
import copy
import functools
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

from agent_framework import (Agent, AgentExecutor, AgentExecutorResponse,
                             AgentResponse)
from agent_framework.openai import OpenAIChatCompletionClient
from agent_framework.orchestrations import (AgentBasedGroupChatOrchestrator,
                                            GroupChatBuilder)
from agent_framework_orchestrations._base_group_chat_orchestrator import (
    GroupChatResponseMessage, ParticipantRegistry)

from stjp_core.foundry.az_credential import AzCliCredential
from baselines.base import AttemptResult, BaselineRunner
from baselines.instructions import (build_bare_instructions,
                                     build_global_spec_instructions)
from stjp_core.monitor.monitor import SessionMonitor, TraceEvent

# Hard wall-clock timeout per attempt. The unsafe-protocol arm can deadlock
# (agents emit WAIT forever because the global type has a partial-branch
# participation flaw). Without this, the arm would hang indefinitely.
DEFAULT_ATTEMPT_TIMEOUT_S = 180.0

# Type alias: a builder(case, role) -> str produces the per-role system prompt.
# Default is build_bare_instructions (intent-only); pass
# build_global_spec_instructions for the fair-comparison arm that gives
# agents the global protocol text without projection/monitor.

if TYPE_CHECKING:  # pragma: no cover
    from case_loader import Case
    from stjp_core.monitor.stjp_live_emitter import LiveEventEmitter


def _build_orchestrator_instructions(case: "Case",
                                     protocol_text: Optional[str] = None
                                     ) -> str:
    """LLM speaker-selection prompt for the GroupChat orchestrator agent.

    The orchestrator is MAF's intent-carrying component: it ALWAYS holds the
    full user intent (``case.intent_effective`` — the whole document at doc
    scale), because deciding who acts next toward the user's goals is exactly
    the job the intent informs. Under the fair intent-carrying policy the
    participants then do NOT need to carry it too.

    ``protocol_text`` (the maf_groupchat_llmvalid_orch kind): the validated
    global protocol is placed HERE — with the planner — instead of being
    broadcast into every participant prompt.
    """
    roles = ", ".join(case.roles)
    proto_block = ""
    if protocol_text:
        proto_block = f"""
Validated global protocol (authoritative interaction plan — schedule speakers
so the conversation follows it):
---
{protocol_text}
---
"""
    return f"""You are the orchestrator of a multi-agent {case.case_id} pipeline.

Participants (you must pick one of these names exactly): {roles}.

User intent:
{case.intent_effective}
{proto_block}
Your job: read the most recent message, decide WHICH participant should speak
next to keep the pipeline progressing toward the goals, and reply with ONLY
that participant's name. No prose, no explanation, no quotes.

If the pipeline is complete (last message used label '{case.terminal_label}'),
reply with the SAME name you just picked - the run will terminate soon
regardless.
"""


def _parse_action(text: str) -> Optional[dict]:
    """Best-effort JSON action lift; returns None if the reply isn't an action."""
    text = (text or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        text = "\n".join(l for l in text.splitlines()
                         if not l.startswith("```")).strip()
    s, e = text.find("{"), text.rfind("}")
    if s < 0 or e < 0:
        return None
    try:
        return json.loads(text[s:e + 1])
    except Exception:
        return None


def _extract_usage(response) -> tuple[int, int]:
    """(prompt_tokens, completion_tokens) from a MAF response. Normalises keys."""
    ud = getattr(response, "usage_details", None) or {}
    prompt = int(ud.get("input_token_count") or
                 ud.get("prompt_tokens") or
                 ud.get("input_tokens") or 0)
    completion = int(ud.get("output_token_count") or
                     ud.get("completion_tokens") or
                     ud.get("output_tokens") or 0)
    return prompt, completion


class MAFGatedOrchestrator(AgentBasedGroupChatOrchestrator):
    """MAF LLM orchestrator with an STJP pre-broadcast message gate."""

    def __init__(self, agent, participant_registry, *, efsms, refinements,
                 max_rounds: int, on_reject=None):
        super().__init__(
            agent=agent, participant_registry=participant_registry,
            max_rounds=max_rounds)
        self._monitor = SessionMonitor(efsms, refinements)
        self._accepted_steps = 0
        self._rejected: list[tuple[str, Optional[str], str]] = []
        self.blocked_attempts: list[dict] = []
        self._on_reject = on_reject or (lambda record: None)

    @staticmethod
    def _response_key(response) -> tuple[str, Optional[str], str]:
        if isinstance(response, AgentExecutorResponse):
            ar = response.agent_response
            return response.executor_id, getattr(ar, "response_id", None), ar.text or ""
        if isinstance(response, GroupChatResponseMessage):
            return "", None, response.message.text or ""
        return "", None, ""

    def consume_rejected(self, response: AgentExecutorResponse) -> bool:
        key = self._response_key(response)
        for index, rejected in enumerate(self._rejected):
            if rejected == key:
                self._rejected.pop(index)
                return True
        return False

    def _probe(self, actor: str, text: str):
        action = _parse_action(text)
        if not action:
            return None, None
        send_to = action.get("send_to")
        label = action.get("label", "")
        if not send_to or label == "WAIT":
            return None, None
        event = TraceEvent(
            sender=actor, receiver=send_to, label=label,
            payload=str(action.get("payload", "")),
            step=self._accepted_steps + 1)
        for monitor in self._monitor.monitors.values():
            probe = copy.deepcopy(monitor)
            violation = probe.process_event(event)
            if violation is not None:
                return event, violation
        return event, None

    async def _handle_response(self, response, ctx) -> None:
        actor = ctx.get_source_executor_id()
        text = self._response_key(response)[2]
        event, violation = self._probe(actor, text)
        if violation is None:
            if event is not None:
                for monitor in self._monitor.monitors.values():
                    monitor.process_event(event)
                self._accepted_steps += 1
            await super()._handle_response(response, ctx)
            return

        record = {
            "step": self._accepted_steps + 1,
            "sender": actor,
            "receiver": event.receiver,
            "label": event.label,
            "payload": event.payload,
            "gate_verdict": "rejected",
            "reject_reason": violation.message,
        }
        self.blocked_attempts.append(record)
        self._rejected.append(self._response_key(response))
        self._on_reject(record)

        if await self._check_round_limit_and_yield(ctx):
            return
        feedback = (
            "CONTRACT MONITOR - your previous action "
            f"({event.label} to {event.receiver}) was REJECTED and NOT "
            f"broadcast.\nReason: {violation.message}\n"
            f"Expected here: {violation.expected}\n"
            "Choose a contract-compliant action now.")
        await self._send_request_to_participant(
            actor, ctx, additional_instruction=feedback)
        self._increment_round()


class MAFGroupChatRunner(BaselineRunner):
    """MAF GroupChatBuilder, either with an LLM orchestrator_agent
    (schedule="orchestrator", the default) or a PROGRAMMATIC selection_func
    implementing the EFSM enabled-sender rule (schedule="efsm", the
    maf_localvalid_sched kind — BENCHMARK_PLAN_V3 §10.8), optionally with
    a pre-broadcast gate (`maf_localvalid_gate`).

    Parameterised by `instructions_builder` so the same class powers most of
    the MAF arms:
      - maf_skills      : build_unchecked_skills_instructions
      - maf_groupchat (legacy) : build_bare_instructions / build_bare_fairintent_instructions
      - maf_globalvalid : build_global_spec_(fairintent_)instructions(override=...)
      - maf_groupchat_unsafe : build_global_spec_instructions(override=...)
      - maf_localvalid / maf_localvalid_gate / maf_localvalid_sched :
        build_spec_minimal_instructions(override=...)

    schedule="efsm" (feasibility confirmed 2026-08-05 — see
    agent_framework_orchestrations/_group_chat.py: GroupChatBuilder accepts
    `selection_func: Callable[[GroupChatState], Awaitable[str] | str]` as a
    first-class alternative to `orchestrator_agent`, mutually exclusive with
    it): no orchestrator Agent/LLM call is made at all. The selection
    function recomputes each participant's projected-EFSM state by replaying
    `GroupChatState.conversation` through a fresh
    `stjp_core.monitor.monitor.RoleMonitor` on every call (stateless — no
    synchronization needed with MAF's own transcript) and returns the first
    round-robin-ordered participant with an enabled SEND at its current
    state — the SAME claim predicate as FoundryRunner(schedule="efsm") /
    main.py's RoundRobinGateLoop(schedule="efsm").

    `gate=True` uses a custom AgentBasedGroupChatOrchestrator, a documented
    GroupChatBuilder extension point, to validate each participant response
    before the default append/broadcast path. Rejected output is never added
    to the shared transcript; the same participant is re-prompted with the
    contract verdict. `maf_localvalid_sched` keeps gate=False so scheduling
    remains isolated from enforcement.
    """

    def __init__(self, case: "Case", scenario_key: str, scenario_name: str,
                 instructions_builder: Callable = build_bare_instructions,
                 attempt_timeout_s: float = DEFAULT_ATTEMPT_TIMEOUT_S, *,
                 protocol_path_override: Optional[Path] = None,
                 goals_path_override: Optional[Path] = None,
                 orchestrator_protocol_path: Optional[Path] = None,
                 schedule: str = "orchestrator",
                 gate: bool = False):
        super().__init__(case, scenario_key, scenario_name)
        if schedule not in ("orchestrator", "efsm"):
            raise ValueError(f"unknown schedule: {schedule!r} (expected "
                             f"'orchestrator' or 'efsm')")
        self._chat_client: Optional[OpenAIChatCompletionClient] = None
        self._participants: dict[str, Agent] = {}
        self._orchestrator: Optional[Agent] = None
        self._instructions_builder = instructions_builder
        self._attempt_timeout_s = attempt_timeout_s
        self._protocol_override = protocol_path_override
        self._goals_override = goals_path_override
        # When set (maf_localvalid), the ORCHESTRATOR prompt carries this
        # global protocol (Scribble source + deterministic paraphrase) — the
        # protocol lives with the planner, not broadcast into every
        # participant prompt. Unused when schedule="efsm" (no orchestrator).
        self._orch_protocol_path = orchestrator_protocol_path
        self._schedule = schedule
        self._gate = gate
        self._efsms: Optional[dict] = None
        self._refinements: Optional[dict] = None

    def active_protocol_path(self) -> Path:
        return self._protocol_override or self.case.protocol_path

    def goal_set(self):
        if self._goals_override is None:
            return self.case.goal_set()
        from case_loader import load_goal_set_from_yaml
        return load_goal_set_from_yaml(self._goals_override, self.case.intent)

    def reset_for_trial(self, trial: int) -> None:
        """Rebuild chat client + participants + orchestrator per trial.

        Defensive isolation: ensures no object-level state on chat_client
        (e.g. internal token bookkeeping) or agents carries between trials.
        Each agent.run() call is already stateless without a session, so
        this is belt-and-suspenders for the comparison's purity.
        """
        # Calling setup() rebuilds everything from scratch.
        self.setup()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def setup(self) -> None:
        azure_endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
        api_version = os.environ.get("AZURE_OPENAI_API_VERSION",
                                     "2024-12-01-preview")
        deployment = os.environ["AZURE_OPENAI_DEPLOYMENT"]
        credential = AzCliCredential()

        self._chat_client = OpenAIChatCompletionClient(
            model=deployment, azure_endpoint=azure_endpoint,
            api_version=api_version, credential=credential,
        )

        # One participant agent per role. Prompt comes from the configured
        # builder: bare (intent only) or global-spec (intent + global protocol).
        # Stash every per-role prompt so case_runner.py can persist it under
        # run_dir/prompts/<arm>/. Also stash the orchestrator's speaker-
        # selection prompt under the reserved key "__orchestrator__" — it
        # is a real LLM-call prompt unique to this arm family and must be
        # auditable too.
        self._participants = {}
        for role in self.case.roles:
            instr = self._instructions_builder(self.case, role)
            self._role_prompts[role] = instr
            self._participants[role] = Agent(
                client=self._chat_client,
                instructions=instr,
                # MAF requires agent names to be C-style identifiers (no hyphens).
                name=f"{role}",
                description=f"{role} agent for {self.case.case_id} "
                            f"(MAF GroupChat, {self.scenario_key})",
            )

        if self._schedule == "efsm" or self._gate:
            # No orchestrator Agent/LLM call at all — speaker selection is a
            # programmatic function against the projected EFSM. Compute the
            # per-role EFSMs once here so the (stateless, per-call) selection
            # function doesn't reparse the protocol every round.
            from stjp_core.compiler.efsm_parser import get_all_efsms
            proto_path = self.active_protocol_path()
            self._efsms = get_all_efsms(proto_path, self.case.protocol_name,
                                        self.case.roles)
            if self._gate:
                from stjp_core.compiler.refinement_checker import (
                    load_refinements_for_protocol)
                self._refinements = load_refinements_for_protocol(proto_path)
        if self._schedule == "efsm":
            self._orchestrator = None
            return

        orch_protocol_text = None
        if self._orch_protocol_path is not None:
            from stjp_core.compiler.protocol_parser import parse_protocol_file
            from baselines.instructions import _paraphrase_global_protocol
            parsed = parse_protocol_file(self._orch_protocol_path)
            paraphrase = _paraphrase_global_protocol(
                self.case, protocol_path=self._orch_protocol_path)
            orch_protocol_text = (f"{parsed.raw_content}\n\n"
                                  f"Natural-language summary:\n{paraphrase}")
        orch_instr = _build_orchestrator_instructions(
            self.case, protocol_text=orch_protocol_text)
        self._role_prompts["__orchestrator__"] = orch_instr
        # Collision-proof name: gem_dev_team has a ROLE literally named
        # "Orchestrator", which would duplicate the executor ID otherwise.
        orch_name = "StjpProtocolOrchestrator"
        while orch_name in self.case.roles:
            orch_name = "_" + orch_name
        self._orchestrator = Agent(
            client=self._chat_client,
            instructions=orch_instr,
            name=orch_name,
            description=f"Speaker selector for {self.case.case_id} GroupChat",
        )

    # ------------------------------------------------------------------
    # EFSM-driven selection_func (schedule="efsm" — maf_localvalid_sched)
    # ------------------------------------------------------------------

    def _build_efsm_selection_func(self):
        """A GroupChatSelectionFunction (plain sync callable — GroupChatBuilder
        awaits it only if it returns an awaitable) implementing the EFSM
        enabled-sender claim predicate. Stateless per call: rebuilds fresh
        RoleMonitors from `state.conversation` every round, so it needs no
        shared mutable state with MAF's own transcript bookkeeping — only a
        small round-robin tie-break queue (closed over here) so that when
        more than one role has an enabled SEND, selection stays deterministic
        and fair instead of always picking the same role."""
        from stjp_core.monitor.monitor import RoleMonitor, TraceEvent

        roles = list(self.case.roles)
        efsms = self._efsms
        assert efsms is not None, "setup() must run before the workflow starts"
        tie_break_queue = list(roles)

        def selection_func(state) -> str:
            events: list[TraceEvent] = []
            step = 0
            for msg in state.conversation:
                if getattr(msg, "role", None) != "assistant":
                    continue
                actor = getattr(msg, "author_name", None)
                if actor not in efsms:
                    continue
                action = _parse_action(getattr(msg, "text", "") or "")
                if not action:
                    continue
                send_to = action.get("send_to")
                label = action.get("label", "")
                if not send_to or label == "WAIT":
                    continue
                step += 1
                events.append(TraceEvent(sender=actor, receiver=send_to,
                                         label=label,
                                         payload=str(action.get("payload", "")),
                                         step=step))

            monitors = {role: RoleMonitor(efsms[role]) for role in roles}
            for ev in events:
                for mon in monitors.values():
                    mon.process_event(ev)

            enabled = [
                role for role in tie_break_queue
                if any(t.direction == "send"
                       for t in monitors[role].efsm.transitions_from(
                           monitors[role].current_state))
            ]
            # A validated protocol always has >=1 enabled sender until every
            # role reaches an accepting state; if none is enabled (shouldn't
            # happen), fall back to round-robin rather than raising, so
            # max_rounds — not an exception — is what ends the attempt.
            actor = enabled[0] if enabled else tie_break_queue[0]
            tie_break_queue.remove(actor)
            tie_break_queue.append(actor)
            return actor

        return selection_func

    # ------------------------------------------------------------------
    # Per-attempt
    # ------------------------------------------------------------------

    def run_attempt(self, trial: int, attempt: int,
                    branch_hint: Optional[str],
                    emitter: "LiveEventEmitter") -> AttemptResult:
        return asyncio.run(self._run_attempt_async(
            trial, attempt, branch_hint, emitter))

    async def _run_attempt_async(self, trial: int, attempt: int,
                                  branch_hint: Optional[str],
                                  emitter: "LiveEventEmitter") -> AttemptResult:
        case = self.case
        assert self._participants
        assert self._schedule == "efsm" or self._orchestrator is not None

        # Fresh workflow per attempt -- prior attempts' state cannot leak in.
        gated_orchestrator = None
        if self._schedule == "efsm":
            workflow = (
                GroupChatBuilder(
                    participants=list(self._participants.values()),
                    selection_func=self._build_efsm_selection_func(),
                    orchestrator_name="EFSMScheduler",
                )
                .with_max_rounds(case.max_steps + 4)
                .build()
            )
        elif self._gate:
            assert self._orchestrator is not None
            assert self._efsms is not None
            participant_executors = [
                AgentExecutor(agent) for agent in self._participants.values()
            ]
            gated_orchestrator = MAFGatedOrchestrator(
                self._orchestrator,
                ParticipantRegistry(participant_executors),
                efsms=self._efsms,
                refinements=self._refinements,
                max_rounds=case.max_steps + 4,
                on_reject=lambda record: emitter.emit_marker(
                    "gated", trial=trial, attempt=attempt,
                    scenario=self.scenario_name, **record),
            )
            workflow = GroupChatBuilder(
                participants=participant_executors,
                orchestrator=gated_orchestrator,
            ).build()
        else:
            workflow = (
                GroupChatBuilder(
                    participants=list(self._participants.values()),
                    orchestrator_agent=self._orchestrator,
                )
                .with_max_rounds(case.max_steps + 4)  # slack for orchestrator picks
                .build()
            )

        hint_clause = f"  Branch hint: this scenario is a {branch_hint}-revenue case." \
            if branch_hint else ""
        task = (f"Start the {case.case_id} pipeline now. "
                f"Each participant should reply with one JSON action per turn "
                f"(see your instructions).{hint_clause}")

        from stjp_core.evaluation.goal_elicitor import verify_goals_against_trace
        goal_set = case.goal_set()
        events: list[TraceEvent] = []
        history: list[dict] = []
        prompt_tk = completion_tk = calls = 0
        step = 0

        try:
            result = await asyncio.wait_for(workflow.run(task),
                                            timeout=self._attempt_timeout_s)
        except asyncio.TimeoutError:
            print(f"  [{self.scenario_name}] workflow TIMEOUT after "
                  f"{self._attempt_timeout_s:.0f}s (likely deadlocked "
                  f"under an unsafe protocol)", flush=True)
            emitter.emit_marker("attempt_timeout", trial=trial, attempt=attempt,
                                timeout_s=self._attempt_timeout_s,
                                scenario=self.scenario_name)
            return AttemptResult(events=events,
                                 usage={"prompt_tokens": prompt_tk,
                                        "completion_tokens": completion_tk,
                                        "total_tokens": prompt_tk + completion_tk,
                                        "calls": calls})
        except Exception as e:
            print(f"  [{self.scenario_name}] workflow run FAIL: "
                  f"{type(e).__name__}: {str(e)[:160]}", flush=True)
            return AttemptResult(events=events,
                                 usage={"prompt_tokens": 0, "completion_tokens": 0,
                                        "total_tokens": 0, "calls": 0})

        for wev in result:
            data = getattr(wev, "data", None)

            # Orchestrator-level responses (speaker-selection LLM calls): count
            # their cost so the comparison is honest about GroupChat overhead.
            if isinstance(data, AgentResponse):
                pt, ct = _extract_usage(data)
                prompt_tk += pt
                completion_tk += ct
                calls += 1
                continue

            # Participant responses: parse JSON action and emit TraceEvent.
            if isinstance(data, AgentExecutorResponse):
                ar = data.agent_response
                pt, ct = _extract_usage(ar)
                prompt_tk += pt
                completion_tk += ct
                calls += 1
                if (gated_orchestrator is not None
                        and gated_orchestrator.consume_rejected(data)):
                    continue

                actor = data.executor_id
                action = _parse_action(ar.text or "")
                if action is None:
                    continue
                send_to = action.get("send_to")
                label = action.get("label", "")
                payload = str(action.get("payload", ""))
                if not send_to or label == "WAIT":
                    continue
                step += 1
                ev = TraceEvent(sender=actor, receiver=send_to, label=label,
                                payload=payload, payload_type="", step=step)
                events.append(ev)
                history.append({"sender": actor, "receiver": send_to,
                                "label": label, "payload": payload})

                n_goals_ok = sum(1 for ok, _ in verify_goals_against_trace(
                    goal_set, events).values() if ok)
                rec = emitter.emit(
                    ev, trial=trial, scenario=self.scenario_name,
                    goals_pass=n_goals_ok, goals_total=len(goal_set.goals),
                    extra={"tokens": {"prompt": pt, "completion": ct,
                                      "total": pt + ct}},
                )
                viol = rec['violation']['type'] if rec['violation'] else 'OK'
                print(f"  [{self.scenario_name:>20s}] step {step:2d}: "
                      f"{actor} -> {send_to} : {label}({payload[:30]})  "
                      f"viol={viol}", flush=True)
                if label == case.terminal_label:
                    break

        usage = {"prompt_tokens": prompt_tk,
                 "completion_tokens": completion_tk,
                 "total_tokens": prompt_tk + completion_tk,
                 "calls": calls}
        return AttemptResult(events=events, usage=usage)
