"""
NuscrCompiler — drives the coinductive nuscr fork via Docker.

nuscr (phou/nuscr_coinduction) is invoked through the ``nuscr-coind`` Docker
image built from ``tools/nuscr/Dockerfile``. This backend implements the same
two operations as the Scribble backend (see ``compiler_iface.ProtocolCompiler``)
so downstream code (monitor, generation) can consume either interchangeably —
both produce the same ``EFSM`` dataclass.

Because nuscr is not Scribble-compatible, ``.scr`` inputs are first translated
to ``.nuscr`` (``nuscr_syntax.scr_to_nuscr``) and written under
``<NUSCR_DIR>/_stjp_tmp/`` so the Docker mount exposes them at a space-free
``/work`` path inside the container (the repo itself sits under a path with a
space, "OneDrive - Microsoft", which nuscr's CLI — like Scribble's — dislikes).

Environments whose network policy blocks Docker Hub (e.g. Claude Code on the
web) can point ``STJP_NUSCR_BIN`` at a native nuscr binary instead — built by
the fork's ``build-nuscr`` GitHub Actions workflow and fetched from the
``ci-artifacts`` branch (see docs/1_TECH_SETUP.md). When set, all invocations
run the binary directly and Docker is not required.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from stjp_core.config import (
    NUSCR_BIN,
    NUSCR_DIR,
    NUSCR_DOCKER_IMAGE,
    NUSCR_PROJECTION_MODE,
)
from stjp_core.compiler.efsm_parser import EFSM, parse_nuscr_fsm_dot
from stjp_core.compiler.nuscr_syntax import scr_to_nuscr

_TMP_SUBDIR = "_stjp_tmp"


class NuscrCompiler:
    """Protocol compiler backed by the coinductive nuscr fork (via Docker)."""

    name = "nuscr"

    def __init__(
        self,
        image: str = NUSCR_DOCKER_IMAGE,
        mode: str = NUSCR_PROJECTION_MODE,
        nuscr_dir: Path = NUSCR_DIR,
        binary: str | None = NUSCR_BIN,
    ):
        self.image = image
        self.mode = mode
        self.nuscr_dir = Path(nuscr_dir)
        self.binary = binary or None

    # -- internals ---------------------------------------------------------

    def _stage(self, protocol_path: Path) -> str:
        """Translate .scr->.nuscr (or copy .nuscr) into _stjp_tmp; return the
        container-relative path under /work."""
        protocol_path = Path(protocol_path)
        tmp_dir = self.nuscr_dir / _TMP_SUBDIR
        tmp_dir.mkdir(parents=True, exist_ok=True)
        out = tmp_dir / f"{protocol_path.stem}.nuscr"
        if protocol_path.suffix == ".nuscr":
            out.write_text(protocol_path.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            out.write_text(
                scr_to_nuscr(protocol_path.read_text(encoding="utf-8")),
                encoding="utf-8",
            )
        if self.binary:
            return str(out)
        return f"/work/{_TMP_SUBDIR}/{out.name}"

    def _docker(self, args: list[str]) -> subprocess.CompletedProcess:
        """Run nuscr — natively when ``STJP_NUSCR_BIN`` is set, else via Docker."""
        if self.binary:
            cmd = [self.binary, *args]
        else:
            cmd = [
                "docker", "run", "--rm",
                "-v", f"{self.nuscr_dir}:/work",
                self.image, *args,
            ]
        return subprocess.run(cmd, capture_output=True, text=True)

    # -- ProtocolCompiler interface ---------------------------------------

    def validate(self, protocol_path: Path) -> tuple[bool, str]:
        """Run ``nuscr check``. nuscr prints 'Well-formed: yes' / 'Balanced: yes'
        on success (unlike Scribble's silence=success)."""
        try:
            work = self._stage(protocol_path)
        except Exception as e:  # noqa: BLE001 - surface staging errors as invalid
            return False, f"nuscr staging error: {e}"
        result = self._docker(["check", work])
        out = (result.stdout or "").strip()
        err = (result.stderr or "").strip()
        if result.returncode == 0 and "Well-formed: yes" in out:
            return True, ""
        return False, out or err or f"nuscr check failed (rc={result.returncode})"

    def project_efsm(self, protocol_path: Path, protocol_name: str, role: str) -> EFSM:
        """Run ``nuscr --fsm=ROLE@PROTO`` and parse the DOT into an EFSM."""
        work = self._stage(protocol_path)
        result = self._docker([f"--fsm={role}@{protocol_name}", work])
        if result.returncode != 0:
            raise RuntimeError(
                f"nuscr --fsm failed for {role}@{protocol_name}: "
                f"{(result.stderr or result.stdout).strip()}"
            )
        return parse_nuscr_fsm_dot(result.stdout, role, protocol_name)

    # -- nuscr-specific extras --------------------------------------------

    def project_local_type(
        self, protocol_path: Path, protocol_name: str, role: str, mode: str | None = None
    ) -> str:
        """Run ``nuscr project [--mode=MODE] FILE ROLE@PROTO`` and return the
        textual local type. Use ``mode='coinductive-full'`` to project recursive
        receive-merges that the default inductive projection leaves as bare rec.
        """
        work = self._stage(protocol_path)
        mode = mode or self.mode
        args = ["project"]
        if mode:
            args.append(f"--mode={mode}")
        args += [work, f"{role}@{protocol_name}"]
        result = self._docker(args)
        if result.returncode != 0:
            raise RuntimeError(
                f"nuscr project failed for {role}@{protocol_name}: "
                f"{(result.stderr or result.stdout).strip()}"
            )
        return result.stdout.strip()

    def roles_and_protocols(self, protocol_path: Path) -> list[tuple[str, str]]:
        """Run ``nuscr --enum`` -> list of (role, protocol) pairs."""
        work = self._stage(protocol_path)
        result = self._docker(["--enum", work])
        pairs: list[tuple[str, str]] = []
        for line in (result.stdout or "").splitlines():
            m = re.match(r"^\s*(\w+)@(\w+)\s*$", line)
            if m:
                pairs.append((m.group(1), m.group(2)))
        return pairs
