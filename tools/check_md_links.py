#!/usr/bin/env python3
"""check_md_links.py — verify every relative link and menu anchor in the repo's
markdown files points at something real.

Why this exists: documentation rot is invisible until a reader hits a dead
link. A small example — after docs/results/RESULT_4_FULL_STACK.md was renamed
to RESULT_04_FULL_STACK.md, every document that still linked the old name
would 404 on GitHub; this script catches all of them in one pass.

What it checks, for every tracked *.md file:
  1. Relative file links: [text](path) where path is not http(s)/mailto —
     the target file or directory must exist on disk.
  2. Same-file anchors: [text](#section-name) — a heading that slugifies to
     that anchor (GitHub rules: lowercase, spaces to hyphens, punctuation
     dropped) must exist in the same file.
  3. Cross-file anchors: [text](other.md#section) — the heading must exist
     in the target file.

Usage:
  python tools/check_md_links.py            # check the whole repo
  python tools/check_md_links.py docs       # check one subtree
Exit code 0 = clean, 1 = at least one broken link (each printed as
file:line: problem).
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
HEADING_RE = re.compile(r"^#{1,6}\s+(.*)$", re.MULTILINE)


def slugify(heading: str) -> str:
    """GitHub's anchor rule: strip formatting, lowercase, spaces->hyphens,
    drop everything that is not a word character or hyphen."""
    h = re.sub(r"[*_`]", "", heading).strip()
    h = h.lower().replace(" ", "-")
    return re.sub(r"[^\w\-]", "", h)


def anchors_of(md_path: Path, cache: dict[Path, set[str]]) -> set[str]:
    if md_path not in cache:
        try:
            text = md_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            cache[md_path] = set()
            return cache[md_path]
        slugs: set[str] = set()
        seen: dict[str, int] = {}
        for m in HEADING_RE.finditer(text):
            s = slugify(m.group(1))
            # GitHub disambiguates duplicate headings as slug, slug-1, ...
            n = seen.get(s, 0)
            seen[s] = n + 1
            slugs.add(s if n == 0 else f"{s}-{n}")
        cache[md_path] = slugs
    return cache[md_path]


def tracked_md_files(subtree: str | None) -> list[Path]:
    out = subprocess.run(["git", "ls-files", "*.md", "**/*.md"],
                         cwd=REPO, capture_output=True, text=True).stdout
    files = [REPO / line for line in out.splitlines() if line.strip()]
    if subtree:
        base = (REPO / subtree).resolve()
        files = [f for f in files if base in f.resolve().parents
                 or f.resolve() == base]
    return sorted(set(files))


def main() -> int:
    subtree = sys.argv[1] if len(sys.argv) > 1 else None
    cache: dict[Path, set[str]] = {}
    problems: list[str] = []
    n_links = 0

    for md in tracked_md_files(subtree):
        text = md.read_text(encoding="utf-8", errors="replace")
        in_fence = False
        for lineno, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
            if in_fence:
                continue
            for m in LINK_RE.finditer(line):
                target = m.group(1)
                if target.startswith(("http://", "https://", "mailto:")):
                    continue
                n_links += 1
                rel = md.relative_to(REPO)
                if target.startswith("#"):
                    if target[1:] not in anchors_of(md, cache):
                        problems.append(f"{rel}:{lineno}: dead anchor "
                                        f"{target}")
                    continue
                path_part, _, frag = target.partition("#")
                # Links may URL-encode characters ("STJP%20Demo.html");
                # decode before touching the filesystem.
                from urllib.parse import unquote
                dest = (md.parent / unquote(path_part)).resolve()
                if not dest.exists():
                    problems.append(f"{rel}:{lineno}: missing target "
                                    f"{target}")
                    continue
                if frag and dest.suffix == ".md":
                    if frag not in anchors_of(dest, cache):
                        problems.append(f"{rel}:{lineno}: anchor #{frag} "
                                        f"not found in {path_part}")

    for p in problems:
        print(p)
    print(f"\nchecked {n_links} links in "
          f"{len(tracked_md_files(subtree))} files -> "
          f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
