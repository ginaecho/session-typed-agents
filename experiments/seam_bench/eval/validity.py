"""validity.py — thin adapters over the two real verifiers Seam-Bench scores
against, each wrapped in a subprocess + wall-clock-timeout guard.

  validate(text)              -> (valid, validator_msg)
      the Scribble validator (stjp_core/compiler/validator.py::
      ScribbleValidator.validate_protocol) — parses / well-formedness /
      deadlock-freedom, exactly what the live drafting loop rejects on.

  bisim_equivalent(a, b)      -> (equivalent, reason)
      the E5 EFSM-bisimulation / conversation-equivalence checker
      (experiments/scripts/efsm_equiv.py::protocols_equivalent — same-role-set
      + per-role projected-EFSM bisimulation + identical accepted-conversation
      language). Located per the W1 task card's instruction to search
      stjp_core + experiments for "the equivalence checker the docs call E5":
      efsm_equiv.py is that checker (module docstring: "BENCHMARK_PLAN_V2 §6
      / E5"), built on stjp_core/compiler/efsm_parser.py.

"Valid" here means the REAL Scribble-java CLI (org.scribble.cli.CommandLine)
said so — never a Python-only approximation. Wire a fresh checkout to the
shared cloud build with `bash tools/setup_scribble_cloud.sh`; if the jars
are missing, `require_toolchain()` raises `ToolchainMissing` (loud, no
fallback to any weaker checker). The pass rule itself lives in validator.py:
returncode==0 AND empty *stdout* — the JVM prints a
"Picked up JAVA_TOOL_OPTIONS..." banner on *stderr* in this environment,
which is deliberately not treated as failure.

Both verifiers ultimately shell out to `java`. Neither the validator nor the
E5 checker has an internal timeout, so a wedged JVM could otherwise stall an
entire eval sweep. Both adapters here run the real call in a fresh
subprocess (`python -m experiments.seam_bench.eval._worker`, its own process
**group**) and, on timeout, kill the whole group — not just the immediate
child — so an orphaned `java` process cannot survive the guard. See
_worker.py.

Bulk use: each validation spawns a JVM (~0.5-1s), so `validate_many()` /
`bisim_many()` fan the per-item subprocess calls over a thread pool
(subprocess-bound work — threads are the right primitive), and every verdict
is cached in-process keyed by protocol-text SHA-256, so a repeated draft
never re-rolls a JVM.
"""
from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Sequence

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]  # experiments/seam_bench/eval/validity.py -> repo root

# Scribble validation is a JVM cold-start (~1-2s typical) plus compile; 30s
# is generous headroom for a hang guard, not a performance budget. The E5
# check is much heavier — it re-validates AND projects BOTH protocols
# per-role, then walks the conversation language; the slowest _corpus
# skeleton (corpus_003) takes ~20s solo and blew a 30s guard under 4-way
# pool contention during smoke (correctly degraded to False; not cached).
# Hence the separate, larger bisim default.
DEFAULT_TIMEOUT_S = 30.0
DEFAULT_BISIM_TIMEOUT_S = 120.0

# Thread-pool width for validate_many/bisim_many — a process-fanout knob
# (each unit of work is one JVM subprocess), not a GIL question.
DEFAULT_MAX_WORKERS = 4


class ToolchainMissing(RuntimeError):
    """The real Scribble-java toolchain is not wired into this checkout.
    Raised loudly — never downgraded to a warning or a silent fallback to a
    weaker checker; a validity number produced without the real CLI would be
    meaningless."""


def require_toolchain() -> Path:
    """Assert the real Scribble-java jars are present and return the lib dir.

    Every public adapter calls this before spawning a worker, so a missing
    toolchain fails on the FIRST call with an actionable message instead of
    surfacing as N cryptic per-item worker crashes."""
    from stjp_core.config import SCRIBBLE_PATH  # late: keep module import light
    lib = SCRIBBLE_PATH / "lib"
    if not lib.is_dir() or not any(lib.glob("*.jar")):
        raise ToolchainMissing(
            f"Scribble-java jars not found under {lib} — the REAL validator "
            f"is required (no fallback). Run `bash tools/setup_scribble_cloud.sh` "
            f"from the repo root to wire this checkout to the shared build.")
    return lib


# ── in-process verdict cache, keyed by protocol-text SHA-256 ─────────────

_cache_lock = threading.Lock()
_validate_cache: dict[str, tuple[bool, str]] = {}
_bisim_cache: dict[tuple[str, str], tuple[bool, str]] = {}


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def clear_cache() -> None:
    """Drop all cached verdicts (tests; or after a toolchain change)."""
    with _cache_lock:
        _validate_cache.clear()
        _bisim_cache.clear()


def cache_stats() -> dict[str, int]:
    with _cache_lock:
        return {"validate": len(_validate_cache), "bisim": len(_bisim_cache)}


class VerifierTimeout(RuntimeError):
    """A verifier subprocess exceeded its timeout and was killed. Callers
    normally never see this directly — validate()/bisim_equivalent() catch
    it and return (False, <message noting the timeout>) so a hung verifier
    degrades to "counted as invalid," not a crashed eval run."""


