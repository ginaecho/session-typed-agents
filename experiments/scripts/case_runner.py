"""case_runner.py — case-agnostic multi-baseline experiment driver.

Drives N scenarios in parallel for any case in experiments/cases/<case_id>/.
Scenarios are registered in experiments/baselines/registry.py; the default
set is bare / maf_native / maf_foundry (WITHOUT-side) and spec / min
(WITH-side). Outputs land in experiments/cases/<case_id>/runs/<timestamp>-n<N>-dual/.

Usage:
    python scripts/case_runner.py <case_id> [n_trials]
    python scripts/case_runner.py code_review 1
    python scripts/case_runner.py --all 10
"""
from __future__ import annotations

import json
import os
import random
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


# ---------------------------------------------------------------------------
# Path wiring — pull in everything from stjp_core/ as the library layer, plus
# experiments/baselines/ for the framework runners.
# ---------------------------------------------------------------------------

HERE = Path(__file__).resolve().parent
EXPERIMENTS_DIR = HERE.parent
TESTING_IDEAS = EXPERIMENTS_DIR.parent
STJP_CORE = TESTING_IDEAS / "stjp_core"
CASES_DIR = EXPERIMENTS_DIR / "cases"

sys.path.insert(0, str(HERE))             # case_loader
sys.path.insert(0, str(EXPERIMENTS_DIR))  # baselines package
sys.path.insert(0, str(TESTING_IDEAS))        # stjp_core library modules
load_dotenv(STJP_CORE / ".env")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Foundry tracing → Application Insights (so Foundry-side runs are portal-visible).
# MAF-native runs bypass Foundry by design; we document that in baselines/maf_native.py.
from stjp_core.foundry.foundry_tracing import enable_foundry_tracing
enable_foundry_tracing(service_name="stjp-case-runner")

from stjp_core.compiler.efsm_parser import get_all_efsms
from stjp_core.compiler.refinement_checker import load_refinements_for_protocol
from stjp_core.evaluation.goal_elicitor import verify_goals_against_trace
from stjp_core.monitor.stjp_live_emitter import LiveEventEmitter

from case_loader import Case
from baselines import SCENARIOS, make_runner
from baselines.base import BaselineRunner

import evaluate_run  # Set B (goal-achievement) metrics, run at end of each run
from evaluate_run import VOCABULARY_ARMS  # arms whose prompt contained the protocol's message labels
from stats import wilson  # 95% confidence interval for a success proportion


# Retry-to-success: a trial keeps re-running with fresh threads until all
# goals pass, or MAX_ATTEMPTS is exhausted. Final per-trial outcome captured
# in the trial_end marker.
MAX_ATTEMPTS = 3

# Dual-demo live mirror: maps an arm key -> a fixed filename in stjp_core/
# that stjp_comparison.html polls. Empty for a normal run; the dual-demo
# driver (stjp_core/apps/stjp_dual_demo.py) sets it to
#   {armA: "events_left.jsonl", armB: "events_right.jsonl"}
# so the two chosen arms stream into the live side-by-side viewer.
DUAL_MIRROR: dict[str, str] = {}


# Foundry truncates agent instructions at 8000 chars on install (see
# FoundryRunner.setup / experiment_via_agent_service.py). MAF runners pass
# instructions through unchanged. We record both lengths in index.json so a
# reviewer can spot prompts that were silently clipped on the Foundry path.
PROMPT_INSTALL_LIMIT_FOUNDRY = 8000

# Per-arm install behaviour: Foundry-stack arms truncate at the limit above;
# MAF arms install the full string. Used only for the `truncated` flag in
# prompts/<arm>/index.json — does not affect runtime behaviour.
_FOUNDRY_INSTALL_KEYS = {"bare", "spec_llmvalid", "min_llmvalid", "spec_llmvalid_gate", "min_llmvalid_gate", "min_llmvalid_gate_nohint", "min_llmvalid_gate_lastrecv", "min_llmvalid_sched", "global_decentralized", "unchecked_skills"}


