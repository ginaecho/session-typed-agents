#!/usr/bin/env python3
"""Sync MY /stjp updates to the ginaecho/session-typed-agents remote.

Her repo root == this repo's `stjp/` subdirectory. We NEVER push the eag
monorepo to her remote. We copy file CONTENT into a worktree checked out on
her branch, commit as ginaecho, and push.

WHAT COUNTS AS "my updates" — the commit range, NOT a full mirror align.
Her repo is an older partial mirror that has drifted (its .github/,
CITATION.cff, SOURCES.md, etc. differ for reasons unrelated to this work).
Blindly content-aligning everything would push drift the user never asked
about and could clobber her own versions. So the default is:

    files changed in eag commits SINCE the last recorded sync (a marker sha),
    content-verified against the worktree (CRLF-normalized) so line-ending-
    only diffs never make an empty commit.

The marker lives in `stjp/tools/.last_upstream_sync` (committed to eag,
EXCLUDED from the sync — it is eag-side bookkeeping). `--audit` additionally
content-diffs the WHOLE tracked /stjp set and reports drift for human review
(this is what catches a file edited before the marker but never synced — the
experiments/CLAUDE.md class of miss).

SAFETY (hard-coded, never parameterized):
  remote   : upstream -> https://github.com/ginaecho/session-typed-agents
  branch   : gc/updated_benchmarks
  identity : ginaecho <tzuchunchen@microsoft.com>
  scope    : files under stjp/ ONLY (mapped to the worktree root)
  excluded : the marker file, LATEST run-pointers, .env

USAGE (from anywhere in the eag repo):
  python stjp/tools/sync_stjp_to_upstream.py --dry-run            # list, no push
  python stjp/tools/sync_stjp_to_upstream.py -m "docs: <summary>" # sync + push
  python stjp/tools/sync_stjp_to_upstream.py --since <eag-sha> -m "..."
  python stjp/tools/sync_stjp_to_upstream.py --audit             # full drift report
If no worktree on the branch exists:
  git worktree add <path> upstream/gc/updated_benchmarks
"""
import argparse
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

REMOTE = "upstream"
BRANCH = "gc/updated_benchmarks"
GINA_NAME = "ginaecho"
GINA_EMAIL = "tzuchunchen@microsoft.com"
UPSTREAM_URL = "https://github.com/ginaecho/session-typed-agents"
MARKER_REL = "tools/.last_upstream_sync"          # under stjp/, excluded from sync
EXCLUDE_SUFFIXES = ("/LATEST",)                    # volatile per-machine run pointers
EXCLUDE_NAMES = (".env",)


def run(cmd, cwd=None, check=True):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        sys.exit("FAILED: %s\n%s%s" % (" ".join(cmd), r.stdout, r.stderr))
    return r


def norm_hash(p: Path):
    try:
        return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    except Exception:
        return None


def excluded(rel: str) -> bool:
    if rel == MARKER_REL:
        return True
    if rel.rsplit("/", 1)[-1] in EXCLUDE_NAMES:
        return True
    return any(rel.endswith(sfx) for sfx in EXCLUDE_SUFFIXES)


def locate():
    here = Path(__file__).resolve()
    repo_root = Path(run(["git", "rev-parse", "--show-toplevel"],
                         cwd=str(here.parent)).stdout.strip())
    src_stjp = here.parents[1]                      # stjp/tools/ -> stjp/
    stjp_rel = src_stjp.relative_to(repo_root).as_posix()
    # worktree on BRANCH whose upstream points at her repo
    wt = None
    for block in run(["git", "worktree", "list", "--porcelain"],
                     cwd=str(repo_root)).stdout.split("\n\n"):
        path = branch = None
        for line in block.splitlines():
            if line.startswith("worktree "):
                path = line[9:].strip()
            elif line.startswith("branch "):
                branch = line[7:].strip()
        if path and branch and branch.endswith(BRANCH):
            got = run(["git", "-C", path, "remote", "get-url", REMOTE], check=False)
            if UPSTREAM_URL in got.stdout:
                wt = Path(path)
    return repo_root, src_stjp, stjp_rel, wt


