# Copyright (c) Microsoft. All rights reserved.
#
# STJP hosted-group workflow — sdlc_release_gate, ALL 10 core arms in one
# WorkflowAgent (docs/reference/SDLC_HOSTED_WORKFLOW_SPEC.md). One request
# selects the arm; the Coordinator executor drives that arm's loop and
# returns a trial-record JSON (spec §2).
#
# ARM RENAME (2026-08-05, BENCHMARK_PLAN_V3 §10.8 "Final arm naming"): the
# 7-arm matrix (+ global_decentralized, added same-day) was renamed to a
# uniform `(maf_)?(global|local)valid(_gate|_sched)?` vocabulary, plus two
# real-skill-file baselines (`skills`/`maf_skills`, replacing `bare`/
# `maf_groupchat`) and a genuinely new arm (`maf_localvalid_sched` — MAF
# GroupChat + local contracts + EFSM-driven speaker selection; feasibility
# confirmed the same day by reading the installed agent_framework_orchestrations
# package: GroupChatBuilder(selection_func=...) is a documented first-class
# alternative to orchestrator_agent). See docs/BENCHMARK_PLAN_V3.md §10.8 for
# the full old-name/new-name table. This container has NO legacy-key aliasing
# (unlike experiments/baselines/registry.py) — it is rebuilt from
# build_hosted_artifacts.py on every deploy, so there is no old run dir that
# depends on the container itself resolving an old key.
#
# Import discipline (spec §5 gate 2 — "Structure main.py so the loop is
# importable/testable without ResponsesHostServer"): everything above
# main()/build_group() imports only agent_framework + the two sibling
# modules (efsm_walker, session_view) + stdlib. agent_framework_foundry_hosting,
# azure.identity and dotenv are imported LAZILY inside main()/_build_role_clients()
# so a test can `import main` and drive RoundRobinGateLoop / MafGroupChatLoop
# directly with a FakeChatClient-backed agent_framework.Agent, with none of
# the hosting/Azure packages installed.

from __future__ import annotations

import copy
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import agent_framework as af

import efsm_walker as walker
import session_view

logger = logging.getLogger(__name__)

HERE = Path(__file__).resolve().parent
ARTIFACTS_DIR = HERE / "artifacts"

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

# Arm semantics in-container — spec §3 table, renamed 2026-08-05 (see module
# header):
#   skills                : fixed round-robin; NO monitor at all; worker
#                          prompt is the real published per-role skill file
#                          (ex `bare`)
#   maf_skills            : same skill-file prompts, MAF GroupChat runtime
#                          with the standard LLM orchestrator (ex `maf_groupchat`)
#   globalvalid            : round-robin; monitor OBSERVES only; whole
#                          validated plan as TEXT in every role prompt
#                          (ex `global_decentralized`)
#   maf_globalvalid         : same global-text prompt, MAF runtime
#                          (ex `maf_groupchat_llmvalid`)
#   localvalid               : round-robin; monitor OBSERVES only (records a
#                          would-be verdict via reject_reason but never
#                          blocks); validated projected per-role local
#                          contract (ex `min_llmvalid`)
#   maf_localvalid            : same local contracts, MAF runtime, orchestrator
#                          holds intent + the validated global plan
#                          (ex `maf_groupchat_llmvalid_orch`)
#   localvalid_gate            : round-robin + GATE (rejects pre-delivery,
#                          re-prompts, liveness hint) (ex `min_llmvalid_gate`)
#   maf_localvalid_gate        : same local contracts and LLM-orchestrated
#                          MAF GroupChat, with a custom orchestrator that
#                          rejects before transcript append/broadcast
#   localvalid_sched            : gate + EFSM SCHEDULER (poll only
#                          enabled-SEND roles) — full STJP execution plane
#                          (ex `min_llmvalid_sched`)
#   maf_localvalid_sched          : NEW (feasibility confirmed 2026-08-05).
#                          Same local contracts as maf_localvalid, but the
#                          NEXT SPEAKER is chosen by a PROGRAMMATIC EFSM
#                          enabled-sender function
#                          (GroupChatBuilder(selection_func=...)) instead of
#                          an LLM orchestrator agent. No gate, so this arm
#                          isolates scheduling only on the MAF runtime.
ARM_CONFIG: dict[str, dict] = {
    "skills": {"kind": "roundrobin", "use_monitor": False, "gate": False,
               "schedule": "roundrobin", "hints": False},
    "maf_skills": {"kind": "maf"},
    "globalvalid": {"kind": "roundrobin", "use_monitor": True, "gate": False,
                     "schedule": "roundrobin", "hints": False},
    "maf_globalvalid": {"kind": "maf"},
    "localvalid": {"kind": "roundrobin", "use_monitor": True, "gate": False,
                    "schedule": "roundrobin", "hints": False},
    "maf_localvalid": {"kind": "maf"},
    "localvalid_gate": {"kind": "roundrobin", "use_monitor": True, "gate": True,
                         "schedule": "roundrobin", "hints": True},
    "maf_localvalid_gate": {"kind": "maf_gate"},
    "localvalid_sched": {"kind": "roundrobin", "use_monitor": True, "gate": True,
                          "schedule": "efsm", "hints": True},
    "maf_localvalid_sched": {"kind": "maf_sched"},
}


