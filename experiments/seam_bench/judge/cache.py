"""Verdict cache — plan v2.1 §5.1.

"Verdicts are cached keyed by (class, model, temp, prompt_hash,
payload_hash) — reproducible reruns, and a cache hit is by construction
identical isolation."

This is a plain on-disk JSON cache, one file per key hash. No heavy deps
(no sqlite, no diskcache) — a rerun of the same pipeline over the same
payloads must be a pure cache hit with zero LLM calls, which this
satisfies whether the rerun happens in the same process or a fresh one.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def cache_key(class_: str, model_id: str, temperature: float, prompt_hash: str, payload_hash: str) -> tuple:
    """The canonical (class, model, temp, prompt_hash, payload_hash) key from §5.1."""
    return (class_, model_id, round(float(temperature), 4), prompt_hash, payload_hash)


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0

    @property
    def total(self) -> int:
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        return self.hits / self.total if self.total else 0.0


class VerdictCache:
    """Generic (key-tuple -> JSON value) disk cache.

    Used for judge verdicts, paraphrase text, reconstructed-intent text,
    comparator scores, and probe-compilation results — anything that is a
    pure function of (class, model, temp, prompt, payload) and should
    never be recomputed for the same inputs.
    """

    def __init__(self, cache_dir: str | Path):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.stats = CacheStats()

    def _path_for(self, key: tuple) -> Path:
        raw = "|".join(str(part) for part in key)
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}.json"

    def get(self, key: tuple) -> Any:
        path = self._path_for(key)
        if path.exists():
            self.stats.hits += 1
            return json.loads(path.read_text(encoding="utf-8"))
        self.stats.misses += 1
        return None

    def put(self, key: tuple, value: Any) -> None:
        path = self._path_for(key)
        path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")

    def get_or_compute(self, key: tuple, compute: Callable[[], Any]) -> Any:
        cached = self.get(key)
        if cached is not None:
            return cached
        value = compute()
        self.put(key, value)
        return value

    def clear(self) -> None:
        for f in self.cache_dir.glob("*.json"):
            f.unlink()
        self.stats = CacheStats()