def audit(repo_root, src_stjp, stjp_rel, wt):
    listed = run(["git", "ls-files", stjp_rel], cwd=str(repo_root)).stdout.splitlines()
    prefix = stjp_rel + "/"
    drift = []
    for path in listed:
        if not path.startswith(prefix):
            continue
        rel = path[len(prefix):]
        if excluded(rel) or "/runs/" in rel:        # runs are append-only; skip hashing
            continue
        s, d = src_stjp / rel, wt / rel
        if not s.exists():
            continue
        if not d.exists() or norm_hash(s) != norm_hash(d):
            drift.append(rel)
    print("AUDIT — tracked non-runs /stjp files whose content differs on her repo")
    print("(includes long-standing mirror drift you may NOT want to sync):")
    for r in sorted(drift):
        print("  ~ " + r)
    print("\n%d file(s) differ. Sync a specific one with --since or by editing "
          "the marker; do NOT bulk-push drift." % len(drift))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--message", "-m")
    ap.add_argument("--since", help="eag sha to diff from (default: marker file)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--audit", action="store_true")
    args = ap.parse_args()

    repo_root, src_stjp, stjp_rel, wt = locate()
    if wt is None or not wt.exists():
        sys.exit("No worktree on %s. Create: git worktree add <path> %s/%s"
                 % (BRANCH, REMOTE, BRANCH))
    if args.audit:
        audit(repo_root, src_stjp, stjp_rel, wt)
        return

    marker = src_stjp / MARKER_REL
    since = args.since or (marker.read_text().strip() if marker.exists() else None)
    if not since:
        sys.exit("No sync marker at %s and no --since given. Pass --since <eag-sha> "
                 "of the last synced commit (git log will show it)." % MARKER_REL)

    # files my commits touched since the marker (precise; ignores mirror drift)
    cand = run(["git", "diff", "--name-only", since, "HEAD", "--", stjp_rel],
               cwd=str(repo_root)).stdout.splitlines()
    prefix = stjp_rel + "/"
    changed = []
    for path in cand:
        if not path.startswith(prefix):
            continue
        rel = path[len(prefix):]
        if excluded(rel):
            continue
        s = src_stjp / rel
        if not s.exists():
            continue                                 # deleted in eag; skip (manual)
        d = wt / rel
        if (not d.exists()) or norm_hash(s) != norm_hash(d):
            changed.append(rel)

    head = run(["git", "rev-parse", "--short", "HEAD"], cwd=str(repo_root)).stdout.strip()
    print("SOURCE  : %s" % src_stjp)
    print("WORKTREE: %s  (%s/%s)" % (wt, REMOTE, BRANCH))
    print("range   : %s..HEAD(%s)" % (since[:8], head))
    print("to sync : %d file(s)" % len(changed))
    for c in changed:
        print("  M " + c)
    if not changed:
        print("Nothing to sync in this range. (Run --audit to check for older drift.)")
        return
    if args.dry_run:
        print("\n[dry-run] re-run with -m \"<message>\" to commit + push.")
        return
    if not args.message:
        sys.exit("\n-m/--message required to push (or --dry-run).")

    run(["git", "-C", str(wt), "fetch", "-q", REMOTE, BRANCH])
    run(["git", "-C", str(wt), "merge", "-q", "--ff-only", "%s/%s" % (REMOTE, BRANCH)],
        check=False)
    for rel in changed:
        d = wt / rel
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_stjp / rel, d)
    run(["git", "-C", str(wt), "add", "-f"] + changed)
    if not run(["git", "-C", str(wt), "diff", "--cached", "--name-only"]).stdout.split():
        print("\nOnly line-ending differences — nothing committed.")
        return
    run(["git", "-C", str(wt),
         "-c", "user.name=%s" % GINA_NAME, "-c", "user.email=%s" % GINA_EMAIL,
         "commit", "-q", "-m", args.message])
    run(["git", "-C", str(wt), "push", "-q", REMOTE, BRANCH])
    wt_head = run(["git", "-C", str(wt), "rev-parse", "--short", "HEAD"]).stdout.strip()
    # advance the marker to the eag HEAD we just synced from
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(run(["git", "rev-parse", "HEAD"], cwd=str(repo_root)).stdout.strip() + "\n")
    print("\nPUSHED %d file(s) as %s -> %s/%s (her commit %s)."
          % (len(changed), GINA_NAME, REMOTE, BRANCH, wt_head))
    print("Marker advanced to eag HEAD %s — commit stjp/%s in eag to persist."
          % (head, MARKER_REL))


if __name__ == "__main__":
    main()