def _persist_prompts(runner: "BaselineRunner", run_dir: Path) -> None:
    """Write each role's full system prompt under run_dir/prompts/<arm>/.

    Required by the persistence policy in experiments/CLAUDE.md: every WITH-arm
    and global-text arm ships a freshly built prompt per role per run; without
    this artefact, claims about projection / refinement / intent text cannot
    be independently checked from the run dir alone.

    Layout:
        run_dir/
          prompts/
            <arm_key>/
              <Role>.system.md      <-- full pre-install string
              index.json            <-- per-role SHA256 + char count + truncated flag

    Subclasses that do not populate ``self._role_prompts`` produce an empty
    arm entry — we still write an index.json with an explicit empty list and
    a warning marker so the gap is visible in the artefact tree rather than
    silently absent.
    """
    import hashlib

    arm_key = runner.scenario_key
    out_dir = run_dir / "prompts" / arm_key
    out_dir.mkdir(parents=True, exist_ok=True)

    prompts = runner.prompts()  # {role_or_special: full prompt}
    if not prompts:
        # Make the absence visible — easier to spot than a missing folder.
        (out_dir / "index.json").write_text(
            json.dumps({"warning": "no prompts captured for this arm",
                        "arm_key": arm_key,
                        "scenario_name": runner.scenario_name,
                        "roles": []}, indent=2),
            encoding="utf-8")
        print(f"  [{runner.scenario_name}] WARNING: no prompts captured "
              f"(runner did not populate _role_prompts)", flush=True)
        return

    install_truncates = arm_key in _FOUNDRY_INSTALL_KEYS
    limit = PROMPT_INSTALL_LIMIT_FOUNDRY if install_truncates else None

    index_roles = []
    for role, text in prompts.items():
        safe = role.replace("/", "_")
        (out_dir / f"{safe}.system.md").write_text(text, encoding="utf-8")
        sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
        chars = len(text)
        truncated = bool(limit and chars > limit)
        index_roles.append({
            "role": role,
            "chars": chars,
            "sha256": sha,
            "install_limit": limit,
            "truncated_on_install": truncated,
        })

    (out_dir / "index.json").write_text(
        json.dumps({"arm_key": arm_key,
                    "scenario_name": runner.scenario_name,
                    "install_truncates": install_truncates,
                    "install_limit": limit,
                    "roles": index_roles}, indent=2),
        encoding="utf-8")


# ---------------------------------------------------------------------------
# Per-scenario driver (framework-agnostic; delegates to the BaselineRunner)
# ---------------------------------------------------------------------------

