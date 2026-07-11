"""d1_expand.py — D1: grow the protocol set from the seeds toward >=5,000
unique valid protocols (SEAM_TRAINING_EXECUTION_PLAN.md §3/§9, W3).

Three families of operators, all deterministic given --seed:

  sweep    parameter sweeps over role count (2-6), branch width, recursion
           on/off, and guard density, across five shape generators (four
           reused verbatim from the repo: `gen_corpus.py`'s pipe/star/fan/
           negotiation shapes and `integration_stress.ProtocolGenerator`;
           one new: a parametrized N-role retry-loop shape modelled on
           experiments/cases/retry_loop/protocols/v1.scr for the recursion
           axis, since the reused generators are acyclic by construction).
  compose  compositional child-insertion via stjp_core/compiler/incremental
           .py::add_subprotocol — attaches a small 2-role child protocol to
           a random small seed (<=5 roles, to bound the EFSM re-projection
           cost) at a random valid anchor.
  crossover  validated crossover: splice a contiguous run of top-level
           messages from one ProtocolGenerator-shaped candidate into
           another of the SAME role count (so role names line up), then
           let the validator decide.

EVERY candidate is fed to the real Scribble validator
(stjp_core/compiler/validator.py, via common.validate_text) before being
kept; rejects are counted, not silently dropped. Uniqueness is decided by
signature.py's EFSM-equivalence-class signature, never by text.

Every candidate is fully self-contained (deterministic per (seed, kind,
idx) — no shared mutable generator state), so generation AND evaluation
(validate + signature, both Scribble-CLI-bound) run together inside a
thread pool (subprocess.run releases the GIL) — see --workers.

Usage:
    python d1_expand.py --target 5000 --max-candidates 20000 --seed 1 \
        -o /path/to/full/d1_dataset.jsonl --workers 4

Emits a DatasetRecord JSONL (see common.py) plus a saturation-curve JSON
(uniques found vs candidates attempted, sampled every --curve-every).
"""
from __future__ import annotations

import argparse
import json
import random
import re
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

from stjp_core.compiler.incremental import add_subprotocol               # noqa: E402
from stjp_core.compiler.refinement_checker import parse_refn_text        # noqa: E402

import gen_corpus                                                        # noqa: E402
from integration_stress import ProtocolGenerator                        # noqa: E402

from common import (validate_text, roles_of, module_stem, has_recursion, # noqa: E402
                    role_count, depth_bucket, all_seeds, DatasetRecord,
                    write_jsonl, write_sample, assert_toolchain)
from signature import SignatureCache                                     # noqa: E402

TYPES = ["String", "Double", "Int", "Bool"]
_JAVA = {"String": "java.lang.String", "Double": "java.lang.Double",
         "Int": "java.lang.Integer", "Bool": "java.lang.Boolean"}
_MSG_RE = re.compile(r'^(\s*)(\w+)\(([^)]*)\)\s+from\s+(\w+)\s+to\s+(\w+)\s*;\s*$')


def _header(module: str, proto: str, roles: list[str]) -> list[str]:
    lines = [f"module {module};", ""]
    for t in TYPES:
        lines.append(f'data <java> "{_JAVA[t]}" from "rt.jar" as {t};')
    lines.append("")
    lines.append(f"global protocol {proto}({', '.join('role ' + r for r in roles)}) {{")
    return lines


# ── shape: retry-loop (parametrized recursion axis) ─────────────────────

