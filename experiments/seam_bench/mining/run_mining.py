"""run_mining.py — end-to-end D5 mining run over every reachable source.

Usage:
    python run_mining.py --out-dir <dir> [--remote-checkout DIR=REPO ...]

Sources wired in by default:
    - local-vendored: experiments/cases/skills_safety/*/skills_original/
      (always available, no network).
    - remote checkouts, if present on disk (this task's harvest used git
      clones staged under a scratch directory — see
      docs/reference/reports/seam/W8_miner.md for the exact commands and
      probe results):
        github/awesome-copilot                 (copilot_style adapter)
        VoltAgent/awesome-claude-code-subagents (skill_dir_style adapter)
        anthropics/skills                      (skill_dir_style adapter)

If a remote checkout directory does not exist, that source is skipped (not
an error) and the skip is recorded in the run's stdout summary — this
script must run to completion using ONLY the local-vendored source with no
network access, per the task's "if remote harvest is blocked, proceed with
local material" instruction.

Writes:
    <out-dir>/ledger.jsonl          one LedgerEntry per harvested artifact
    <out-dir>/dataset_records.jsonl every emitted DatasetRecord (test-real)
    <out-dir>/funnel.json           FunnelStats.to_json()
    <out-dir>/team_results.jsonl    one line per team attempted, with the
                                     stage it reached and (on failure) why
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
for p in (str(REPO_ROOT), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

from harvest import (                                             # noqa: E402
    Artifact, adapter_copilot_style, adapter_skill_dir_style,
    adapter_local_vendored, adapter_crewai_style)
from ledger import build_ledger, to_json as ledger_to_json         # noqa: E402
from team_builder import build_teams                               # noqa: E402
from formalize import run_formalize, assert_toolchain, ToolchainMissing  # noqa: E402
from schema import write_jsonl                                     # noqa: E402

DEFAULT_REMOTES = {
    # label -> (checkout_dir, source_repo, adapter_name)
    "awesome-copilot": ("awesome-copilot", "github/awesome-copilot", "copilot"),
    "VoltAgent": ("VoltAgent", "VoltAgent/awesome-claude-code-subagents", "skilldir"),
    "anthropic-skills": ("anthropic-skills", "anthropics/skills", "skilldir"),
    # W17 additions (R3's item 2.d, "if still short of target"):
    "crewAI-core": ("crewAI-core", "crewAIInc/crewAI", "crewai"),
    "crewAI-examples": ("crewAI-examples", "crewAIInc/crewAI-examples", "crewai"),
    # W17 fallback source (74 candidates from a-c+crewai fell short of the
    # ~100 coordination-requiring target; probed reachable, Apache-2.0
    # confirmed via root LICENSE file):
    "rohitg00-toolkit": ("rohitg00-toolkit", "rohitg00/awesome-claude-code-toolkit", "skilldir"),
}


def harvest_all(remote_root: Path | None) -> list[Artifact]:
    artifacts: list[Artifact] = []

    cases_dir = REPO_ROOT / "experiments" / "cases" / "skills_safety"
    vendored = adapter_local_vendored(cases_dir)
    artifacts.extend(vendored)
    print(f"[harvest] local_vendored: {len(vendored)} artifacts from {cases_dir}")

    for label, (subdir, repo, kind) in DEFAULT_REMOTES.items():
        if remote_root is None:
            print(f"[harvest] SKIPPED {label} ({repo}) — no --remote-root given")
            continue
        checkout = remote_root / subdir
        if not checkout.is_dir():
            print(f"[harvest] SKIPPED {label} ({repo}) — {checkout} does not exist "
                  f"(remote not staged; this is not an error, see W8_miner.md probe)")
            continue
        if kind == "copilot":
            found = adapter_copilot_style(checkout, repo)
        elif kind == "crewai":
            found = adapter_crewai_style(checkout, repo)
        else:
            found = adapter_skill_dir_style(checkout, repo)
        artifacts.extend(found)
        print(f"[harvest] {label} ({repo}): {len(found)} artifacts from {checkout}")

    return artifacts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--remote-root", type=Path, default=None,
                    help="directory containing awesome-copilot/, VoltAgent/, "
                         "anthropic-skills/ checkouts (git clones); omit to "
                         "run local-vendored-only")
    args = ap.parse_args(argv)

    print("[mining] checking real Scribble toolchain (fail-loud) ...")
    try:
        assert_toolchain()
    except ToolchainMissing as e:
        print(f"[mining] FATAL: {e}", file=sys.stderr)
        return 2
    print("[mining] toolchain OK")

    artifacts = harvest_all(args.remote_root)
    print(f"[mining] total harvested: {len(artifacts)}")

    ledger = build_ledger(artifacts)
    n_quarantined = sum(1 for e in ledger.values() if e.quarantined)
    print(f"[mining] ledger: {len(ledger)} entries, {n_quarantined} quarantined")

    team_result = build_teams(artifacts)
    print(f"[mining] teams: {len(team_result.teams)} formed, "
          f"{len(team_result.unteamed)} artifacts unteamed, "
          f"{len(team_result.skipped_too_large)} directories skipped (too large)")

    records, funnel, results = run_formalize(artifacts, team_result.teams, ledger)
    print(f"[mining] DatasetRecords emitted: {len(records)}")
    print(json.dumps(funnel.to_json(), indent=2))

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    with (out_dir / "ledger.jsonl").open("w", encoding="utf-8") as f:
        for entry in ledger.values():
            f.write(json.dumps(ledger_to_json(entry), sort_keys=True, ensure_ascii=False) + "\n")

    write_jsonl(out_dir / "dataset_records.jsonl", records)

    with (out_dir / "team_results.jsonl").open("w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps({
                "team_id": r.team.team_id,
                "source_repo": r.team.source_repo,
                "heuristic": r.team.heuristic,
                "roles": r.team.role_names,
                "stage_reached": r.stage_reached,
                "ok": r.ok,
                "error": (r.error or "")[:500],
            }, sort_keys=True, ensure_ascii=False) + "\n")

    (out_dir / "funnel.json").write_text(
        json.dumps({
            "funnel": funnel.to_json(),
            "n_artifacts_harvested": len(artifacts),
            "n_teams": len(team_result.teams),
            "n_unteamed": len(team_result.unteamed),
            "n_dirs_skipped_too_large": len(team_result.skipped_too_large),
            "n_records_emitted": len(records),
        }, indent=2, sort_keys=True), encoding="utf-8")

    print(f"[mining] wrote outputs to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