def run_scenario(runner: BaselineRunner, n_trials: int, run_dir: Path) -> dict:
    """Run n_trials for one scenario, with retry-to-success per trial.

    Each trial keeps retrying (fresh runner state per attempt) until all
    goal predicates pass, or MAX_ATTEMPTS is reached. The trial_end marker
    captures: succeeded, attempts_used, cumulative tokens across attempts.
    """
    case = runner.case
    key, name = runner.scenario_key, runner.scenario_name
    fname = f"events_{key}.jsonl"
    events_path = run_dir / fname
    mirror_path = STJP_CORE / DUAL_MIRROR[key] if key in DUAL_MIRROR else None

    # Per-arm protocol + goals: LLM-drafted arms point at LLM-valid/unsafe
    # .scr + their re-anchored goals.yaml. Defaults fall back to case-level.
    active_protocol = runner.active_protocol_path()
    goal_set = runner.goal_set()

    # Fair success rule. Goals are anchored to exact (sender, receiver,
    # label) message triples taken from the protocol. Arms that were shown
    # the protocol (VOCABULARY_ARMS) are judged strictly against those
    # triples. Arms that were NOT shown the protocol (bare, maf_*) never saw
    # the labels, so for them a goal passes if the right sender delivered a
    # predicate-satisfying payload to the right receiver under ANY label.
    # Example of why: the bare prompt says "the tax verifier must approve
    # the audit" but the strict rule demands the exact label
    # `RevenueAuditApproval` — a word the bare agents were never given.
    # Judging them on it measures vocabulary, not coordination (this is the
    # same reasoning evaluate_run.py already applies to its strict_pct).
    strict_labels = key in VOCABULARY_ARMS
    success_rule = "strict" if strict_labels else "role_pair"

    # Observational fallback: an unsafe protocol fails Scribble projection
    # (Scribble's own refusal IS the validator catching the unsafety). For
    # those arms we still want to run the agents and observe behaviour —
    # deadlock, timeout, accidental success — so we degrade gracefully to
    # an empty-monitor mode (SessionMonitor with no per-role state machines
    # records events but issues no protocol verdicts).
    projection_failed = False
    projection_error = ""
    try:
        efsms = get_all_efsms(active_protocol, case.protocol_name, case.roles)
        refinements = load_refinements_for_protocol(active_protocol)
    except Exception as e:
        projection_failed = True
        projection_error = f"{type(e).__name__}: {e}"
        efsms = {}
        refinements = {}
        print(f"  [{name}] PROJECTION REFUSED for {active_protocol.name}: "
              f"{projection_error[:160]}\n"
              f"  [{name}] falling back to OBSERVATIONAL mode "
              f"(no monitor verdicts; events still recorded)", flush=True)

    emitter = LiveEventEmitter(events_path, efsms, refinements,
                               mirror_path=mirror_path)
    if projection_failed:
        emitter.emit_marker("protocol_unprojectable",
                            protocol=str(active_protocol),
                            error=projection_error[:600],
                            scenario=name)

    runner.setup()
    # Persist installed prompts immediately after setup so the artefact exists
    # even if the trial loop later crashes. See experiments/CLAUDE.md
    # "Persistence policy" for the layout.
    try:
        _persist_prompts(runner, run_dir)
    except Exception as e:
        print(f"  [{name}] prompt persistence FAILED: "
              f"{type(e).__name__}: {e}", flush=True)
    monitor_note = ("OBSERVATIONAL — Scribble refused projection"
                    if projection_failed
                    else f"monitor against {active_protocol.name}")
    print(f"  [{name}] setup complete ({monitor_note}, "
          f"{len(goal_set.goals)} goals)", flush=True)

    summary = {"scenario": name, "scenario_key": key, "trials": []}

    for trial in range(n_trials):
        branch = case.branch_hints[trial % len(case.branch_hints)] \
            if case.branch_hints else None
        # Per-trial reset: MAF runners rebuild agent objects to guarantee
        # no object-level state carries between trials. Foundry runners are
        # already trial-independent via fresh threads per attempt.
        runner.reset_for_trial(trial)
        emitter.emit_marker("trial_start", trial=trial, branch=branch,
                            scenario=name)
        print(f"\n--- {name} trial {trial+1}/{n_trials}  branch={branch} ---",
              flush=True)

        cum_prompt = cum_completion = cum_calls = 0
        succeeded = False
        attempts_used = 0
        final_events: list = []

        for attempt in range(1, MAX_ATTEMPTS + 1):
            attempts_used = attempt
            random.seed(trial * 7 + attempt * 31 + hash(key) % 100)
            emitter.reset_monitors()
            emitter.emit_marker("attempt_start", trial=trial, attempt=attempt,
                                branch=branch, scenario=name)
            result = runner.run_attempt(trial, attempt, branch, emitter)
            usage = result.usage
            events = result.events
            cum_prompt += usage["prompt_tokens"]
            cum_completion += usage["completion_tokens"]
            cum_calls += usage["calls"]

            # The arm's own success rule decides retry + trial success; the
            # strict result is always recorded alongside so both numbers are
            # available post-hoc for every arm.
            strict_results = verify_goals_against_trace(goal_set, events, branch)
            if strict_labels:
                goal_results = strict_results
            else:
                goal_results = verify_goals_against_trace(
                    goal_set, events, branch, match_labels=False)
            all_goals_pass = bool(goal_results) and all(
                ok for ok, _ in goal_results.values())
            n_goals_ok = sum(1 for ok, _ in goal_results.values() if ok)
            n_goals_total = len(goal_results)
            n_goals_ok_strict = sum(1 for ok, _ in strict_results.values() if ok)

            emitter.emit_marker("attempt_end", trial=trial, attempt=attempt,
                                events=len(events),
                                goals_pass=n_goals_ok,
                                goals_total=n_goals_total,
                                goals_pass_strict=n_goals_ok_strict,
                                success_rule=success_rule,
                                all_goals_pass=all_goals_pass,
                                tokens=usage,
                                extra=result.extra)
            print(f"    attempt {attempt}/{MAX_ATTEMPTS}: "
                  f"events={len(events)}  goals={n_goals_ok}/{n_goals_total} "
                  f"({success_rule}; strict={n_goals_ok_strict})  "
                  f"tokens={usage['prompt_tokens']+usage['completion_tokens']}  "
                  f"{'OK' if all_goals_pass else 'retry'}",
                  flush=True)

            final_events = events
            if all_goals_pass:
                succeeded = True
                break

        cum_total = cum_prompt + cum_completion
        emitter.emit_marker("trial_end", trial=trial,
                            succeeded=succeeded,
                            success_rule=success_rule,
                            attempts=attempts_used,
                            events=len(final_events),
                            tokens={"prompt_tokens": cum_prompt,
                                    "completion_tokens": cum_completion,
                                    "total_tokens": cum_total,
                                    "calls": cum_calls})
        summary["trials"].append({"trial": trial, "branch": branch,
                                  "succeeded": succeeded,
                                  "attempts": attempts_used,
                                  "events": len(final_events),
                                  "tokens": {"prompt_tokens": cum_prompt,
                                             "completion_tokens": cum_completion,
                                             "total_tokens": cum_total,
                                             "calls": cum_calls}})

    runner.teardown()
    emitter.close()
    print(f"  -> {events_path} ({events_path.stat().st_size} bytes)", flush=True)
    return summary


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def summarize_run(run_dir: Path) -> dict:
    """Aggregate events_<key>.jsonl for every scenario into summary.json."""
    from collections import defaultdict

    def _aggregate(path: Path):
        trials = []
        cur = None
        types = defaultdict(int)
        total_events = total_viol = 0
        if not path.exists():
            return {"trials": [], "events": 0, "violations": 0,
                    "violation_types": {}, "succeeded": 0, "n_trials": 0,
                    "total_attempts": 0, "successful_attempts_sum": 0,
                    "prompt_tokens": 0, "completion_tokens": 0,
                    "total_tokens": 0, "calls": 0,
                    "successful_tokens_sum": 0,
                    "total_seconds": 0.0, "successful_seconds_sum": 0.0}

        succeeded_n = 0
        success_rule = None   # "strict" or "role_pair", from trial_end markers
        total_attempts = 0
        successful_attempts_sum = 0
        total_prompt = total_completion = total_calls = 0
        successful_tokens_sum = 0
        # Wall-clock: trial_start.ts and trial_end.ts are ms-since-epoch
        # (set by LiveEventEmitter). Derive per-trial duration here.
        total_seconds = 0.0
        successful_seconds_sum = 0.0
        trial_start_ts = None

        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            ev = json.loads(line)
            m = ev.get("marker")
            if m == "trial_start":
                cur = {"branch": ev.get("branch"), "events": 0, "viol": 0,
                       "succeeded": False, "attempts": 0,
                       "prompt_tokens": 0, "completion_tokens": 0,
                       "total_tokens": 0, "calls": 0, "seconds": 0.0}
                trial_start_ts = ev.get("ts")
            elif m == "trial_end":
                if cur:
                    cur["succeeded"] = bool(ev.get("succeeded"))
                    success_rule = ev.get("success_rule") or success_rule
                    cur["attempts"] = ev.get("attempts", 0)
                    tk = ev.get("tokens") or {}
                    cur["prompt_tokens"] = tk.get("prompt_tokens", 0)
                    cur["completion_tokens"] = tk.get("completion_tokens", 0)
                    cur["total_tokens"] = tk.get("total_tokens", 0)
                    cur["calls"] = tk.get("calls", 0)
                    # ms -> seconds; only count if both timestamps present
                    end_ts = ev.get("ts")
                    if trial_start_ts is not None and end_ts is not None:
                        cur["seconds"] = round((end_ts - trial_start_ts) / 1000.0, 1)
                    total_prompt += cur["prompt_tokens"]
                    total_completion += cur["completion_tokens"]
                    total_calls += cur["calls"]
                    total_attempts += cur["attempts"]
                    total_seconds += cur["seconds"]
                    if cur["succeeded"]:
                        succeeded_n += 1
                        successful_attempts_sum += cur["attempts"]
                        successful_tokens_sum += cur["total_tokens"]
                        successful_seconds_sum += cur["seconds"]
                    trials.append(cur)
                cur = None
                trial_start_ts = None
            elif m in ("attempt_start", "attempt_end"):
                continue
            else:
                if cur is None:
                    continue
                cur["events"] += 1
                total_events += 1
                if ev.get("violation"):
                    cur["viol"] += 1
                    total_viol += 1
                    types[ev["violation"].get("type", "?")] += 1
        return {"trials": trials, "events": total_events, "violations": total_viol,
                "violation_types": dict(types),
                "succeeded": succeeded_n,
                "success_rule": success_rule,
                "n_trials": len(trials),
                "total_attempts": total_attempts,
                "successful_attempts_sum": successful_attempts_sum,
                "prompt_tokens": total_prompt,
                "completion_tokens": total_completion,
                "total_tokens": total_prompt + total_completion,
                "calls": total_calls,
                "successful_tokens_sum": successful_tokens_sum,
                "total_seconds": round(total_seconds, 1),
                "successful_seconds_sum": round(successful_seconds_sum, 1)}

    def pct(num, den):
        return round(num / den * 100, 1) if den else 0.0

    def avg(num, den):
        return round(num / den, 1) if den else 0.0

    # "sequential" = arms ran one at a time (wall-clock trustworthy);
    # "parallel" = arms shared one rate-limited deployment (seconds include
    # contention — do not base speed claims on them); "unknown" for run dirs
    # from before this stamp existed.
    execution_mode = "unknown"
    mode_path = run_dir / "execution_mode.json"
    if mode_path.exists():
        try:
            execution_mode = json.loads(
                mode_path.read_text(encoding="utf-8")).get(
                    "execution_mode", "unknown")
        except Exception:
            pass

    summary = {"run_dir": str(run_dir), "execution_mode": execution_mode,
               "scenarios": {}}
    for key, name, _factory in SCENARIOS:
        agg = _aggregate(run_dir / f"events_{key}.jsonl")
        n = agg["n_trials"]
        succ = agg["succeeded"]
        # tokens/sec = LLM throughput; combines latency + payload size.
        # A useful single-number speed-vs-cost summary.
        tk_per_sec = (agg["total_tokens"] / agg["total_seconds"]
                      if agg["total_seconds"] > 0 else 0.0)
        # 95% Wilson interval on the success proportion. At n=10, "100% vs
        # 60%" reads decisive but the intervals ([72,100] vs [31,83]) overlap
        # — publish the range, not just the point.
        ci_lo, ci_hi = wilson(succ, n)
        # Surface silently clipped prompts: the Foundry service truncates
        # installed instructions at 8000 chars. A clipped arm underperforms
        # for the wrong reason, so the summary must say so out loud rather
        # than leave it buried in prompts/<arm>/index.json.
        truncated_roles: list[str] = []
        idx_path = run_dir / "prompts" / key / "index.json"
        if idx_path.exists():
            try:
                idx = json.loads(idx_path.read_text(encoding="utf-8"))
                truncated_roles = [r["role"] for r in idx.get("roles", [])
                                   if r.get("truncated_on_install")]
            except Exception:
                pass
        summary["scenarios"][key] = {
            "scenario_name": name,
            **agg,
            "success_rate_pct": pct(succ, n),
            "success_rate_ci95_pct": [round(ci_lo * 100, 1),
                                      round(ci_hi * 100, 1)],
            "prompt_truncated_roles": truncated_roles,
            "avg_attempts_all": avg(agg["total_attempts"], n),
            "avg_attempts_success": avg(agg["successful_attempts_sum"], succ),
            "avg_tokens_per_trial": avg(agg["total_tokens"], n),
            "avg_tokens_per_success": avg(agg["successful_tokens_sum"], succ),
            "avg_prompt_per_trial": avg(agg["prompt_tokens"], n),
            "avg_completion_per_trial": avg(agg["completion_tokens"], n),
            "avg_calls_per_trial": avg(agg["calls"], n),
            "avg_seconds_per_trial": avg(agg["total_seconds"], n),
            "avg_seconds_per_success": avg(agg["successful_seconds_sum"], succ),
            "tokens_per_second": round(tk_per_sec, 1),
        }
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def print_summary(case: Case, summary: dict) -> None:
    scs = summary["scenarios"]
    n_trials = max((s["n_trials"] for s in scs.values()), default=0)
    print("\n" + "=" * 110)
    print(f"  CASE: {case.case_id}   n_trials={n_trials}   MAX_ATTEMPTS={MAX_ATTEMPTS}")
    print("=" * 110)
    cols = [(k, n) for k, n, _ in SCENARIOS if k in scs]
    header_cols = "  ".join(f"{n:>20s}" for _, n in cols)
    print(f"  {'metric':28s}  {header_cols}")
    print(f"  {'-'*28}  " + "  ".join("-" * 20 for _ in cols))

    def row(label, fmt, key):
        vals = "  ".join(fmt.format(scs[k][key]) for k, _ in cols)
        print(f"  {label:28s}  {vals}")

    row("success rate",          "{:>19.1f}%", "success_rate_pct")
    # CI + rule rows are strings, not floats — format by hand.
    ci_vals = "  ".join(
        f"{'[{:.0f},{:.0f}]%'.format(*scs[k]['success_rate_ci95_pct']):>20s}"
        for k, _ in cols)
    print(f"  {'success 95% CI (Wilson)':28s}  {ci_vals}")
    rule_vals = "  ".join(
        f"{(scs[k].get('success_rule') or '-'):>20s}" for k, _ in cols)
    print(f"  {'success rule':28s}  {rule_vals}")
    row("avg attempts (all)",    "{:>20.2f}",  "avg_attempts_all")
    row("avg attempts (success)","{:>20.2f}",  "avg_attempts_success")
    row("avg seconds/trial",     "{:>20.1f}",  "avg_seconds_per_trial")
    row("avg seconds/success",   "{:>20.1f}",  "avg_seconds_per_success")
    row("avg tokens/trial (cum)","{:>20.1f}",  "avg_tokens_per_trial")
    row("avg tokens/success",    "{:>20.1f}",  "avg_tokens_per_success")
    row("  prompt/trial",        "{:>20.1f}",  "avg_prompt_per_trial")
    row("  completion/trial",    "{:>20.1f}",  "avg_completion_per_trial")
    row("avg calls/trial",       "{:>20.1f}",  "avg_calls_per_trial")
    row("tokens/second",         "{:>20.1f}",  "tokens_per_second")
    row("total events",          "{:>20d}",    "events")
    row("total violations",      "{:>20d}",    "violations")

    mode = summary.get("execution_mode", "unknown")
    if mode != "sequential":
        print(f"  NOTE: execution_mode={mode} — arms shared one rate-limited "
              f"deployment, so seconds/trial include queueing contention. "
              f"Use --sequential for trustworthy wall-clock comparisons.")

    # Loud warning for any arm whose installed prompt was clipped at the
    # Foundry 8000-char limit — its numbers are not comparable.
    for k, n in cols:
        clipped = scs[k].get("prompt_truncated_roles") or []
        if clipped:
            print(f"  WARNING: arm '{k}' had prompts TRUNCATED on install "
                  f"for roles {clipped} — treat this arm's results as "
                  f"invalid for comparison.")

    # Token savings vs bare, for the non-bare arms
    if "bare" in scs and scs["bare"]["avg_tokens_per_trial"]:
        bare_tk = scs["bare"]["avg_tokens_per_trial"]
        for k, _ in cols:
            if k == "bare":
                continue
            scs[k]["token_savings_vs_bare_pct"] = round(
                (1 - scs[k]["avg_tokens_per_trial"] / bare_tk) * 100, 1)
        save_vals = []
        for k, _ in cols:
            if k == "bare":
                save_vals.append(" " * 20)
            else:
                save_vals.append(f"{scs[k]['token_savings_vs_bare_pct']:>19.1f}%")
        print(f"  {'token savings vs bare':28s}  " + "  ".join(save_vals))


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def _completed_arm_keys(run_dir: Path, n_trials: int) -> set[str]:
    """Detect which arms already have all n_trials trial_end markers written.

    Used by --resume to skip arms that completed in a prior partial run.
    Conservative: counts a trial_end marker per JSONL line (one per trial).
    Incomplete arms (fewer trial_ends than n_trials) are re-run from scratch
    on resume — LiveEventEmitter truncates the JSONL at the start of run.
    """
    done: set[str] = set()
    for key, _, _ in SCENARIOS:
        p = run_dir / f"events_{key}.jsonl"
        if not p.exists():
            continue
        n_trial_ends = 0
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                ev = json.loads(line)
            except Exception:
                continue
            if ev.get("marker") == "trial_end":
                n_trial_ends += 1
        if n_trial_ends >= n_trials:
            done.add(key)
    return done


