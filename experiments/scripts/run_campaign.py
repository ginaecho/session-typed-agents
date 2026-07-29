"""run_campaign.py — run a benchmark campaign: several cases across several
Azure OpenAI deployments in parallel, safely.

The single-case entry point is scripts/case_runner.py (one case, one
deployment). This script only LAUNCHES case_runner.py processes and decides
when to start the next one. It never computes or records any benchmark
result — all logs and summaries are written by case_runner.py itself into
experiments/cases/<case>/runs/<run folder>/.

Safety rules (each one exists because its absence caused a real incident,
2026-07-28 — see docs/reference/HOW_TO_RUN_BENCHMARKS.md):

  1. ONE JOB PER DEPLOYMENT AT A TIME. Deployments run in parallel with each
     other, but each deployment runs its queue strictly one case at a time.
     Two jobs on one deployment share its rate limit and starve each other.
  2. EXACTLY ONE LAUNCHER PROCESS. A lock file refuses a second launcher; a
     startup scan refuses to start while case_runner.py processes from an
     earlier launcher are still alive. Two launchers fight: one kills a run,
     the other "helpfully" restarts it.
  3. RUN FOLDERS RESOLVED BY PID, NEVER BY THE LATEST FILE. case_runner.py
     names each run folder <timestamp>-<deployment>-p<pid>-n<N>-dual. When
     the same case runs on two deployments at once, both overwrite the single
     cases/<case>/LATEST pointer, so LATEST cannot tell the two runs apart —
     resolving by the launched process's pid can.

Stall handling: if a job's newest events_*.jsonl has been quiet longer than
stall_minutes, the job is killed and relaunched with --resume (completed
settings are skipped, the interrupted one re-runs). Relaunches are capped so
a broken job can never loop forever.

Usage:
    python scripts/run_campaign.py <campaign.yaml> [--dry-run]

Campaign file (YAML):
    n: 10
    settings: [bare, unchecked_skills, min_llmvalid_gate]   # case_runner --arms
    sequential: false        # true = pass --sequential (fair wall-clock)
    stall_minutes: 25
    poll_seconds: 60
    deployments:
      gpt-5-mini: [skills_safety/gem_dev_team, agenticpay_settlement]
      gpt-5.4:    [skills_safety/gem_dev_team]

Requirements: `az login` done, JAVA_HOME set (Scribble validation), and each
deployment name existing in the Azure AI Foundry project.
"""
from __future__ import annotations

import atexit
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
EXPERIMENTS_DIR = HERE.parent
CASES_DIR = EXPERIMENTS_DIR / "cases"
LOCK_PATH = EXPERIMENTS_DIR / ".run_campaign.lock"
LOG_ROOT = EXPERIMENTS_DIR / "campaign_logs"

MAX_LAUNCH_FAILURES = 3   # exits before a run folder ever appeared
MAX_RESUMES = 20          # stall-kills + early exits after the folder exists


def say(msg: str) -> None:
    print(f"[campaign {time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ---------------------------------------------------------------- rule 2 —
# exactly one launcher

def _pid_alive(pid: int) -> bool:
    if os.name == "nt":
        try:
            out = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True, text=True, timeout=30).stdout
            return str(pid) in out
        except Exception:
            return True  # cannot verify -> assume alive (safe side)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _other_case_runners() -> list[str]:
    """Return 'pid :: case' lines for case_runner.py processes already
    running (from any earlier launcher). Empty list if none or unknowable."""
    if os.name != "nt":
        return []
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process | Where-Object { $_.Name -match "
             "'^python' -and $_.CommandLine -match 'case_runner\\.py' } | "
             "ForEach-Object { $_.ProcessId.ToString() + ' :: ' + "
             "$_.CommandLine }"],
            capture_output=True, text=True, timeout=60).stdout
        return [ln.strip() for ln in out.splitlines() if ln.strip()]
    except Exception:
        return []


def acquire_lock() -> None:
    if LOCK_PATH.exists():
        try:
            old = int(LOCK_PATH.read_text(encoding="utf-8").strip())
        except ValueError:
            old = None
        if old is not None and _pid_alive(old):
            say(f"REFUSED: another launcher (pid {old}) holds "
                f"{LOCK_PATH.name}. Rule 2: exactly one launcher. "
                f"Stop it first, or delete the lock file if it is stale.")
            sys.exit(1)
        say(f"stale lock from dead pid {old} - taking over")
    LOCK_PATH.write_text(str(os.getpid()), encoding="utf-8")
    atexit.register(lambda: LOCK_PATH.unlink(missing_ok=True))