# ---------------------------------------------------------------------------
# Artifact loading (pure stdlib — no network, no Azure)
# ---------------------------------------------------------------------------

def load_artifacts(artifacts_dir: Path = ARTIFACTS_DIR) -> tuple[dict, dict, dict, list, dict]:
    """Returns (case_meta, efsms, payload_guards, choice_guards, prompts)."""
    case_meta = json.loads((artifacts_dir / "case_meta.json").read_text(encoding="utf-8"))
    efsm_json = json.loads((artifacts_dir / "efsm.json").read_text(encoding="utf-8"))
    refn_json = json.loads((artifacts_dir / "refinements.json").read_text(encoding="utf-8"))
    prompts = json.loads((artifacts_dir / "prompts.json").read_text(encoding="utf-8"))
    efsms = walker.efsms_from_json(efsm_json)
    payload_guards, choice_guards = walker.refinements_from_json(refn_json)
    return case_meta, efsms, payload_guards, choice_guards, prompts


# ---------------------------------------------------------------------------
# Parallel-safety call layer (spec §7.1): 429/throttling retried with
# exponential backoff INSIDE the call layer; a throttled retry is NEVER
# counted as a call/attempt/violation. Wraps whichever chat client the
# role Agents use (FoundryChatClient / OpenAIChatCompletionClient), so it
# protects BOTH the round-robin loop's direct agent.run() calls and the
# MAF loop's GroupChatBuilder-internal calls transparently.
# ---------------------------------------------------------------------------

_RATE_LIMIT_HINTS = (
    "429", "Too Many Requests", "TooManyRequests", "RateLimitError",
    "RateLimit", "rate limit", "ThrottlingException", "Throttled",
    "throttl",
)


def _is_rate_limited(exc: BaseException) -> bool:
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if status == 429:
        return True
    s = f"{type(exc).__name__}: {exc}"
    return any(h.lower() in s.lower() for h in _RATE_LIMIT_HINTS)


class RetryingChatClient:
    """Wraps any agent_framework chat client with 429 backoff (spec §7.1):
    base 2s, cap 60s, max 8 tries. A throttled retry never counts as a call;
    every retry emits a 'throttled' event via ``log_fn``."""

    def __init__(self, inner, *, log_fn=None, base: float = 2.0,
                 cap: float = 60.0, max_tries: int = 8):
        self._inner = inner
        self._log_fn = log_fn or (lambda **kw: None)
        self._base = base
        self._cap = cap
        self._max_tries = max_tries

    def __getattr__(self, name):
        # Delegate everything not explicitly overridden (model, service_url,
        # tokenizer, ...) to the wrapped client.
        return getattr(self._inner, name)

    async def get_response(self, *args, **kwargs):
        import asyncio
        last_exc: Optional[BaseException] = None
        for attempt in range(self._max_tries):
            try:
                call = self._inner.get_response(*args, **kwargs)
                return await call if hasattr(call, "__await__") else call
            except Exception as e:  # noqa: BLE001 - must inspect any client's error type
                if not _is_rate_limited(e):
                    raise
                last_exc = e
                delay = min(self._base * (2 ** attempt), self._cap)
                self._log_fn(event="throttled", attempt=attempt + 1,
                             max_tries=self._max_tries, delay_s=delay,
                             error=f"{type(e).__name__}: {str(e)[:200]}")
                await asyncio.sleep(delay)
        assert last_exc is not None
        raise last_exc


def _extract_usage(response) -> tuple[int, int]:
    """(prompt_tokens, completion_tokens) — same key-normalisation as
    experiments/baselines/maf_groupchat.py::_extract_usage."""
    ud = getattr(response, "usage_details", None) or {}
    prompt = int(ud.get("input_token_count") or ud.get("prompt_tokens") or
                 ud.get("input_tokens") or 0)
    completion = int(ud.get("output_token_count") or ud.get("completion_tokens") or
                      ud.get("output_tokens") or 0)
    return prompt, completion