def run_case(case_id: str, n_trials: int,
             resume_dir: Optional[Path] = None,
             semantic: bool = False,
             sequential: bool = False) -> dict:
    case_dir = CASES_DIR / case_id
    case = Case.load(case_dir)
    print("=" * 72)
    print(f"  CASE {case.case_id}   v{case.version}   n_trials={n_trials}")
    print(f"  protocol: {case.protocol_path.name}")
    print(f"  roles:    {case.roles}")
    print(f"  intent:   {case.intent[:120]}...")
    print(f"  scenarios: {[k for k, _, _ in SCENARIOS]}")
    print("=" * 72)

    if resume_dir is not None:
        run_dir = resume_dir
        if not run_dir.exists():
            print(f"  ERROR: resume dir does not exist: {run_dir}")
            sys.exit(2)
        completed = _completed_arm_keys(run_dir, n_trials)
        print(f"  RESUME mode: scanning {run_dir.relative_to(EXPERIMENTS_DIR)}")
        if completed:
            print(f"  already-completed arms (will SKIP): {sorted(completed)}")
        else:
            print(f"  no completed arms found; running all from scratch")
    else:
        completed = set()
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        run_dir = case.runs_dir / f"{timestamp}-n{n_trials}-dual"
        run_dir.mkdir(parents=True, exist_ok=True)
        print(f"  run dir:  {run_dir.relative_to(EXPERIMENTS_DIR)}")
    (case.case_dir / "LATEST").write_text(run_dir.name, encoding="utf-8")

    # Wave-based execution to avoid Azure OpenAI gpt-4o TPM throttling:
    #   wave 1: Foundry-only arms in parallel (use Agent Service, which
    #           handles 429s internally — no cross-arm contention surfaced)
    #   wave 2: MAF arms sequentially, one at a time
    #           (MAF's OpenAIChatCompletionClient surfaces 429s as errors
    #            that count as no-progress — so any concurrency among MAF
    #            arms causes spurious "deadlock" signals)
    FOUNDRY_KEYS = {"bare", "spec_llmvalid", "min_llmvalid", "spec_llmvalid_gate", "min_llmvalid_gate", "min_llmvalid_gate_nohint", "min_llmvalid_gate_lastrecv", "min_llmvalid_sched", "global_decentralized", "unchecked_skills"}

    def _run_one(idx: int, runner_):
        print(f"\n[experiment {idx+1}] {runner_.scenario_name} "
              f"({runner_.scenario_key})", flush=True)
        try:
            run_scenario(runner_, n_trials=n_trials, run_dir=run_dir)
        except Exception as e:
            import traceback
            print(f"  [{runner_.scenario_name}] FAILED: "
                  f"{type(e).__name__}: {e}", flush=True)
            traceback.print_exc()

    foundry_arms = [(i, k, n) for i, (k, n, _) in enumerate(SCENARIOS)
                    if k in FOUNDRY_KEYS and k not in completed]
    maf_arms     = [(i, k, n) for i, (k, n, _) in enumerate(SCENARIOS)
                    if k not in FOUNDRY_KEYS and k not in completed]

    if sequential:
        # UNCONTENDED timing mode: every arm runs alone, one at a time.
        # Why: in the default parallel mode all Foundry arms share one Azure
        # deployment's rate limit, so each arm's wall-clock includes waiting
        # out a traffic jam the benchmark itself created — and the arm that
        # makes the fewest calls waits least. Any seconds-based claim
        # ("4x faster") must come from a --sequential run; summary.json
        # records which mode produced it (execution_mode).
        print(f"\n{'='*72}\n  SEQUENTIAL mode: all arms one at a time "
              f"(trustworthy wall-clock) — "
              f"{[k for _, k, _ in foundry_arms + maf_arms]}\n{'='*72}",
              flush=True)
        for idx, key, _ in foundry_arms + maf_arms:
            runner = make_runner(case, key)
            _run_one(idx, runner)
    else:
        # Wave 1 — Foundry arms in parallel
        print(f"\n{'='*72}\n  WAVE 1: Foundry arms (parallel) — "
              f"{[k for _, k, _ in foundry_arms]}\n{'='*72}", flush=True)
        threads = []
        for idx, key, _ in foundry_arms:
            runner = make_runner(case, key)
            t = threading.Thread(target=_run_one, args=(idx, runner),
                                 name=f"{case.case_id}-{key}")
            threads.append(t)
            t.start()
        for t in threads:
            t.join()

        # Wave 2 — MAF arms sequentially
        print(f"\n{'='*72}\n  WAVE 2: MAF arms (sequential) — "
              f"{[k for _, k, _ in maf_arms]}\n{'='*72}", flush=True)
        for idx, key, _ in maf_arms:
            runner = make_runner(case, key)
            _run_one(idx, runner)

    # Stamp the mode into the run dir so summarize_run (including later
    # --summarize-only reruns) can mark whether seconds are contended.
    (run_dir / "execution_mode.json").write_text(
        json.dumps({"execution_mode":
                    "sequential" if sequential else "parallel"}),
        encoding="utf-8")

    summary = summarize_run(run_dir)
    print_summary(case, summary)

    # --- Set B: goal-achievement metrics --------------------------------
    # Goal evaluation is now part of every run, not a separate manual
    # evaluate_run.py step. strict + role-pair are deterministic and free;
    # the LLM-judged semantic metric runs only with --semantic.
    try:
        evout = evaluate_run.evaluate(case, run_dir, semantic=semantic)
        evaluate_run.print_eval(case, evout)
    except Exception as e:
        import traceback
        print(f"  [Set B / goal eval] FAILED: {type(e).__name__}: {e}",
              flush=True)
        traceback.print_exc()
    return summary