# ---------------------------------------------------------------- rule 3 —
# pid-based run-folder resolution

def dir_for_pid(case_id: str, pid: int) -> str | None:
    runs = CASES_DIR / case_id / "runs"
    if not runs.exists():
        return None
    cands = [d for d in runs.glob(f"*-p{pid}-*") if d.is_dir()]
    if not cands:
        return None
    best = max(cands, key=lambda d: d.stat().st_mtime)
    return f"cases/{case_id}/runs/{best.name}"


def newest_events_mtime(run_dir: str | None) -> float | None:
    if not run_dir:
        return None
    p = EXPERIMENTS_DIR / run_dir
    files = list(p.glob("events_*.jsonl")) if p.exists() else []
    return max((f.stat().st_mtime for f in files), default=None)


def summary_exists(run_dir: str | None) -> bool:
    return bool(run_dir) and (EXPERIMENTS_DIR / run_dir / "summary.json").exists()


# ---------------------------------------------------------------- launching

def launch(deployment: str, job: dict, log_dir: Path) -> subprocess.Popen:
    env = dict(os.environ,
               AZURE_OPENAI_DEPLOYMENT=deployment,
               PYTHONIOENCODING="utf-8")
    cmd = [sys.executable, "scripts/case_runner.py", job["case"], str(job["n"]),
           "--arms", job["settings"]]
    if job["sequential"]:
        cmd.append("--sequential")
    if job["run_dir"]:
        cmd += ["--resume", job["run_dir"]]
    lf = open(log_dir / job["log"], "a", encoding="utf-8")
    lf.write(f"\n== {deployment} {job['case']} resume={bool(job['run_dir'])} "
             f"@ {datetime.now().isoformat(timespec='seconds')} ==\n")
    lf.flush()
    proc = subprocess.Popen(cmd, cwd=str(EXPERIMENTS_DIR), env=env,
                            stdout=lf, stderr=lf)
    job["pid"] = proc.pid
    say(f"{deployment} LAUNCH {job['case']} pid {proc.pid} "
        f"(resume={bool(job['run_dir'])}, log={job['log']})")
    return proc


# ---------------------------------------------------------------- campaign

def load_campaign(path: Path) -> dict:
    spec = yaml.safe_load(path.read_text(encoding="utf-8"))
    problems = []
    if not isinstance(spec.get("deployments"), dict) or not spec["deployments"]:
        problems.append("'deployments' must map deployment name -> case list")
    settings = spec.get("settings")
    if isinstance(settings, list):
        settings = ",".join(str(s) for s in settings)
    if not isinstance(settings, str) or not settings.strip():
        problems.append("'settings' must be a non-empty list or "
                        "comma-separated string")
    else:
        spec["settings"] = settings
    if not isinstance(spec.get("n"), int) or spec["n"] < 1:
        problems.append("'n' must be a positive integer")
    for dep, cases in (spec.get("deployments") or {}).items():
        for case_id in cases or []:
            if not (CASES_DIR / case_id / "case.yaml").exists():
                problems.append(f"unknown case '{case_id}' (deployment {dep}): "
                                f"no cases/{case_id}/case.yaml")
    if problems:
        for p in problems:
            say(f"campaign file INVALID: {p}")
        sys.exit(2)
    spec.setdefault("sequential", False)
    spec.setdefault("stall_minutes", 25)
    spec.setdefault("poll_seconds", 60)
    return spec


def build_queues(spec: dict) -> dict[str, list[dict]]:
    queues: dict[str, list[dict]] = {}
    for dep, cases in spec["deployments"].items():
        queues[dep] = [{
            "case": case_id,
            "n": spec["n"],
            "settings": spec["settings"],
            "sequential": spec["sequential"],
            "log": f"{dep}--{case_id.replace('/', '-')}.log",
            "run_dir": None, "pid": None,
            "launch_failures": 0, "resumes": 0,
        } for case_id in cases]
    return queues