def retry_shape(module: str, n_roles: int, branch_width: int, rng: random.Random) -> str:
    """N-role generalisation of experiments/cases/retry_loop/protocols/v1.scr:
    a Worker reports to (n_roles-2) observers, then a Manager-like decider
    either finalises or asks for a retry, looping via `rec`/`continue`."""
    n_roles = max(3, n_roles)
    worker, manager = "Worker", "Manager"
    observers = [f"Obs{i}" for i in range(n_roles - 2)]
    roles = [worker, manager] + observers
    lines = _header(module, "Retry", roles)
    for r in [manager] + observers:
        lines.append(f"    StartTask(String) from {worker} to {r};")
    lines.append("    rec Attempt {")
    for r in [manager] + observers:
        lines.append(f"        AttemptResult(Double) from {worker} to {r};")
    lines.append(f"        choice at {manager} {{")
    for r in [worker] + observers:
        lines.append(f"            Accept(String) from {manager} to {r};")
    if branch_width >= 2 and observers:
        lines.append(f"            AuditConfirm(String) from {observers[0]} to {manager};")
    lines.append(f"            FinalSummary(String) from {manager} to {worker};")
    lines.append("        } or {")
    for r in [worker] + observers:
        lines.append(f"            Retry(String) from {manager} to {r};")
    lines.append("            continue Attempt;")
    lines.append("        }")
    lines.append("    }")
    lines.append("}")
    return "\n".join(lines) + "\n"


# ── guard density: attach a .refn sidecar to a validated candidate ──────

def _numeric_messages(text: str) -> list[tuple[str, str, str, str]]:
    """[(sender, receiver, label, type)] for top-level messages with a
    single scalar payload type this module knows how to guard."""
    out = []
    for line in text.splitlines():
        m = _MSG_RE.match(line)
        if not m:
            continue
        _, lbl, ty, a, b = m.groups()
        ty = ty.strip()
        if ty in ("Double", "Int", "String"):
            out.append((a, b, lbl, ty))
    return out


def make_refn(text: str, density: float, rng: random.Random) -> str | None:
    msgs = _numeric_messages(text)
    if density <= 0 or not msgs:
        return None
    chosen = [m for m in msgs if rng.random() < density]
    if not chosen:
        return None
    lines = ["# auto-generated D1 guard sidecar", ""]
    for a, b, lbl, ty in chosen:
        lines.append(f"[{a} -> {b} : {lbl}]")
        if ty == "String":
            lines.append("type:    str")
            lines.append("require: len(x) > 0")
        else:
            pytype = "float" if ty == "Double" else "int"
            hi = rng.choice([100, 1000, 100000])
            lines.append(f"type:    {pytype}")
            lines.append("require: x >= 0")
            lines.append(f"require: x <= {hi}")
        lines.append("")
    refn = "\n".join(lines)
    try:
        parse_refn_text(refn)
    except Exception:
        return None
    return refn


# ── sweep grid ────────────────────────────────────────────────────────

_ROLE_COUNTS = [2, 3, 4, 5, 6]
_BRANCH_WIDTHS = [1, 2, 3]
_SHAPES = ["gen", "pipe", "star", "fan", "nego", "retry"]
_GUARD_DENSITIES = [0.0, 0.5, 1.0]
_SWEEP_GRID = [
    (nr, bw, shape, gd)
    for nr in _ROLE_COUNTS for bw in _BRANCH_WIDTHS for shape in _SHAPES
    for gd in _GUARD_DENSITIES
]