def main():
    args = sys.argv[1:]
    if not args:
        print("usage: case_runner.py <case_id|--all> [n_trials] "
              "[--resume <run_dir>] [--semantic]")
        print("       case_runner.py <case_id> --summarize-only <run_dir> "
              "[--semantic]")
        print("  --resume: scan run_dir for completed arms and skip them; "
              "incomplete arms re-run from scratch.")
        print("  --summarize-only: regenerate summary.json + summary_eval.json "
              "and reprint the tables for an existing run_dir without running "
              "new trials. Useful when metric code has changed since the run.")
        print("  --semantic: also compute the LLM-judged semantic goal metric "
              "(~5 LLM calls per trial per arm). Off by default — the strict "
              "and role-pair goal metrics always run.")
        print("  --sequential: run every arm one at a time (no shared "
              "rate-limit contention). Required for any wall-clock/speed "
              "claim; the default parallel mode is fine for token metrics.")
        print("  --arms: comma-separated scenario keys to run (default: all "
              f"registered arms: {[k for k, _, _ in SCENARIOS]})")
        sys.exit(2)

    # --semantic: opt into the LLM-judged Set B metric (costs LLM calls).
    semantic = "--semantic" in args
    args = [a for a in args if a != "--semantic"]

    # --sequential: uncontended one-arm-at-a-time execution (fair timing).
    sequential = "--sequential" in args
    args = [a for a in args if a != "--sequential"]

    # --arms: restrict the run to a subset of registered scenario keys.
    if "--arms" in args:
        idx = args.index("--arms")
        if idx + 1 >= len(args):
            print("--arms requires a comma-separated list of scenario keys")
            sys.exit(2)
        chosen = [a.strip() for a in args[idx + 1].split(",") if a.strip()]
        known = {k for k, _, _ in SCENARIOS}
        unknown = [a for a in chosen if a not in known]
        if unknown:
            print(f"--arms: unknown scenario keys {unknown} "
                  f"(known: {sorted(known)})")
            sys.exit(2)
        # Slice-assign so every module holding a reference to the registry
        # list (run_case's wave split, summarize, persisters) sees the filter.
        SCENARIOS[:] = [s for s in SCENARIOS if s[0] in chosen]
        args = args[:idx] + args[idx + 2:]

    # --summarize-only: shortcut, no runner work, just re-aggregate.
    if "--summarize-only" in args:
        idx = args.index("--summarize-only")
        if idx + 1 >= len(args):
            print("--summarize-only requires a run directory path"); sys.exit(2)
        run_dir = Path(args[idx + 1]).resolve()
        if not run_dir.exists():
            print(f"run_dir does not exist: {run_dir}"); sys.exit(2)
        case_id = args[0]
        case = Case.load(CASES_DIR / case_id)
        summary = summarize_run(run_dir)
        print_summary(case, summary)
        try:
            evout = evaluate_run.evaluate(case, run_dir, semantic=semantic)
            evaluate_run.print_eval(case, evout)
        except Exception as e:
            import traceback
            print(f"  [Set B / goal eval] FAILED: {type(e).__name__}: {e}")
            traceback.print_exc()
        return

    # Parse --resume out of args
    resume_dir: Optional[Path] = None
    if "--resume" in args:
        idx = args.index("--resume")
        if idx + 1 >= len(args):
            print("--resume requires a run directory path"); sys.exit(2)
        resume_dir = Path(args[idx + 1]).resolve()
        args = args[:idx] + args[idx + 2:]

    if args[0] == "--all":
        if resume_dir is not None:
            print("--resume is incompatible with --all (resume is per-run)")
            sys.exit(2)
        n = int(args[1]) if len(args) > 1 and args[1].isdigit() else 10
        case_ids = [p.name for p in sorted(CASES_DIR.iterdir())
                    if p.is_dir() and (p / "case.yaml").exists()]
        print(f"running all cases at n={n}: {case_ids}")
        for cid in case_ids:
            run_case(cid, n, semantic=semantic, sequential=sequential)
    else:
        case_id = args[0]
        n = int(args[1]) if len(args) > 1 and args[1].isdigit() else 10
        run_case(case_id, n, resume_dir=resume_dir, semantic=semantic,
                 sequential=sequential)


if __name__ == "__main__":
    main()
