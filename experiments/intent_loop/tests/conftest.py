"""Offline test fixtures — no network, no JVM, no Azure config.

Mirrors the seam_bench test convention: everything runs against MockChat
and the mock validator; the real toolchain is never touched.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
