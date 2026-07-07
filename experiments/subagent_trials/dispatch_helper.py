"""Batch dispatcher glue between engine.py and externally-run LLM subagents.

Used by the skills-safety benchmark runs (2026-07-06, cloud): the orchestrating
session drives one cheap-LLM (Haiku-class) subagent per (run, role) per round;
each subagent answers ALL active trials' prompts for that role in one call
(cross-TRIAL batching only — a subagent never sees two roles of the same
trial, so there is no intra-trial information leakage; see the run notes in
docs/results/RESULT_8_SKILL_SAFETY.md for the trade-off discussion).

Round protocol:

    python dispatch_helper.py step --dir runs/<run> [--dir runs/<run2> ...]

Each call, per run dir, in order:
  1. if a round is pending and every batch has a reply file -> merge replies
     into replies_round<N>.json and `engine.py submit` it;
  2. if the run is still active -> `engine.py next`, group the polls by role,
     and write batches_round<N>/<Role>.json (+ expected .reply.json path);
  3. if the run is finished -> `engine.py report`.

Prints a JSON manifest: for every run, either `{"done": true, report...}` or
the list of batch files awaiting subagent replies. A batch file is:

    {"role": "...", "reply_file": ".../<Role>.reply.json",
     "prompts": [{"trial": 1, "prompt": "..."}, ...]}

The subagent must write to reply_file:

    {"replies": [{"trial": 1, "action": {"action": "send"|"wait", ...}}]}

(`action` may also be a raw string; both are normalised before submit.)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ENGINE = _HERE / "engine.py"


def _engine(cmd: list[str]) -> dict:
    out = subprocess.run([sys.executable, str(_ENGINE)] + cmd,
                         capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"engine {cmd} failed:\n{out.stdout}\n{out.stderr}")
    # engine `next` prints one JSON object; `submit`/`report` print JSON then
    # possibly a trailing "saved:" line — take the first JSON blob.
    text = out.stdout.strip()
    depth = 0
    for i, ch in enumerate(text):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[: i + 1])
    raise RuntimeError(f"no JSON in engine output: {text[:200]}")


def _pending_round(run_dir: Path) -> int | None:
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    r = state["round"]
    if r == 0:
        return None
    if (run_dir / f"replies_round{r}.json").exists():
        return None          # already submitted
    if (run_dir / f"polls_round{r}.json").exists():
        return r
    return None


def _merge_and_submit(run_dir: Path, rnd: int) -> dict:
    bdir = run_dir / f"batches_round{rnd}"
    replies = []
    for bf in sorted(bdir.glob("*.json")):
        if bf.name.endswith(".reply.json"):
            continue
        batch = json.loads(bf.read_text(encoding="utf-8"))
        rf = Path(batch["reply_file"])
        if not rf.exists():
            raise RuntimeError(f"missing reply file: {rf}")
        got = json.loads(rf.read_text(encoding="utf-8"))
        by_trial = {int(r["trial"]): r for r in got.get("replies", [])}
        for p in batch["prompts"]:
            r = by_trial.get(int(p["trial"]))
            action = r.get("action", r.get("reply", "")) if r else ""
            reply = (json.dumps(action) if isinstance(action, dict)
                     else str(action or ""))
            replies.append({"trial": p["trial"], "role": batch["role"],
                            "reply": reply})
    rfile = run_dir / f"replies_round{rnd}.json"
    rfile.write_text(json.dumps({"replies": replies}, indent=2),
                     encoding="utf-8")
    return _engine(["submit", "--dir", str(run_dir), "--file", str(rfile)])


def _emit_batches(run_dir: Path, polls: dict,
                  chunk: int | None = None) -> list[dict]:
    rnd = polls["round"]
    bdir = run_dir / f"batches_round{rnd}"
    bdir.mkdir(exist_ok=True)
    by_role: dict[str, list] = {}
    for p in polls["polls"]:
        by_role.setdefault(p["role"], []).append(
            {"trial": p["trial"], "prompt": p["prompt"]})
    manifest = []
    for role, prompts in sorted(by_role.items()):
        # chunking caps prompts per subagent call (large n) and restores some
        # cross-trial independence (each chunk is a separate model call)
        chunks = ([prompts] if not chunk else
                  [prompts[i:i + chunk] for i in range(0, len(prompts), chunk)])
        for ci, part in enumerate(chunks):
            suffix = "" if len(chunks) == 1 else f".c{ci + 1}"
            bf = bdir / f"{role}{suffix}.json"
            rf = bdir / f"{role}{suffix}.reply.json"
            bf.write_text(json.dumps({
                "role": role, "reply_file": str(rf), "prompts": part},
                indent=2), encoding="utf-8")
            manifest.append({"run": run_dir.name, "round": rnd, "role": role,
                             "batch_file": str(bf), "reply_file": str(rf),
                             "n_prompts": len(part)})
    return manifest


def step(run_dirs: list[Path], chunk: int | None = None) -> dict:
    out = {"batches": [], "submitted": [], "done": []}
    for run_dir in run_dirs:
        rnd = _pending_round(run_dir)
        if rnd is not None:
            out["submitted"].append(
                {"run": run_dir.name,
                 **_merge_and_submit(run_dir, rnd)})
        polls = _engine(["next", "--dir", str(run_dir)])
        if polls.get("done"):
            report = _engine(["report", "--dir", str(run_dir)])
            out["done"].append({"run": run_dir.name, **{
                k: report[k] for k in (
                    "case", "arm", "trials", "gcr_pct", "cgc_pct",
                    "total_disasters", "avg_tokens_est_per_trial",
                    "cost_to_goal_tokens", "avg_seconds_per_trial",
                    "success", "deadlock", "max_rounds",
                    "total_gate_rejections") if k in report}})
        else:
            out["batches"].extend(_emit_batches(run_dir, polls, chunk))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["step"])
    ap.add_argument("--dir", action="append", required=True)
    ap.add_argument("--chunk", type=int, default=None)
    args = ap.parse_args()
    print(json.dumps(step([Path(d) for d in args.dir], args.chunk), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