async def _agent_turn(agent, view_text: str) -> tuple[str, int, int]:
    resp = await agent.run(view_text)
    ptk, ctk = _extract_usage(resp)
    return resp.text or "", ptk, ctk


# ---------------------------------------------------------------------------
# Loop result + the two loop classes (spec §3 arm table)
# ---------------------------------------------------------------------------

@dataclass
class RoleLoopResult:
    events: list = field(default_factory=list)
    blocked_attempts: list = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    calls: int = 0
    terminated_by: Optional[str] = None   # terminal_label|max_steps|efsm_end|error
    error: Optional[str] = None


class RoundRobinGateLoop:
    """skills / globalvalid / localvalid / localvalid_gate / localvalid_sched.

    Ports experiments/baselines/foundry_runner.py::FoundryRunner.run_attempt's
    control flow exactly (actor selection, liveness hint, gate probe-then-
    commit via deepcopy, re-prompt-on-reject, consec_wait bail-out), against
    the vendored EFSM walker instead of Foundry AgentsClient threads.
    """

    def __init__(self, *, roles: list[str], role_agents: dict, terminal_label: str,
                 max_steps: int, use_monitor: bool, gate: bool, schedule: str,
                 efsms: dict, payload_guards: dict, choice_guards: list,
                 hints: bool = True, log_fn=None):
        if schedule not in ("roundrobin", "efsm"):
            raise ValueError(f"unknown schedule: {schedule!r}")
        if schedule == "efsm" and not gate:
            raise ValueError("schedule='efsm' requires gate=True")
        self.roles = list(roles)
        self.role_agents = role_agents
        self.terminal_label = terminal_label
        self.max_steps = max_steps
        self.use_monitor = use_monitor
        self.gate = gate
        self.schedule = schedule
        self.efsms = efsms
        self.payload_guards = payload_guards
        self.choice_guards = choice_guards
        self.hints = hints
        self.log_fn = log_fn or (lambda **kw: None)

    async def run(self, branch_hint: Optional[str] = None) -> RoleLoopResult:
        result = RoleLoopResult()
        history: list[dict] = []
        actor_queue = list(self.roles)
        consec_wait = 0
        step = 0

        sm = None
        if self.use_monitor:
            sm = walker.SessionMonitor(self.efsms, self.payload_guards, self.choice_guards)

        gate_feedback: dict[str, str] = {}

        while step < self.max_steps:
            # -- pick the actor -------------------------------------------------
            if self.schedule == "efsm" and sm is not None:
                if sm.all_accepting():
                    result.terminated_by = "efsm_end"
                    break
                enabled = [r for r in actor_queue if sm.monitors[r].enabled_sends()]
                if not enabled:
                    result.terminated_by = "error"
                    result.error = ("EFSM scheduler found no enabled-SEND role and "
                                     "not all roles accepting (unexpected deadlock "
                                     "for a validated protocol)")
                    break
                actor = enabled[0]
                actor_queue.remove(actor)
                actor_queue.append(actor)
            else:
                actor = actor_queue.pop(0)
                actor_queue.append(actor)

            hint = branch_hint if (step == 0 and actor == self.roles[0]) else None
            view = session_view.build_view(actor, history, hint)

            # -- liveness nudge (gate arms only, hints=True) --------------------
            if self.gate and self.hints and sm is not None:
                mon = sm.monitors.get(actor)
                if mon is not None:
                    trans = mon.efsm.transitions_from(mon.current_state)
                    sends = [t for t in trans if t.direction == "send"]
                    if trans and len(sends) == len(trans):
                        acts = "; ".join(f"SEND {t.label} to {t.peer}" for t in sends)
                        view = (f"Protocol status: per your role contract you are "
                                f"at state {mon.current_state}. The available "
                                f"action at this state is: {acts}. There is no "
                                f"incoming message to wait for at this state.\n\n"
                                ) + view

            if self.gate and actor in gate_feedback:
                view = gate_feedback.pop(actor) + "\n\n" + view

            # -- call the actor ---------------------------------------------------
            try:
                reply_text, ptk, ctk = await _agent_turn(self.role_agents[actor], view)
                result.calls += 1
                result.prompt_tokens += ptk
                result.completion_tokens += ctk
                action = session_view.parse_action(reply_text)
            except Exception as e:
                self.log_fn(event="parse_error", actor=actor, error=str(e))
                consec_wait += 1
                if consec_wait > 2 * len(self.roles):
                    result.terminated_by = "max_steps"
                    break
                continue

            send_to = action.get("send_to")
            label = action.get("label", "")
            payload = str(action.get("payload", ""))
            if not send_to or label == "WAIT":
                consec_wait += 1
                if consec_wait > 2 * len(self.roles):
                    result.terminated_by = "max_steps"
                    break
                continue

            # -- GATE: contract check BEFORE delivery -----------------------------
            gate_verdict = "delivered"
            reject_reason = None
            if sm is not None:
                probe_ev = walker.TraceEvent(sender=actor, receiver=send_to,
                                             label=label, payload=payload,
                                             step=step + 1)
                v = None
                for _mon in sm.monitors.values():
                    probe_mon = copy.deepcopy(_mon)
                    pv = probe_mon.process_event(probe_ev)
                    if pv is not None:
                        v = pv
                        break
                if v is not None and self.gate:
                    gate_verdict = "rejected"
                    reject_reason = v.message
                    result.blocked_attempts.append({
                        "step": step + 1, "sender": actor, "receiver": send_to,
                        "label": label, "payload": payload,
                        "gate_verdict": "rejected", "reject_reason": reject_reason,
                    })
                    gate_feedback[actor] = (
                        "CONTRACT MONITOR — your previous action "
                        f"({label} to {send_to}) was REJECTED and NOT delivered.\n"
                        f"Reason: {reject_reason}\nExpected here: {v.expected}\n"
                        "Choose a contract-compliant action now.")
                    self.log_fn(event="gated", actor=actor, send_to=send_to,
                                label=label, payload=payload[:80],
                                violation_type=v.violation_type, reason=reject_reason)
                    consec_wait += 1
                    if consec_wait > 2 * len(self.roles):
                        result.terminated_by = "max_steps"
                        break
                    continue
                if v is not None and not self.gate:
                    # observe-only (localvalid / globalvalid): record the would-be verdict,
                    # still deliver — spec §3 "always delivers".
                    reject_reason = f"WOULD-REJECT (observe-only, not enforced): {v.message}"
                # Commit for real: accepted, or observe-only never blocks.
                sm.process_event(probe_ev)

            consec_wait = 0
            step += 1
            ev = {"step": step, "sender": actor, "receiver": send_to, "label": label,
                  "payload": payload, "gate_verdict": gate_verdict,
                  "reject_reason": reject_reason}
            result.events.append(ev)
            history.append({"sender": actor, "receiver": send_to, "label": label,
                            "payload": payload})
            self.log_fn(event="event", **ev)
            if label == self.terminal_label:
                result.terminated_by = "terminal_label"
                break

        if result.terminated_by is None:
            result.terminated_by = "max_steps"
        return result


