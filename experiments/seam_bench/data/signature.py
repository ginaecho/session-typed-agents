"""signature.py — canonical EFSM-equivalence-class signature for a protocol.

Design (the v1 "acceptable fallback" from SEAM_TRAINING_EXECUTION_PLAN.md
§9/W3): per-role canonical minimized-automaton form — states relabelled by
BFS order from the initial state, transitions sorted — hashed together
across all roles. This is NOT a from-scratch algorithm: it reuses the
repo's own canonicalization, `stjp_core.compiler.incremental.efsm_signature`
(written for exactly this purpose — "stable under Scribble's state
renumbering" — to detect unchanged roles across incremental re-projection).
Reusing it means signature.py and incremental.py can never silently
disagree about what "the same EFSM" means.

Ground truth for verification is the repo's OWN pairwise equivalence
checker, `experiments/scripts/efsm_equiv.py::protocols_equivalent`, which
implements the paper's E5 definition: same role set, per-role EFSMs
bisimilar (product-BFS, exact for Scribble's deterministic transition
systems), AND identical global conversation language. `verify_against_checker`
below cross-checks the two on many pairs and reports the agreement rate —
see the module docstring's "acceptable v1" escape hatch: escalate if the
agreement is below 100%.

Two protocols get the SAME signature iff, for every role, the canonical
per-role transition multiset (after BFS relabelling) is identical, AND the
role sets match. This is a slightly finer partition than E5 bisimulation in
one respect (E5's `efsm_bisimilar` is a coarser quotient — it does not
require the SAME canonical numbering, only *a* bijection between reachable
state pairs — so in principle two EFSMs could be bisimilar via a
non-BFS-order bijection while landing in different BFS-canonical forms).
In practice, because Scribble's projection is deterministic per protocol
text, BFS-from-initial-state with edges sorted by (direction, peer, label)
recovers a unique canonical form for each behaviour, and the verification
harness below empirically checks agreement on the corpus + generated
population; see the W3 report for the measured rate.
"""
from __future__ import annotations

