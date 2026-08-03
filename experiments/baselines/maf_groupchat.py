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
import functools
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

from agent_framework import Agent, AgentExecutorResponse, AgentResponse
from agent_framework.openai import OpenAIChatCompletionClient
from agent_framework.orchestrations import GroupChatBuilder

from stjp_core.foundry.az_credential import AzCliCredential
from baselines.base import AttemptResult, BaselineRunner
from baselines.instructions import (build_bare_instructions,
                                     build_global_spec_instructions)
from stjp_core.monitor.monitor import TraceEvent

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
                                     protocol_text: str | None = None) -> str:
    """LLM speaker-selection prompt for the GroupChat orchestrator agent.

    With ``protocol_text`` the orchestrator HOLDS THE PLAN: the validated
    global protocol is embedded in its prompt so its speaker choices can
    follow the intended order. Without it (the original topology) the
    orchestrator sees only roles + intent and picks speakers blind.
    """
    roles = ", ".join(case.roles)
    proto_block = ""
    if protocol_text:
        proto_block = f"""
The team must follow this validated coordination protocol. Use the message
order below to decide which participant is due to act next:
---
{protocol_text}
---
"""
    return f"""You are the orchestrator of a multi-agent {case.case_id} pipeline.

Participants (you must pick one of these names exactly): {roles}.

User intent:
{case.intent}
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


class MAFGroupChatRunner(BaselineRunner):
    """MAF GroupChatBuilder with LLM orchestrator_agent.

    Parameterised by `instructions_builder` so the same class powers four arms:
      - maf_groupchat        : build_bare_instructions
      - maf_groupchat_global : build_global_spec_instructions  (canonical .scr)
      - maf_groupchat_llmvalid: build_global_spec_instructions(override=...)
      - maf_groupchat_unsafe : build_global_spec_instructions(override=...)
    """

    def __init__(self, case: "Case", scenario_key: str, scenario_name: str,
                 instructions_builder: Callable = build_bare_instructions,
                 attempt_timeout_s: float = DEFAULT_ATTEMPT_TIMEOUT_S, *,
                 protocol_path_override: Optional[Path] = None,
                 goals_path_override: Optional[Path] = None,
                 orchestrator_holds_protocol: bool = False):
        super().__init__(case, scenario_key, scenario_name)
        self._chat_client: Optional[OpenAIChatCompletionClient] = None
        self._participants: dict[str, Agent] = {}
        self._orchestrator: Optional[Agent] = None
        self._instructions_builder = instructions_builder
        self._attempt_timeout_s = attempt_timeout_s
        self._protocol_override = protocol_path_override
        self._goals_override = goals_path_override
        self._orchestrator_holds_protocol = orchestrator_holds_protocol

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

        proto_text = None
        if self._orchestrator_holds_protocol:
            proto_text = self.active_protocol_path().read_text(encoding="utf-8")
        orch_instr = _build_orchestrator_instructions(self.case, proto_text)
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
        assert self._orchestrator is not None and self._participants

        # Fresh workflow per attempt -- prior attempts' state cannot leak in.
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
