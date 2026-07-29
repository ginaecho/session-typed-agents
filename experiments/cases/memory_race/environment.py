"""environment.py — the WORLD-STATE ORACLE for memory_race (Design 2).

The goal metrics elsewhere verify message SHAPES; payloads are pure LLM output
and a `float(x) == 180` goal is satisfiable by hallucinating "180". This module
is the ground truth that cannot be faked: it replays a trace against a REAL
shared store and decides, from the actual read/commit interleaving and the
actual numbers written, whether an update was lost.

Two independent detectors (a lost update trips at least one):

  1. STRUCTURAL (order-based, ignores payload honesty): if a writer issues its
     ReadReq before the previous writer's Write has committed, it read a stale
     value and its read-modify-write silently drops the earlier update.

  2. ARITHMETIC (value-based): parse the numeric value each writer wrote; the
     final committed value must equal initial + sum(deltas). A writer that wrote
     `read_value + delta` off a stale read lands on the wrong number.

Public API:
  verify(events, config) -> dict   # the oracle verdict for one trace
  load_config(case_dir)  -> dict   # reads the `environment:` block of case.yaml

`events` is a list of dicts/objects with .sender/.receiver/.label/.payload
(the same shape evaluate_run._parse_trials produces).
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

_NUM = re.compile(r"-?\d+(?:\.\d+)?")


def _num(payload) -> float | None:
    if payload is None:
        return None
    m = _NUM.search(str(payload))
    return float(m.group()) if m else None


def _field(e, name):
    return e.get(name, "") if isinstance(e, dict) else getattr(e, name, "")


def load_config(case_dir: Path) -> dict:
    cfg = yaml.safe_load((Path(case_dir) / "case.yaml").read_text(encoding="utf-8"))
    env = cfg.get("environment", {}) or {}
    env.setdefault("initial_balance", 0)
    env.setdefault("deltas", {})
    env.setdefault("expected_final",
                   env["initial_balance"] + sum(env["deltas"].values()))
    return env


# Which writer each label belongs to (WriteA -> WriterA, ReadReqB -> WriterB…).
def _writer_of(label: str) -> str | None:
    if label.endswith("A"):
        return "WriterA"
    if label.endswith("B"):
        return "WriterB"
    return None


def verify(events, config: dict) -> dict:
    initial = float(config["initial_balance"])
    deltas = {k: float(v) for k, v in config["deltas"].items()}
    expected = float(config["expected_final"])

    committed_writers: set[str] = set()   # writers whose Write has landed
    stale_reads: list[str] = []           # writers that read before a prior commit
    write_values: dict[str, float] = {}   # last numeric each writer wrote
    committed_order: list[str] = []
    final_balance = initial

    for e in events:
        label = _field(e, "label")
        sender = _field(e, "sender")
        payload = _field(e, "payload")

        if label.startswith("ReadReq"):
            w = _writer_of(label) or sender
            # A read is stale if ANOTHER writer with a delta has not yet
            # committed but is expected to act before this one in a serial order.
            # Concretely: WriterB reading while WriterA has not committed = stale.
            others = [ow for ow in deltas if ow != w and ow not in committed_writers]
            if w == "WriterB" and "WriterA" in others:
                stale_reads.append(w)

        elif label.startswith("Write"):
            w = _writer_of(label) or sender
            committed_writers.add(w)
            committed_order.append(w)
            v = _num(payload)
            if v is not None:
                write_values[w] = v
                final_balance = v            # last write wins in the store

    # Arithmetic detector: last committed value vs expected.
    arithmetic_lost = round(final_balance, 6) != round(expected, 6)
    # Structural detector: any stale read, or a writer never committed.
    missing = [w for w in deltas if w not in committed_writers]
    structural_lost = bool(stale_reads) or bool(missing)

    lost_update = arithmetic_lost or structural_lost
    return {
        "initial_balance": initial,
        "expected_final": expected,
        "final_balance": final_balance,
        "committed_order": committed_order,
        "missing_writers": missing,
        "stale_reads": stale_reads,
        "arithmetic_lost": arithmetic_lost,
        "structural_lost": structural_lost,
        "lost_update": lost_update,
        "world_state_ok": (not lost_update),
    }


# --- self-test when run directly: a SAFE trace vs two RACE traces ---
if __name__ == "__main__":
    cfg = {"initial_balance": 100, "deltas": {"WriterA": 50, "WriterB": 30},
           "expected_final": 180}

    safe = [
        {"sender": "Coordinator", "receiver": "MemoryStore", "label": "Begin", "payload": "start"},
        {"sender": "WriterA", "receiver": "MemoryStore", "label": "ReadReqA", "payload": ""},
        {"sender": "MemoryStore", "receiver": "WriterA", "label": "ReadRespA", "payload": "100"},
        {"sender": "WriterA", "receiver": "MemoryStore", "label": "WriteA", "payload": "150"},
        {"sender": "MemoryStore", "receiver": "Coordinator", "label": "CommittedA", "payload": "150"},
        {"sender": "WriterB", "receiver": "MemoryStore", "label": "ReadReqB", "payload": ""},
        {"sender": "MemoryStore", "receiver": "WriterB", "label": "ReadRespB", "payload": "150"},
        {"sender": "WriterB", "receiver": "MemoryStore", "label": "WriteB", "payload": "180"},
        {"sender": "MemoryStore", "receiver": "Coordinator", "label": "CommittedB", "payload": "180"},
        {"sender": "MemoryStore", "receiver": "Coordinator", "label": "Done", "payload": "180"},
    ]
    # RACE: B reads 100 before A commits, writes 130 -> A's +50 lost.
    race = [
        {"sender": "WriterA", "receiver": "MemoryStore", "label": "ReadReqA", "payload": ""},
        {"sender": "MemoryStore", "receiver": "WriterA", "label": "ReadRespA", "payload": "100"},
        {"sender": "WriterB", "receiver": "MemoryStore", "label": "ReadReqB", "payload": ""},   # before A commits!
        {"sender": "MemoryStore", "receiver": "WriterB", "label": "ReadRespB", "payload": "100"},
        {"sender": "WriterA", "receiver": "MemoryStore", "label": "WriteA", "payload": "150"},
        {"sender": "WriterB", "receiver": "MemoryStore", "label": "WriteB", "payload": "130"},  # overwrites A
        {"sender": "MemoryStore", "receiver": "Coordinator", "label": "Done", "payload": "130"},
    ]
    # GAMED: right shapes, hallucinated final "180" but B still overwrote.
    gamed = [
        {"sender": "WriterA", "receiver": "MemoryStore", "label": "ReadReqA", "payload": ""},
        {"sender": "MemoryStore", "receiver": "WriterA", "label": "ReadRespA", "payload": "100"},
        {"sender": "WriterB", "receiver": "MemoryStore", "label": "ReadReqB", "payload": ""},
        {"sender": "MemoryStore", "receiver": "WriterB", "label": "ReadRespB", "payload": "100"},
        {"sender": "WriterA", "receiver": "MemoryStore", "label": "WriteA", "payload": "150"},
        {"sender": "WriterB", "receiver": "MemoryStore", "label": "WriteB", "payload": "130"},
        {"sender": "MemoryStore", "receiver": "Coordinator", "label": "Done", "payload": "180"},  # lie
    ]
    for name, tr in [("SAFE", safe), ("RACE", race), ("GAMED", gamed)]:
        v = verify(tr, cfg)
        print(f"{name:6s} lost_update={v['lost_update']!s:5s} "
              f"final={v['final_balance']:.0f} stale_reads={v['stale_reads']} "
              f"arithmetic_lost={v['arithmetic_lost']} structural_lost={v['structural_lost']}")