def _build_maf_gated_orchestrator(
        orchestrator_agent, participant_executors, *,
        efsms, payload_guards, choice_guards, max_rounds, log_fn):
    """Build a MAF orchestrator that gates before transcript append/broadcast."""
    from agent_framework import AgentExecutorResponse
    from agent_framework.orchestrations import AgentBasedGroupChatOrchestrator
    from agent_framework_orchestrations._base_group_chat_orchestrator import (
        GroupChatResponseMessage, ParticipantRegistry)

    class GatedOrchestrator(AgentBasedGroupChatOrchestrator):
        def __init__(self):
            super().__init__(
                agent=orchestrator_agent,
                participant_registry=ParticipantRegistry(participant_executors),
                max_rounds=max_rounds)
            self._monitor = walker.SessionMonitor(
                efsms, payload_guards, choice_guards)
            self._accepted_steps = 0
            self._rejected: list[tuple[str, Optional[str], str]] = []
            self.blocked_attempts: list[dict] = []

        @staticmethod
        def _response_key(response):
            if isinstance(response, AgentExecutorResponse):
                ar = response.agent_response
                return (response.executor_id,
                        getattr(ar, "response_id", None), ar.text or "")
            if isinstance(response, GroupChatResponseMessage):
                return "", None, response.message.text or ""
            return "", None, ""

        def consume_rejected(self, response) -> bool:
            key = self._response_key(response)
            for index, rejected in enumerate(self._rejected):
                if rejected == key:
                    self._rejected.pop(index)
                    return True
            return False

        def _probe(self, actor: str, text: str):
            action = session_view.parse_action_or_none(text)
            if not action:
                return None, None
            send_to = action.get("send_to")
            label = action.get("label", "")
            if not send_to or label == "WAIT":
                return None, None
            event = walker.TraceEvent(
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
            event, violation = self._probe(
                actor, self._response_key(response)[2])
            if violation is None:
                if event is not None:
                    self._monitor.process_event(event)
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
            log_fn(
                event="gated", actor=actor, send_to=event.receiver,
                label=event.label, payload=event.payload[:80],
                violation_type=violation.violation_type,
                reason=violation.message)

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

    return GatedOrchestrator()


class MafGroupChatLoop:
    """maf_skills / maf_globalvalid / maf_localvalid / maf_localvalid_gate
    (schedule="orchestrator") or maf_localvalid_sched (schedule="efsm").

    Drives agent_framework.orchestrations.GroupChatBuilder EXACTLY as
    experiments/baselines/maf_groupchat.py::MAFGroupChatRunner._run_attempt_async
    does (same max_rounds slack, same task string, same event/usage
    extraction). With gate=True, a custom AgentBasedGroupChatOrchestrator
    validates before invoking MAF's default append/broadcast path and
    re-prompts the same participant after rejection.

    schedule="orchestrator" (maf_skills / maf_globalvalid / maf_localvalid /
    maf_localvalid_gate):
    an LLM `orchestrator_agent` picks the next speaker each round — the
    MAF-alone / MAF+STJP-compile-time-artifacts condition.

    schedule="efsm" (maf_localvalid_sched, NEW): NO orchestrator agent / LLM
    call for speaker selection at all. `GroupChatBuilder(selection_func=...)`
    — confirmed a first-class, documented, mutually-exclusive alternative to
    `orchestrator_agent` in agent_framework_orchestrations/_group_chat.py's
    `GroupChatBuilder.__init__` / `_set_orchestrator` — is given a plain
    Python callable that recomputes each participant's projected-EFSM state
    by replaying the GroupChat's own conversation transcript through the
    SAME vendored `walker.SessionMonitor`/`RoleMonitor` this file's
    RoundRobinGateLoop uses, and returns the first round-robin-ordered
    participant with an enabled SEND at its current state — the SAME claim
    predicate as RoundRobinGateLoop(schedule="efsm"). This isolates
    "protocol-derived speaker scheduling" only, not enforcement.
    """

    def __init__(self, *, participant_agents: dict,
                 orchestrator_agent=None,
                 terminal_label: str, max_steps: int,
                 schedule: str = "orchestrator",
                 efsms: Optional[dict] = None, log_fn=None):
        if schedule not in ("orchestrator", "efsm"):
            raise ValueError(f"unknown schedule: {schedule!r}")
        if schedule == "orchestrator" and orchestrator_agent is None:
            raise ValueError("schedule='orchestrator' requires orchestrator_agent")
        if schedule == "efsm" and efsms is None:
            raise ValueError("schedule='efsm' requires efsms")
        self.participant_agents = participant_agents
        self.orchestrator_agent = orchestrator_agent
        self.terminal_label = terminal_label
        self.max_steps = max_steps
        self.schedule = schedule
        self.efsms = efsms
        self.gate = False
        self.payload_guards = {}
        self.choice_guards = []
        self.log_fn = log_fn or (lambda **kw: None)

    def with_gate(self, payload_guards: dict, choice_guards: list):
        self.gate = True
        self.payload_guards = payload_guards
        self.choice_guards = choice_guards
        return self

    def _build_efsm_selection_func(self):
        """A GroupChatSelectionFunction (plain sync callable) implementing
        the EFSM enabled-sender claim predicate. Stateless per call —
        rebuilds fresh RoleMonitors from the GroupChat's own
        `state.conversation` every round; a small round-robin tie-break
        queue (closed over here) keeps selection deterministic and fair
        when more than one role has an enabled SEND."""
        roles = list(self.participant_agents.keys())
        efsms = self.efsms
        tie_break_queue = list(roles)

        def selection_func(state) -> str:
            events: list = []
            step = 0
            for msg in state.conversation:
                if getattr(msg, "role", None) != "assistant":
                    continue
                actor = getattr(msg, "author_name", None)
                if actor not in efsms:
                    continue
                action = session_view.parse_action_or_none(getattr(msg, "text", "") or "")
                if not action:
                    continue
                send_to = action.get("send_to")
                label = action.get("label", "")
                if not send_to or label == "WAIT":
                    continue
                step += 1
                events.append(walker.TraceEvent(
                    sender=actor, receiver=send_to, label=label,
                    payload=str(action.get("payload", "")), step=step))

            monitors = {role: walker.RoleMonitor(efsms[role], {}, [])
                       for role in roles}
            for ev in events:
                for mon in monitors.values():
                    mon.process_event(ev)

            enabled = [role for role in tie_break_queue
                      if monitors[role].enabled_sends()]
            actor = enabled[0] if enabled else tie_break_queue[0]
            tie_break_queue.remove(actor)
            tie_break_queue.append(actor)
            return actor

        return selection_func

    async def run(self, branch_hint: Optional[str] = None) -> RoleLoopResult:
        from agent_framework import AgentExecutorResponse, AgentResponse
        from agent_framework.orchestrations import GroupChatBuilder

        result = RoleLoopResult()
        gated_orchestrator = None
        if self.schedule == "efsm":
            workflow = (
                GroupChatBuilder(participants=list(self.participant_agents.values()),
                                 selection_func=self._build_efsm_selection_func(),
                                 orchestrator_name="EFSMScheduler")
                .with_max_rounds(self.max_steps + 4)
                .build()
            )
        elif self.gate:
            from agent_framework import AgentExecutor
            participant_executors = [
                AgentExecutor(agent)
                for agent in self.participant_agents.values()
            ]
            gated_orchestrator = _build_maf_gated_orchestrator(
                self.orchestrator_agent, participant_executors,
                efsms=self.efsms,
                payload_guards=self.payload_guards,
                choice_guards=self.choice_guards,
                max_rounds=self.max_steps + 4,
                log_fn=self.log_fn)
            workflow = GroupChatBuilder(
                participants=participant_executors,
                orchestrator=gated_orchestrator,
            ).build()
        else:
            workflow = (
                GroupChatBuilder(participants=list(self.participant_agents.values()),
                                 orchestrator_agent=self.orchestrator_agent)
                .with_max_rounds(self.max_steps + 4)
                .build()
            )
        hint_clause = (f"  Branch hint: this scenario is a {branch_hint}-revenue case."
                       if branch_hint else "")
        task = (f"Start the sdlc_release_gate pipeline now. Each participant "
                f"should reply with one JSON action per turn (see your "
                f"instructions).{hint_clause}")

        step = 0
        try:
            wf_result = await workflow.run(task)
        except Exception as e:
            result.terminated_by = "error"
            result.error = f"{type(e).__name__}: {e}"
            return result

        for wev in wf_result:
            data = getattr(wev, "data", None)
            if isinstance(data, AgentResponse):
                ptk, ctk = _extract_usage(data)
                result.prompt_tokens += ptk
                result.completion_tokens += ctk
                result.calls += 1
                continue
            if isinstance(data, AgentExecutorResponse):
                ar = data.agent_response
                ptk, ctk = _extract_usage(ar)
                result.prompt_tokens += ptk
                result.completion_tokens += ctk
                result.calls += 1
                if (gated_orchestrator is not None
                        and gated_orchestrator.consume_rejected(data)):
                    continue
                actor = data.executor_id
                action = session_view.parse_action_or_none(ar.text or "")
                if action is None:
                    continue
                send_to = action.get("send_to")
                label = action.get("label", "")
                payload = str(action.get("payload", ""))
                if not send_to or label == "WAIT":
                    continue
                step += 1
                ev = {"step": step, "sender": actor, "receiver": send_to,
                      "label": label, "payload": payload,
                      "gate_verdict": "delivered", "reject_reason": None}
                result.events.append(ev)
                self.log_fn(event="event", **ev)
                if label == self.terminal_label:
                    result.terminated_by = "terminal_label"
                    break

        if result.terminated_by is None:
            result.terminated_by = "max_steps"
        if gated_orchestrator is not None:
            result.blocked_attempts.extend(gated_orchestrator.blocked_attempts)
        return result


async def run_trial_with_agents(arm: str, role_agents: dict, orchestrator_agent,
                                 *, roles: list[str], terminal_label: str,
                                 max_steps: int, efsms: dict, payload_guards: dict,
                                 choice_guards: list, branch_hint: Optional[str] = None,
                                 log_fn=None) -> RoleLoopResult:
    """The ONE entry point gate 2 unit-tests directly (no ResponsesHostServer,
    no Azure): given already-constructed agent_framework.Agent objects (which
    may wrap a FakeChatClient), drive the arm's loop and return a
    RoleLoopResult."""
    cfg = ARM_CONFIG[arm]
    if cfg["kind"] == "roundrobin":
        loop = RoundRobinGateLoop(
            roles=roles, role_agents=role_agents, terminal_label=terminal_label,
            max_steps=max_steps, use_monitor=cfg["use_monitor"], gate=cfg["gate"],
            schedule=cfg["schedule"], efsms=efsms, payload_guards=payload_guards,
            choice_guards=choice_guards, hints=cfg.get("hints", True), log_fn=log_fn)
    elif cfg["kind"] == "maf_sched":
        # maf_localvalid_sched: NO orchestrator agent — speaker selection is
        # the programmatic EFSM enabled-sender function (see
        # MafGroupChatLoop._build_efsm_selection_func).
        loop = MafGroupChatLoop(
            participant_agents=role_agents, schedule="efsm", efsms=efsms,
            terminal_label=terminal_label, max_steps=max_steps, log_fn=log_fn)
    elif cfg["kind"] == "maf_gate":
        loop = MafGroupChatLoop(
            participant_agents=role_agents,
            orchestrator_agent=orchestrator_agent,
            schedule="orchestrator", efsms=efsms,
            terminal_label=terminal_label, max_steps=max_steps,
            log_fn=log_fn).with_gate(payload_guards, choice_guards)
    else:
        loop = MafGroupChatLoop(
            participant_agents=role_agents, orchestrator_agent=orchestrator_agent,
            schedule="orchestrator",
            terminal_label=terminal_label, max_steps=max_steps, log_fn=log_fn)
    return await loop.run(branch_hint=branch_hint)


def build_trial_record(arm: str, model: str, trial: int, case_meta: dict,
                        result: RoleLoopResult) -> dict:
    """The response-text JSON, spec §2, byte-for-byte field set."""
    return {
        "arm": arm,
        "model": model,
        "trial": trial,
        "case": case_meta.get("case_id", "sdlc_release_gate"),
        "prompts_schema_version": case_meta.get("prompts_schema_version", 2),
        "intent_sha": case_meta.get("intent_sha256"),
        "events": result.events,
        "blocked_attempts": result.blocked_attempts,
        "usage": {"prompt_tokens": result.prompt_tokens,
                  "completion_tokens": result.completion_tokens,
                  "total_tokens": result.prompt_tokens + result.completion_tokens,
                  "calls": result.calls},
        "terminated_by": result.terminated_by,
        "error": result.error,
    }


# ---------------------------------------------------------------------------
# Tracing (best-effort; spec §2 "every trial also sets span attributes ...").
# Guarded so a missing/incompatible opentelemetry install never breaks a trial.
# ---------------------------------------------------------------------------

def _set_span_attributes(attrs: dict) -> None:
    try:
        from opentelemetry import trace
        span = trace.get_current_span()
        for k, v in attrs.items():
            span.set_attribute(k, v)
    except Exception:  # noqa: BLE001 - tracing must never break a trial
        pass


def _add_span_event(name: str, attrs: dict) -> None:
    try:
        from opentelemetry import trace
        span = trace.get_current_span()
        span.add_event(name, attributes={k: str(v) for k, v in attrs.items()})
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------
# Coordinator — the single WorkflowAgent executor. Parses the request JSON
# (spec §2), builds role Agents from prompts.json[arm], drives the arm's
# loop, returns the trial-record JSON as the workflow output.
# ---------------------------------------------------------------------------

class Coordinator(af.Executor):
    def __init__(self, *, case_meta: dict, efsms: dict, payload_guards: dict,
                 choice_guards: list, prompts: dict, build_role_clients_fn):
        super().__init__(id="sdlc-release-gate-coordinator")
        self._case_meta = case_meta
        self._efsms = efsms
        self._payload_guards = payload_guards
        self._choice_guards = choice_guards
        self._prompts = prompts
        self._build_role_clients_fn = build_role_clients_fn

    @af.handler
    async def handle(self, message: list[af.Message], ctx: af.WorkflowContext[str, str]) -> None:
        text = "".join((m.text or "") for m in message)
        try:
            req = json.loads(text)
        except Exception as e:
            await ctx.yield_output(json.dumps({
                "error": f"bad request JSON: {type(e).__name__}: {e}",
                "terminated_by": "error"}))
            return

        arm = req.get("stjp_arm")
        trial = int(req.get("trial", 0))
        branch_hint = req.get("branch_hint")
        max_steps = req.get("max_steps") or self._case_meta["max_steps"]

        if arm not in ARM_CONFIG:
            await ctx.yield_output(json.dumps({
                "arm": arm, "case": self._case_meta.get("case_id"),
                "error": f"unknown stjp_arm {arm!r}; known: {CORE_ARMS}",
                "terminated_by": "error"}))
            return
        if arm not in self._prompts:
            await ctx.yield_output(json.dumps({
                "arm": arm, "case": self._case_meta.get("case_id"),
                "error": f"no prompts.json entry for arm {arm!r}",
                "terminated_by": "error"}))
            return

        client, model = self._build_role_clients_fn()

        _set_span_attributes({
            "stjp.arm": arm, "stjp.case": self._case_meta.get("case_id", ""),
            "stjp.trial": trial, "stjp.model": model, "stjp.schema": 2,
        })

        role_prompts = self._prompts[arm]
        roles = self._case_meta["roles"]
        role_agents = {r: af.Agent(client, role_prompts[r], name=r) for r in roles}
        orchestrator_agent = None
        if "__orchestrator__" in role_prompts:
            orchestrator_agent = af.Agent(client, role_prompts["__orchestrator__"],
                                          name="Orchestrator")

        def log_fn(event, **kw):
            if event == "throttled":
                _add_span_event("throttled", kw)
            elif event == "gated":
                _add_span_event("gate_rejected", kw)

        try:
            result = await run_trial_with_agents(
                arm, role_agents, orchestrator_agent, roles=roles,
                terminal_label=self._case_meta["terminal_label"],
                max_steps=max_steps, efsms=self._efsms,
                payload_guards=self._payload_guards,
                choice_guards=self._choice_guards, branch_hint=branch_hint,
                log_fn=log_fn)
        except Exception as e:
            logger.exception("trial failed: arm=%s trial=%s", arm, trial)
            result = RoleLoopResult(terminated_by="error",
                                    error=f"{type(e).__name__}: {e}")

        record = build_trial_record(arm, model, trial, self._case_meta, result)
        await ctx.yield_output(json.dumps(record))


# ---------------------------------------------------------------------------
# Role-agent chat client: STJP_CHAT_API=chat|responses (spec §7.3), ambient
# managed identity (spec §7.4 — never AzCliCredential in container code).
# ---------------------------------------------------------------------------

def _throttle_log(**kw) -> None:
    logger.warning("throttled: %s", kw)
    _add_span_event("throttled", kw)


def _build_role_clients() -> tuple[object, str]:
    """(chat_client, model_name). Default surface is 'responses'
    (FoundryChatClient — the airline_seat pattern) unless STJP_CHAT_API=chat
    (the two DeepSeek groups; DeepSeek Foundry deployments are served via
    the chat-completions-compatible surface, spec §7.3)."""
    from azure.identity import DefaultAzureCredential

    model = os.environ.get("AZURE_AI_MODEL_DEPLOYMENT_NAME", "gpt-4o")
    api = os.environ.get("STJP_CHAT_API", "responses").strip().lower()
    # Ambient managed identity in-container — NEVER AzCliCredential here
    # (that is a local-workstation-only credential; spec §7.4).
    credential = DefaultAzureCredential()

    if api == "chat":
        from agent_framework.openai import OpenAIChatCompletionClient
        inner = OpenAIChatCompletionClient(
            model=model,
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
            credential=credential,
        )
    else:
        from agent_framework.foundry import FoundryChatClient
        inner = FoundryChatClient(
            project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
            model=model,
            credential=credential,
        )
    client = RetryingChatClient(inner, log_fn=_throttle_log)
    return client, model


# ---------------------------------------------------------------------------
# Group assembly + entry point
# ---------------------------------------------------------------------------

def build_group() -> "af.WorkflowAgent":
    case_meta, efsms, payload_guards, choice_guards, prompts = load_artifacts()
    coordinator = Coordinator(
        case_meta=case_meta, efsms=efsms, payload_guards=payload_guards,
        choice_guards=choice_guards, prompts=prompts,
        build_role_clients_fn=_build_role_clients)
    workflow = af.WorkflowBuilder(
        start_executor=coordinator, output_from=[coordinator],
        name="stjp-sdlc-release-gate",
        description="STJP sdlc_release_gate 10-arm hosted group",
    ).build()
    return af.WorkflowAgent(
        workflow, name="stjp-sdlc-release-gate-group",
        description="STJP sdlc_release_gate hosted as one grouped WorkflowAgent "
                    "serving all 10 core arms "
                    "(spec: docs/reference/SDLC_HOSTED_WORKFLOW_SPEC.md).",
    )


def main():
    os.environ.setdefault("AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING", "true")
    os.environ.setdefault(
        "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "true")
    os.environ.setdefault(
        "AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED", "true")
    from dotenv import load_dotenv
    from agent_framework_foundry_hosting import ResponsesHostServer

    load_dotenv()
    group = build_group()
    ResponsesHostServer(group).run()


if __name__ == "__main__":
    main()
