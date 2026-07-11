"""d3_repair.py — D3: mutation-based repair tuples (SEAM_TRAINING_EXECUTION_
PLAN.md §3/§9, W3).

For each gold protocol, apply the repo's mutation operators, run the real
Scribble validator, and split the outcome two ways:

  - validator REJECTS the mutant  -> a RepairRecord: (intent, broken,
    counterexample, gold, operator). `counterexample` is the validator's
    error string **verbatim** — the model learns to read the checker, not
    to guess (SEAM_AUTOTRAINING_PLAN.md §2 A4).
  - validator still ACCEPTS the mutant (a semantic near-miss) -> NOT
    repair data; written to samples/calibration_candidates.jsonl for the
    W6/W7 judge-calibration pipeline (§6).

Two operator families, both genuinely imported (never copied):

  text     the 7 general-purpose text-level operators in
           experiments/scripts/mutate_protocol.py (circular_wait,
           swap_order, drop_message, rewire_peer, undeclare_role,
           branch_asymmetry, flip_branch_subject) — already the repo's
           established mutation surface for arbitrary .scr text (used by
           mutation_bench.py / translation_fidelity.py). Runs against
           ANY gold protocol regardless of provenance (seed corpus, named
           case, or D1-expanded).
  local    the 5 LocalType-level operators named explicitly in the W3 task
           card, `experiments/scripts/integration_stress.py::s2_mutation`
           (drop_receive, retype_payload, swap_fifo, reroute_peer,
           rename_label). These operate on a per-role LocalType AST, which
           only exists for protocols this module generates itself via
           `integration_stress.ProtocolGenerator` (there is no general
           .scr-text -> LocalType projector in the repo — global->local
           synthesis only runs the other direction). `s2_mutation`'s
           mutation-selection logic was extracted into a pure function,
           `apply_local_mutation`, in that module (see its docstring) so
           this file can import it instead of duplicating the operator
           bodies; `s2_mutation` itself is unchanged (same RNG order),
           so integration_stress.py's seeded suite is unaffected.

Every gold needs a non-null `intent` (the RepairRecord schema requires
one, unlike DatasetRecord's nullable field). Preference order: (1) a real
D2 back-translated intent, if `--intents-jsonl` (mapping family -> intent)
is supplied; (2) the named case's human-written `case.yaml` description,
for seeds that have one; (3) a deterministic templated stub built from
role/label names (Scribble-vocabulary-free prose, never real training
data — flagged `intent_source: "stub"` is NOT recorded in the fixed
RepairRecord schema, so it is logged in the run stats instead).

Usage:
    python d3_repair.py --target 20000 --max-mutations 60000 --seed 1 \
        --gold-jsonl /path/to/d1_dataset.full.jsonl \
        -o /path/to/full/d3_repair.jsonl --workers 4
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
SCRIPTS_DIR = REPO_ROOT / "experiments" / "scripts"
for p in (REPO_ROOT, SCRIPTS_DIR, HERE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from stjp_core.compiler.validator import ScribbleValidator               # noqa: E402
from stjp_core.compiler.global_synthesizer import (                      # noqa: E402
    synthesize_global, SynthesisError)

from mutate_protocol import mutate, CLASSES as TEXT_OPERATORS            # noqa: E402
from integration_stress import ProtocolGenerator, apply_local_mutation, \
    MUTATIONS as LOCAL_OPERATORS                                        # noqa: E402

from common import (roles_of, module_stem, all_seeds, case_intent,       # noqa: E402
                    DatasetRecord, RepairRecord, write_jsonl, read_jsonl,
                    assert_toolchain)
from signature import SignatureCache                                     # noqa: E402

ALL_OPERATORS = list(TEXT_OPERATORS) + list(LOCAL_OPERATORS)

# per-operator yield-table row template. `applied` counts mutants that
# reached the Scribble validator; `rejected` of those became RepairRecords;
# `validator_passed` became calibration candidates; `synthesis_rejected`
# (local family only) died in global_synthesizer before any text existed;
# `not_applicable` = the operator produced nothing for the drawn gold.
_PER_OP_ZERO = {"applied": 0, "rejected": 0, "validator_passed": 0,
                "synthesis_rejected": 0, "not_applicable": 0}


# ── intent recovery (no gold Scribble vocabulary leaks into the stub) ───

def stub_intent(text: str, seed_case: str) -> tuple[str, str]:
    ci = case_intent(seed_case)
    if ci:
        return ci, "case_description"
    rs = roles_of(text)
    labels = []
    import re
    for line in text.splitlines():
        m = re.match(r'^\s*(\w+)\([^)]*\)\s+from\s+(\w+)\s+to\s+(\w+)\s*;', line)
        if m:
            labels.append(m.group(1))
    first = labels[0] if labels else "an initial handoff"
    last = labels[-1] if labels else "a final confirmation"
    party_list = ", ".join(rs[:-1]) + (f" and {rs[-1]}" if len(rs) > 1 else rs[0] if rs else "the participants")
    return (f"Coordinate {party_list} through a multi-step exchange that "
            f"starts with {first} and ends with {last}."), "stub"


# ── gold pool ─────────────────────────────────────────────────────────

def load_golds(gold_jsonl: Path | None, use_seeds: bool, seed: int,
               n_generated: int) -> list[dict]:
    """Each gold: {text, seed_case, family, has_lts, lts (optional)}."""
    golds: list[dict] = []
    if use_seeds:
        for s in all_seeds():
            golds.append({"text": s.text, "seed_case": s.seed_case,
                         "has_lts": False, "lts": None})
    if gold_jsonl and gold_jsonl.exists():
        for row in read_jsonl(gold_jsonl):
            golds.append({"text": row["protocol"], "seed_case": row.get("seed_case", "d1"),
                         "has_lts": False, "lts": None})
    # a dedicated LocalType-bearing pool for the "local" operator family —
    # freshly generated here (see module docstring: no general .scr->
    # LocalType projector exists in the repo).
    rng = random.Random(f"{seed}-lts-pool")
    for i in range(n_generated):
        g = ProtocolGenerator(rng)
        n_roles = rng.randint(3, 6)
        roles, body = g.generate(n_roles, rng.randint(6, 12), rng.randint(1, 2))
        text = g.render(roles, body, f"d3lts{i:05d}", "Gen")
        lts = g.project(roles, body)
        golds.append({"text": text, "seed_case": f"d3:generated:{i}",
                     "has_lts": True, "lts": lts})
    return golds


def clean_counterexample(err: str) -> str:
    """The validator's error string, verbatim EXCEPT for one environment
    artifact: this sandbox's JVM prints a 'Picked up JAVA_TOOL_OPTIONS: ...'
    banner on stderr (proxy/truststore config — see the NOTE in
    tools/setup_scribble_cloud.sh). That line is launcher noise, not part
    of Scribble's verdict, and it leaks host-specific proxy details into
    training data — drop exactly those lines, keep everything else."""
    return "\n".join(l for l in err.splitlines()
                     if not l.startswith("Picked up JAVA_TOOL_OPTIONS")).strip()


# ── per-task worker ───────────────────────────────────────────────────

def _mutate_text_op(gold_text: str, op: str, rng: random.Random) -> str | None:
    return mutate(gold_text, op, rng)


def _mutate_local_op(lts: dict, rng: random.Random) -> tuple[str | None, str]:
    mutated, role, kind = apply_local_mutation(rng, lts)
    try:
        result = synthesize_global(mutated, protocol_name="Mut",
                                   module_name=f"mut{rng.randint(0, 1_000_000)}")
    except SynthesisError as e:
        return None, kind
    return result.protocol_text, kind


def _run_task(idx: int, seed: int, gold: dict, op: str,
             sig_cache: SignatureCache, intents: dict[str, str] | None
             ) -> dict:
    rng = random.Random(f"{seed}-mut-{idx}-{op}")
    gold_text = gold["text"]
    if op in TEXT_OPERATORS:
        mutant = _mutate_text_op(gold_text, op, rng)
        actual_op = op
        if mutant is None:
            return {"ok": False, "reason": "not_applicable", "operator": actual_op}
    else:
        if not gold["has_lts"]:
            return {"ok": False, "reason": "not_applicable", "operator": op}
        mutant, actual_op = _mutate_local_op(gold["lts"], rng)
        if mutant is None:
            # the mutated LocalTypes no longer compose into ANY global type
            # — global_synthesizer caught the defect upstream of Scribble
            # (the `caught_by=synthesis` layer in integration_stress terms).
            # No protocol text exists to put in `broken`, so this cannot be
            # a repair tuple; it is counted per-operator so the yield table
            # shows where the local-op family's mutants die.
            return {"ok": False, "reason": "synthesis_rejected",
                    "operator": actual_op}

    with tempfile.TemporaryDirectory() as td:
        wd = Path(td)
        stem = module_stem(mutant)
        p = wd / f"{stem}.scr"
        p.write_text(mutant, encoding="utf-8")
        ok, err = ScribbleValidator().validate_protocol(p)

    # golds are known-valid (corpus/named-case files, or D1 outputs that were
    # validated at generation); assume_valid skips a redundant validate JVM
    # call, and a genuinely-invalid gold still fails loudly inside `-fsm`
    # projection (SignatureError). Cached by text hash after the first call
    # per gold, so repeated mutations of one gold cost zero extra JVMs here.
    family = sig_cache.signature(gold_text, assume_valid=True)

    intent, intent_source = None, None
    if intents and family in intents:
        intent, intent_source = intents[family], "d2"
    else:
        intent, intent_source = stub_intent(gold_text, gold["seed_case"])

    if not ok:
        return {"ok": True, "kind": "repair", "operator": actual_op,
                "family": family, "gold": gold_text, "broken": mutant,
                "counterexample": clean_counterexample(err), "intent": intent,
                "intent_source": intent_source, "seed_case": gold["seed_case"]}
    else:
        return {"ok": True, "kind": "calibration", "operator": actual_op,
                "family": family, "gold": gold_text, "mutant": mutant,
                "intent": intent, "intent_source": intent_source,
                "seed_case": gold["seed_case"]}


def build(target: int, max_mutations: int, seed: int, workers: int,
         gold_jsonl: Path | None, use_seeds: bool, n_generated: int,
         intents_jsonl: Path | None, cache_path: Path | None,
         progress_every: int = 50, checkpoint_path: Path | None = None,
         checkpoint_every_s: float = 30.0
         ) -> tuple[list[RepairRecord], list[dict], dict]:
    golds = load_golds(gold_jsonl, use_seeds, seed, n_generated)
    sig_cache = SignatureCache(cache_path)
    intents = None
    if intents_jsonl and intents_jsonl.exists():
        intents = {}
        for row in read_jsonl(intents_jsonl):
            if row.get("family") and row.get("intent"):
                intents.setdefault(row["family"], row["intent"])

    repairs: list[RepairRecord] = []
    calibration: list[dict] = []
    attempted = not_applicable = synthesis_rejected = 0
    per_op: dict[str, dict[str, int]] = {op: dict(_PER_OP_ZERO)
                                        for op in ALL_OPERATORS}
    t0 = time.time()
    last_ckpt = time.time()

    rng_task = random.Random(seed)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        idx = 0
        inflight = {}
        while len(repairs) < target and (attempted < max_mutations or inflight):
            while len(inflight) < workers * 3 and attempted + len(inflight) < max_mutations:
                gold = golds[idx % len(golds)]
                # draw the operator from the family that can actually apply
                # to this gold — sampling local (LocalType-level) ops against
                # golds that carry no LocalTypes burned ~40% of the first
                # run's mutation budget as guaranteed not_applicable.
                pool_ops = ALL_OPERATORS if gold["has_lts"] else TEXT_OPERATORS
                op = pool_ops[rng_task.randrange(len(pool_ops))]
                fut = pool.submit(_run_task, idx, seed, gold, op, sig_cache, intents)
                inflight[fut] = idx
                idx += 1
            if not inflight:
                break
            for fut in as_completed(list(inflight), timeout=None):
                inflight.pop(fut)
                attempted += 1
                res = fut.result()
                if not res["ok"]:
                    op = res.get("operator", "?")
                    per_op.setdefault(op, dict(_PER_OP_ZERO))
                    if res["reason"] == "synthesis_rejected":
                        per_op[op]["synthesis_rejected"] += 1
                        synthesis_rejected += 1
                    else:
                        per_op[op]["not_applicable"] += 1
                        not_applicable += 1
                    break
                op = res["operator"]
                per_op.setdefault(op, dict(_PER_OP_ZERO))
                per_op[op]["applied"] += 1
                if res["kind"] == "repair":
                    per_op[op]["rejected"] += 1
                    rid = f"d3-{len(repairs):06d}"
                    repairs.append(RepairRecord(
                        id=rid, family=res["family"], split="unassigned",
                        intent=res["intent"], broken=res["broken"],
                        counterexample=res["counterexample"], gold=res["gold"],
                        operator=op))
                else:
                    per_op[op]["validator_passed"] += 1
                    calibration.append({
                        "id": f"d3cal-{len(calibration):06d}", "family": res["family"],
                        "seed_case": res["seed_case"], "operator": op,
                        "gold": res["gold"], "mutant": res["mutant"],
                        "intent": res["intent"], "intent_source": res["intent_source"],
                    })
                if attempted % progress_every < 1:
                    rate = attempted / max(1e-9, time.time() - t0)
                    print(f"[d3] mutations={attempted} repairs={len(repairs)} "
                          f"calibration={len(calibration)} n/a={not_applicable} "
                          f"rate={rate:.2f}/s elapsed={time.time()-t0:.0f}s", flush=True)
                if checkpoint_path and time.time() - last_ckpt > checkpoint_every_s:
                    write_jsonl(checkpoint_path, repairs)
                    sig_cache.save()
                    last_ckpt = time.time()
                break
        for fut in list(inflight):
            fut.cancel()

    elapsed = time.time() - t0
    stats = {
        "target": target, "max_mutations": max_mutations, "seed": seed,
        "workers": workers, "n_golds": len(golds),
        "golds_with_lts": sum(1 for g in golds if g["has_lts"]),
        "mutations_attempted": attempted,
        "repair_records": len(repairs), "calibration_candidates": len(calibration),
        "not_applicable": not_applicable,
        "synthesis_rejected": synthesis_rejected,
        "elapsed_seconds": round(elapsed, 1),
        "mutations_per_second": round(attempted / elapsed, 3) if elapsed else None,
        "per_operator_yield": per_op,
    }
    sig_cache.save()
    return repairs, calibration, stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--target", type=int, default=20000)
    ap.add_argument("--max-mutations", type=int, default=80000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--gold-jsonl", default=None,
                    help="D1 DatasetRecord JSONL to draw additional golds from")
    ap.add_argument("--no-seeds", action="store_true",
                    help="exclude the 51 corpus+named-case seeds from the gold pool")
    ap.add_argument("--n-generated", type=int, default=60,
                    help="freshly-generated LocalType-bearing golds for the "
                         "s2_mutation-family operators")
    ap.add_argument("--intents-jsonl", default=None,
                    help="D2 output; family -> intent lookup")
    ap.add_argument("-o", "--out", default=str(HERE / "samples" / "d3_repair.full.jsonl"))
    ap.add_argument("--calibration-out", default=None)
    ap.add_argument("--stats-out", default=None)
    ap.add_argument("--cache", default=str(HERE / ".sig_cache.json"))
    args = ap.parse_args(argv)

    assert_toolchain()   # fail loud, not with fake counterexamples
    out_path = Path(args.out)
    repairs, calibration, stats = build(
        args.target, args.max_mutations, args.seed, args.workers,
        Path(args.gold_jsonl) if args.gold_jsonl else None,
        not args.no_seeds, args.n_generated,
        Path(args.intents_jsonl) if args.intents_jsonl else None,
        Path(args.cache) if args.cache else None,
        checkpoint_path=out_path)

    write_jsonl(out_path, repairs)
    cal_path = Path(args.calibration_out) if args.calibration_out else \
        out_path.parent / "calibration_candidates.full.jsonl"
    write_jsonl(cal_path, calibration)
    stats_path = Path(args.stats_out) if args.stats_out else out_path.with_suffix(".stats.json")
    stats_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")

    print(f"[d3] {stats['repair_records']} repair records + "
          f"{stats['calibration_candidates']} calibration candidates from "
          f"{stats['mutations_attempted']} mutation attempts over "
          f"{stats['n_golds']} golds in {stats['elapsed_seconds']}s -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
