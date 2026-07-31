"""protocol_entry_audit.py — catch the "unenforced entry" protocol-authoring bug
BEFORE any run is spent on it.

The bug class (found live 2026-07-30 in agenticpay_multi_buyer): a global
protocol whose page order implies a sequencing that its messages do not carry.
By the MPST projection rule, an interaction is simply invisible to a role not
involved in it — so a role that receives nothing before its first send is
COMPLETELY unconstrained and may act immediately, no matter what the author
intended. Scribble accepts such protocols (reordering, not deadlock), the
projection is faithful, and the failure only appears at runtime.

Mechanical rule enforced here, per protocol file:
  - Exactly one role (the INITIATOR — the sender of the protocol's first
    interaction) may have a SEND as its first projected action.
  - Every other role's first projected action must be a RECEIVE (a wait).
Any other role starting with a SEND is flagged: its entry into the protocol is
unenforced, i.e. the intended ordering cannot be guaranteed at runtime.

Checks BOTH protocol files per case, because the arms use both:
  - protocols/v1.scr                    (canonical; monitors for settings 1-2)
  - protocols/llm_drafts/valid/v1.scr   (what settings 3-8 project from)

Usage:
    python scripts/protocol_entry_audit.py <case_dir> [<case_dir> ...]
    (case_dir relative to experiments/, e.g. cases/skills_safety/gem_dev_team)

Exit code 0 = all clean; 1 = at least one flag. Projection is done by
scribble-java via stjp_core.compiler.efsm_parser — never by hand.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPERIMENTS_DIR = HERE.parent
sys.path.insert(0, str(EXPERIMENTS_DIR.parent))
sys.path.insert(0, str(HERE))

from case_loader import Case                              # noqa: E402
from stjp_core.compiler.efsm_parser import get_efsm_from_scribble  # noqa: E402

FIRST_INTERACTION = re.compile(r"^\s*\w+\s*\([^)]*\)\s+from\s+(\w+)\s+to\s+(\w+)\s*;")

# Reviewed-and-accepted concurrent entries. A flag is a REVIEW demand, not an
# automatic verdict: an extra send-first role is BENIGN when its send has no
# intended precondition (an independent producer whose consumer joins the
# inputs — the consumer's own receive order does the sequencing, and an early
# send just waits in the async buffer). It is a BUG when the intent requires
# the role to wait (multi_buyer's BuyerB). Each entry records the review.
ALLOWLIST: dict[tuple[str, str], str] = {
    ("QuarterlyFinanceReport", "ExpenseAnalyst"):
        "independent data producer; RevenueAnalyst joins RawRevenueData then "
        "ExpenseData (its receive order sequences the join). Reviewed "
        "2026-07-30; empirically 0 violations across all finance runs.",
}


def initiator_of(scr_path: Path) -> str | None:
    """The sender of the first interaction line = the one role allowed to
    start with a send."""
    for line in scr_path.read_text(encoding="utf-8").splitlines():
        m = FIRST_INTERACTION.match(line)
        if m:
            return m.group(1)
    return None


def audit_protocol(scr_path: Path, protocol_name: str, roles: list[str]) -> list[str]:
    flags = []
    initiator = initiator_of(scr_path)
    if initiator is None:
        return [f"could not find a first interaction in {scr_path.name}"]
    for role in roles:
        try:
            efsm = get_efsm_from_scribble(scr_path, protocol_name, role)
        except RuntimeError as e:
            flags.append(f"{role}: projection FAILED ({str(e)[:100]})")
            continue
        first = [t for t in efsm.transitions if t.source == efsm.initial_state]
        if not first:
            flags.append(f"{role}: EMPTY projection (dead role)")
            continue
        sends = [t for t in first if t.direction == "send"]
        if sends and role != initiator:
            if (protocol_name, role) in ALLOWLIST:
                print(f"    (allowed: {role} send-first — reviewed benign: "
                      f"{ALLOWLIST[(protocol_name, role)][:80]}...)")
                continue
            labels = ", ".join(f"!{t.label}->{t.peer}" for t in sends)
            flags.append(
                f"{role}: UNENFORCED ENTRY — first action is a SEND ({labels}) "
                f"but {role} is not the initiator ({initiator}); nothing makes "
                f"it wait, so any intended ordering before this send is not "
                f"realizable (the agenticpay_multi_buyer bug class)")
    return flags


def audit_case(case_dir: Path) -> int:
    case = Case.load(case_dir)
    candidates = [case.protocol_path,
                  case_dir / "protocols" / "llm_drafts" / "valid" / f"{case.version}.scr"]
    n_flags = 0
    for scr in candidates:
        if not scr.exists():
            continue
        rel = scr.relative_to(EXPERIMENTS_DIR) if scr.is_relative_to(EXPERIMENTS_DIR) else scr
        flags = audit_protocol(scr, case.protocol_name, case.roles)
        if flags:
            n_flags += len(flags)
            print(f"  FLAG {rel}:")
            for f in flags:
                print(f"    - {f}")
        else:
            print(f"  ok   {rel}  (initiator={initiator_of(scr)}; all other roles wait first)")
    return n_flags


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    total = 0
    for arg in sys.argv[1:]:
        case_dir = (EXPERIMENTS_DIR / arg).resolve()
        print(f"{arg}:")
        total += audit_case(case_dir)
    print(f"\n{'ALL CLEAN' if total == 0 else f'{total} FLAG(S) — do not run flagged protocols'}")
    sys.exit(0 if total == 0 else 1)


if __name__ == "__main__":
    main()
