#!/usr/bin/env python3
"""run_gate_parity.py — prove the generated gate and the hand-written
checker agree, on the six fixtures pre-registered as P3 in
docs/predictions/SPEC_TO_GATE_PREREGISTRATION.md.

Each fixture is a throwaway git repository with one commit, built to
exhibit exactly one condition. Both tools run over it; the test requires
identical verdicts (violation / no violation). A disagreement fails the
test and is reported — never patched into agreement silently.

Usage: python tools/tests/run_gate_parity.py
Exit 0 = parity on all fixtures, 1 = any disagreement or fixture error.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
HAND = TOOLS / "check_git_rules.py"
GEN = TOOLS / "generated" / "gate_git.py"

OWNER = ["-c", "user.name=ginaecho", "-c", "user.email=gina.tcchen@gmail.com"]
BOT = ["-c", "user.name=Claude", "-c", "user.email=noreply@anthropic.com"]

# (name, branch, git -c identity args, commit message, expect_violation)
FIXTURES = [
    ("clean commit on gc/ branch", "gc/x", OWNER,
     "docs: a perfectly ordinary commit", False),
    ("wrong author identity", "gc/x", BOT,
     "docs: a perfectly ordinary commit", True),
    ("forbidden keyword in body", "gc/x", OWNER,
     "docs: ordinary subject\n\nmentions a claude/... path in the body",
     True),
    ("assistant co-author trailer", "gc/x", OWNER,
     "docs: ordinary subject\n\nCo-Authored-By: Helpful Bot <bot@example.com>",
     True),
    ("clean commit on forbidden branch", "claude/x", OWNER,
     "docs: a perfectly ordinary commit", True),
    ("clean commit on gc/ branch again", "gc/y", OWNER,
     "docs: another ordinary commit", False),
]


def make_fixture(tmp: Path, branch: str, ident: list[str], msg: str) -> Path:
    repo = tmp
    def g(*args):
        subprocess.run(["git", *args], cwd=repo, capture_output=True,
                       text=True, check=True)
    g("init", "-q", "-b", branch)
    g("config", "commit.gpgsign", "false")
    (repo / "f.txt").write_text("x\n")
    g("add", "f.txt")
    subprocess.run(["git", *ident, "commit", "-q", "--no-verify", "-m", msg],
                   cwd=repo, capture_output=True, text=True, check=True)
    return repo


def verdict(tool: Path, repo: Path, branch: str) -> tuple[bool, str]:
    """True = tool reports at least one violation."""
    r = subprocess.run([sys.executable, str(tool), "--repo", str(repo),
                        "--range", "HEAD", "--include-pushed",
                        "--branch", branch],
                       capture_output=True, text=True)
    return r.returncode != 0, r.stdout.strip()


def main() -> int:
    failures = 0
    for name, branch, ident, msg, expect in FIXTURES:
        with tempfile.TemporaryDirectory(prefix="gate-parity-") as d:
            repo = make_fixture(Path(d), branch, ident, msg)
            hand_v, hand_out = verdict(HAND, repo, branch)
            gen_v, gen_out = verdict(GEN, repo, branch)
        agree = hand_v == gen_v
        correct = hand_v == expect
        status = "OK " if (agree and correct) else "FAIL"
        print(f"[{status}] {name}: hand={hand_v} generated={gen_v} "
              f"expected={expect}")
        if not (agree and correct):
            failures += 1
            print(f"  hand-written output:\n    {hand_out.replace(chr(10), chr(10)+'    ')}")
            print(f"  generated output:\n    {gen_out.replace(chr(10), chr(10)+'    ')}")

    print(f"\n{len(FIXTURES)} fixtures -> {len(FIXTURES) - failures} agree, "
          f"{failures} disagree")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