def _run_worker(payload: dict, timeout_s: float) -> dict:
    cmd = [sys.executable, "-m", "experiments.seam_bench.eval._worker"]
    popen_kwargs: dict = dict(
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, cwd=str(REPO_ROOT))
    # New session -> new process group, so a timeout kill can take the whole
    # group (worker + any java child it spawned) rather than leaking an
    # orphaned java process. POSIX-only; falls back to plain kill elsewhere.
    use_pgroup = hasattr(os, "killpg") and hasattr(os, "getpgid")
    if use_pgroup:
        popen_kwargs["start_new_session"] = True
    elif os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

    proc = subprocess.Popen(cmd, **popen_kwargs)
    try:
        out, err = proc.communicate(input=json.dumps(payload), timeout=timeout_s)
    except subprocess.TimeoutExpired:
        if use_pgroup:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
        elif os.name == "nt":
            # `proc.kill()` terminates only the Python worker on Windows;
            # its Java validator child survives and can retain gigabytes.
            # taskkill /T removes the full worker -> launcher -> JVM tree.
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                capture_output=True, text=True, check=False)
        else:
            proc.kill()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        raise VerifierTimeout(
            f"verifier worker exceeded {timeout_s}s and was killed")

    if proc.returncode != 0:
        return {"ok": False,
                "msg": f"worker crashed (rc={proc.returncode}): "
                       f"{(err or '')[-500:]}"}
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return {"ok": False,
                "msg": f"worker produced non-JSON output: "
                       f"stdout={out[-300:]!r} stderr={(err or '')[-300:]!r}"}


def validate(text: str, *, timeout_s: float = DEFAULT_TIMEOUT_S,
              use_cache: bool = True) -> tuple[bool, str]:
    """(valid, validator_msg) for one Scribble protocol source string, via
    the real ScribbleValidator (Scribble-java CLI), subprocess+timeout
    guarded, verdicts cached by text hash. Raises ToolchainMissing if the
    jars are not wired in (never falls back)."""
    require_toolchain()
    key = _text_hash(text)
    if use_cache:
        with _cache_lock:
            if key in _validate_cache:
                return _validate_cache[key]
    try:
        result = _run_worker({"mode": "validate", "text": text}, timeout_s)
    except VerifierTimeout as e:
        # Timeouts are NOT cached: a transient stall must not permanently
        # brand this protocol text invalid for the rest of the process.
        return False, str(e)
    verdict = (bool(result.get("ok")), str(result.get("msg", "")))
    if use_cache:
        with _cache_lock:
            _validate_cache[key] = verdict
    return verdict


def bisim_equivalent(text_a: str, text_b: str, *,
                      timeout_s: float = DEFAULT_BISIM_TIMEOUT_S,
                      use_cache: bool = True) -> tuple[bool, str]:
    """(equivalent, reason) for two Scribble protocol source strings, via
    the real E5 checker (efsm_equiv.protocols_equivalent), subprocess+timeout
    guarded, verdicts cached by (hash_a, hash_b). Both inputs must
    independently validate — a non-validating protocol has no EFSM to
    compare and this returns (False, <error>)."""
    require_toolchain()
    key = (_text_hash(text_a), _text_hash(text_b))
    if use_cache:
        with _cache_lock:
            if key in _bisim_cache:
                return _bisim_cache[key]
    try:
        result = _run_worker(
            {"mode": "bisim", "text_a": text_a, "text_b": text_b}, timeout_s)
    except VerifierTimeout as e:
        return False, str(e)  # timeouts not cached (see validate)
    verdict = (bool(result.get("ok")), str(result.get("msg", "")))
    if use_cache:
        with _cache_lock:
            _bisim_cache[key] = verdict
    return verdict


# ── bulk paths (thread pool over JVM subprocesses) ───────────────────────

def validate_many(texts: Sequence[str], *,
                   timeout_s: float = DEFAULT_TIMEOUT_S,
                   max_workers: int = DEFAULT_MAX_WORKERS,
                   use_cache: bool = True) -> list[tuple[bool, str]]:
    """validate() over a batch, subprocess calls fanned out on a thread
    pool. Result order matches input order. Duplicate texts are deduped
    up-front so each distinct protocol pays at most one JVM even when its
    duplicates would have been in flight concurrently."""
    require_toolchain()
    unique = list(dict.fromkeys(texts))  # preserves first-seen order
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        verdicts = list(pool.map(
            lambda t: validate(t, timeout_s=timeout_s, use_cache=use_cache),
            unique))
    by_text = dict(zip(unique, verdicts))
    return [by_text[t] for t in texts]


def bisim_many(pairs: Sequence[tuple[str, str]], *,
                timeout_s: float = DEFAULT_BISIM_TIMEOUT_S,
                max_workers: int = DEFAULT_MAX_WORKERS,
                use_cache: bool = True) -> list[tuple[bool, str]]:
    """bisim_equivalent() over a batch of (draft, gold) pairs, thread-pool
    fanned. Result order matches input order."""
    require_toolchain()
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        return list(pool.map(
            lambda p: bisim_equivalent(p[0], p[1], timeout_s=timeout_s,
                                        use_cache=use_cache),
            pairs))
