"""Gemini through langchain-google-genai: structured output for screening, token streaming for ask.

The models in Settings.models are tried in order. A model that fails for any reason hands
over to the next one; a key error ends as not_configured only when every model gives it.
Each call has its own timeout, a malformed structured answer gets one retry in the whole
chain, and no new call starts when the caller's deadline (DEADLINE) is near. Errors leave
this module only as LLMError with one of the contract codes: quota, llm_error, not_configured.
Cancellation (asyncio.CancelledError) is never caught.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import AsyncIterator, Sequence
from contextvars import ContextVar
from typing import Any

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, ValidationError

from app.config import Settings, get_settings
from app.schemas import llm_json_schema

log = logging.getLogger("screener.llm")

LOW_TEMPERATURE = 0.2
CALL_TIMEOUT = 45.0  # seconds per model call, at most
MIN_CALL_SECONDS = 8.0  # no new call starts with less time than this before the deadline
STREAM_TOTAL = 90.0  # seconds for a whole streamed answer
MALFORMED_RETRIES = 1  # in the whole chain

# Monotonic time (time.monotonic()) by which the caller needs an answer, or None.
DEADLINE: ContextVar[float | None] = ContextVar("llm_deadline", default=None)


class LLMError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _major_version(model: str) -> int:
    m = re.search(r"gemini-(\d+)", model.lower())
    return int(m.group(1)) if m else 0


def make_chat(model: str, settings: Settings) -> Any:
    """One ChatGoogleGenerativeAI client. Imported lazily so the app starts without the package."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    kwargs: dict[str, Any] = {
        "model": model,
        "google_api_key": settings.google_api_key,
        # 1 means a single attempt: the fallback chain replaces the SDK's blind backoff,
        # which ignores the retry delay that a 429 carries.
        "max_retries": 1,
        "timeout": call_timeout(settings),
    }
    if _major_version(model) >= 3:
        # Gemini 3+ use fixed sampling (the library drops custom values for 3.5 Flash-Lite
        # and 3.6 Flash); reasoning depth is set with the thinking level instead.
        if settings.thinking_level:
            kwargs["thinking_level"] = settings.thinking_level
    else:
        kwargs["temperature"] = LOW_TEMPERATURE
    return ChatGoogleGenerativeAI(**kwargs)


def call_timeout(settings: Settings) -> float:
    return min(float(settings.llm_timeout or CALL_TIMEOUT), CALL_TIMEOUT)


def _time_left(deadline: float | None) -> float | None:
    return None if deadline is None else deadline - time.monotonic()


def classify(exc: BaseException) -> tuple[str, str]:
    """Map an exception to (kind, detail). kind: not_found, quota, auth, bad_request, server, timeout, other."""
    try:
        from langchain_google_genai.chat_models import (
            GoogleAPIError,
            GoogleAuthenticationError,
            GoogleInvalidRequestError,
            GoogleModelNotFoundError,
            GooglePermissionDeniedError,
            GoogleRateLimitError,
        )
    except Exception:  # pragma: no cover - only when the package is missing
        GoogleAPIError = GoogleAuthenticationError = GoogleInvalidRequestError = ()  # type: ignore
        GoogleModelNotFoundError = GooglePermissionDeniedError = GoogleRateLimitError = ()  # type: ignore

    text = str(exc)
    code = getattr(exc, "code", None) or getattr(getattr(exc, "__cause__", None), "code", None)
    lowered = text.lower()
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)) or "timeout" in type(exc).__name__.lower():
        return "timeout", "The model did not answer in time."
    if "api key" in lowered or "api_key" in lowered:
        return "auth", "The Gemini API key was rejected."
    if (GoogleModelNotFoundError and isinstance(exc, GoogleModelNotFoundError)) or code == 404:
        return "not_found", text
    if (GoogleRateLimitError and isinstance(exc, GoogleRateLimitError)) or code == 429 or "resource_exhausted" in lowered:
        return "quota", text
    if (GoogleAuthenticationError and isinstance(exc, (GoogleAuthenticationError, GooglePermissionDeniedError))) or code in (401, 403):
        return "auth", text
    if (GoogleInvalidRequestError and isinstance(exc, GoogleInvalidRequestError)) or code == 400:
        return "bad_request", text
    if (GoogleAPIError and isinstance(exc, GoogleAPIError)) or (isinstance(code, int) and code >= 500):
        return "server", text
    return "other", text


