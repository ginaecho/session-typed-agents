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

# Java for running the Scribble compiler. Honour a real JAVA_HOME from the
# environment if set; otherwise fall back to a JDK present on this machine.
JAVA_HOME = os.environ.get("JAVA_HOME") or r"C:\Program Files\Java\jdk-17.0.18"

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
