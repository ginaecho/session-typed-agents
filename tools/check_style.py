#!/usr/bin/env python3
"""check_style.py — flag known-offender jargon used without its gloss, per
AGENT.md §5 ("Plain-language writing rule").

Why this exists: §5 says every term of art gets a plain-English gloss at
first use, and its known-offender table lists the words this project keeps
slipping into. The rule was already written when, on 2026-07-25, an
assistant that had *read* §5 still coined and repeated a new undefined term
("lens") in its replies — the account is in
docs/reference/SESSION_RECORD_2026-07-25.md §6. Reading a rule once is not
the same as the rule being in force at the moment of writing; a lint that
runs beside tools/check_md_links.py is in force every time.

What it checks, for every tracked *.md file outside docs/archive/ (the
archive is a historical record and stays as written):
  - Each known-offender term that appears in prose (code fences, inline
    code, and link targets don't count) must have its gloss somewhere in
    the same file. A small example: a file may say "canary" freely *if* it
    also says "planted check item with a known correct answer" somewhere;
    a file that says only "canary" fails.
  - Terms marked replace-only ("pillar", "wire" outside the phrase
    "on the wire") are flagged wherever they appear, with the replacement.

The offender list mirrors the table in AGENT.md §5 — keep the two in sync
when adding an offender.

Usage:
  python tools/check_style.py            # check the whole repo
  python tools/check_style.py docs       # check one subtree
Exit code 0 = clean, 1 = at least one problem (each printed as
file:line: problem).
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
# docs/archive/ is a historical record and stays as written. The other
# exclusions are benchmark *inputs*, not documentation: mined or authored
# skill files and generated per-role contracts. Editing those to satisfy a
# style rule would change the experiment materials themselves (and "Escrow"
# there is a role name, not prose).
EXCLUDED = ("docs/archive/", "docs/diary/")
EXCLUDED_PARTS = ("unchecked_skills", "skills_original", "generated",
                  "compiled_skills", "skills")

# term name -> (occurrence regex, gloss-evidence regex or None, advice)
# gloss-evidence None means replace-only: every prose occurrence is flagged.
OFFENDERS: dict[str, tuple[re.Pattern, re.Pattern | None, str]] = {
    "canary": (
        re.compile(r"\bcanar(?:y|ies)\b", re.I),
        re.compile(r"planted check", re.I),
        'gloss as "a planted check item with a known correct answer"',
    ),
    "AST re-emission": (
        re.compile(r"\bAST re-?emission\b", re.I),
        re.compile(r"re-?print|parsed structure", re.I),
        'gloss as "re-printing the protocol from its parsed structure"',
    ),
    "pillar": (
        re.compile(r"\bpillars?\b", re.I),
        None,
        "avoid; name the actual thing it refers to instead",
    ),
    "wire": (
        re.compile(r"\bwire[ds]?\b", re.I),
        None,
        'use "connect(ed)" (the network idiom "on the wire" is allowed)',
    ),
    "seam": (
        # (?!-) keeps the proper name "Seam-Bench" out of scope.
        re.compile(r"\bseams?\b(?!-)", re.I),
        re.compile(r"translation step", re.I),
        'gloss as "the translation step from plain-language intent to '
        'formal protocol"',
    ),
    "lens": (
        re.compile(r"\blens(?:es)?\b", re.I),
        re.compile(r"task assignment", re.I),
        'a mid-project nickname for "a role\'s task assignment" — gloss it '
        "or use the plain phrase",
    ),
    "escrow": (
        re.compile(r"\bescrows?\b", re.I),
        re.compile(r"neutral third party|holds? (?:the )?funds", re.I),
        'gloss as "a neutral third party that holds funds until both '
        'sides deliver"',
    ),
    "geometric median": (
        re.compile(r"\bgeometric median\b", re.I),
        re.compile(r"robust way|extreme judge", re.I),
        'gloss as "a robust way to combine scores so one extreme judge '
        "cannot drag the result\"",
    ),
}

INLINE_CODE_RE = re.compile(r"`[^`]*`")
LINK_TARGET_RE = re.compile(r"\]\([^)\s]*\)")
ON_THE_WIRE_RE = re.compile(r"\bon the wire\b|\bwire format\b", re.I)


def tracked_md_files(subtree: str | None) -> list[Path]:
    out = subprocess.run(["git", "ls-files", "*.md", "**/*.md"],
                         cwd=REPO, capture_output=True, text=True).stdout
    files = []
    for line in out.splitlines():
        if not line.strip() or line.startswith(EXCLUDED):
            continue
        if any(part in Path(line).parts for part in EXCLUDED_PARTS):
            continue
        if subtree and not line.startswith(subtree.rstrip("/") + "/") \
                and line != subtree:
            continue
        files.append(REPO / line)
    return sorted(set(files))


def prose_of(line: str) -> str:
    """Strip the parts of a markdown line that are not prose: inline code
    spans and link targets (a path like cases/escrow/... is a name, not a
    use of the word)."""
    line = INLINE_CODE_RE.sub(" ", line)
    line = LINK_TARGET_RE.sub("]( )", line)
    return line


def main() -> int:
    subtree = sys.argv[1] if len(sys.argv) > 1 else None
    problems: list[str] = []
    files = tracked_md_files(subtree)

    for md in files:
        text = md.read_text(encoding="utf-8", errors="replace")
        # Gloss phrases may wrap across a line break ("planted\ncheck");
        # search them against whitespace-normalized text.
        flat = re.sub(r"\s+", " ", text)
        rel = md.relative_to(REPO)
        reported: set[str] = set()
        in_fence = False
        lint_off = False
        for lineno, raw in enumerate(text.splitlines(), 1):
            # <!-- style-lint: off --> ... <!-- style-lint: on --> marks a
            # region where the offender words appear legitimately — the
            # known-offender table itself, or a verbatim quotation of
            # external material that must not be reworded.
            if re.search(r"<!--\s*style-lint:\s*off\b", raw):
                lint_off = True
                continue
            if re.search(r"<!--\s*style-lint:\s*on\b", raw):
                lint_off = False
                continue
            if raw.lstrip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence or lint_off:
                continue
            line = prose_of(raw)
            for term, (occ_re, gloss_re, advice) in OFFENDERS.items():
                if term in reported:
                    continue
                if term == "wire":
                    line_wo_idiom = ON_THE_WIRE_RE.sub(" ", line)
                    hit = occ_re.search(line_wo_idiom)
                else:
                    hit = occ_re.search(line)
                if not hit:
                    continue
                if gloss_re is not None and gloss_re.search(flat):
                    reported.add(term)  # glossed somewhere in this file: ok
                    continue
                problems.append(f"{rel}:{lineno}: '{hit.group(0)}' without "
                                f"its gloss — {advice}")
                reported.add(term)  # one report per term per file

    for p in problems:
        print(p)
    print(f"\nchecked {len(files)} files -> {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
