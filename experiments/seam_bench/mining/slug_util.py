"""Filesystem-safe slug helper shared by the llm_read extraction/emit steps.

A ``team_id`` can enumerate every role in a large team (see W16). Slugified 1:1
into a filename, one such id produced a 226-char basename / 282-char path that
blew past Windows' MAX_PATH (260) and made ``git clone`` fail the working-tree
checkout ("Filename too long"). ``sanitize`` bounds the slug length while keeping
it unique via a short content hash, so any path derived from it stays portable.

``extraction.py`` (writes ``annotated/<slug>/`` dirs + evidence sidecars) and
``emit_records.py`` (reads those same dirs) both import this one function, so
their slugs are guaranteed to match.
"""
from __future__ import annotations

import hashlib
import re

# "NN_" prefix (3) + slug + ".json" (5), sitting under the deepest committed
# sample dir (~55 chars), keeps the worst-case repo-relative path well under
# Windows' 260-char MAX_PATH even when cloned into a nested directory.
MAX_SLUG_LEN = 96


def sanitize(name: str, max_len: int = MAX_SLUG_LEN) -> str:
    """Slugify ``name`` to ``[A-Za-z0-9_]``, capped at ``max_len`` chars.

    Names within the cap are returned unchanged (so existing short slugs are
    untouched). Over-long names are truncated and suffixed with an 8-hex digest
    of the full name, so two distinct long names never collide onto the same
    filename.
    """
    slug = re.sub(r"[^A-Za-z0-9_]", "_", name)
    if len(slug) <= max_len:
        return slug
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]
    return f"{slug[: max_len - 9]}_{digest}"
