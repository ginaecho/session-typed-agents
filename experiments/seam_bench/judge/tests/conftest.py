from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Callable

import pytest

from experiments.seam_bench.judge.cache import VerdictCache

CORPUS_DIR = Path(__file__).resolve().parents[4] / "experiments" / "cases" / "_corpus"


def load_corpus(name: str) -> str:
    return (CORPUS_DIR / name).read_text(encoding="utf-8")


class MockMessages:
    def __init__(self, responder: Callable[[dict], str]):
        self._responder = responder
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        text = self._responder(kwargs)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])


class MockAnthropic:
    """A minimal stand-in for anthropic.Anthropic. ``responder`` maps a
    create() call's kwargs to the text of the single text content block
    the real API would have returned (a JSON string for structured-output
    calls, plain text otherwise)."""

    def __init__(self, responder: Callable[[dict], str]):
        self.messages = MockMessages(responder)

    @property
    def call_count(self) -> int:
        return len(self.messages.calls)


@pytest.fixture
def cache(tmp_path: Path) -> VerdictCache:
    return VerdictCache(tmp_path / "judge_cache")


@pytest.fixture
def corpus_000() -> str:
    return load_corpus("corpus_000.scr")


@pytest.fixture
def corpus_001() -> str:
    return load_corpus("corpus_001.scr")
