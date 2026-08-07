"""
Live event emitter for stjp_graph.html.

Writes one JSON line per protocol event to events.jsonl as the experiment
runs. Each line carries the per-event monitor verdict (any violation that
fires on that step).

Used by stjp_live_demo.py and stjp_serve.py.
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Optional

from stjp_core.monitor.monitor import SessionMonitor, ViolationType


class LiveEventEmitter:
    """Append-only writer that wraps SessionMonitor for per-event verdicts.

    If ``mirror_path`` is given, every line is also written to that second
    file. The stjp_comparison.html live demo expects events at
    ``stjp_core/events_{bare,spec}.jsonl``; case_runner.py passes those as
    the mirror so case-runs render in the existing live UI.
    """

    _path_locks_guard = threading.Lock()
    _path_locks: dict[Path, threading.Lock] = {}

    @classmethod
    def _path_lock(cls, path: Path) -> threading.Lock:
        resolved = path.resolve()
        with cls._path_locks_guard:
            return cls._path_locks.setdefault(resolved, threading.Lock())

    def __init__(self, jsonl_path: Path, efsms, refinements,
                 mirror_path: Optional[Path] = None, *,
                 truncate: bool = True):
        self.path = Path(jsonl_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if truncate:
            self.path.write_text("", encoding="utf-8")
        self._fh = open(self.path, "a", encoding="utf-8", buffering=1)  # line-buffered
        self._lock = self._path_lock(self.path)
        self._mirror_fh = None
        if mirror_path is not None:
            self.mirror_path = Path(mirror_path)
            self.mirror_path.parent.mkdir(parents=True, exist_ok=True)
            self.mirror_path.write_text("", encoding="utf-8")
            self._mirror_fh = open(self.mirror_path, "a",
                                   encoding="utf-8", buffering=1)
        self._efsms = efsms
        self._refinements = refinements
        self._sm = SessionMonitor(efsms, refinements)

    def reset_monitors(self):
        """Reset all role monitors for a new trial."""
        self._sm = SessionMonitor(self._efsms, self._refinements)

    def emit(self, ev, *, trial: Optional[int] = None,
             scenario: Optional[str] = None,
             goals_pass: Optional[int] = None,
             goals_total: Optional[int] = None,
             extra: Optional[dict] = None) -> dict:
        """Run incremental monitoring on the event, then write a JSON line."""
        violation_dict = None
        # Each role monitor processes the event; first violation we see wins.
        for role, mon in self._sm.monitors.items():
            v = mon.process_event(ev)
            if v is not None:
                violation_dict = {
                    "type": v.violation_type.value,
                    "role": v.role,
                    "state": v.state,
                    "expected": v.expected,
                    "message": v.message,
                }
                break

        record = {
            "ts": time.time() * 1000,
            "step": ev.step,
            "sender": ev.sender,
            "receiver": ev.receiver,
            "label": ev.label,
            "payload": ev.payload,
            "trial": trial,
            "scenario": scenario,
            "goals_pass": goals_pass,
            "goals_total": goals_total,
            "violation": violation_dict,
        }
        if extra:
            record.update(extra)

        line = json.dumps(record) + "\n"
        with self._lock:
            self._fh.write(line)
            self._fh.flush()
            try:
                os.fsync(self._fh.fileno())
            except Exception:
                pass
            if self._mirror_fh is not None:
                self._mirror_fh.write(line)
                self._mirror_fh.flush()
        return record

    def emit_marker(self, kind: str, **kwargs) -> None:
        """Emit a non-event marker (e.g. trial-start, trial-end) for the UI."""
        record = {"ts": time.time() * 1000, "marker": kind}
        record.update(kwargs)
        line = json.dumps(record) + "\n"
        with self._lock:
            self._fh.write(line)
            self._fh.flush()
            if self._mirror_fh is not None:
                self._mirror_fh.write(line)
                self._mirror_fh.flush()

    def close(self):
        with self._lock:
            self._fh.close()
            if self._mirror_fh is not None:
                self._mirror_fh.close()
