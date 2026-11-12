from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from stubs import OBLIGATIONS, TIMELINE, StubCorpus, StubRetriever  # noqa: E402

REAL_CORPUS = ROOT / "data" / "corpus.json"


def parse_sse(text: str) -> list[tuple[str, dict]]:
    events = []
    for block in text.strip().split("\n\n"):
        name, data = None, None
        for line in block.splitlines():
            if line.startswith("event: "):
                name = line[7:]
            elif line.startswith("data: "):
                data = json.loads(line[6:])
        if name:
            events.append((name, data))
    return events


@pytest.fixture
def env(monkeypatch):
    """Fake mode, no key, no delays, no warm-up."""
    from app import config

    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("SCREENER_FAKE_LLM", "1")
    monkeypatch.setenv("SCREENER_FAKE_DELAY", "0")
    monkeypatch.setenv("SCREENER_WARMUP", "0")
    for name in ("RATE_LIMIT_PER_MIN", "RATE_LIMIT_PER_DAY", "DAILY_BUDGET", "GEMINI_MODEL", "GEMINI_FALLBACK_MODELS"):
        monkeypatch.delenv(name, raising=False)
    config.reload_settings()
    yield monkeypatch
    config.reload_settings()


@pytest.fixture
def stub_corpus():
    return StubCorpus()


@pytest.fixture
def stub_retriever(stub_corpus):
    return StubRetriever(stub_corpus)


@pytest.fixture
def stubbed(env, stub_corpus, stub_retriever):
    """Stub corpus, retriever, timeline and obligations everywhere the app reads them."""
    from app import ask, main, screener

    env.setattr(screener, "corpus_or_none", lambda: stub_corpus)
    env.setattr(screener, "retriever_any", lambda: stub_retriever)
    env.setattr(ask, "corpus_or_none", lambda: stub_corpus)
    env.setattr(ask, "retriever_any", lambda: stub_retriever)
    env.setattr(screener, "load_timeline", lambda: TIMELINE)
    env.setattr(screener, "load_obligations", lambda: OBLIGATIONS)
    for lim in (main.limiter, main.global_limiter, main.search_limiter, main.report_limiter):
        lim.reset()
    return env


@pytest.fixture
def client(stubbed):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


def set_env(monkeypatch, **values):
    from app import config

    for k, v in values.items():
        if v is None:
            monkeypatch.delenv(k, raising=False)
        else:
            monkeypatch.setenv(k, str(v))
    return config.reload_settings()
