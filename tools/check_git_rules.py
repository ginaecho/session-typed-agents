#!/usr/bin/env python3
"""check_git_rules.py — mechanically enforce the git rules of AGENT.md
("Git identity — ALWAYS commit/push/PR as ginaecho").

Why this exists: on 2026-07-25 an assistant pushed four commits that broke
three clauses of that section — a forbidden branch name, assistant trailers,
and a wrong author identity — after having opened AGENT.md and read a
*different* section of it (the full account is in
docs/reference/SESSION_RECORD_2026-07-25.md §7). A rule that lives 200 lines
away from where the action happens is not reliably retrieved at the moment of
action. This script is the fix the record itself proposes: turn the
lint-checkable clauses into a mechanism that cannot be skipped, instead of
prose that can.

What it checks:
  1. Branch name — must start with the `gc/` prefix. A platform-managed
     session (for example Claude Code on the web) may force a differently
     named working branch the agent cannot rename; setting
     STJP_PLATFORM_BRANCH=1 downgrades ONLY this check to a loud warning.
     The conflict must then be stated in the agent's reply and the branch
     renamed or merged away by the owner — the warning text says so.
  2. Commit messages — no "claude" keyword anywhere (subject, body,
     trailers), case-insensitive. The rule in AGENT.md says "anywhere",
     and it means it: even a file path quoted in a commit body counts.
  3. Commit identity — author AND committer of every new commit must be one
     of the owner identities AGENT.md names (`ginaecho <gina.tcchen@gmail.com>`
     for this repo; the Microsoft addresses for the mirror flow). A commit
     the owner makes in the GitHub web UI gets committer
     `GitHub <noreply@github.com>`; that is accepted when the author is the
     owner. An assistant or bot identity is never accepted.
  4. Trailers — no Co-Authored-By / session trailer naming anyone but the
     owner. (An assistant trailer is an identity claim; the identity rule
     covers headers, this covers the message body.)

Only commits that have not already been pushed are checked: anything
reachable from an origin/* ref has left the machine, and a pre-push gate
that complains about history it cannot change would just be ignored. Pass
--include-pushed to audit history anyway.

Usage:
  python tools/check_git_rules.py                      # origin/main..HEAD
  python tools/check_git_rules.py --range A..B         # explicit range
  python tools/check_git_rules.py --branch gc/foo      # branch name to judge
Exit code 0 = clean, 1 = at least one violation (each printed as
commit: problem). The pre-push hook in .githooks/pre-push runs this
automatically; enable it once per clone with:
  git config core.hooksPath .githooks
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

OWNER_NAME = "ginaecho"  # REPO may be overridden by --repo (used by the
                         # parity fixtures in tools/tests/)
OWNER_EMAIL = "gina.tcchen@gmail.com"
# Identities AGENT.md's git section names for the owner across both repos,
# plus GitHub's web-editor committer (what the owner's own UI edits carry).
OWNER_IDENTITIES = {
    ("ginaecho", "gina.tcchen@gmail.com"),
    ("ginaecho", "tzuchunchen@microsoft.com"),
    ("Gina Chen", "tzuchunchen+microsoft@microsoft.com"),
}
WEB_FLOW_COMMITTER = ("GitHub", "noreply@github.com")
FORBIDDEN_RE = re.compile(r"claude", re.IGNORECASE)
TRAILER_RE = re.compile(r"^\s*(co-authored-by|[\w-]*session[\w-]*)\s*:\s*(.+)$",
                        re.IGNORECASE | re.MULTILINE)
BRANCH_PREFIX = "gc/"


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True,
                          text=True, check=True).stdout


def current_branch() -> str:
    return git("rev-parse", "--abbrev-ref", "HEAD").strip()


def default_range() -> str:
    """New commits only: everything on HEAD that origin/main does not have."""
    try:
        git("rev-parse", "--verify", "origin/main")
        return "origin/main..HEAD"
    except subprocess.CalledProcessError:
        return "HEAD"


def check_branch(branch: str, problems: list[str], warnings: list[str]) -> None:
    if branch == "HEAD":  # detached; nothing to name-check
        return
    if branch.startswith(BRANCH_PREFIX) or branch == "main":
        return
    msg = (f"branch '{branch}' does not start with '{BRANCH_PREFIX}' "
           f"(AGENT.md: every branch ALWAYS starts with the gc/ prefix)")
    if os.environ.get("STJP_PLATFORM_BRANCH") == "1":
        warnings.append(
            msg + " — tolerated because STJP_PLATFORM_BRANCH=1 says the "
            "platform named this branch; state this conflict in your reply, "
            "and the owner must rename or merge the branch away")
    else:
        problems.append(msg)


def check_commits(rng: str, problems: list[str],
                  include_pushed: bool = False) -> int:
    args = ["rev-list", rng]
    if not include_pushed:
        args += ["--not", "--remotes=origin"]
    shas = [s for s in git(*args).splitlines() if s]
    for sha in shas:
        short = sha[:7]
        an, ae, cn, ce = git(
            "log", "-1", "--format=%an%x00%ae%x00%cn%x00%ce", sha
        ).strip("\n").split("\x00")
        body = git("log", "-1", "--format=%B", sha)

        if (an, ae) not in OWNER_IDENTITIES:
            problems.append(f"{short}: author is '{an} <{ae}>', must be "
                            f"'{OWNER_NAME} <{OWNER_EMAIL}>'")
        if ((cn, ce) not in OWNER_IDENTITIES
                and not ((cn, ce) == WEB_FLOW_COMMITTER
                         and (an, ae) in OWNER_IDENTITIES)):
            problems.append(f"{short}: committer is '{cn} <{ce}>', must be "
                            f"'{OWNER_NAME} <{OWNER_EMAIL}>'")
        for lineno, line in enumerate(body.splitlines(), 1):
            if FORBIDDEN_RE.search(line):
                problems.append(f"{short}: forbidden keyword in commit "
                                f"message line {lineno}: {line.strip()!r}")
        for m in TRAILER_RE.finditer(body):
            value = m.group(2)
            if OWNER_NAME not in value.lower() and "gina" not in value.lower():
                problems.append(f"{short}: assistant/session trailer "
                                f"'{m.group(0).strip()}' — no such trailers "
                                f"(AGENT.md git identity section)")
    return len(shas)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--range", dest="rng", default=None,
                    help="commit range to check (default origin/main..HEAD)")
    ap.add_argument("--branch", default=None,
                    help="branch name to judge (default: current branch)")
    ap.add_argument("--include-pushed", action="store_true",
                    help="also audit commits already on origin/* refs")
    ap.add_argument("--repo", type=Path, default=None,
                    help="repository to check (default: this repo)")
    args = ap.parse_args()
    if args.repo is not None:
        global REPO
        REPO = args.repo.resolve()

    problems: list[str] = []
    warnings: list[str] = []
    check_branch(args.branch or current_branch(), problems, warnings)
    n = check_commits(args.rng or default_range(), problems,
                      include_pushed=args.include_pushed)

    for w in warnings:
        print(f"WARNING: {w}")
    for p in problems:
        print(p)
    print(f"\nchecked {n} commit(s) -> {len(problems)} violation(s), "
          f"{len(warnings)} warning(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
