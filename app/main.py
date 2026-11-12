"""FastAPI app: the page, the reader and search API, screening and ask (SSE), the report."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import ipaddress
import json
import logging
import mimetypes
import os
import re
import threading
import time
from collections import OrderedDict, deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.gzip import GZipMiddleware

from app import ask as ask_mod
from app import report as report_mod
from app import screener
from app.config import ROOT, STATIC_DIR, Settings, get_settings
from app.examples import list_examples
from app.llm import LLMError
from app.visits import Visits
from app.schemas import AskRequest, ReportRequest, ScreenRequest

log = logging.getLogger("screener.api")

MAX_BODY_BYTES = 64 * 1024
RATE_KEYS_MAX = 50_000
SEARCH_THREADS = 4
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; "
    "connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; "
    # The Hugging Face Space page shows the app in an iframe.
    "frame-ancestors 'self' https://huggingface.co https://*.hf.space"
)
SECURITY_HEADERS = [
    (b"content-security-policy", CSP.encode()),
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"no-referrer"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=(), interest-cohort=()"),
    (b"cross-origin-opener-policy", b"same-origin"),
]
# Fonts never change between releases; the page, scripts and styles are checked against
# their ETag on every load, so a new release shows at once.
FONT_CACHE = b"public, max-age=604800"
STATIC_CACHE = b"no-cache"
mimetypes.add_type("font/woff2", ".woff2")


# Logging: no line may carry text a user typed.

_LOGGED_PATHS = {
    "/", "/api/health", "/api/source", "/api/examples", "/api/timeline", "/api/toc", "/api/search",
    "/api/screen", "/api/ask", "/api/report", "/disclaimer",
}


def safe_path(path: str) -> str:
    """The path as it may appear in a log line: known routes only, parameters replaced."""
    path = path.split("?", 1)[0]
    if path in _LOGGED_PATHS:
        return path
    if path.startswith("/api/unit/"):
        return "/api/unit/{ref}"
    if path.startswith("/static/"):
        return "/static/{file}"
    return "/{other}"


class _SafeAccessLog(logging.Filter):
    """uvicorn access lines: (client, method, path, http version, status).

    The client address is replaced by "-" and the path by its safe form."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 3 and isinstance(args[2], str):
            record.args = ("-", args[1], safe_path(args[2]), *args[3:])
        return True


logging.getLogger("uvicorn.access").addFilter(_SafeAccessLog())


# Startup


def _warmup() -> None:
    screener.corpus_or_none()
    screener.retriever_any()


visits = Visits.from_env("eu-ai-act-screener")


@asynccontextmanager
async def lifespan(_: FastAPI):
    if get_settings().warmup:
        threading.Thread(target=_warmup, name="warmup", daemon=True).start()
    visits.start()
    yield
    await asyncio.to_thread(visits.close)


# Middleware