def _sweep_ordinal(idx: int) -> int:
    """Map a global task index (sweep tasks occupy idx % 9 in 0..4, see
    _PATTERN) to a DENSE sweep counter 0,1,2,... Indexing the grid with the
    raw global idx aliases against the grid stride (gcd(9, |grid|) > 1) and
    silently makes whole grid regions unreachable — the first full build
    produced ZERO recursion protocols because every `retry` cell fell in the
    unreachable residue class. Dense numbering visits every cell."""
    return (idx // 9) * 5 + (idx % 9)


def gen_sweep(idx: int, seed: int):
    n_roles, bw, shape, gd = _SWEEP_GRID[_sweep_ordinal(idx) % len(_SWEEP_GRID)]
    rec_on = shape == "retry"
    rng = random.Random(f"{seed}-sweep-{idx}")
    module = f"d1s{idx:06d}"
    try:
        if shape == "retry":
            text = retry_shape(module, n_roles, bw, rng)
        elif shape == "gen":
            g = ProtocolGenerator(rng)
            roles, body = g.generate(max(2, n_roles), rng.randint(6, 12), bw)
            text = g.render(roles, body, module, "Gen")
        elif shape == "pipe":
            text = gen_corpus.pipeline(module, max(2, n_roles), rng)
        elif shape == "star":
            text = gen_corpus.star(module, max(1, n_roles - 1), rng)
        elif shape == "fan":
            text = gen_corpus.fan(module, max(1, n_roles - 2), rng)
        elif shape == "nego":
            text = gen_corpus.negotiation(module, max(3, n_roles), rng)
        else:
            return None
    except Exception:
        return None
    meta = {"operator": "sweep", "shape": shape, "role_count_target": n_roles,
            "branch_width": bw, "recursion": rec_on}
    return text, meta, gd


# ── operator: compositional child-insertion ──────────────────────────────

def gen_compose(idx: int, seed: int, seeds: list, workdir: Path):
    small_seeds = [s for s in seeds if 2 <= len(roles_of(s.text)) <= 5]
    if not small_seeds:
        return None
    rng = random.Random(f"{seed}-compose-{idx}")
    sd = rng.choice(small_seeds)
    parent_text = sd.text
    labels = [m.group(1) for m in
              (re.match(r'^\s*(\w+)\(', ln) for ln in parent_text.splitlines()) if m]
    parent_roles = roles_of(parent_text)
    if not parent_roles:
        return None
    newr = f"Ext{idx}"
    req = rng.choice(parent_roles)
    child_text = (
        f"module d1child{idx};\n\n"
        f'data <java> "java.lang.String" from "rt.jar" as String;\n\n'
        f"aux global protocol SubTask{idx}(role Requester, role Worker) {{\n"
        f"    ChildGo{idx}(String) from Requester to Worker;\n"
        f"    ChildDone{idx}(String) from Worker to Requester;\n"
        f"}}\n")
    # the parent file MUST be named after its module line: Scribble's CLI
    # resolves modules by filename, and incremental_project re-projects the
    # OLD parent file (not just the rewritten _ext/composed ones, whose
    # modules incremental.py rewrites itself). A d1parentN.scr file whose
    # module still says e.g. `corpus_011` fails every `-fsm` call — this
    # exact mismatch made the compose operator yield 0 records in the first
    # full build (all attempts landed in `operator_not_applicable`).
    parent_path = workdir / f"{module_stem(parent_text)}.scr"
    parent_path.write_text(parent_text, encoding="utf-8")
    child_path = workdir / f"d1child{idx}.scr"
    child_path.write_text(child_text, encoding="utf-8")
    anchor = "end"
    if labels and rng.random() < 0.6:
        anchor = f"after:{rng.choice(labels)}"
    try:
        result = add_subprotocol(parent_path, child_path, [req, newr],
                                 anchor=anchor, output_dir=workdir)
    except Exception:
        return None
    if not result.success or not result.composed_path:
        return None
    text = result.composed_path.read_text(encoding="utf-8")
    meta = {"operator": "compose", "seed_case": sd.seed_case,
            "anchor": anchor, "new_role": newr}
    return text, meta, 0.0


# ── operator: validated crossover of same-shape fragments ───────────────

def _depths(text: str):
    depth = 0
    out = []
    for i, line in enumerate(text.splitlines()):
        out.append((i, line, depth))
        depth += line.count("{") - line.count("}")
    return out


def _top_msg_indices(text: str) -> list[int]:
    return [i for i, ln, d in _depths(text) if d == 1 and _MSG_RE.match(ln)]


def crossover(a_text: str, b_text: str, rng: random.Random) -> str | None:
    a_idx = _top_msg_indices(a_text)
    b_idx = _top_msg_indices(b_text)
    if len(a_idx) < 2 or len(b_idx) < 2:
        return None
    a_lines = a_text.splitlines()
    b_lines = b_text.splitlines()
    k = rng.randint(1, min(3, len(b_idx)))
    start = rng.randrange(0, len(b_idx) - k + 1)
    run = [b_lines[b_idx[i]] for i in range(start, start + k)]
    insert_at = a_idx[rng.randrange(len(a_idx))]
    new_lines = a_lines[:insert_at] + run + a_lines[insert_at:]
    stem = f"{module_stem(a_text)}_x_{module_stem(b_text)}"
    text = "\n".join(new_lines) + "\n"
    text = re.sub(r"module\s+[\w.]+\s*;", f"module {stem};", text, count=1)
    return text


def gen_crossover(idx: int, seed: int):
    rng = random.Random(f"{seed}-crossover-{idx}")
    n_roles = rng.choice([3, 4, 5, 6])
    outs = []
    for k in range(2):
        g = ProtocolGenerator(rng)
        roles, body = g.generate(n_roles, rng.randint(6, 12), rng.randint(1, 2))
        outs.append(g.render(roles, body, f"d1cx{idx:06d}{k}", "Gen"))
    text = crossover(outs[0], outs[1], rng)
    if not text:
        return None
    meta = {"operator": "crossover", "role_count_target": n_roles}
    return text, meta, 0.0


# ── per-task worker: generate + validate + sign, all off the main thread ─

_PATTERN = ["sweep"] * 5 + ["compose"] * 2 + ["crossover"] * 2


def _run_task(idx: int, seed: int, seeds: list, sig_cache: SignatureCache) -> dict:
    kind = _PATTERN[idx % len(_PATTERN)]
    with tempfile.TemporaryDirectory() as td:
        wd = Path(td)
        if kind == "sweep":
            r = gen_sweep(idx, seed)
        elif kind == "compose":
            r = gen_compose(idx, seed, seeds, wd)
        else:
            r = gen_crossover(idx, seed)
        if r is None:
            return {"kind": kind, "ok": False, "reason": "operator_not_applicable"}
        text, meta, gd = r
        cached_sig = sig_cache.get_cached(text)
        if cached_sig is not None:
            # text-hash dedupe BEFORE validation: a cached signature implies
            # this exact (whitespace-normalized) text validated once already
            # — don't pay the Scribble JVM again just to rediscover a dup.
            refn = make_refn(text, gd, random.Random(f"{seed}-refn-{idx}")) if gd else None
            return {"kind": kind, "ok": True, "text": text, "refn": refn,
                    "meta": meta, "sig": cached_sig}
        vr = validate_text(text, workdir=wd)
        if not vr.ok:
            return {"kind": kind, "ok": False, "reason": "validator_rejected",
                    "meta": meta}
        refn = make_refn(text, gd, random.Random(f"{seed}-refn-{idx}")) if gd else None
        # validate_text() just ran the real Scribble-java CLI on this exact
        # text and it passed — assume_valid=True skips signature.py's
        # internal re-validate round-trip so we don't pay for the same JVM
        # call twice per kept candidate.
        sig = sig_cache.signature(text, assume_valid=True)
        return {"kind": kind, "ok": True, "text": text, "refn": refn,
                "meta": meta, "sig": sig}


def build(target: int, max_candidates: int, seed: int, workers: int,
         curve_every: int, cache_path: Path | None,
         checkpoint_path: Path | None = None,
         checkpoint_every_s: float = 30.0) -> tuple[list[DatasetRecord], dict]:
    seeds = all_seeds()
    sig_cache = SignatureCache(cache_path)

    records: list[DatasetRecord] = []
    seen_sigs: set[str] = set()
    attempted = rejected = duplicates = not_applicable = 0
    curve: list[dict] = []
    op_counts: dict[str, int] = {}
    t0 = time.time()

    idx = 0
    last_ckpt = time.time()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        inflight = {}
        while len(records) < target and (attempted < max_candidates or inflight):
            while len(inflight) < workers * 3 and attempted + len(inflight) < max_candidates:
                fut = pool.submit(_run_task, idx, seed, seeds, sig_cache)
                inflight[fut] = idx
                idx += 1
            if not inflight:
                break
            done_set = set()
            for fut in as_completed(list(inflight), timeout=None):
                done_set.add(fut)
                break  # process one at a time to keep the loop responsive
            for fut in done_set:
                inflight.pop(fut)
                attempted += 1
                res = fut.result()
                op_counts[res["kind"]] = op_counts.get(res["kind"], 0) + 1
                if not res["ok"]:
                    if res["reason"] == "operator_not_applicable":
                        not_applicable += 1
                    else:
                        rejected += 1
                    continue
                sig = res["sig"]
                if sig in seen_sigs:
                    duplicates += 1
                    continue
                seen_sigs.add(sig)
                meta = res["meta"]
                text = res["text"]
                rid = f"d1-{len(records):06d}"
                rec = DatasetRecord(
                    id=rid, family=sig, split="unassigned", intent=None,
                    protocol=text, refn=res["refn"], source="synthetic",
                    seed_case=meta.get("seed_case", f"d1:{meta['operator']}"),
                    gen={**meta, "role_count": role_count(text),
                         "has_recursion": has_recursion(text),
                         "depth_bucket": depth_bucket(text)},
                    provenance=None)
                records.append(rec)
            if attempted % curve_every < workers:
                point = {"candidates": attempted, "uniques": len(records),
                        "rejected": rejected, "duplicates": duplicates,
                        "not_applicable": not_applicable,
                        "elapsed_s": round(time.time() - t0, 1)}
                curve.append(point)
                rate = attempted / max(1e-9, time.time() - t0)
                print(f"[d1] candidates={attempted} uniques={len(records)} "
                      f"rejected={rejected} dup={duplicates} n/a={not_applicable} "
                      f"rate={rate:.2f}/s elapsed={point['elapsed_s']}s", flush=True)
            if checkpoint_path and time.time() - last_ckpt > checkpoint_every_s:
                write_jsonl(checkpoint_path, records)
                sig_cache.save()
                last_ckpt = time.time()
        for fut in list(inflight):
            fut.cancel()

    elapsed = time.time() - t0
    stats = {
        "target": target, "max_candidates": max_candidates, "seed": seed,
        "workers": workers,
        "candidates_attempted": attempted, "uniques_found": len(records),
        "validator_rejected": rejected, "signature_duplicates": duplicates,
        "operator_not_applicable": not_applicable,
        "elapsed_seconds": round(elapsed, 1),
        "candidates_per_second": round(attempted / elapsed, 3) if elapsed else None,
        "operator_breakdown": op_counts,
        "saturation_curve": curve,
    }
    sig_cache.save()
    return records, stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--target", type=int, default=5000)
    ap.add_argument("--max-candidates", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--curve-every", type=int, default=25)
    ap.add_argument("-o", "--out", default=str(HERE / "samples" / "d1_dataset.full.jsonl"))
    ap.add_argument("--stats-out", default=None)
    ap.add_argument("--cache", default=str(HERE / ".sig_cache.json"))
    args = ap.parse_args(argv)

    assert_toolchain()   # fail loud, not with 100% silent rejects
    out_path = Path(args.out)
    records, stats = build(args.target, args.max_candidates, args.seed,
                           args.workers, args.curve_every,
                           Path(args.cache) if args.cache else None,
                           checkpoint_path=out_path)
    write_jsonl(out_path, records)
    stats_path = Path(args.stats_out) if args.stats_out else out_path.with_suffix(".stats.json")
    stats_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(f"[d1] {stats['uniques_found']} unique families from "
          f"{stats['candidates_attempted']} candidates "
          f"({stats['validator_rejected']} rejected, "
          f"{stats['signature_duplicates']} duplicate) in "
          f"{stats['elapsed_seconds']}s -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
