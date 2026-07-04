"""gen_corpus.py — build a corpus of VALID Scribble protocols for E1.

Emits protocols across shape families (pipeline / star / fan-out-fan-in /
negotiation-with-choice), 3-7 roles, with and without branching, then keeps
only those the Scribble validator accepts (so the mutation bench starts from a
known-good baseline). Deterministic given the seed.

    python experiments/scripts/gen_corpus.py --n 30 -o protocols/corpus/
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))

from stjp_core.compiler.validator import ScribbleValidator          # noqa: E402
from integration_stress import ProtocolGenerator                    # noqa: E402

TYPES = ["String", "Double", "Int", "Bool"]
_JAVA = {"String": "java.lang.String", "Double": "java.lang.Double",
         "Int": "java.lang.Integer", "Bool": "java.lang.Boolean"}


def _header(module: str, proto: str, roles: list[str]) -> list[str]:
    lines = [f"module {module};", ""]
    for t in TYPES:
        lines.append(f'data <java> "{_JAVA[t]}" from "rt.jar" as {t};')
    lines.append("")
    lines.append(f"global protocol {proto}({', '.join('role ' + r for r in roles)}) {{")
    return lines


def pipeline(module, n_roles, rng) -> str:
    roles = [f"R{i}" for i in range(n_roles)]
    lines = _header(module, "Pipe", roles)
    for i in range(n_roles - 1):
        lines.append(f"    M{i}({rng.choice(TYPES)}) from {roles[i]} to {roles[i+1]};")
    lines.append(f"    Done({rng.choice(TYPES)}) from {roles[-1]} to {roles[0]};")
    lines.append("}")
    return "\n".join(lines) + "\n"


def star(module, n_spokes, rng) -> str:
    roles = ["Hub"] + [f"S{i}" for i in range(n_spokes)]
    lines = _header(module, "Star", roles)
    for i in range(n_spokes):
        lines.append(f"    Ask{i}({rng.choice(TYPES)}) from Hub to S{i};")
    for i in range(n_spokes):
        lines.append(f"    Ans{i}({rng.choice(TYPES)}) from S{i} to Hub;")
    lines.append("}")
    return "\n".join(lines) + "\n"


def fan(module, n_workers, rng) -> str:
    roles = ["Src"] + [f"W{i}" for i in range(n_workers)] + ["Sink"]
    lines = _header(module, "Fan", roles)
    for i in range(n_workers):
        lines.append(f"    Task{i}({rng.choice(TYPES)}) from Src to W{i};")
    for i in range(n_workers):
        lines.append(f"    Res{i}({rng.choice(TYPES)}) from W{i} to Sink;")
    lines.append(f"    Report(String) from Sink to Src;")
    lines.append("}")
    return "\n".join(lines) + "\n"


def negotiation(module, n_roles, rng) -> str:
    # a choice at a Decider notifying two participants in both branches
    roles = ["Boss", "X", "Y"]
    if n_roles > 3:
        roles.append("Z")
    lines = _header(module, "Nego", roles)
    lines.append("    choice at Boss {")
    lines.append(f"        Accept({rng.choice(TYPES)}) from Boss to X;")
    lines.append(f"        AccNote({rng.choice(TYPES)}) from Boss to Y;")
    lines.append("    } or {")
    lines.append(f"        Reject({rng.choice(TYPES)}) from Boss to X;")
    lines.append(f"        RejNote({rng.choice(TYPES)}) from Boss to Y;")
    lines.append("    }")
    lines.append(f"    Result(String) from X to Boss;")
    lines.append(f"    Ack(String) from Y to Boss;")
    if "Z" in roles:
        lines.append(f"    Log(String) from Boss to Z;")
        lines.append(f"    Logged(String) from Z to Boss;")
    lines.append("}")
    return "\n".join(lines) + "\n"


# Bias toward choice-bearing shapes so the choice-defect operators
# (branch_asymmetry, flip_branch_subject) apply across most of the corpus,
# while keeping acyclic non-choice shapes for the reordering operators.
SHAPES = [
    ("nego", lambda m, rng: negotiation(m, rng.randint(3, 4), rng)),
    ("gen", None),   # ProtocolGenerator — always >=1 choice
    ("nego", lambda m, rng: negotiation(m, rng.randint(3, 4), rng)),
    ("pipe", lambda m, rng: pipeline(m, rng.randint(3, 6), rng)),
    ("gen", None),
    ("star", lambda m, rng: star(m, rng.randint(2, 4), rng)),
    ("nego", lambda m, rng: negotiation(m, rng.randint(3, 4), rng)),
    ("fan", lambda m, rng: fan(m, rng.randint(2, 4), rng)),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("-o", "--out", default="protocols/corpus")
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    validator = ScribbleValidator()
    rng = random.Random(args.seed)

    kept = 0
    attempts = 0
    while kept < args.n and attempts < args.n * 4:
        attempts += 1
        module = f"corpus_{kept:03d}"
        shape_name, fn = SHAPES[attempts % len(SHAPES)]
        if fn is None:
            g = ProtocolGenerator(rng)
            roles, body = g.generate(rng.randint(4, 6), rng.randint(6, 10),
                                     rng.randint(1, 2))
            text = g.render(roles, body, module, "Gen")
        else:
            text = fn(module, rng)
        p = out / f"{module}.scr"
        p.write_text(text, encoding="utf-8")
        ok, err = validator.validate_protocol(p)
        if ok:
            kept += 1
            print(f"[corpus] +{module}.scr ({shape_name})")
        else:
            p.unlink()
    print(f"\n[corpus] kept {kept} valid protocol(s) in {out} "
          f"(from {attempts} attempts)")
    return 0 if kept >= args.n else 1


if __name__ == "__main__":
    raise SystemExit(main())