def main() -> None:
    args = [a for a in sys.argv[1:]]
    dry = "--dry-run" in args
    args = [a for a in args if a != "--dry-run"]
    if len(args) != 1:
        print(__doc__)
        sys.exit(2)
    spec = load_campaign(Path(args[0]).resolve())
    queues = build_queues(spec)

    say("plan:")
    for dep, q in queues.items():
        say(f"  {dep}: " + " -> ".join(j["case"] for j in q))
    say(f"  n={spec['n']} settings={spec['settings']} "
        f"sequential={spec['sequential']} stall={spec['stall_minutes']}min")
    if dry:
        say("dry run - nothing launched")
        return

    if not os.environ.get("JAVA_HOME"):
        say("WARNING: JAVA_HOME is not set - Scribble validation inside "
            "case_runner.py may fail")
    strays = _other_case_runners()
    if strays:
        say("REFUSED: case_runner.py processes are already running. Rule 2: "
            "a second launcher (or its orphans) must be stopped first:")
        for line in strays:
            say(f"  {line}")
        sys.exit(1)
    acquire_lock()

    log_dir = LOG_ROOT / datetime.now().strftime("%Y%m%dT%H%M%S")
    log_dir.mkdir(parents=True, exist_ok=True)
    say(f"job logs: {log_dir}")

    running: dict[str, dict | None] = {dep: None for dep in queues}
    failed: list[str] = []
    try:
        while True:
            busy = False
            for dep, q in queues.items():
                slot = running[dep]
                if slot is None:                       # rule 1: one job/lane
                    if q:
                        job = q.pop(0)
                        running[dep] = {"job": job,
                                        "proc": launch(dep, job, log_dir)}
                        busy = True
                    continue
                busy = True
                job, proc = slot["job"], slot["proc"]
                if job["run_dir"] is None:             # rule 3: pid, not LATEST
                    job["run_dir"] = dir_for_pid(job["case"], job["pid"])

                if proc.poll() is not None:            # process exited
                    if summary_exists(job["run_dir"]):
                        say(f"{dep} DONE {job['case']} -> {job['run_dir']}")
                        running[dep] = None
                    elif job["run_dir"] is None:
                        job["launch_failures"] += 1
                        if job["launch_failures"] >= MAX_LAUNCH_FAILURES:
                            say(f"{dep} FAILED {job['case']}: exited "
                                f"{job['launch_failures']}x before creating a "
                                f"run folder - see {job['log']}. Skipping.")
                            failed.append(f"{dep}:{job['case']}")
                            running[dep] = None
                        else:
                            say(f"{dep} {job['case']} exited with no run "
                                f"folder (attempt {job['launch_failures']}) "
                                f"- relaunching")
                            slot["proc"] = launch(dep, job, log_dir)
                    else:
                        job["resumes"] += 1
                        if job["resumes"] > MAX_RESUMES:
                            say(f"{dep} FAILED {job['case']}: {MAX_RESUMES} "
                                f"resumes without finishing. Skipping.")
                            failed.append(f"{dep}:{job['case']}")
                            running[dep] = None
                        else:
                            say(f"{dep} {job['case']} exited early "
                                f"(resume {job['resumes']}) - resuming")
                            slot["proc"] = launch(dep, job, log_dir)
                    continue

                mtime = newest_events_mtime(job["run_dir"])   # stall guard
                if mtime is not None and \
                        (time.time() - mtime) / 60 >= spec["stall_minutes"]:
                    job["resumes"] += 1
                    if job["resumes"] > MAX_RESUMES:
                        say(f"{dep} FAILED {job['case']}: stalled past "
                            f"{MAX_RESUMES} resumes. Skipping.")
                        try:
                            proc.kill()
                        except Exception:
                            pass
                        failed.append(f"{dep}:{job['case']}")
                        running[dep] = None
                    else:
                        say(f"{dep} STALL {job['case']} (quiet >= "
                            f"{spec['stall_minutes']}min) - kill + resume "
                            f"({job['resumes']}/{MAX_RESUMES})")
                        try:
                            proc.kill()
                        except Exception:
                            pass
                        time.sleep(5)
                        slot["proc"] = launch(dep, job, log_dir)

            if not busy:
                break
            time.sleep(spec["poll_seconds"])
    finally:
        # never leave orphan runners behind (they would trip rule 2 next time)
        for slot in running.values():
            if slot and slot["proc"].poll() is None:
                try:
                    slot["proc"].kill()
                except Exception:
                    pass

    if failed:
        say("campaign finished WITH FAILURES: " + ", ".join(failed))
        sys.exit(1)
    say("campaign finished - all jobs done")


if __name__ == "__main__":
    main()