def _raise_final(kinds: list[str]) -> None:
    if kinds and all(k == "auth" for k in kinds):
        raise LLMError("not_configured", "The Gemini API key was rejected by Google.")
    if kinds and all(k == "quota" for k in kinds):
        raise LLMError("quota", "The free model quota is used up for now. Please try again later.")
    raise LLMError("llm_error", "The language model could not answer. Please try again in a minute.")


def _check_ready(settings: Settings) -> None:
    if not settings.google_api_key:
        raise LLMError("not_configured", "Screening is not configured on this server (no Gemini API key).")


def _kind(exc: BaseException, model: str) -> str:
    """quota, auth or error. A key or permission error on one model does not end the chain:
    the next model may be open to the key."""
    kind, _detail = classify(exc)
    # Never log user text; only the model name and the kind.
    log.warning("model %s failed: %s", model, kind)
    return kind if kind in ("quota", "auth") else "error"


async def generate_structured(
    messages: Sequence[BaseMessage],
    schema: type[BaseModel],
    settings: Settings | None = None,
    chat_factory=make_chat,
    deadline: float | None = None,
) -> tuple[BaseModel, str]:
    """One structured answer. Returns (parsed model, model name).

    Gemini gets the plain schema of llm_json_schema(); the answer is validated with the
    pydantic model. A malformed answer is retried once on the same model, once in the
    whole chain. `deadline` (or DEADLINE) stops the chain before the caller gives up."""
    settings = settings or get_settings()
    _check_ready(settings)
    deadline = deadline if deadline is not None else DEADLINE.get()
    plain_schema = llm_json_schema(schema)
    kinds: list[str] = []
    retries = MALFORMED_RETRIES
    for model in settings.models:
        left = _time_left(deadline)
        if left is not None and left < MIN_CALL_SECONDS:
            log.warning("model chain stopped before %s: deadline", model)
            kinds.append("error")
            break
        try:
            runnable = chat_factory(model, settings).with_structured_output(
                plain_schema, method="json_schema", include_raw=True
            )
        except Exception as exc:  # a bad model name can fail at construction
            kinds.append(_kind(exc, model))
            continue
        while True:
            left = _time_left(deadline)
            timeout = call_timeout(settings) if left is None else max(1.0, min(call_timeout(settings), left))
            try:
                out = await asyncio.wait_for(runnable.ainvoke(list(messages)), timeout=timeout)
            except Exception as exc:
                kinds.append(_kind(exc, model))
                break
            parsed = out.get("parsed") if isinstance(out, dict) and "parsed" in out else out
            if isinstance(parsed, dict):
                try:
                    parsed = schema.model_validate(parsed)
                except ValidationError:
                    parsed = None
            if isinstance(parsed, schema):
                return parsed, model
            log.warning("model %s returned a malformed structured answer", model)
            left = _time_left(deadline)
            if retries > 0 and (left is None or left >= MIN_CALL_SECONDS):
                retries -= 1
                continue
            kinds.append("error")
            break
    _raise_final(kinds)
    raise AssertionError("unreachable")


def chunk_text(chunk: Any) -> str:
    """Text of a streamed AIMessageChunk; content is a string or a list of blocks."""
    content = getattr(chunk, "content", chunk)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out = []
        for block in content:
            if isinstance(block, str):
                out.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                out.append(block.get("text") or "")
        return "".join(out)
    return ""


async def stream_text(
    messages: Sequence[BaseMessage],
    settings: Settings | None = None,
    chat_factory=make_chat,
) -> AsyncIterator[str]:
    """Stream answer text. Falls back to the next model only before the first token.

    Each chunk has to arrive within the call timeout and the whole answer within STREAM_TOTAL."""
    settings = settings or get_settings()
    _check_ready(settings)
    kinds: list[str] = []
    end = time.monotonic() + STREAM_TOTAL
    for model in settings.models:
        started = False
        try:
            chat = chat_factory(model, settings)
            stream = chat.astream(list(messages)).__aiter__()
            while True:
                left = end - time.monotonic()
                if left <= 0:
                    raise TimeoutError("stream took too long")
                try:
                    chunk = await asyncio.wait_for(stream.__anext__(), timeout=min(call_timeout(settings), left))
                except StopAsyncIteration:
                    break
                text = chunk_text(chunk)
                if text:
                    started = True
                    yield text
            if started:
                return
            kinds.append("error")  # an empty answer: try the next model
        except Exception as exc:
            kind = _kind(exc, model)
            if started:
                raise LLMError("llm_error", "The answer was cut off. Please ask again.") from exc
            kinds.append(kind)
        if time.monotonic() >= end:
            break
    _raise_final(kinds)
