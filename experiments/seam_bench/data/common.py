"""common.py — shared plumbing for the D1-D3 data builders.

Fixed JSONL record schemas (do not redesign; extend only via optional
fields — see docs/reference/SEAM_TRAINING_EXECUTION_PLAN.md §3):

    DatasetRecord: {id, family, split, intent, protocol, refn, source,
                    seed_case, gen, provenance}
    RepairRecord:  {id, family, split, intent, broken, counterexample,
                    gold, operator}

Also: seed discovery (30-protocol corpus + 19 named cases), a validator
wrapper that writes to a scratch dir and returns (ok, err, roles,
protocol_name), and small text utilities reused across builders.
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterator

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from stjp_core.compiler.validator import ScribbleValidator          # noqa: E402

CORPUS_DIR = REPO_ROOT / "experiments" / "cases" / "_corpus"
CASES_DIR = REPO_ROOT / "experiments" / "cases"

_MODULE_RE = re.compile(r"module\s+([\w.]+)\s*;")
_HEADER_RE = re.compile(r"global\s+protocol\s+(\w+)\s*\(([^)]*)\)", re.DOTALL)
_ROLE_RE = re.compile(r"role\s+(\w+)")


def module_stem(text: str) -> str:
    m = _MODULE_RE.search(text)
    return m.group(1) if m else "proto"


def _main_header(text: str) -> re.Match | None:
    """First `global protocol` header that is NOT an `aux` one. Composed
    protocols (compiler/incremental.py output) carry spliced `aux global
    protocol` child blocks BEFORE the main protocol; a naive first-match
    lands inside a child and Scribble then errors with 'Invalid aux
    protocol specified as root'. Same guard as incremental.py's
    _main_header_match."""
    for m in _HEADER_RE.finditer(text):
        prefix = text[max(0, m.start() - 8):m.start()]
        if "aux" not in prefix:
            return m
    return None


def protocol_name(text: str) -> str:
    m = _main_header(text)
    return m.group(1) if m else ""


def roles_of(text: str) -> list[str]:
    m = _main_header(text)
    return _ROLE_RE.findall(m.group(2)) if m else []


def has_recursion(text: str) -> bool:
    return bool(re.search(r"\brec\s+\w+\s*\{", text))


def role_count(text: str) -> int:
    return len(roles_of(text))


def depth_bucket(text: str) -> str:
    """Rough structural-depth bucket used for split stratification: counts
    top-level + nested `choice at` occurrences as a proxy for branch depth."""
    n = len(re.findall(r"\bchoice\s+at\s+\w+", text))
    if n == 0:
        return "flat"
    if n <= 2:
        return "shallow"
    return "deep"


class ToolchainMissing(RuntimeError):
    pass


def assert_toolchain() -> None:
    """FAIL-LOUD preflight: the real Scribble-java toolchain must be wired
    (tools/setup_scribble_cloud.sh) before any builder runs. Without this,
    a missing JVM/jar would surface as ScribbleValidator returning
    (False, 'Scribble execution error: ...') for EVERY candidate — i.e.
    silent 100% rejection that looks like operator failure, or worse, D3
    'counterexamples' that are actually toolchain errors. A known-good
    corpus protocol must validate, and a corrupted copy must be rejected
    with a real parser error (not an execution error)."""
    from stjp_core.config import SCRIBBLE_PATH
    lib = Path(SCRIBBLE_PATH) / "lib"
    if not lib.is_dir() or not any(lib.glob("*.jar")):
        raise ToolchainMissing(
            f"Scribble jars not found under {lib} — run "
            f"`bash tools/setup_scribble_cloud.sh` from the repo root first.")
    gold = CORPUS_DIR / "corpus_000.scr"
    ok, err = ScribbleValidator().validate_protocol(gold)
    if not ok:
        raise ToolchainMissing(
            f"gold protocol {gold.name} failed validation — the toolchain "
            f"is mis-wired, not the protocol: {err[:300]}")
    broken = gold.read_text(encoding="utf-8").replace("protocol", "protooocol", 1)
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "corrupt_check.scr"
        p.write_text(broken, encoding="utf-8")
        ok2, err2 = ScribbleValidator().validate_protocol(p)
    if ok2 or "execution error" in err2.lower():
        raise ToolchainMissing(
            f"corrupted protocol was "
            f"{'accepted' if ok2 else 'rejected for the wrong reason'} "
            f"({err2[:200]}) — the validator is not actually judging.")


@dataclass
class ValidationResult:
    ok: bool
    error: str
    roles: list[str]
    protocol_name: str
    module_stem: str


def validate_text(text: str, workdir: Path | None = None) -> ValidationResult:
    """Write `text` to a scratch .scr and run the real Scribble validator
    (stjp_core/compiler/validator.py) — the repo's own well-formedness
    checker. No shortcuts: every candidate protocol in this package is
    accepted or rejected by this exact function."""
    stem = module_stem(text)
    pname = protocol_name(text)
    rs = roles_of(text)

    def _run(wd: Path) -> tuple[bool, str]:
        p = wd / f"{stem}.scr"
        p.write_text(text, encoding="utf-8")
        return ScribbleValidator().validate_protocol(p)

    if workdir is not None:
        ok, err = _run(workdir)
    else:
        with tempfile.TemporaryDirectory() as td:
            ok, err = _run(Path(td))
    return ValidationResult(ok=ok, error=err, roles=rs, protocol_name=pname,
                            module_stem=stem)


# ── seed discovery ───────────────────────────────────────────────────────

@dataclass
class Seed:
    seed_case: str            # e.g. "corpus_003" or "banking"
    text: str
    refn: str | None
    origin: str                # "corpus" | "named_case"


def iter_corpus_seeds() -> Iterator[Seed]:
    for p in sorted(CORPUS_DIR.glob("*.scr")):
        yield Seed(seed_case=p.stem, text=p.read_text(encoding="utf-8"),
                   refn=None, origin="corpus")


def iter_named_case_seeds() -> Iterator[Seed]:
    for case_yaml in sorted(CASES_DIR.rglob("case.yaml")):
        case_dir = case_yaml.parent
        v1 = case_dir / "protocols" / "v1.scr"
        if not v1.exists():
            continue
        refn_path = case_dir / "protocols" / "v1.refn"
        refn = refn_path.read_text(encoding="utf-8") if refn_path.exists() else None
        rel = case_dir.relative_to(CASES_DIR).as_posix()
        yield Seed(seed_case=rel, text=v1.read_text(encoding="utf-8"),
                   refn=refn, origin="named_case")


def all_seeds() -> list[Seed]:
    return list(iter_corpus_seeds()) + list(iter_named_case_seeds())


def case_intent(seed_case: str) -> str | None:
    """Best-effort recovery of the human-written intent/description for a
    named case (used as a D2 register anchor, never verbatim in outputs
    that must forbid Scribble vocabulary — see d2_backtranslate.py)."""
    case_yaml = CASES_DIR / seed_case / "case.yaml"
    if not case_yaml.exists():
        return None
    try:
        import yaml
        data = yaml.safe_load(case_yaml.read_text(encoding="utf-8"))
    except Exception:
        return None
    return (data.get("description") or data.get("intent") or "").strip() or None


# ── JSONL record schemas (FIXED — extend only via optional fields) ──────

@dataclass
class DatasetRecord:
    id: str
    family: str
    split: str                 # "train" | "dev" | "test-syn" | "test-real"
    intent: str | None
    protocol: str
    refn: str | None
    source: str                # "synthetic" | "mined"
    seed_case: str
    gen: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] | None = None

    def to_json(self) -> dict:
        return asdict(self)


@dataclass
class RepairRecord:
    id: str
    family: str
    split: str
    intent: str
    broken: str
    counterexample: str
    gold: str
    operator: str

    def to_json(self) -> dict:
        return asdict(self)


def write_jsonl(path: Path, records: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            obj = r.to_json() if hasattr(r, "to_json") else r
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    out = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def write_sample(path: Path, records: list, cap: int = 200) -> None:
    """Data artifacts policy: commit CODE + small samples (<=200 records)
    under experiments/seam_bench/data/samples/, never full multi-MB builds."""
    write_jsonl(path, records[:cap])
