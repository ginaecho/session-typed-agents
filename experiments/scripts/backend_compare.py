"""backend_compare.py — scribble-java vs coinductive nuscr, rigorously.

Compares the two MPST backends on the SAME correctly-named mutants, so no
verdict is an artifact of a filename/module-name mismatch (the bug that
corrupted the first ad-hoc comparison on 2026-07-28).

For every corpus protocol:
  1. baseline: validate the ORIGINAL with both backends (must be valid → any
     rejection here is a FALSE POSITIVE for that backend).
  2. per mutation class (the reorder/deadlock ops), apply the mutation, write it
     to `<module>.scr` (filename == module declaration), validate with both.
     A backend that REJECTS the mutant "caught" it.

Reports per class: applied, scribble caught, nuscr caught. Higher caught = more
sensitive to injected faults. NOTE (honest): some reorder mutants are
equivalent-valid (not real deadlocks), so accepting them is correct — this is
why "caught" is a sensitivity measure, not a pure accuracy score. The
meaningful signal is the DELTA between backends on the same inputs.

Usage: python scripts/backend_compare.py [n_corpus] [classes...]
  python scripts/backend_compare.py 30 circular_wait swap_order drop_message rewire_peer
"""
import glob
import json
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(EXP))
sys.path.insert(0, str(EXP.parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from stjp_core.compiler.validator import ScribbleValidator
from stjp_core.compiler.nuscr_compiler import NuscrCompiler
from mutate_protocol import mutate

OUT = EXP / "reports" / "backend_compare.json"
TMP = EXP / ".tmp_backend_compare"


def module_of(text: str) -> str:
    m = re.search(r"module\s+(\w+)", text)
    return m.group(1) if m else "v1"


# nuscr emits these when it CANNOT ANALYSE a protocol (tool limitation / parse
# / infra) — as opposed to a genuine well-formedness rejection. Miscounting
# these as "rejected the deadlock" is the same bug we fixed for scribble's
# module-name errors (2026-07-28). Excluded from both "caught" and false-positives.
NUSCR_TOOL_ERR = ("not implemented", "i'm sorry", "unfortunate", "syntax error",
                  "unbound", "parse error", "fatal error", "uncaught",
                  "no such file", "cannot", "failure", "exception")


def _is_nuscr_tool_error(err: str) -> bool:
    e = (err or "").lower()
    return any(s in e for s in NUSCR_TOOL_ERR)


def valid_both(sv, nc, path: Path):
    try:
        sok, serr = sv.validate_protocol(path)
    except Exception as e:
        sok, serr = None, str(e)
    # a name/parse error is NOT a deadlock verdict — flag it
    name_err = bool(serr) and ("mismatch" in serr or "Simple module name" in serr)
    try:
        nok, nerr = nc.validate(path)
    except Exception as e:
        nok, nerr = None, str(e)
    # a nuscr tool-limitation is NOT a deadlock verdict either
    nuscr_err = (nok is not True) and (_is_nuscr_tool_error(nerr) or nok is None)
    return sok, name_err, nok, nuscr_err


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    classes = sys.argv[2:] or ["circular_wait", "swap_order", "drop_message", "rewire_peer"]
    sv, nc = ScribbleValidator(), NuscrCompiler()
    rng = random.Random(11)
    TMP.mkdir(exist_ok=True)
    corpus = sorted(glob.glob(str(EXP / "cases" / "_corpus" / "*.scr")))[:n]

    # baseline false positives (a VALID protocol wrongly rejected). Tool errors
    # excluded — they mean "couldn't analyse", not "invalid".
    base = {"scribble_fp": 0, "nuscr_fp": 0, "nuscr_tool_errors": 0, "n": 0}
    for src in corpus:
        txt = Path(src).read_text(encoding="utf-8")
        f = TMP / f"{module_of(txt)}.scr"; f.write_text(txt, encoding="utf-8")
        sok, name_err, nok, nuscr_err = valid_both(sv, nc, f)
        base["n"] += 1
        base["scribble_fp"] += int(sok is False and not name_err)
        base["nuscr_fp"] += int(nok is False and not nuscr_err)
        base["nuscr_tool_errors"] += int(nuscr_err)

    results = {"n_corpus": len(corpus), "baseline_false_positives": base, "classes": {}}
    for cls in classes:
        # "caught" only over mutants BOTH backends could analyse (exclude
        # scribble name-errors and nuscr tool-errors), so the comparison is
        # over a common, semantically-judged set.
        applied = s_caught = n_caught = name_errs = nuscr_errs = comparable = 0
        for src in corpus:
            txt = Path(src).read_text(encoding="utf-8")
            m = mutate(txt, cls, rng)
            if not m:
                continue
            f = TMP / f"{module_of(m)}.scr"; f.write_text(m, encoding="utf-8")
            sok, name_err, nok, nuscr_err = valid_both(sv, nc, f)
            applied += 1
            name_errs += int(name_err); nuscr_errs += int(nuscr_err)
            if name_err or nuscr_err:
                continue  # not a semantic verdict on one side — exclude
            comparable += 1
            s_caught += int(sok is False)
            n_caught += int(nok is False)
        results["classes"][cls] = {
            "applied": applied, "comparable": comparable,
            "scribble_caught": s_caught, "nuscr_caught": n_caught,
            "scribble_name_errors_excluded": name_errs,
            "nuscr_tool_errors_excluded": nuscr_errs,
        }
        print(f"{cls:<16} applied={applied:>3} comparable={comparable:>3}  "
              f"scribble={s_caught:>3}  nuscr={n_caught:>3}  "
              f"(nuscr_tool_err_excl={nuscr_errs})", flush=True)

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nbaseline false positives: scribble {base['scribble_fp']}/{base['n']}, "
          f"nuscr {base['nuscr_fp']}/{base['n']} (both should be 0)")
    print(f"WROTE {OUT}")


if __name__ == "__main__":
    main()
