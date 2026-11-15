"""Settings read from the environment. Paths are relative to the repo root."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

from app import __version__

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
STATIC_DIR = ROOT / "app" / "static"
CORPUS_PATH = DATA_DIR / "corpus.json"
TIMELINE_PATH = DATA_DIR / "timeline.json"
OBLIGATIONS_PATH = DATA_DIR / "obligations.json"
CHROMA_DIR = ROOT / "chroma_db"

VERSION = __version__

# Checked on 11 Nov 2026 against https://aistudio.google.com/docs/models,
# https://aistudio.google.com/docs/pricing and https://aistudio.google.com/docs/rate-limits:
# all three are listed with a free tier; 3.5 Flash-Lite and 3.1 Flash-Lite are Stable,
# 2.5 Flash-Lite is "served until further notice".
DEFAULT_MODEL = "gemini-3.5-flash-lite"
DEFAULT_FALLBACKS = ("gemini-3.1-flash-lite", "gemini-2.5-flash-lite")
# The values langchain-google-genai accepts for thinking_level; anything else falls back to low.
THINKING_LEVELS = ("minimal", "low", "medium", "high")

# A local .env works for the owner; on the Space the variables come from secrets.
load_dotenv(ROOT / ".env")


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    try:
        return float(raw) if raw else default
    except ValueError:
        return default


def _flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    google_api_key: str | None
    gemini_model: str
    fallback_models: tuple[str, ...]
    fake_llm: bool
    rate_limit_per_min: int
    rate_limit_per_day: int
    daily_budget: int
    search_limit_per_min: int
    port: int
    llm_timeout: float
    thinking_level: str | None
    max_concurrent: int = 4
    trusted_proxy_hops: int = 1
    global_rate_per_min: int = 20
    screen_deadline: float = 120.0
    report_limit_per_min: int = 20
    report_secret: str | None = field(default=None, repr=False)
    fake_delay: float = 0.4
    warmup: bool = True
    version: str = VERSION
    root: Path = field(default=ROOT)

    @property
    def models(self) -> tuple[str, ...]:
        """The first model followed by the fallbacks, without duplicates."""
        seen: list[str] = []
        for name in (self.gemini_model, *self.fallback_models):
            if name and name not in seen:
                seen.append(name)
        return tuple(seen)

    @property
    def llm_ready(self) -> bool:
        return self.fake_llm or bool(self.google_api_key)


def _load() -> Settings:
    fallbacks_raw = os.environ.get("GEMINI_FALLBACK_MODELS")
    if fallbacks_raw is None:
        fallbacks = DEFAULT_FALLBACKS
    else:
        fallbacks = tuple(m.strip() for m in fallbacks_raw.split(",") if m.strip())
    thinking = os.environ.get("GEMINI_THINKING_LEVEL", "low").strip().lower() or None
    if thinking in {"none", "off", "default"}:
        thinking = None
    elif thinking not in THINKING_LEVELS:
        thinking = "low"
    return Settings(
        google_api_key=(os.environ.get("GOOGLE_API_KEY") or "").strip() or None,
        gemini_model=(os.environ.get("GEMINI_MODEL") or "").strip() or DEFAULT_MODEL,
        fallback_models=fallbacks,
        fake_llm=_flag("SCREENER_FAKE_LLM"),
        rate_limit_per_min=_int("RATE_LIMIT_PER_MIN", 6),
        rate_limit_per_day=_int("RATE_LIMIT_PER_DAY", 60),
        daily_budget=_int("DAILY_BUDGET", 900),
        search_limit_per_min=_int("SEARCH_LIMIT_PER_MIN", 60),
        port=_int("PORT", 7860),
        llm_timeout=_float("LLM_TIMEOUT", 60.0),
        thinking_level=thinking,
        max_concurrent=_int("MAX_CONCURRENT_LLM", 4),
        trusted_proxy_hops=max(0, _int("TRUSTED_PROXY_HOPS", 1)),
        global_rate_per_min=_int("GLOBAL_RATE_PER_MIN", 20),
        screen_deadline=_float("SCREEN_DEADLINE", 120.0),
        report_limit_per_min=_int("REPORT_LIMIT_PER_MIN", 20),
        report_secret=(os.environ.get("REPORT_SECRET") or "").strip() or None,
        fake_delay=_float("SCREENER_FAKE_DELAY", 0.4),
        warmup=os.environ.get("SCREENER_WARMUP", "1").strip() != "0",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return _load()


def reload_settings() -> Settings:
    """Re-read the environment (used by tests)."""
    get_settings.cache_clear()
    return get_settings()