import hashlib
import json
import random
import sys
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
SCRIPTS_DIR = REPO_ROOT / "experiments" / "scripts"
for p in (REPO_ROOT, SCRIPTS_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from stjp_core.compiler.efsm_parser import EFSM, get_all_efsms          # noqa: E402
from stjp_core.compiler.incremental import efsm_signature                # noqa: E402
from stjp_core.compiler.validator import ScribbleValidator               # noqa: E402
from stjp_core.critic.protocol_paths import paths_for_protocol           # noqa: E402
from efsm_equiv import efsm_bisimilar, protocols_equivalent              # noqa: E402

from common import module_stem, protocol_name, roles_of                  # noqa: E402

SIG_VERSION = "efsmv1"


class SignatureError(Exception):
    pass


def _project(text: str, workdir: Path, assume_valid: bool = False) -> dict[str, EFSM]:
    stem = module_stem(text)
    p = workdir / f"{stem}.scr"
    p.write_text(text, encoding="utf-8")
    if not assume_valid:
        ok, err = ScribbleValidator().validate_protocol(p)
        if not ok:
            raise SignatureError(f"protocol {stem} does not validate: {err[:300]}")
    try:
        return get_all_efsms(p, protocol_name(text), roles_of(text))
    except RuntimeError as e:
        # assume_valid callers skip the explicit validate() round-trip above;
        # if the text turns out malformed anyway, Scribble's `-fsm` command
        # itself fails (get_efsm_from_scribble raises) — surface that the
        # same way an explicit validate() failure would.
        raise SignatureError(f"protocol {stem} projection failed: {e}") from e


def protocol_signature(text: str, assume_valid: bool = False) -> str:
    """Canonical EFSM-equivalence-class signature, hex string prefixed with
    the format version. Requires `text` to validate (raises SignatureError
    otherwise — an invalid candidate has no equivalence class).

    `assume_valid=True` skips the internal Scribble `validate_protocol`
    round-trip and goes straight to `-fsm` projection — a real throughput
    win for callers (d1_expand.py, d3_repair.py) that already ran
    `common.validate_text` on this exact text and know it passed: without
    this, every kept candidate paid for the real Scribble-java CLI twice
    (once to validate, once again inside the signature computation). Never
    skips validation blindly — a malformed text still raises
    SignatureError via the `-fsm` command's own failure."""
    with tempfile.TemporaryDirectory() as td:
        efsms = _project(text, Path(td), assume_valid=assume_valid)
    per_role = sorted((role, efsm_signature(e)) for role, e in efsms.items())
    canon = json.dumps(per_role, sort_keys=True, default=list)
    digest = hashlib.sha256(canon.encode("utf-8")).hexdigest()[:32]
    return f"{SIG_VERSION}:{digest}"


class SignatureCache:
    """In-memory (+ optional on-disk) cache: canonical-whitespace text hash
    -> signature. Every builder in this package should route through one of
    these instead of calling protocol_signature directly — dedupe against
    thousands of candidates would otherwise re-invoke the Scribble CLI (a
    JVM per role) for texts already seen."""

    def __init__(self, path: Path | None = None):
        self.path = path
        self._mem: dict[str, str] = {}
        self._lock = threading.Lock()
        if path and path.exists():
            try:
                self._mem = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self._mem = {}

    @staticmethod
    def _key(text: str) -> str:
        import re
        canon = re.sub(r"\s+", " ", text.strip())
        return hashlib.sha256(canon.encode("utf-8")).hexdigest()

    def get_cached(self, text: str) -> str | None:
        """Text-hash lookup WITHOUT computing: returns the cached signature
        or None. Lets builders dedupe by text hash BEFORE spending a
        Scribble validation on a candidate text they have already processed
        (the validate step is redundant for a text whose signature — which
        implies validity — is already known)."""
        with self._lock:
            return self._mem.get(self._key(text))

    def signature(self, text: str, assume_valid: bool = False) -> str:
        """Thread-safe: multiple worker threads (see d1_expand.py's pool)
        may call this concurrently. The dict get/set is lock-protected; the
        (expensive, Scribble-CLI-bound) computation itself happens outside
        the lock, so two threads racing on the same unseen text may both
        compute it once — correctness is unaffected, only a rare redundant
        computation. `assume_valid` is forwarded to protocol_signature —
        pass True only when the caller already validated this exact text."""
        k = self._key(text)
        with self._lock:
            if k in self._mem:
                return self._mem[k]
        sig = protocol_signature(text, assume_valid=assume_valid)
        with self._lock:
            self._mem[k] = sig
        return sig

    def save(self) -> None:
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                self.path.write_text(json.dumps(self._mem, indent=0), encoding="utf-8")


# ── verification against the repo's own pairwise checker ────────────────

@dataclass
class _ProtoView:
    text: str
    roles: tuple[str, ...]
    efsms: dict[str, EFSM]
    language: frozenset
    sig: str


def _build_view(text: str, workdir: Path) -> _ProtoView:
    efsms = _project(text, workdir)
    lang = frozenset(
        tuple((e.sender, e.receiver, e.label) for e in path)
        for path in paths_for_protocol(text).paths)
    per_role = sorted((role, efsm_signature(e)) for role, e in efsms.items())
    digest = hashlib.sha256(
        json.dumps(per_role, sort_keys=True, default=list).encode()).hexdigest()[:32]
    return _ProtoView(text=text, roles=tuple(sorted(efsms)), efsms=efsms,
                      language=lang, sig=f"{SIG_VERSION}:{digest}")


def _checker_equivalent(a: _ProtoView, b: _ProtoView) -> tuple[bool, str]:
    """Replicates efsm_equiv.protocols_equivalent's verdict exactly (same
    role-set / per-role-bisimilar / same-language definition) but reuses
    already-computed projections instead of re-invoking Scribble — see
    verify_against_checker's docstring for why, and the report for a
    spot-check against the unoptimized function."""
    if a.roles != b.roles:
        return False, "role sets differ"
    for role in a.roles:
        ok, why = efsm_bisimilar(a.efsms[role], b.efsms[role])
        if not ok:
            return False, f"role {role}: {why}"
    if a.language != b.language:
        return False, "conversation language differs"
    return True, "equivalent"


def verify_against_checker(texts: list[str], n_pairs: int = 200,
                           seed: int = 0, spot_check: int = 20) -> dict:
    """Cross-check protocol_signature() equality against the repo's own
    pairwise checker (efsm_equiv.protocols_equivalent) on `n_pairs` random
    pairs drawn from `texts` (deduplicated, validated). Returns a report
    dict with the agreement rate; per the W3 task card, <100% must be
    escalated in the report, not silently accepted.
    """
    rng = random.Random(seed)
    with tempfile.TemporaryDirectory() as td:
        wd = Path(td)
        views: list[_ProtoView] = []
        skipped = 0
        for t in texts:
            try:
                views.append(_build_view(t, wd))
            except SignatureError:
                skipped += 1
        n = len(views)
        pairs = []
        seen = set()
        attempts = 0
        while len(pairs) < min(n_pairs, n * (n - 1) // 2) and attempts < n_pairs * 20:
            attempts += 1
            i, j = rng.randrange(n), rng.randrange(n)
            if i == j or (min(i, j), max(i, j)) in seen:
                continue
            seen.add((min(i, j), max(i, j)))
            pairs.append((i, j))

        agree = disagree = 0
        disagreements = []
        for i, j in pairs:
            a, b = views[i], views[j]
            sig_eq = a.sig == b.sig
            checker_eq, why = _checker_equivalent(a, b)
            if sig_eq == checker_eq:
                agree += 1
            else:
                disagree += 1
                disagreements.append({
                    "a_sig": a.sig, "b_sig": b.sig,
                    "sig_equal": sig_eq, "checker_equal": checker_eq,
                    "checker_reason": why,
                })

        # spot-check a subset against the REAL (unoptimized) function to
        # confirm the fast in-process replica agrees with calling Scribble
        # fresh for both protocols.
        spot = []
        for i, j in pairs[:spot_check]:
            a, b = views[i], views[j]
            real_eq, real_why = protocols_equivalent(a.text, b.text)
            fast_eq, _ = _checker_equivalent(a, b)
            spot.append({"agree": real_eq == fast_eq, "real": real_eq,
                        "fast": fast_eq, "reason": real_why})
        spot_agree = sum(1 for s in spot if s["agree"])

        total = agree + disagree
        return {
            "unique_protocols_considered": len(texts),
            "unique_protocols_validated": n,
            "unique_protocols_skipped_invalid": skipped,
            "pairs_tested": total,
            "agree": agree,
            "disagree": disagree,
            "agreement_rate_pct": round(100 * agree / total, 2) if total else None,
            "disagreements_sample": disagreements[:10],
            "spot_check_pairs": len(spot),
            "spot_check_agree": spot_agree,
            "spot_check_matches_real_checker": spot_agree == len(spot),
        }


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verify", action="store_true",
                    help="run verify_against_checker over corpus + named "
                         "cases + validator-passing mutants of both")
    ap.add_argument("--pairs", type=int, default=200)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("-o", "--out", default=None)
    args = ap.parse_args(argv)

    if not args.verify:
        ap.print_help()
        return 2

    from common import all_seeds
    sys.path.insert(0, str(SCRIPTS_DIR))
    from mutate_protocol import mutate, CLASSES                          # noqa

    rng = random.Random(args.seed)
    texts = [s.text for s in all_seeds()]
    # add validator-passing mutants (near-misses) as extra population —
    # these are exactly the hard negatives the signature must still get
    # right (structurally similar, behaviourally different or identical).
    extra = []
    for s in all_seeds():
        for cls in CLASSES:
            m = mutate(s.text, cls, rng)
            if m:
                extra.append(m)
    texts += extra[: max(0, 120 - len(texts))]

    report = verify_against_checker(texts, n_pairs=args.pairs, seed=args.seed)
    print(json.dumps(report, indent=2))
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if report.get("agreement_rate_pct") == 100.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