class SecurityHeaders:
    """Pure ASGI middleware, so streaming responses pass through untouched."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {k.lower() for k, _ in headers}
                headers += [(k, v) for k, v in SECURITY_HEADERS if k not in present]
                path = scope.get("path", "")
                if b"cache-control" not in present and (path == "/" or path.startswith("/static/")):
                    headers.append((b"cache-control", FONT_CACHE if path.endswith(".woff2") else STATIC_CACHE))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)


class ErrorShield:
    """Last line for unexpected exceptions: a fixed 500 answer, the exception type in the log.

    It sits inside Starlette's ServerErrorMiddleware, so that one never sees the exception
    and never logs its message (which can hold user text) or a traceback."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        started = False

        async def tracking_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, tracking_send)
        except Exception as exc:
            log.error("unhandled %s on %s", type(exc).__name__, safe_path(scope.get("path", "")))
            if not started:
                body = json.dumps({"error": {"code": "llm_error", "message": "Something went wrong on the server."}}).encode()
                await send({"type": "http.response.start", "status": 500,
                            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
                await send({"type": "http.response.body", "body": body})


app = FastAPI(title="EU AI Act Screener", version=get_settings().version, lifespan=lifespan,
              docs_url=None, redoc_url=None, openapi_url=None)
# Added first is innermost: ErrorShield, then gzip, then the security headers on every answer.
app.add_middleware(ErrorShield)
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(SecurityHeaders)
app.mount("/static", StaticFiles(directory=STATIC_DIR, check_dir=False), name="static")


# Errors


def error(code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


class BodyTooLarge(Exception):
    pass


@app.exception_handler(BodyTooLarge)
async def _too_large(_: Request, __: BodyTooLarge):
    return error("invalid_input", "The request is too large.", 413)


@app.exception_handler(RequestValidationError)
async def _validation_error(_: Request, exc: RequestValidationError):
    # Only pydantic's fixed message and the field path are sent back, never the input.
    msg = "Invalid input."
    errors = exc.errors()
    if errors:
        first = errors[0]
        msg = str(first.get("msg") or msg).removeprefix("Value error, ")
        loc = [str(x) for x in first.get("loc", ()) if x not in ("body", "query", "path")]
        if loc and first.get("type") != "value_error":
            msg = f"{'.'.join(loc)[:80]}: {msg}"
    return error("invalid_input", msg[:300], 400)


@app.exception_handler(StarletteHTTPException)
async def _http_error(_: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return error("not_found", "Not found.", 404)
    if exc.status_code == 405:
        return error("invalid_input", "Method not allowed.", 405)
    return error("invalid_input", "Invalid request.", exc.status_code)


# Rate limiting, in memory, per process.


def _utc_day() -> str:
    return datetime.now(timezone.utc).date().isoformat()


@dataclass
class _Entry:
    minute: deque = field(default_factory=deque)
    day: str = ""
    count: int = 0


@dataclass
class Ticket:
    """One counted LLM request; refunded when the stream ends before the model is called."""

    key: str
    day: str
    budget: bool
    at: float = 0.0
    refunded: bool = False


class RateLimiter:
    """Per-key limits per minute and per UTC day, plus one daily budget for the whole app.

    At most `max_keys` keys are kept; the least recently used key is evicted first, so a
    flood of made-up X-Forwarded-For values cannot grow memory. Each key holds at most
    `per_min` time stamps. The budget resets when the UTC day changes."""

    def __init__(self, max_keys: int = RATE_KEYS_MAX, clock=time.monotonic, today=_utc_day) -> None:
        self.lock = threading.Lock()
        self.max_keys = max_keys
        self.clock = clock
        self.today = today
        self.keys: OrderedDict[str, _Entry] = OrderedDict()
        self.budget_day = ""
        self.budget_used = 0

    def hit(self, key: str, per_min: int, per_day: int | None = None, budget: int | None = None) -> tuple[str | None, Ticket | None]:
        """Count one request. Returns (None, ticket) when allowed, else ('rate_limited', 'rate_limited_day'
        or 'quota', None)."""
        now = self.clock()
        today = self.today()
        with self.lock:
            entry = self.keys.get(key)
            if entry is None:
                entry = _Entry(day=today)
                self.keys[key] = entry
                while len(self.keys) > self.max_keys:
                    self.keys.popitem(last=False)
            else:
                self.keys.move_to_end(key)
            while entry.minute and now - entry.minute[0] > 60:
                entry.minute.popleft()
            if entry.day != today:
                entry.day, entry.count = today, 0
            if self.budget_day != today:
                self.budget_day, self.budget_used = today, 0
            if per_min and len(entry.minute) >= per_min:
                return "rate_limited", None
            if per_day and entry.count >= per_day:
                return "rate_limited_day", None
            if budget is not None and self.budget_used >= budget:
                return "quota", None
            entry.minute.append(now)
            entry.count += 1
            if budget is not None:
                self.budget_used += 1
            return None, Ticket(key=key, day=today, budget=budget is not None, at=now)

    def refund(self, ticket: Ticket) -> None:
        with self.lock:
            if ticket.refunded:
                return
            ticket.refunded = True
            entry = self.keys.get(ticket.key)
            if entry is not None and entry.day == ticket.day:
                entry.count = max(0, entry.count - 1)
                try:
                    entry.minute.remove(ticket.at)
                except ValueError:
                    pass
            if ticket.budget and self.budget_day == ticket.day:
                self.budget_used = max(0, self.budget_used - 1)

    def reset(self) -> None:
        with self.lock:
            self.keys.clear()
            self.budget_day, self.budget_used = "", 0


class Slots:
    """How many screenings and questions run at once."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.active = 0

    def acquire(self, limit: int) -> bool:
        with self.lock:
            if self.active >= limit:
                return False
            self.active += 1
            return True

    def release(self) -> None:
        with self.lock:
            self.active = max(0, self.active - 1)


limiter = RateLimiter()
global_limiter = RateLimiter()
search_limiter = RateLimiter()
report_limiter = RateLimiter()
slots = Slots()
GLOBAL_KEY = "all"
# Searches run in worker threads; at most this many embed and rank at once.
_search_sem = threading.BoundedSemaphore(SEARCH_THREADS)


def normalize_ip(value: str | None) -> str | None:
    """A rate-limit key for an address: IPv4 as is, IPv4-mapped IPv6 unwrapped, IPv6 by its /64."""
    if not value:
        return None
    try:
        ip = ipaddress.ip_address(value.strip())
    except ValueError:
        return None
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            return str(ip.ipv4_mapped)
        return str(ipaddress.IPv6Network((int(ip) >> 64 << 64, 64)))
    return str(ip)


def client_ip(request: Request, settings: Settings | None = None) -> str:
    """The client address, counted from the right of X-Forwarded-For.

    TRUSTED_PROXY_HOPS proxies in front of the app each append the address they saw, so
    with N hops the client is the N-th address from the right; anything to its left was
    written by the client. With 0 hops, or a header that is too short or unparseable,
    the socket address is used."""
    settings = settings or get_settings()
    peer = request.client.host if request.client else None
    fallback = normalize_ip(peer) or (peer or "unknown")[:64]
    hops = settings.trusted_proxy_hops
    if hops <= 0:
        return fallback
    entries = [e.strip() for e in ",".join(request.headers.getlist("x-forwarded-for")).split(",") if e.strip()]
    if len(entries) < hops:
        return fallback
    return normalize_ip(entries[-hops]) or fallback


@dataclass
class Gate:
    """The counted tickets of one LLM request; refunded when the model was never called."""

    tickets: list[tuple[RateLimiter, Ticket]]
    llm_started: bool = False

    def refund(self) -> None:
        for lim, ticket in self.tickets:
            lim.refund(ticket)


def seconds_to_utc_midnight() -> int:
    now = datetime.now(timezone.utc)
    return max(1, 86400 - (now.hour * 3600 + now.minute * 60 + now.second))


def rate_limited(message: str, retry_after: int = 60) -> JSONResponse:
    """429 rate_limited with Retry-After in seconds."""
    r = error("rate_limited", message, 429)
    r.headers["Retry-After"] = str(retry_after)
    return r


def _llm_gate(request: Request, accepted: bool) -> JSONResponse | Gate:
    """Checks before an LLM stream. On success a concurrency slot is held and tickets counted."""
    settings = get_settings()
    if not accepted:
        return error("terms_required", "Please accept the terms before you use this tool.", 403)
    if screener.corpus_or_none() is None:
        return error("not_configured", "The Act text is not loaded on this server yet.", 503)
    if not settings.llm_ready:
        return error("not_configured", "This server has no Gemini API key, so screening and questions are off. The reader and search still work.", 503)
    if not slots.acquire(settings.max_concurrent):
        return error("busy", "The server is busy with other screenings. Try again in a moment.", 429)
    verdict, ticket = limiter.hit(client_ip(request, settings), settings.rate_limit_per_min, settings.rate_limit_per_day, settings.daily_budget)
    if ticket is None:
        slots.release()
        if verdict == "quota":
            r = error("quota", "The daily limit of this demo is reached. Please come back tomorrow.", 503)
            r.headers["Retry-After"] = str(seconds_to_utc_midnight())
            return r
        if verdict == "rate_limited_day":
            return rate_limited("You reached the daily limit of this demo for your connection. Please come back tomorrow.",
                                seconds_to_utc_midnight())
        return rate_limited("Too many requests. Please wait a minute and try again.")
    _, all_ticket = global_limiter.hit(GLOBAL_KEY, settings.global_rate_per_min)
    if all_ticket is None:
        limiter.refund(ticket)
        slots.release()
        return rate_limited("Too many requests on this server right now. Please wait a minute and try again.")
    return Gate([(limiter, ticket), (global_limiter, all_ticket)])


async def _read_body(request: Request) -> bytes:
    """The body, read in chunks and stopped at MAX_BODY_BYTES, whatever Content-Length says."""
    declared = request.headers.get("content-length")
    if declared is not None:
        if not declared.isdigit():
            raise BodyTooLarge()
        if int(declared) > MAX_BODY_BYTES:
            raise BodyTooLarge()
    buf = bytearray()
    async for chunk in request.stream():
        buf += chunk
        if len(buf) > MAX_BODY_BYTES:
            raise BodyTooLarge()
    return bytes(buf)


def _parse(raw: bytes, model):
    try:
        return model.model_validate_json(raw)
    except Exception as exc:
        errors = getattr(exc, "errors", None)
        raise RequestValidationError(errors() if callable(errors) else [{"msg": "Invalid JSON.", "loc": ("body",), "type": "value_error"}])


async def _body(request: Request, model):
    return _parse(await _read_body(request), model)


def sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, separators=(',', ':'))}\n\n"


SSE_HEADERS = {"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"}
# The event after which the model is being called: the request is spent from then on.
LLM_START = {("stage", "reasoning"), ("sources", None)}


# Signed results: /api/report renders only results this process produced.

_RANDOM_SECRET = os.urandom(32)


def _secret() -> bytes:
    configured = get_settings().report_secret
    return configured.encode("utf-8") if configured else _RANDOM_SECRET


def canonical_result(result: dict) -> bytes:
    body = {k: v for k, v in result.items() if k != "signature"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8", "surrogatepass")


def sign_result(result: dict, description: str) -> str:
    """HMAC-SHA256 (hex) of the result without `signature`, a newline and the SHA-256 of the description."""
    digest = hashlib.sha256(description.encode("utf-8", "surrogatepass")).hexdigest().encode("ascii")
    return hmac.new(_secret(), canonical_result(result) + b"\n" + digest, hashlib.sha256).hexdigest()


def signature_ok(result: dict, description: str, signature: object) -> bool:
    if not isinstance(signature, str) or not signature:
        return False
    return hmac.compare_digest(sign_result(result, description).encode("ascii"), signature.encode("utf-8", "replace"))


DEADLINE_MESSAGE = "This took too long and was stopped. Please try again."


async def _stream(events: AsyncIterator[tuple[str, dict]], gate: Gate, description: str | None = None) -> AsyncIterator[str]:
    """SSE lines of a pipeline, under one deadline for the whole run. With `description`, the
    result event is signed."""
    loop = asyncio.get_running_loop()
    end = loop.time() + get_settings().screen_deadline
    try:
        while True:
            remaining = end - loop.time()
            if remaining <= 0:
                raise TimeoutError
            try:
                name, data = await asyncio.wait_for(anext(events), remaining)
            except StopAsyncIteration:
                break
            if (name, data.get("stage") if name == "stage" else None) in LLM_START:
                gate.llm_started = True
            if name == "result" and description is not None:
                data = dict(data)
                data["signature"] = sign_result(data, description)
            yield sse(name, data)
    except TimeoutError:
        log.warning("stream stopped at the deadline")
        yield sse("error", {"code": "llm_error", "message": DEADLINE_MESSAGE})
    except LLMError as exc:
        yield sse("error", {"code": exc.code, "message": exc.message})
    except Exception as exc:
        log.error("stream failed: %s", type(exc).__name__)
        yield sse("error", {"code": "llm_error", "message": "Something went wrong while answering. Please try again."})
    finally:
        await events.aclose()


class LLMStreamResponse(StreamingResponse):
    """An SSE answer that holds a concurrency slot and the rate-limit tickets of its Gate.

    It watches for the client to leave while it streams: then the stream task is cancelled,
    which cancels the model call it is awaiting. The slot is always released, and the
    tickets are refunded when the model was never called."""

    def __init__(self, content: AsyncIterator[str], gate: Gate):
        super().__init__(content, media_type="text/event-stream", headers=SSE_HEADERS)
        self.gate = gate

    async def __call__(self, scope, receive, send) -> None:
        async def watch() -> None:
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return

        stream = asyncio.create_task(self.stream_response(send))
        watcher = asyncio.create_task(watch())
        try:
            done, _ = await asyncio.wait({stream, watcher}, return_when=asyncio.FIRST_COMPLETED)
            if stream not in done:
                stream.cancel()
            watcher.cancel()
            await asyncio.gather(stream, watcher, return_exceptions=True)
        finally:
            for task in (stream, watcher):
                if not task.done():
                    task.cancel()
            aclose = getattr(self.body_iterator, "aclose", None)
            if aclose is not None:
                try:
                    await aclose()
                except Exception:
                    pass
            slots.release()
            if not self.gate.llm_started:
                self.gate.refund()


# Routes


@app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
async def index(request: Request):
    visits.count(request.method, request.headers)
    page = STATIC_DIR / "index.html"
    if page.is_file():
        return FileResponse(page, media_type="text/html")
    return HTMLResponse("<!doctype html><title>EU AI Act Screener</title><p>The page is not built yet.</p>")


def retrieval_mode() -> str:
    """hybrid: BM25 and dense vectors; keyword: BM25 only (no usable chroma_db); none: no search."""
    r = screener.retriever_any()
    if r is None:
        return "none"
    try:
        return "hybrid" if r.ready() else "keyword"
    except Exception:
        return "none"


@app.api_route("/api/health", methods=["GET", "HEAD"])
async def health():
    settings = get_settings()
    corpus = screener.corpus_or_none()
    retrieval = await asyncio.to_thread(retrieval_mode) if corpus is not None else "none"
    return {
        "status": "ok",
        "version": settings.version,
        "llm_ready": settings.llm_ready,
        "fake_llm": settings.fake_llm,
        "model": "fake" if settings.fake_llm else settings.gemini_model,
        "units": len(corpus.units) if corpus is not None else 0,
        "corpus": corpus is not None,
        "text_version": screener.text_version(corpus) if corpus is not None else None,
        "retrieval": retrieval,
        "timeline": screener.load_timeline() is not None,
        "obligations": bool(screener.load_obligations()),
    }


def _read_disclaimer() -> str | None:
    try:
        return (ROOT / "DISCLAIMER.md").read_text(encoding="utf-8")
    except OSError:
        return None


# Read once at start; the file is part of the image.
DISCLAIMER_TEXT = _read_disclaimer()


@app.api_route("/disclaimer", methods=["GET", "HEAD"])
async def disclaimer():
    if DISCLAIMER_TEXT is None:
        return error("not_found", "Not found.", 404)
    return Response(content=DISCLAIMER_TEXT, media_type="text/plain; charset=utf-8")


@app.get("/api/examples")
async def examples():
    return list_examples()


@app.get("/api/timeline")
async def timeline():
    data = screener.load_timeline()
    if data is None:
        return error("not_configured", "The timeline data is not available.", 503)
    return data


def _corpus_or_error():
    corpus = screener.corpus_or_none()
    if corpus is None:
        return None, error("not_configured", "The Act text is not loaded on this server yet.", 503)
    return corpus, None


@app.get("/api/source")
async def source():
    corpus, err = _corpus_or_error()
    if err:
        return err
    return corpus.source


@app.get("/api/toc")
async def toc():
    corpus, err = _corpus_or_error()
    if err:
        return err
    return corpus.toc()


@app.get("/api/unit/{ref}")
async def unit(ref: str):
    corpus, err = _corpus_or_error()
    if err:
        return err
    if len(ref) > 64:
        return error("not_found", "No such article, annex or recital.", 404)
    rid = None
    try:
        rid = corpus.normalize_ref(ref)
    except Exception:
        rid = None
    obj = corpus.get(rid or ref)
    # An id that names a part that does not exist ("art-6-99") is not found, not its unit.
    if obj is not None and _ID_FORM.fullmatch(ref.strip()) and obj.id.lower() != ref.strip().lower():
        obj = None
    u = corpus.unit_of(obj.id) if obj is not None else None
    if u is None:
        return error("not_found", "No such article, annex or recital.", 404)
    prev, nxt = corpus.neighbors(u.id)
    return {
        "id": u.id,
        "kind": u.kind,
        "number": u.number,
        "label": corpus.label(u.id),
        "title": u.title,
        "chapter": u.chapter,
        "chapter_title": u.chapter_title,
        "section": u.section,
        "section_title": u.section_title,
        "page_start": u.page_start,
        "page_end": u.page_end,
        "page_url": corpus.page_url(u.id),
        "pdf_url": getattr(u, "pdf_url", None) or corpus.source.get("pdf_url"),
        "amended": bool(getattr(u, "amended", False)),
        "text": u.text,
        "parts": [
            {"id": p.id, "label": p.label, "text": p.text, "page": p.page, "amended": bool(getattr(p, "amended", False))}
            for p in u.parts
        ],
        "prev": prev,
        "next": nxt,
        "focus": obj.id if obj.id != u.id else None,
    }


_ID_FORM = re.compile(r"(?i)(art|annex|rec)-[0-9a-z]+(-[0-9a-z]+)?")


def _search(q: str, k: int, kinds: tuple[str, ...] | None):
    r = screener.retriever_any()
    if r is None:
        return None
    try:
        with _search_sem:
            if r.ready():
                return r.search(q, k=k, kinds=kinds)
            return r.keyword_search(q, k=k, kinds=kinds)
    except Exception as exc:
        log.warning("search failed: %s", type(exc).__name__)
        return None


@app.get("/api/search")
async def search(
    request: Request,
    q: str = Query(min_length=1, max_length=300),
    k: int = Query(default=20, ge=1, le=50),
    kind: str | None = Query(default=None, pattern="^(article|annex|recital)$"),
):
    settings = get_settings()
    verdict, _ = search_limiter.hit(client_ip(request, settings), settings.search_limit_per_min)
    if verdict is not None:
        return rate_limited("Too many searches. Please wait a minute.")
    corpus, err = _corpus_or_error()
    if err:
        return err
    hits = await asyncio.to_thread(_search, q.strip(), k, (kind,) if kind else None)
    if hits is None:
        return error("not_configured", "Search is not available on this server yet.", 503)
    out = []
    for h in hits:
        snippet = " ".join(h.text.split())
        if len(snippet) > 320:
            snippet = snippet[:320].rsplit(" ", 1)[0] + " ..."
        out.append({
            "ref": h.ref, "unit_id": h.unit_id, "kind": h.kind, "label": h.label, "title": h.title,
            "snippet": snippet, "page": h.page, "page_url": corpus.page_url(h.ref), "score": round(float(h.score), 6),
        })
    return {"query": q, "hits": out}


@app.post("/api/screen")
async def screen(request: Request):
    req = await _body(request, ScreenRequest)
    gate = _llm_gate(request, req.accepted_terms)
    if isinstance(gate, JSONResponse):
        return gate
    return LLMStreamResponse(_stream(screener.screen(req), gate, description=req.description), gate)


@app.post("/api/ask")
async def ask(request: Request):
    req = await _body(request, AskRequest)
    gate = _llm_gate(request, req.accepted_terms)
    if isinstance(gate, JSONResponse):
        return gate
    return LLMStreamResponse(_stream(ask_mod.ask(req), gate), gate)


INVALID_SIGNATURE = (
    "This result was not produced by this server, or the server restarted since. "
    "Screen the description again to download a report."
)


@app.post("/api/report")
async def report(request: Request):
    settings = get_settings()
    verdict, _ = report_limiter.hit(client_ip(request, settings), settings.report_limit_per_min)
    if verdict is not None:
        return rate_limited("Too many reports. Please wait a minute.")
    raw = await _read_body(request)
    req = _parse(raw, ReportRequest)
    # The signature is read from the raw body, so it works whether or not the model has the field.
    try:
        signature = json.loads(raw)["result"].get("signature")
    except Exception:
        signature = None
    description = req.description.strip()
    if not signature_ok(req.result.model_dump(), description, signature):
        return error("invalid_signature", INVALID_SIGNATURE, 400)
    corpus, err = _corpus_or_error()
    if err:
        return err
    md = report_mod.render(req.result, description, corpus)
    # The file name is fixed: nothing from the request goes into a header.
    return Response(
        content=md,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="eu-ai-act-screening.md"'},
    )
