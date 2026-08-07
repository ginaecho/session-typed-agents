"""Configuration constants for the STJP library.

All experiment artefacts (protocols, skills, runs) live under
``experiments/cases/<case>/`` — see ``experiments/CLAUDE.md``. This module
only carries paths needed to invoke the Scribble compiler. The previously
exported ``PROTOCOLS_DIR``, ``SKILLS_DIR`` and ``VERSION_HISTORY_FILE``
constants were removed on 2026-05-29 along with the legacy data directories
they pointed at.
"""

import os
from pathlib import Path

# Directory Configuration
BASE_DIR = Path(__file__).parent          # stjp_core/
REPO_ROOT = BASE_DIR.parent               # testing_ideas/

# Scribble Configuration
# Resolved RELATIVE to the repo so it survives the project being moved/renamed.
# Layout: scribble-java/scribble-dist/target/{lib/*.jar, scribblec.sh}
SCRIBBLE_PATH = REPO_ROOT / "scribble-java" / "scribble-dist" / "target"

# Java for running the Scribble compiler. Honour JAVA_HOME from the
# environment ONLY if it actually exists on disk — this machine's ambient
# JAVA_HOME points at a non-existent JDK-11 placeholder path, which used to
# win over the fallback and break every Scribble invocation (found during
# the 2026-08-05 toolchain preflight). Otherwise fall back to the first
# real JDK found.
def _resolve_java_home() -> str:
    candidates = [os.environ.get("JAVA_HOME"),
                  r"C:\Program Files\Java\jdk-17.0.19",
                  r"C:\Program Files\Java\jdk-17.0.18"]
    for c in candidates:
        if c and Path(c).exists():
            return c
    # Last resort: whatever `java` resolves to on PATH (empty string keeps
    # subprocess env untouched so PATH lookup applies).
    return ""

JAVA_HOME = _resolve_java_home()

# ---------------------------------------------------------------------------
# Protocol compiler backend selection
# ---------------------------------------------------------------------------
# STJP can drive two protocol compilers behind a common interface
# (compiler/compiler_iface.py):
#   - "scribble" (default): the vendored scribble-java (org.scribble.cli).
#   - "nuscr": the coinductive nuscr fork (phou/nuscr_coinduction), invoked via
#     Docker. nuscr is NOT Scribble-compatible and supports only a fragment of
#     the protocols scribble-java accepts, but it can COINDUCTIVELY project some
#     recursive protocols that stock projection rejects.
COMPILER_BACKEND = os.environ.get("STJP_COMPILER_BACKEND", "scribble")

# nuscr (coinductive fork) — vendored checkout + Docker image built from
# tools/nuscr/Dockerfile. See docs/reference/NUSCR_AND_SKILL_SAFETY_PLAN.md.
NUSCR_DIR = REPO_ROOT / "nuscr-coinduction"
NUSCR_DOCKER_IMAGE = os.environ.get("STJP_NUSCR_IMAGE", "nuscr-coind:latest")
# Native nuscr binary (skips Docker entirely). Point this at a binary built by
# the fork's build-nuscr GitHub Actions workflow (ci-artifacts branch) when the
# environment cannot pull Docker images (e.g. Claude Code on the web).
NUSCR_BIN = os.environ.get("STJP_NUSCR_BIN", "")
# Projection mode: "inductive-full" (default nuscr), "coinductive-full"
# (knowledge-set coinductive projection with full receive merge), or
# "coinductive-plain". Coinductive modes project recursive receive-merges that
# the inductive mode leaves as a bare rec.
NUSCR_PROJECTION_MODE = os.environ.get("STJP_NUSCR_MODE", "coinductive-full")
