"""hosted_campaign.py — driver for the hosted-group workflow
(docs/reference/SDLC_HOSTED_WORKFLOW_SPEC.md §4).

Invokes the deployed/local `stjp-sdlc-release-gate-group*` WorkflowAgent
once per trial x arm (spec §2 request/response contract), persists a
STANDARD run dir that `summarize_run`/`evaluate_run` from case_runner.py
consume UNCHANGED, and cross-checks the container's gate verdicts against
an independent local replay (Set A).

STATUS (S4 implementation, 2026-08-05): this is the DRIVER SKELETON deliverable
of spec §1/§4. It is structurally complete (CLI, per-wave concurrency
scaffolding, persistence matching case_runner.py's exact schema, Set-A
cross-check, retry-to-success) but has NOT been exercised beyond what
acceptance gate 3 required (a single manual `azd ai agent invoke --local`
call made directly, not through this script — see the S4 report). Per spec
§5.4 the implementer stops here for orchestrator review before any
`azd deploy` or n>1 run; --endpoint-mode hosted is therefore UNTESTED (no
agent has been deployed yet).

Usage:
    python hosted_campaign.py sdlc_release_gate --arms skills --n 1 \\
        --models mini --endpoint-mode local

    python hosted_campaign.py sdlc_release_gate --n 30 \\
        --models sol,mini,v4pro,v4flash --parallel-models

    python hosted_campaign.py sdlc_release_gate --n 30 --models mini \\
        --sequential   # dedicated timing pass, one arm at a time
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Path wiring — mirrors experiments/scripts/case_runner.py.
# ---------------------------------------------------------------------------

HERE = Path(__file__).resolve().parent
EXPERIMENTS_DIR = HERE.parent
REPO_ROOT = EXPERIMENTS_DIR.parent
STJP_CORE = REPO_ROOT / "stjp_core"
CASES_DIR = EXPERIMENTS_DIR / "cases"
FOUNDRY_AGENTS_ROOT = (REPO_ROOT / "foundry_hosted_agents" /
                       "agent-framework-agent-with-remote-mcp-tools-responses")
ARTIFACTS_DIR = FOUNDRY_AGENTS_ROOT / "agents" / "sdlc_release_gate" / "artifacts"

sys.path.insert(0, str(HERE))
sys.path.insert(0, str(EXPERIMENTS_DIR))
sys.path.insert(0, str(REPO_ROOT))
load_dotenv(STJP_CORE / ".env")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from case_loader import Case, load_goal_set_from_yaml
from case_runner import _persist_intent, MAX_ATTEMPTS  # reuse, never re-implement
from evaluate_run import VOCABULARY_ARMS  # reuse, never re-implement
from stjp_core.evaluation.goal_elicitor import verify_goals_against_trace
from stjp_core.compiler.efsm_parser import get_all_efsms
from stjp_core.compiler.refinement_checker import load_refinements_for_protocol
from stjp_core.monitor.monitor import SessionMonitor, TraceEvent
from stjp_core.monitor.stjp_live_emitter import LiveEventEmitter


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
    "maf_localvalid_sched",   # EFSM-scheduled MAF arm
                              # same day): MAF GroupChat + local contracts +
                              # EFSM-driven speaker selection, no gate. In
                              # evaluate_run.VOCABULARY_ARMS -> strict rule.
]
# RENAMED 2026-08-05 (BENCHMARK_PLAN_V3 §10.8 "Final arm naming",
# project-owner directive): bare->skills, maf_groupchat->maf_skills,
# global_decentralized->globalvalid, maf_groupchat_llmvalid->maf_globalvalid,
# min_llmvalid->localvalid, maf_groupchat_llmvalid_orch->maf_localvalid,
# min_llmvalid_gate->localvalid_gate, min_llmvalid_sched->localvalid_sched,
# plus the MAF gate and scheduler arms above. This driver has no legacy-key
# aliasing -- old run dirs (produced under the old CORE_ARMS list) are
# UNTOUCHED and still summarize/evaluate via case_runner.py's ALL_SCENARIOS
# + evaluate_run.VOCABULARY_ARMS, which DO keep the old keys resolvable.

# Parallel-model deployment (spec §1B / §7.2): one WorkflowAgent group per
# matrix model, same source dir, differing only in AZURE_AI_MODEL_DEPLOYMENT_NAME.
# "port" is the LOCAL server port each wave's `python main.py` process listens
# on (S6 local-container execution, BENCHMARK_IMPLEMENTATION_STEPS.md §4.5) --
# distinct per model so the four waves can run as four concurrent local
# processes without colliding (LocalAgentInvoker default of 8088 collides
# across waves otherwise).
MODEL_GROUPS = {
    "sol": {"group": "stjp-sdlc-release-gate-group-sol", "model": "gpt-5.6-sol",
            "concurrency": 1, "port": 8091},
    "mini": {"group": "stjp-sdlc-release-gate-group-mini", "model": "gpt-5-mini",
              "concurrency": 1, "port": 8092},
    "v4pro": {"group": "stjp-sdlc-release-gate-group-v4pro", "model": "DeepSeek-V4-Pro",
               "concurrency": 1, "port": 8093},
    # V4-Flash (cap 125) stays at concurrency=1 always (spec §7.2).
    "v4flash": {"group": "stjp-sdlc-release-gate-group-v4flash", "model": "DeepSeek-V4-Flash",
                 "concurrency": 1, "port": 8094},
}

# Driver client timeout >= 30 min (spec §7.5: a trial is one long request,
# up to max_steps x 7 roles worth of LLM calls). Raised to 60 min after the
# S5 smoke observed a legitimate (zero-throttle, actively progressing)
# gpt-5-mini retry attempt exceed 30 min of SSE silence: turns average
# ~25-30s and wait-heavy attempts can run 100+ calls, so a 30-min read
# timeout cuts off live trials. 60 min still satisfies the spec's
# ">= 30 min" bound.
DRIVER_TIMEOUT_S = 60 * 60


# ---------------------------------------------------------------------------
# Invokers — local (azd ai agent invoke --local, the SAME tool acceptance
# gate 3 validates) and hosted (untested skeleton; no agent is deployed yet).
# ---------------------------------------------------------------------------

class WorkflowBusyError(RuntimeError):
    """The single-instance WorkflowAgent is still executing a previous
    request ('Workflow is already running; concurrent runs are not allowed
    on the same instance.') -- transport-level condition, never an attempt."""


def _validated_usage(record: dict) -> tuple[int, int, int]:
    """Return trustworthy usage or reject the response as benchmark evidence."""
    if record.get("error"):
        raise RuntimeError(f"workflow returned an error: {record['error']}")
    usage = record.get("usage")
    if not isinstance(usage, dict):
        raise RuntimeError("workflow response has no usage object")
    values: dict[str, int] = {}
    for key in ("prompt_tokens", "completion_tokens", "calls"):
        value = usage.get(key)
        if isinstance(value, bool) or not isinstance(value, int):
            raise RuntimeError(
                f"workflow usage.{key} must be an integer, got {value!r}")
        values[key] = value
    if values["prompt_tokens"] <= 0:
        raise RuntimeError("workflow reported zero prompt tokens")
    if values["completion_tokens"] <= 0:
        raise RuntimeError("workflow reported zero completion tokens")
    if values["calls"] <= 0:
        raise RuntimeError("workflow reported zero model calls")
    reported_total = usage.get("total_tokens")
    computed_total = values["prompt_tokens"] + values["completion_tokens"]
    if reported_total is not None and reported_total != computed_total:
        raise RuntimeError(
            "workflow usage.total_tokens does not equal prompt + completion "
            f"({reported_total!r} != {computed_total})")
    return (values["prompt_tokens"], values["completion_tokens"],
            values["calls"])


def _unwrap_local_response(body: dict) -> dict:
    """LOCAL `--output raw` returns the Responses-API ENVELOPE
    (object='response', output=[...]) -- the trial record (spec §2) is the
    agent's final text nested inside the output items' content parts.

    VERIFIED live 2026-08-05 (S6 first launch): parsing the outermost {...}
    of the raw body yields the envelope, whose key set shadows the trial
    record with empty defaults (events -> missing, usage -> missing,
    terminated_by -> None), which silently produced all-zero attempt rows
    (0 events / 0 calls / 0 tokens after a real 848s trial). Unwrap here;
    pass through anything that already looks like a bare trial record."""
    if "output" not in body and body.get("object") != "response":
        return body  # already a bare trial/error record
    if body.get("status") == "failed":
        msg = ((body.get("error") or {}).get("message")) or json.dumps(body)[:400]
        if "already running" in msg:
            raise WorkflowBusyError(msg)
        raise RuntimeError(f"local agent returned failed response: {msg}")
    texts: list[str] = []
    for item in body.get("output", []):
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    texts.append(part["text"])
        elif isinstance(item.get("text"), str):
            texts.append(item["text"])
    joined = "\n".join(texts)
    if not joined.strip():
        raise RuntimeError(
            "local response envelope contained no output text (status="
            f"{body.get('status')!r}); cannot recover trial record")
    return _extract_json_body(joined)


class LocalAgentInvoker:
    """Invokes a locally-running `azd ai agent run` server via
    `azd ai agent invoke --local` (spec §4 "local: azd ai agent run server").
    Requires the target group's server to already be running (started
    separately, e.g. `azd ai agent run stjp-sdlc-release-gate-group-mini
    --no-client`).

    Busy handling: the local WorkflowAgent executes ONE request at a time;
    a request sent while another is in flight fails INSTANTLY with
    'Workflow is already running'. That is a transport-level wait (same
    philosophy as 429s, spec §7.1) -- poll-retry up to ~30 min; a busy
    retry is never counted as an attempt, a call, or a WAIT."""

    BUSY_POLL_S = 20
    BUSY_MAX_TRIES = 90  # 90 x 20s = 30 min, matching DRIVER_TIMEOUT_S

    def __init__(self, group_name: str, *, port: int = 8088,
                 cwd: Path = FOUNDRY_AGENTS_ROOT, timeout_s: int = DRIVER_TIMEOUT_S):
        self.group_name = group_name
        self.port = port
        self.cwd = cwd
        self.timeout_s = timeout_s

    def _invoke_once(self, request: dict) -> dict:
        with tempfile.NamedTemporaryFile(
                "w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(request, f)
            req_path = f.name
        try:
            proc = subprocess.run(
                ["azd", "ai", "agent", "invoke", self.group_name, "--local",
                 "--new-session", "-f", req_path, "--port", str(self.port),
                 "--timeout", str(self.timeout_s), "--no-prompt",
                 "--output", "raw"],
                cwd=str(self.cwd), capture_output=True, text=True,
                timeout=self.timeout_s + 30)
        finally:
            try:
                Path(req_path).unlink()
            except OSError:
                pass
        if proc.returncode != 0:
            raise RuntimeError(
                f"azd ai agent invoke --local failed (exit {proc.returncode}): "
                f"{proc.stderr[-2000:]}")
        return _extract_json_body(proc.stdout)

    def invoke(self, request: dict) -> dict:
        for busy_try in range(self.BUSY_MAX_TRIES):
            body = self._invoke_once(request)
            try:
                return _unwrap_local_response(body)
            except WorkflowBusyError:
                if busy_try == self.BUSY_MAX_TRIES - 1:
                    raise
                print(f"[hosted_campaign] {self.group_name}: workflow busy, "
                      f"waiting {self.BUSY_POLL_S}s "
                      f"({busy_try + 1}/{self.BUSY_MAX_TRIES})", flush=True)
                time.sleep(self.BUSY_POLL_S)
        raise RuntimeError("unreachable")


class HostedAgentInvoker:
    """Invokes a DEPLOYED agent's responses endpoint DIRECTLY (spec §4
    "hosted: the project's responses endpoint for the deployed agent"):

        POST {FOUNDRY_PROJECT_ENDPOINT}/agents/{group}/endpoint/protocols/
             openai/responses?api-version=v1

    with a bearer token fetched via `az account get-access-token --scope
    https://ai.azure.com/.default` (cached until <5 min to expiry).

    WHY not `azd ai agent invoke` (S5 smoke finding, 2026-08-05): azd's
    auth chain (agents extension -> nested `azd auth token` -> az) applies
    Go azidentity's ~10s subprocess timeout to az, and az on this
    workstation needs ~7s even for a CACHE HIT -- under any load the chain
    breaks with "failed to get auth token: AzureDeveloperCLICredential:
    exit status 1" (observed killing two mini smoke waves). Fetching the
    token ourselves under a generous timeout is reliable; the request
    body/response format was verified against the deployed mini group
    (probe trials: HTTP 200 on both stream=false JSON envelope and
    stream=true SSE).

    The request STREAMS (stream=true + SSE parse) to mirror the one path
    already proven to survive a 543.8s bare trial end-to-end (azd's own
    client streams); the trial-record JSON is taken from the terminal
    `response.completed` event (fallback `response.output_text.done`).
    `last_trace_id` comes from the X-Request-Id response header, which
    equals the Application Insights operation_Id (verified: the probe's
    request id appears as an operation_Id row under the group's
    cloud_RoleName)."""

    def __init__(self, group_name: str, *, project_endpoint: Optional[str] = None,
                 timeout_s: int = DRIVER_TIMEOUT_S):
        import os
        self.group_name = group_name
        self.project_endpoint = (project_endpoint or
                                 os.environ["FOUNDRY_PROJECT_ENDPOINT"]).rstrip("/")
        self.timeout_s = timeout_s
        self.last_trace_id: Optional[str] = None

    _az_token_cache: Optional[tuple] = None  # (token, epoch_expiry), class-level

    @classmethod
    def _bearer_token(cls) -> str:
        import shutil
        if cls._az_token_cache and cls._az_token_cache[1] - time.time() > 300:
            return cls._az_token_cache[0]
        az = shutil.which("az")  # az is az.cmd on Windows; resolve explicitly
        if not az:
            raise RuntimeError("az CLI not found on PATH")
        proc = subprocess.run(
            [az, "account", "get-access-token",
             "--scope", "https://ai.azure.com/.default", "-o", "json"],
            capture_output=True, text=True, timeout=120)
        if proc.returncode != 0:
            raise RuntimeError(
                f"az account get-access-token failed (exit {proc.returncode}): "
                f"{proc.stderr[-1000:]}")
        tok = json.loads(proc.stdout)
        expiry = float(tok.get("expires_on") or (time.time() + 3000))
        cls._az_token_cache = (tok["accessToken"], expiry)
        return tok["accessToken"]

    def invoke(self, request: dict) -> dict:
        import requests

        url = (f"{self.project_endpoint}/agents/{self.group_name}"
               f"/endpoint/protocols/openai/responses?api-version=v1")
        body = {"input": json.dumps(request), "stream": True}
        last_exc: Optional[BaseException] = None
        # Transport-level retries ONLY (connection drops / 401 token expiry /
        # gateway 5xx). Like a 429, a transport retry is noise -- it never
        # counts as an LLM call, an attempt, or a WAIT (spec §7.1 analogue).
        # A READ TIMEOUT is deliberately NOT retried: it means the trial is
        # still running (or hung) server-side after DRIVER_TIMEOUT_S of SSE
        # silence -- re-POSTing would start a DUPLICATE trial while the first
        # may still be consuming quota (observed on the mini smoke). It
        # propagates as a hard per-trial failure and gateway-probe signal.
        for attempt in range(1, 4):
            try:
                return self._post_and_parse(requests, url, body)
            except requests.exceptions.ConnectionError as e:
                if "read timed out" in str(e).lower():
                    raise
                last_exc = e
            except requests.exceptions.ReadTimeout:
                raise
            except requests.exceptions.Timeout as e:
                last_exc = e  # connect timeout only -- no request started
            except requests.exceptions.HTTPError as e:
                status = getattr(e.response, "status_code", None)
                if status == 401:
                    HostedAgentInvoker._az_token_cache = None  # force refresh
                elif status not in (408, 429, 500, 502, 503, 504):
                    raise
                last_exc = e
            print(f"[hosted_campaign] transient transport failure for "
                  f"{self.group_name} (try {attempt}/3): "
                  f"{type(last_exc).__name__}: {str(last_exc)[:200]}; "
                  f"retrying in 15s", flush=True)
            time.sleep(15)
        assert last_exc is not None
        raise last_exc

    def _post_and_parse(self, requests, url: str, body: dict) -> dict:
        headers = {"Authorization": f"Bearer {self._bearer_token()}",
                   "Content-Type": "application/json",
                   "Accept": "text/event-stream"}
        final_text: Optional[str] = None
        with requests.post(url, headers=headers, json=body, stream=True,
                           timeout=(30, self.timeout_s)) as resp:
            resp.raise_for_status()
            xrid = resp.headers.get("X-Request-Id", "")
            self.last_trace_id = xrid.split(",")[0].strip() or None
            for raw_line in resp.iter_lines(decode_unicode=True):
                if not raw_line or not raw_line.startswith("data:"):
                    continue
                try:
                    evt = json.loads(raw_line[len("data:"):].strip())
                except (ValueError, TypeError):
                    continue
                etype = evt.get("type")
                if etype == "response.output_text.done":
                    final_text = evt.get("text") or final_text
                elif etype == "response.completed":
                    for item in (evt.get("response") or {}).get("output") or []:
                        if item.get("type") != "message":
                            continue
                        for part in item.get("content") or []:
                            if (part.get("type") == "output_text"
                                    and part.get("text")):
                                final_text = part["text"]
                elif etype in ("response.failed", "response.incomplete", "error"):
                    raise RuntimeError(
                        f"hosted responses stream reported {etype}: "
                        f"{json.dumps(evt)[:2000]}")
        if final_text is None:
            raise ValueError(
                f"no output_text in hosted responses stream for {self.group_name}")
        return _extract_json_body(final_text)


def _extract_json_body(text: str) -> dict:
    """The trial-record JSON is the ONLY JSON object in the response body
    (spec §2); locate the outermost {...} span, tolerating CLI banner/log
    lines around it (azd prints a "Session:"/"Invocation:" summary unless
    --output raw is used, and --output raw may still include HTTP status/
    header lines above the body)."""
    s = text.find("{")
    e = text.rfind("}")
    if s < 0 or e < 0:
        raise ValueError(f"no JSON object found in response:\n{text[:2000]}")
    return json.loads(text[s:e + 1])


# ---------------------------------------------------------------------------
# Set A cross-check: replay the container's delivered events through the
# LOCAL stjp_core SessionMonitor against llm_drafts/valid (spec §4).
# ---------------------------------------------------------------------------

def build_local_monitor(case: Case) -> tuple[SessionMonitor, Path]:
    llmvalid_path = case.case_dir / "protocols" / "llm_drafts" / "valid" / "v1.scr"
    efsms = get_all_efsms(llmvalid_path, case.protocol_name, case.roles)
    refinements = load_refinements_for_protocol(llmvalid_path)
    return SessionMonitor(efsms, refinements), llmvalid_path


def cross_check_verdicts(case: Case, trial_record: dict) -> list[str]:
    """Independent re-derivation: walk the container's delivered events
    through a FRESH local SessionMonitor; a mismatch between "container said
    delivered/rejected" and "local monitor says conformant/violation" for
    any GATE arm (localvalid_gate / maf_localvalid_gate / localvalid_sched)
    actually reject) is a HARD ERROR per spec §4. For non-gate arms the
    container never rejects, so this only re-derives the SAME conformance
    verdict a case_runner run would have recorded for cross-reference; it is
    not itself an error signal there."""
    mismatches: list[str] = []
    sm, _ = build_local_monitor(case)
    for ev in trial_record.get("events", []):
        tev = TraceEvent(sender=ev["sender"], receiver=ev["receiver"],
                         label=ev["label"], payload=ev.get("payload", ""),
                         step=ev["step"])
        local_violation = None
        for mon in sm.monitors.values():
            v = mon.process_event(tev)
            if v is not None:
                local_violation = v
                break
        container_verdict = ev.get("gate_verdict", "delivered")
        arm = trial_record.get("arm")
        # RENAMED 2026-08-05 (BENCHMARK_PLAN_V3 §10.8): these were
        # min_llmvalid_gate / min_llmvalid_sched. Getting this set wrong is
        # not cosmetic -- it silently disables the hard-error cross-check
        # for the gate arms.
        if arm in ("localvalid_gate", "maf_localvalid_gate",
                   "localvalid_sched"):
            # A DELIVERED event under gate enforcement must be locally
            # conformant -- if the container delivered it, the local replay
            # must not find a violation either (both walk the SAME llm-valid
            # EFSM from the SAME artifacts).
            if container_verdict == "delivered" and local_violation is not None:
                mismatches.append(
                    f"step {ev['step']}: container delivered "
                    f"{ev['sender']}->{ev['receiver']}:{ev['label']} but "
                    f"local replay flags {local_violation.violation_type.value}: "
                    f"{local_violation.message}")
    for b in trial_record.get("blocked_attempts", []):
        # A rejected send must ALSO be a violation locally (probed, not
        # committed -- so replay it against a COPY to avoid consuming state
        # the real trace never actually advanced past).
        import copy
        probe_sm, _ = build_local_monitor(case)
        # Fast-forward the probe monitor through every delivered event before
        # this blocked attempt's step so its state matches the container's
        # state at rejection time.
        for ev in trial_record.get("events", []):
            if ev["step"] >= b["step"]:
                break
            tev = TraceEvent(sender=ev["sender"], receiver=ev["receiver"],
                             label=ev["label"], payload=ev.get("payload", ""),
                             step=ev["step"])
            for mon in probe_sm.monitors.values():
                mon.process_event(tev)
        probe_ev = TraceEvent(sender=b["sender"], receiver=b["receiver"],
                              label=b["label"], payload=b.get("payload", ""),
                              step=b["step"])
        found_violation = False
        for mon in probe_sm.monitors.values():
            v = copy.deepcopy(mon).process_event(probe_ev)
            if v is not None:
                found_violation = True
                break
        if not found_violation:
            mismatches.append(
                f"step {b['step']}: container REJECTED "
                f"{b['sender']}->{b['receiver']}:{b['label']} but local "
                f"replay finds no violation for it")
    return mismatches


# ---------------------------------------------------------------------------
# Per-trial pipeline: invoke -> parse -> cross-check -> persist
# ---------------------------------------------------------------------------

def run_one_trial(case: Case, invoker, arm: str, trial: int,
                   branch_hint: Optional[str], max_steps: Optional[int],
                   emitter: LiveEventEmitter, goal_set, strict_labels: bool,
                   success_rule: str, model_key: Optional[str] = None) -> dict:
    """Retry-to-success (<=MAX_ATTEMPTS), SAME per-arm success rule as
    case_runner.py (evaluate_run.VOCABULARY_ARMS -> strict vs role_pair).

    ``model_key`` (sol/mini/v4pro/v4flash) is stamped onto the trial_start /
    attempt_end / trial_end markers so a --parallel-models run — where all
    four model waves append to the SAME events_<arm>.jsonl — stays cleanly
    attributable per (arm, model) when the run is summarized. Without it the
    interleaved markers cannot be split back out by model."""
    cum_prompt = cum_completion = cum_calls = 0
    succeeded = False
    attempts_used = 0
    final_record: dict = {}

    emitter.emit_marker("trial_start", trial=trial, branch=branch_hint,
                        scenario=arm, model=model_key)

    for attempt in range(1, MAX_ATTEMPTS + 1):
        attempts_used = attempt
        emitter.reset_monitors()
        emitter.emit_marker("attempt_start", trial=trial, attempt=attempt,
                            branch=branch_hint, scenario=arm)

        request = {"stjp_arm": arm, "trial": trial, "branch_hint": branch_hint,
                   "max_steps": max_steps}
        t0 = time.time()
        record = invoker.invoke(request)
        wall_s = time.time() - t0

        mismatches = cross_check_verdicts(case, record)
        if mismatches:
            raise RuntimeError(
                f"Set-A cross-check FAILED for arm={arm} trial={trial} "
                f"attempt={attempt}:\n  " + "\n  ".join(mismatches))

        events = [TraceEvent(sender=e["sender"], receiver=e["receiver"],
                             label=e["label"], payload=e.get("payload", ""),
                             step=e["step"]) for e in record.get("events", [])]

        strict_results = verify_goals_against_trace(goal_set, events, branch_hint)
        goal_results = (strict_results if strict_labels else
                        verify_goals_against_trace(goal_set, events, branch_hint,
                                                   match_labels=False))
        all_goals_pass = bool(goal_results) and all(ok for ok, _ in goal_results.values())
        n_goals_ok = sum(1 for ok, _ in goal_results.values() if ok)
        n_goals_total = len(goal_results)
        n_goals_ok_strict = sum(1 for ok, _ in strict_results.values() if ok)

        try:
            prompt_tk, completion_tk, calls = _validated_usage(record)
        except RuntimeError as exc:
            emitter.emit_marker(
                "attempt_end", trial=trial, attempt=attempt, events=0,
                model=model_key, evidence_valid=False,
                invalid_reason=str(exc),
                tokens={"prompt_tokens": 0, "completion_tokens": 0,
                        "total_tokens": 0, "calls": 0})
            raise RuntimeError(
                f"INVALID BENCHMARK EVIDENCE arm={arm} model={model_key} "
                f"trial={trial} attempt={attempt}: {exc}") from exc
        cum_prompt += prompt_tk
        cum_completion += completion_tk
        cum_calls += calls

        # Re-emit each delivered event through the shared LiveEventEmitter
        # so events_<arm>.jsonl gets the EXACT case_runner.py schema
        # (ts/step/sender/receiver/label/payload/trial/scenario/goals_pass/
        # goals_total/violation) -- this IS the independent local
        # verdict case_runner-produced run dirs always carry.
        running_events: list[TraceEvent] = []
        for ev in events:
            running_events.append(ev)
            n_ok = sum(1 for ok, _ in verify_goals_against_trace(
                goal_set, running_events).values() if ok)
            emitter.emit(ev, trial=trial, scenario=arm, goals_pass=n_ok,
                         goals_total=len(goal_set.goals))

        emitter.emit_marker(
            "attempt_end", trial=trial, attempt=attempt, events=len(events),
            model=model_key,
            goals_pass=n_goals_ok, goals_total=n_goals_total,
            goals_pass_strict=n_goals_ok_strict, success_rule=success_rule,
            all_goals_pass=all_goals_pass,
            tokens={"prompt_tokens": prompt_tk, "completion_tokens": completion_tk,
                    "total_tokens": prompt_tk + completion_tk, "calls": calls},
            extra={"terminated_by": record.get("terminated_by"),
                   "model": record.get("model"),
                   "blocked_attempts": len(record.get("blocked_attempts", [])),
                   "wall_seconds": round(wall_s, 1)})

        final_record = record
        if all_goals_pass:
            succeeded = True
            break

    cum_total = cum_prompt + cum_completion
    emitter.emit_marker("trial_end", trial=trial, succeeded=succeeded,
                        model=model_key,
                        success_rule=success_rule, attempts=attempts_used,
                        events=len(final_record.get("events", [])),
                        tokens={"prompt_tokens": cum_prompt,
                                "completion_tokens": cum_completion,
                                "total_tokens": cum_total, "calls": cum_calls})
    return {"trial": trial, "branch": branch_hint, "succeeded": succeeded,
            "attempts": attempts_used, "record": final_record}


# ---------------------------------------------------------------------------
# Persistence: prompts/<arm>/<Role>.system.md, intent.md, hosted_meta.json
# ---------------------------------------------------------------------------

def persist_prompts_from_artifacts(run_dir: Path, arm: str, prompts: dict) -> None:
    import hashlib
    out_dir = run_dir / "prompts" / arm
    out_dir.mkdir(parents=True, exist_ok=True)
    role_map = prompts.get(arm, {})
    index_roles = []
    for role, text in role_map.items():
        safe = role.replace("/", "_")
        (out_dir / f"{safe}.system.md").write_text(text, encoding="utf-8")
        index_roles.append({"role": role, "chars": len(text),
                            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()})
    (out_dir / "index.json").write_text(json.dumps({
        "arm_key": arm, "prompts_schema_version": 2,
        "install_truncates": False, "install_limit": None,
        "roles": index_roles}, indent=2), encoding="utf-8")


def write_hosted_meta(run_dir: Path, *, group_name: str, model: str,
                      endpoint_mode: str, wave: str, span_ids_sample: list) -> None:
    # Per-wave filename (hosted_meta_<wave>.json) so the four --parallel-models
    # waves don't clobber each other's meta (a single hosted_meta.json would
    # keep only whichever wave finished last). A combined hosted_meta.json is
    # still written for backward-compat readers, last-wave-wins as before.
    payload = {
        "group_name": group_name, "model": model, "endpoint_mode": endpoint_mode,
        "wave": wave, "span_ids_sample": span_ids_sample,
        "artifacts_dir": str(ARTIFACTS_DIR),
        "written_at": datetime.now().isoformat(),
    }
    (run_dir / f"hosted_meta_{wave}.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8")
    (run_dir / "hosted_meta.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Wave driver (spec §7.2: 1 trial in flight per group; arms run sequentially
# inside a wave). Async so --parallel-models can run the 4 waves concurrently.
# ---------------------------------------------------------------------------

async def run_wave(case: Case, model_key: str, arms: list[str], n: int, *,
                   endpoint_mode: str, run_dir: Path, prompts: dict) -> None:
    cfg = MODEL_GROUPS[model_key]
    group_name, model, concurrency = cfg["group"], cfg["model"], cfg["concurrency"]

    if endpoint_mode == "local":
        invoker = LocalAgentInvoker(group_name, port=cfg["port"])
    else:
        # HostedAgentInvoker resolves the deployed agent's endpoint + auth
        # itself via `azd ai agent invoke <group_name>` (no --local) -- no
        # separate `azd ai agent show` round-trip needed (see class docstring).
        invoker = HostedAgentInvoker(group_name)

    sem = asyncio.Semaphore(concurrency)
    span_ids_sample: list = []

    async def _one(arm: str, trial: int, branch_hint: Optional[str]):
        async with sem:
            efsm_json_path = ARTIFACTS_DIR / "efsm.json"  # sanity: artifacts exist
            if not efsm_json_path.exists():
                raise FileNotFoundError(
                    f"missing {efsm_json_path} -- run build_hosted_artifacts.py first")
            events_path = run_dir / f"events_{arm}.jsonl"
            # One emitter per (arm) so events_<arm>.jsonl matches case_runner's
            # one-file-per-arm layout even though trials for different arms in
            # the SAME wave interleave under asyncio.
            llmvalid_path = case.case_dir / "protocols" / "llm_drafts" / "valid" / "v1.scr"
            efsms = get_all_efsms(llmvalid_path, case.protocol_name, case.roles)
            refinements = load_refinements_for_protocol(llmvalid_path)
            # run_campaign creates each arm file once. Parallel model waves
            # must append without truncating evidence written by another wave.
            emitter = LiveEventEmitter(
                events_path, efsms, refinements, truncate=False)

            strict_labels = arm in VOCABULARY_ARMS
            success_rule = "strict" if strict_labels else "role_pair"
            goals_path = case.case_dir / "protocols" / "llm_drafts" / "valid" / "goals.yaml"
            goal_set = (load_goal_set_from_yaml(goals_path, case.intent)
                       if goals_path.exists() else case.goal_set())

            try:
                result = await asyncio.to_thread(
                    run_one_trial, case, invoker, arm, trial, branch_hint,
                    case.max_steps, emitter, goal_set, strict_labels, success_rule,
                    model_key)
            finally:
                emitter.close()
            return result

    for arm in arms:  # arms run SEQUENTIALLY inside a wave (spec §7.2)
        persist_prompts_from_artifacts(run_dir, arm, prompts)
        for trial in range(n):
            branch_hint = (case.branch_hints[trial % len(case.branch_hints)]
                          if case.branch_hints else None)
            await _one(arm, trial, branch_hint)
            trace_id = getattr(invoker, "last_trace_id", None)
            if trace_id:
                span_ids_sample.append(
                    {"arm": arm, "trial": trial, "trace_id": trace_id})

    write_hosted_meta(run_dir, group_name=group_name, model=model,
                      endpoint_mode=endpoint_mode, wave=model_key,
                      span_ids_sample=span_ids_sample)


async def run_campaign(case_id: str, arms: list[str], n: int, models: list[str], *,
                       endpoint_mode: str, parallel_models: bool,
                       dir_tag: Optional[str] = None) -> Path:
    case = Case.load(CASES_DIR / case_id, intent_scale="doc")
    prompts = json.loads((ARTIFACTS_DIR / "prompts.json").read_text(encoding="utf-8"))

    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    model_tag = "-".join(models)
    tag = f"-{dir_tag}" if dir_tag else ""
    run_dir = case.runs_dir / f"{ts}-hosted{tag}-{model_tag}-n{n}"
    run_dir.mkdir(parents=True, exist_ok=True)
    for arm in arms:
        (run_dir / f"events_{arm}.jsonl").write_text("", encoding="utf-8")
    _persist_intent(case, run_dir)  # reuse case_runner._persist_intent verbatim

    print(f"[hosted_campaign] case={case.case_id} arms={arms} n={n} "
          f"models={models} endpoint_mode={endpoint_mode} "
          f"parallel_models={parallel_models}")
    print(f"[hosted_campaign] run_dir={run_dir}")

    if parallel_models:
        await asyncio.gather(*[
            run_wave(case, m, arms, n, endpoint_mode=endpoint_mode, run_dir=run_dir,
                    prompts=prompts)
            for m in models
        ])
    else:
        for m in models:  # --sequential: one model, one arm at a time
            await run_wave(case, m, arms, n, endpoint_mode=endpoint_mode,
                          run_dir=run_dir, prompts=prompts)

    return run_dir


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("case_id", nargs="?", default="skills_safety/sdlc_release_gate")
    p.add_argument("--arms", default=",".join(CORE_ARMS),
                  help="comma-separated arm keys (default: all 10 core arms)")
    p.add_argument("--n", type=int, default=1, help="trials per arm per model")
    p.add_argument("--models", default="mini",
                  help="comma-separated model keys: sol,mini,v4pro,v4flash")
    p.add_argument("--endpoint-mode", choices=["local", "hosted"], default="local")
    p.add_argument("--parallel-models", action="store_true",
                  help="run all requested model waves concurrently "
                       "(indicative wall-clock only)")
    p.add_argument("--sequential", action="store_true",
                  help="dedicated timing pass: models AND arms run one at a "
                       "time (uncontended wall-clock)")
    p.add_argument("--dir-tag", default=None,
                  help="optional tag inserted into the run dir name, e.g. "
                       "'smoke' -> <ts>-hosted-smoke-<model>-n<n> (evidence "
                       "isolation: smoke dirs must never look like campaign "
                       "data, spec S5)")
    args = p.parse_args()

    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    unknown = [a for a in arms if a not in CORE_ARMS]
    if unknown:
        print(f"unknown arm(s): {unknown} (known: {CORE_ARMS})")
        sys.exit(2)
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    unknown_m = [m for m in models if m not in MODEL_GROUPS]
    if unknown_m:
        print(f"unknown model(s): {unknown_m} (known: {list(MODEL_GROUPS)})")
        sys.exit(2)
    if args.parallel_models and args.sequential:
        print("--parallel-models and --sequential are mutually exclusive")
        sys.exit(2)

    run_dir = asyncio.run(run_campaign(
        args.case_id, arms, args.n, models,
        endpoint_mode=args.endpoint_mode,
        parallel_models=args.parallel_models and not args.sequential,
        dir_tag=args.dir_tag))
    print(f"[hosted_campaign] DONE -> {run_dir}")


if __name__ == "__main__":
    main()
