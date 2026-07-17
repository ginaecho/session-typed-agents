"""FoundryRunner — drives an N-role pipeline through Azure AI Foundry Agent Service.

One runner instance per (case, scenario). The scenario is determined entirely
by the `builder` callable that produces per-role system instructions:

  - bare : build_bare_instructions  (no protocol)
  - spec : build_spec_instructions  (verbose EFSM + refinements)
  - min  : build_spec_minimal_instructions (terse SEND/RECV + guards)

Per-trial protocol:
  1. Create one Foundry thread per role (fresh state per attempt).
  2. Round-robin actor queue. For each actor:
       a. Build the actor's view of the shared session history.
       b. Post it as a 'user' message to that actor's thread.
       c. runs.create_and_process(thread, agent).
       d. Read the assistant reply, parse the JSON action.
       e. If SEND: emit a TraceEvent + extend history.
       f. If WAIT / no-send: advance actor queue; bail after too many waits.
  3. Stop on terminal label or max_steps.

Token accounting comes from run.usage on each runs.create_and_process call.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

from baselines.base import AttemptResult, BaselineRunner
from baselines._foundry_client import get_foundry_client
from baselines.instructions import agent_name

# Three small session-loop helpers (view-builder, JSON-action parser,
# assistant-text reader) live in stjp_core/foundry/session_helpers.py.
# Imported as `ex` for back-compat with prior code paths.
import stjp_core.foundry.session_helpers as ex
from stjp_core.monitor.monitor import TraceEvent

if TYPE_CHECKING:  # pragma: no cover
    from case_loader import Case
    from stjp_core.monitor.stjp_live_emitter import LiveEventEmitter


DEPLOYMENT = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")


# Retry on TRANSIENT errors: DNS resolution failures, brief network blips,
# 5xx server errors, 429 rate-limits. These are infrastructure noise, not
# experiment signal. Distinguishes "the network hiccupped" from "the agent
# made no progress" (which should still count toward consec_wait).
_TRANSIENT_ERROR_HINTS = (
    "getaddrinfo failed",      # DNS
    "Failed to resolve",       # DNS, alt phrasing
    "ServiceRequestError",
    "ConnectionError",
    "TimeoutError",
    "RemoteProtocolError",
    "ServiceResponseError",
    "Internal Server Error",   # 5xx
    "Bad Gateway",             # 502
    "Service Unavailable",     # 503
    "Gateway Timeout",         # 504
    "Too Many Requests",       # 429
    "rate limit",
)


def _is_transient(exc: BaseException) -> bool:
    s = f"{type(exc).__name__}: {exc}"
    return any(hint in s for hint in _TRANSIENT_ERROR_HINTS)


def _retry_transient(fn, *, what: str, max_attempts: int = 5,
                      base_delay: float = 1.0):
    """Call fn() with exponential-backoff retry on transient errors only.

    Backoff schedule: 1s, 2s, 4s, 8s, 16s (caps at attempts=5 -> ~30s total).
    Non-transient exceptions propagate immediately.
    """
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as e:
            if not _is_transient(e):
                raise
            if attempt == max_attempts:
                print(f"    [retry] {what}: TRANSIENT after {max_attempts} "
                      f"attempts, giving up: {type(e).__name__}: {str(e)[:120]}",
                      flush=True)
                raise
            delay = base_delay * (2 ** (attempt - 1))
            print(f"    [retry] {what}: TRANSIENT ({type(e).__name__}) "
                  f"attempt {attempt}/{max_attempts}; sleep {delay:.0f}s",
                  flush=True)
            time.sleep(delay)


class FoundryRunner(BaselineRunner):
    """Runs bare / spec / min by switching the instructions builder."""

    def __init__(self, case: "Case", scenario_key: str, scenario_name: str,
                 builder: Callable[["Case", str], str], *,
                 protocol_path_override: Optional[Path] = None,
                 goals_path_override: Optional[Path] = None,
                 gate: bool = False, schedule: str = "roundrobin",
                 hints: bool = True):
        super().__init__(case, scenario_key, scenario_name)
        self._builder = builder
        self._role_to_id: dict[str, str] = {}
        self._client = None
        self._protocol_override = protocol_path_override
        self._goals_override = goals_path_override
        # Gate mode (the "C+ enforced" arm): an in-line SessionMonitor checks
        # every parsed action BEFORE it is delivered. Off-contract sends
        # (off_protocol / unexpected_peer / refinement / choice_guard) are
        # REJECTED: not appended to history, not delivered to the receiver,
        # and the offending role is re-prompted with the monitor's verdict.
        # This converts "violation is unlikely" into "violation cannot
        # complete" — the property prompts alone can never give.
        self._gate = gate
        self._gate_efsms = None
        self._gate_refn = None
        # Schedule "efsm" (the STJP execution plane, delm_runner Plane B on
        # real agents): only roles whose projected local state has an enabled
        # SEND are polled. Deadlock-freedom of the validated global type
        # guarantees the enabled set is non-empty until termination, so idle
        # roles are never prompted — the round-robin polling cost disappears.
        # Requires gate=True: the scheduler reads the gate monitor's state,
        # which only stays in sync with reality because off-contract sends
        # are rejected before commit.
        # Schedule "lastreceiver" (the CHEAP-HEURISTIC control for the EFSM
        # scheduler): poll the receiver of the last committed message next;
        # when that yields nothing (a WAIT, a gate rejection, or no messages
        # yet), fall back to taking turns in a fixed circle (round-robin).
        # It needs NO protocol — only the observed message history — so
        # comparing min_llmvalid_gate_lastrecv vs min_llmvalid_sched
        # (identical prompt + gate) isolates what the protocol-derived
        # scheduler adds BEYOND this heuristic. See
        # docs/BENCHMARK_FAIRNESS_REVIEW.md, Problem 4: in a mostly-linear
        # pipeline "ask whoever just got a message" removes most idle polls
        # without session types; the EFSM scheduler must earn its keep on
        # branching / fan-in / concurrency, not on beating a fixed circle.
        if schedule not in ("roundrobin", "efsm", "lastreceiver"):
            raise ValueError(f"unknown schedule: {schedule!r}")
        if schedule == "efsm" and not gate:
            raise ValueError("schedule='efsm' requires gate=True (the "
                             "scheduler tracks the gate monitor's state)")
        self._schedule = schedule
        # hints=False ablates the per-turn "liveness nudge" (the injected
        # "you are at state N; the available action is SEND X to Y" line).
        # The nudge is ground-truth guidance beyond enforcement, so
        # min_llmvalid_gate vs min_llmvalid_gate_nohint separates "gate
        # blocks wrong messages" from "gate also whispers the next move".
        # Gate REJECTION feedback is kept in both — an enforcement system
        # must say what it rejected and why, or retries are blind.
        self._hints = hints

    def active_protocol_path(self) -> Path:
        return self._protocol_override or self.case.protocol_path

    def goal_set(self):
        if self._goals_override is None:
            return self.case.goal_set()
        from case_loader import load_goal_set_from_yaml
        return load_goal_set_from_yaml(self._goals_override, self.case.intent)

    # ------------------------------------------------------------------
    # Setup: register / refresh per-role Foundry agents.
    # ------------------------------------------------------------------

    def setup(self) -> None:
        self._client = get_foundry_client()
        if self._gate:
            # Project once; a FRESH SessionMonitor is built per attempt from
            # these (RoleMonitor state is mutable).
            from stjp_core.compiler.efsm_parser import get_all_efsms
            from stjp_core.compiler.refinement_checker import (
                load_refinements_for_protocol)
            self._gate_efsms = get_all_efsms(
                self.active_protocol_path(), self.case.protocol_name,
                self.case.roles)
            self._gate_refn = load_refinements_for_protocol(
                self.active_protocol_path())
        existing = {a.name: a for a in _retry_transient(
            lambda: list(self._client.list_agents()),
            what=f"{self.scenario_key}.list_agents")}
        for role in self.case.roles:
            name = agent_name(self.case, role, self.scenario_key)
            full_instr = self._builder(self.case, role)
            # Stash the FULL pre-truncation prompt so case_runner can persist
            # it under run_dir/prompts/<arm>/<role>.system.md. The 8000-char
            # truncation below is what Foundry actually sees; saving the full
            # version lets reviewers spot silent over-truncation.
            self._role_prompts[role] = full_instr
            instr = full_instr[:8000]
            if name in existing:
                a = existing[name]
                try:
                    # model= included so a deployment change in .env actually
                    # applies to reused agents (instructions-only updates
                    # silently kept the old model).
                    _retry_transient(
                        lambda: self._client.update_agent(
                            agent_id=a.id, model=DEPLOYMENT,
                            instructions=instr),
                        what=f"{self.scenario_key}.update_agent({name})")
                except Exception as e:
                    # Non-transient (or transient that exhausted retries) — warn, keep going.
                    print(f"  [warn] update {name}: {type(e).__name__}: {e}")
                self._role_to_id[role] = a.id
            else:
                agent = _retry_transient(
                    lambda: self._client.create_agent(
                        model=DEPLOYMENT, name=name,
                        description=f"AI_ST_verf {self.case.case_id} {role} "
                                    f"({self.scenario_key})",
                        instructions=instr),
                    what=f"{self.scenario_key}.create_agent({name})")
                self._role_to_id[role] = agent.id

    # ------------------------------------------------------------------
    # One attempt: drive the Foundry agents until terminal or max_steps.
    # ------------------------------------------------------------------

    def run_attempt(self, trial: int, attempt: int,
                    branch_hint: Optional[str],
                    emitter: "LiveEventEmitter") -> AttemptResult:
        assert self._client is not None, "setup() must be called first"
        client = self._client
        case = self.case

        # Fresh threads per attempt -- prior attempts' state cannot leak in.
        # Retry on transient DNS/network errors so a single blip doesn't
        # discard the whole attempt.
        role_to_thread: dict[str, str] = {}
        for role in case.roles:
            t = _retry_transient(
                lambda r=role: client.threads.create(metadata={
                    "case": case.case_id, "role": r,
                    "scenario": self.scenario_name,
                    "trial_marker": str(int(time.time())),
                }),
                what=f"{self.scenario_key}.threads.create({role})")
            role_to_thread[role] = t.id

        events: list[TraceEvent] = []
        history: list[dict] = []
        actor_queue = list(case.roles)
        consec_wait = 0
        step = 0
        goal_set = self.goal_set()
        from stjp_core.evaluation.goal_elicitor import verify_goals_against_trace

        prompt_tk = completion_tk = calls = 0

        # Gate mode: fresh monitor per attempt + pending re-prompts.
        gate_sm = None
        gate_feedback: dict[str, str] = {}
        gated = 0
        if self._gate:
            import copy as _copy
            from stjp_core.monitor.monitor import SessionMonitor
            gate_sm = SessionMonitor(self._gate_efsms, self._gate_refn)

        # lastreceiver schedule: who to ask next because they just received
        # a message. None = no fresh lead; fall back to the fixed circle.
        last_recv_hint: Optional[str] = None

        while step < case.max_steps:
            if self._schedule == "lastreceiver":
                if last_recv_hint is not None and last_recv_hint in actor_queue:
                    actor = last_recv_hint
                    actor_queue.remove(actor)
                    actor_queue.append(actor)
                else:
                    actor = actor_queue.pop(0)
                    actor_queue.append(actor)
                # One shot per lead: if this poll doesn't commit a send, the
                # next poll goes round-robin instead of re-asking the same
                # role forever (which would just burn the wait budget).
                last_recv_hint = None
            elif self._schedule == "efsm" and gate_sm is not None:
                # EFSM claim predicate: poll only roles with an enabled SEND
                # at their current projected state. Rotation among enabled
                # roles preserved via actor_queue order (fairness at
                # concurrent states, e.g. Fetcher + ExpenseAnalyst both
                # enabled at session start).
                if all(m.efsm.is_accepting(m.current_state)
                       for m in gate_sm.monitors.values()):
                    break
                enabled = [r for r in actor_queue
                           if any(t.direction == "send"
                                  for t in gate_sm.monitors[r].efsm
                                  .transitions_from(
                                      gate_sm.monitors[r].current_state))]
                if not enabled:
                    # Cannot happen for a Scribble-validated (deadlock-free)
                    # type; bail rather than spin if it somehow does.
                    break
                actor = enabled[0]
                actor_queue.remove(actor)
                actor_queue.append(actor)
            else:
                actor = actor_queue.pop(0)
                actor_queue.append(actor)

            hint = (branch_hint if step == 0 and actor == case.roles[0] else None)
            view = ex._build_view(actor, history, hint)
            if self._gate and self._hints and gate_sm is not None:
                # Liveness nudge: safety monitoring can never flag a WAIT
                # (no event, nothing to judge), so a role parked at a
                # SEND-only contract state can stall the whole session
                # without ever "violating". The projection tells us exactly
                # when that's happening — say it at the point of decision.
                mon = gate_sm.monitors.get(actor)
                if mon is not None:
                    trans = mon.efsm.transitions_from(mon.current_state)
                    sends = [t for t in trans if t.direction == "send"]
                    if trans and len(sends) == len(trans):
                        # Plain ASCII, neutral phrasing: an earlier wording
                        # ("WAIT is OFF-CONTRACT here; act now", with an
                        # em-dash that mojibaked on the wire) made gpt-5.4
                        # REFUSE outright ("I cannot assist with that
                        # request") and stalled the whole arm.
                        acts = "; ".join(f"SEND {t.label} to {t.peer}"
                                         for t in sends)
                        view = (f"Protocol status: per your role contract "
                                f"you are at state {mon.current_state}. "
                                f"The available action at this state is: "
                                f"{acts}. There is no incoming message to "
                                f"wait for at this state.\n\n") + view
            if self._gate and actor in gate_feedback:
                view = gate_feedback.pop(actor) + "\n\n" + view
            step_prompt = step_completion = 0
            try:
                _retry_transient(
                    lambda: client.messages.create(
                        thread_id=role_to_thread[actor],
                        role="user", content=view),
                    what=f"{self.scenario_key}.messages.create")
                run = _retry_transient(
                    lambda: client.runs.create_and_process(
                        thread_id=role_to_thread[actor],
                        agent_id=self._role_to_id[actor]),
                    what=f"{self.scenario_key}.runs.create_and_process")
                calls += 1
                if run.usage is not None:
                    step_prompt = run.usage.prompt_tokens or 0
                    step_completion = run.usage.completion_tokens or 0
                    prompt_tk += step_prompt
                    completion_tk += step_completion
                if str(run.status).split(".")[-1].lower() != "completed":
                    consec_wait += 1
                    if consec_wait > 2 * len(case.roles):
                        break
                    continue
                reply = _retry_transient(
                    lambda: ex._latest_assistant_text(client, role_to_thread[actor]),
                    what=f"{self.scenario_key}.latest_assistant_text")
                action = ex._parse_action(reply)
            except Exception:
                consec_wait += 1
                if consec_wait > 2 * len(case.roles):
                    break
                continue

            send_to = action.get("send_to")
            label = action.get("label", "")
            payload = str(action.get("payload", ""))
            if not send_to or label == "WAIT":
                consec_wait += 1
                if consec_wait > 2 * len(case.roles):
                    break
                continue

            # ---- GATE: contract check BEFORE delivery ------------------
            if self._gate and gate_sm is not None:
                probe_ev = TraceEvent(sender=actor, receiver=send_to,
                                      label=label, payload=payload,
                                      payload_type="", step=step + 1)
                gate_v = None
                for _role, _mon in gate_sm.monitors.items():
                    _probe = _copy.deepcopy(_mon)
                    _v = _probe.process_event(probe_ev)
                    if _v is not None:
                        gate_v = _v
                        break
                if gate_v is not None:
                    gated += 1
                    gate_feedback[actor] = (
                        "CONTRACT MONITOR — your previous action "
                        f"({label} to {send_to}) was REJECTED and NOT "
                        f"delivered.\nReason: {gate_v.message}\n"
                        f"Expected here: {gate_v.expected}\n"
                        "Choose a contract-compliant action now."
                    )
                    emitter.emit_marker(
                        "gated", trial=trial, scenario=self.scenario_name,
                        sender=actor, receiver=send_to, label=label,
                        payload=payload[:80],
                        gate_violation=gate_v.violation_type.value,
                        reason=gate_v.message[:200])
                    print(f"  [{self.scenario_name:>20s}] GATED  : "
                          f"{actor} -> {send_to} : {label}({payload[:30]})  "
                          f"[{gate_v.violation_type.value}]", flush=True)
                    consec_wait += 1
                    if consec_wait > 2 * len(case.roles):
                        break
                    continue
                # Accepted: commit the event to the live gate monitor so the
                # contract state advances with reality.
                for _mon in gate_sm.monitors.values():
                    _mon.process_event(probe_ev)

            consec_wait = 0
            step += 1
            if self._schedule == "lastreceiver":
                last_recv_hint = send_to
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
                extra={"tokens": {"prompt": step_prompt,
                                  "completion": step_completion,
                                  "total": step_prompt + step_completion}},
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
        extra = {"threads": role_to_thread, "schedule": self._schedule}
        if self._gate:
            extra["gated"] = gated
            extra["hints"] = self._hints
        return AttemptResult(events=events, usage=usage, extra=extra)
