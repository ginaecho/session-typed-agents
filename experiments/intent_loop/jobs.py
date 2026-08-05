"""jobs.py — background episode runs with observable progress.

A live episode is ~8-15 LLM calls and can take minutes, which is far too
long to hold an HTTP request open — especially for an agent client, which
would have to guess a timeout. So POST /api/runs returns a job id
immediately and both humans and agents poll GET /api/runs/<id>, watching
the same stage events the loop emits (start -> interrogated -> drafted ->
evaluated -> done).

In-memory and single-process on purpose: this is a local research tool, and
the durable record of every run is the session directory plus the corpus
JSONL, not this registry. Losing job state on restart costs nothing;
completed work is already on disk.
"""
from __future__ import annotations

import threading
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Job:
    def __init__(self, job_id: str, kind: str, params: dict):
        self.id = job_id
        self.kind = kind
        self.params = params
        self.state = "queued"          # queued|running|succeeded|failed
        self.events: list[dict] = []
        self.result: Optional[dict] = None
        self.error: Optional[str] = None
        self.created = _now()
        self.finished: Optional[str] = None
        self._lock = threading.Lock()
        #: When a human is answering the interrogation, the run thread
        #: blocks and these carry the open question to the UI and the reply
        #: back. A conversation needs the run to WAIT, not to finish and be
        #: read afterwards.
        self.awaiting: Optional[str] = None
        self.answer_sink: Optional[Callable[[str], None]] = None

    def ask(self, questions: str) -> None:
        with self._lock:
            self.awaiting = questions
        self.emit("awaiting_answer", {"questions": questions})

    def answer(self, text: str) -> bool:
        """Deliver a human reply. False if nothing was waiting for one."""
        with self._lock:
            sink, waiting = self.answer_sink, self.awaiting
            self.awaiting = None
        if sink is None or waiting is None:
            return False
        sink(text)
        self.emit("answer_received", {"chars": len(text)})
        return True

    def emit(self, stage: str, detail: dict) -> None:
        with self._lock:
            self.events.append({"stage": stage, "at": _now(), **detail})

    def to_dict(self, include_events: bool = True) -> dict[str, Any]:
        with self._lock:
            d = {"id": self.id, "kind": self.kind, "state": self.state,
                 "params": self.params, "created": self.created,
                 "finished": self.finished, "result": self.result,
                 "error": self.error, "awaiting": self.awaiting,
                 "stage": (self.events[-1]["stage"] if self.events
                           else None),
                 "stage_since": (self.events[-1]["at"] if self.events
                                 else self.created)}
            if include_events:
                d["events"] = list(self.events)
            return d


class JobRegistry:
    """Thread-safe job store. `max_jobs` bounds memory on a long-lived
    server by dropping the oldest FINISHED jobs (running ones are never
    evicted)."""

    def __init__(self, max_jobs: int = 200):
        self._jobs: dict[str, Job] = {}
        self._order: list[str] = []
        self._lock = threading.Lock()
        self.max_jobs = max_jobs

    def submit(self, kind: str, params: dict,
               fn: Callable[[Job], dict]) -> Job:
        job = Job(uuid.uuid4().hex[:12], kind, params)
        with self._lock:
            self._jobs[job.id] = job
            self._order.append(job.id)
            self._evict_locked()

        def _run() -> None:
            job.state = "running"
            try:
                job.result = fn(job)
                job.state = "succeeded"
            except Exception as e:
                job.error = f"{type(e).__name__}: {e}"
                job.emit("error", {"traceback": traceback.format_exc()[-4000:]})
                job.state = "failed"
            finally:
                job.finished = _now()

        threading.Thread(target=_run, name=f"job-{job.id}",
                         daemon=True).start()
        return job

    def _evict_locked(self) -> None:
        while len(self._order) > self.max_jobs:
            for i, jid in enumerate(self._order):
                if self._jobs[jid].state in ("succeeded", "failed"):
                    del self._jobs[jid]
                    self._order.pop(i)
                    break
            else:
                return  # nothing evictable

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self) -> list[Job]:
        with self._lock:
            return [self._jobs[j] for j in reversed(self._order)]
