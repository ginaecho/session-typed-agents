"""Emit DatasetRecord(source="mined", split="test-real") for every team that
reached validator_passed in extraction.py's run. Requires extraction.py to
have already been run against the same --scratch-dir (so annotated/ +
pipeline_out/ are populated).

Usage:
    python -m experiments.seam_bench.mining.llm_read.emit_records \\
        --remote-root <...> --scratch-dir <same dir extraction.py used>
"""
from __future__ import annotations
import argparse
import sys, json, hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[3]
MINING = HERE.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(MINING))

from run_mining import harvest_all
from team_builder import build_teams
from ledger import build_ledger
from intent_extract import extract_intent
from schema import DatasetRecord, write_jsonl
from slug_util import sanitize  # length-capped: keeps filenames portable on Windows
from stjp_core.generation.skill_compactor import compact_and_synthesize

WINNERS = {
  0: ("pr_merge__reduced_Author_Merger", ["Author", "Merger"]),
  1: ("content_pipeline__full", ["Researcher", "Writer", "Editor", "Publisher"]),
  2: ("airline_seat__full", ["Triage", "SeatBooking", "FlightSystem"]),
}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--remote-root", type=Path, default=None)
    ap.add_argument("--scratch-dir", type=Path, required=True)
    args = ap.parse_args()
    scratch = args.scratch_dir
    annot = scratch / "annotated"
    out_dir = scratch / "pipeline_out"

    artifacts = harvest_all(args.remote_root)
    by_id = {a.artifact_id: a for a in artifacts}
    ledger = build_ledger(artifacts)
    intents = {aid: extract_intent(a) for aid, a in by_id.items()}
    team_result = build_teams(artifacts)
    teams = team_result.teams

    records = []
    for i, (reduced_id, kept_roles) in WINNERS.items():
        t = teams[i]
        team_dir = annot / sanitize(t.team_id)
        out_scr = out_dir / f"{i:02d}_{sanitize(t.team_id)}.scr"
        result = compact_and_synthesize(team_dir, out_scr, protocol_name="Team%d" % i,
                                        llm_client=None, save_local_types=True)
        assert result.valid, (i, result.error)

        by_role = {a.role_hint: a for aid in t.artifact_ids for a in [by_id[aid]]}
        kept_ids = [by_role[r].artifact_id for r in kept_roles]

        parts = []
        n_human = 0
        for aid in kept_ids:
            it = intents.get(aid)
            if it is not None and it.text:
                n_human += 1
                parts.append(it.text.strip())
        team_intent = " ".join(parts) if parts else None
        intent_source = "human" if n_human == len(kept_ids) else ("mixed" if n_human else "needs-reverse-engineering")

        protocol_text = result.protocol_text
        family_hash = hashlib.sha256(protocol_text.encode("utf-8")).hexdigest()[:16]
        dropped_roles = [r for r in t.role_names if r not in kept_roles]
        record = DatasetRecord(
            id=f"mined:llm_read:{t.team_id}",
            family=family_hash,
            split="test-real",
            intent=team_intent,
            protocol=protocol_text,
            refn=None,
            source="mined",
            seed_case=t.team_id,
            gen={
                "family_placeholder": True,
                "family_todo": "sha256(protocol_text)[:16] placeholder, see W8_miner.md",
                "synthesis_mode": result.synthesis_mode,
                "compactor_mode": "no-llm (block-annotated copies; blocks were written by the W16 human/LLM extraction pass, not by the skill author)",
                "team_heuristic": t.heuristic,
                "extraction_method": "llm_read_extraction",
                "extraction_worker": "W16",
                "roles_in_original_team": t.role_names,
                "roles_kept_after_extraction": kept_roles,
                "roles_dropped_no_evidence": dropped_roles,
            },
            provenance={
                "intent_source": intent_source,
                "team_id": t.team_id,
                "source_repo": t.source_repo,
                "roles": kept_roles,
                "note": "protocol was NOT authored by the skill's original writer; the "
                        "fenced localtype block per role was written by W16 (LLM-read "
                        "extraction) from evidence quotes recorded in "
                        "experiments/seam_bench/mining/samples/llm_read_evidence/"
                        f"{i:02d}_{sanitize(t.team_id)}.json -- see that file for the "
                        "verbatim quote backing every send/receive edge.",
                "artifacts": [
                    {
                        "artifact_id": aid,
                        "path": by_id[aid].path,
                        "source_repo": ledger[aid].source_repo,
                        "license_spdx": ledger[aid].license_spdx,
                        "commit_sha": ledger[aid].commit_sha,
                        "retrieval_route": ledger[aid].retrieval_route,
                    }
                    for aid in kept_ids
                ],
            },
        )
        records.append(record)

    out_path = MINING / "samples" / "llm_read_dataset_records.jsonl"
    n = write_jsonl(out_path, records)
    print(f"wrote {n} records to {out_path}")

if __name__ == "__main__":
    main()
