// All network access lives here. With ?mock=1 in the URL every call is answered from fixtures,
// when the server has them; mock.js is loaded only then, through a dynamic import.

const WANT_MOCK = new URLSearchParams(location.search).get("mock") === "1";
export let MOCK = WANT_MOCK;

export class ApiError extends Error {
  constructor(code, message, status = 0) {
    super(message || code);
    this.code = code;
    this.status = status;
  }
}

let mockMod = null;
// Resolves true when the mock is in use, false otherwise (not asked for, or no fixtures on this server).
export const mockReady = WANT_MOCK
  ? import("./mock.js").then(async (m) => { await m.available(); mockMod = m; return true; })
    .catch(() => { MOCK = false; return false; })
  : Promise.resolve(false);
async function mock() {
  return (await mockReady) ? mockMod : null;
}

async function errorFrom(res) {
  let code = "llm_error";
  let message = `Request failed (${res.status}).`;
  try {
    const body = await res.json();
    if (body && body.error) {
      code = body.error.code || code;
      message = body.error.message || message;
    }
  } catch { /* not JSON */ }
  if (res.status === 404 && code === "llm_error") code = "not_found";
  if (res.status === 429 && code === "llm_error") code = "rate_limited";
  const err = new ApiError(code, message, res.status);
  const ra = Number(res.headers.get("Retry-After"));
  if (Number.isFinite(ra) && ra > 0) err.retryAfter = ra;
  return err;
}

async function getJSON(path) {
  let res;
  try {
    res = await fetch(path, { headers: { Accept: "application/json" } });
  } catch {
    throw new ApiError("network", "The server could not be reached.");
  }
  if (!res.ok) throw await errorFrom(res);
  return res.json();
}

// Reads a text/event-stream response and calls onEvent(name, data) per event.
async function readStream(res, onEvent, signal) {
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    if (signal && signal.aborted) { reader.cancel(); return; }
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    buf = buf.replace(/\r\n/g, "\n");
    let idx;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      let event = "message";
      const data = [];
      for (const line of chunk.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data.push(line.slice(5).replace(/^ /, ""));
      }
      if (!data.length) continue;
      let parsed;
      try { parsed = JSON.parse(data.join("\n")); } catch { parsed = data.join("\n"); }
      onEvent(event, parsed);
    }
  }
}

async function postStream(path, body, onEvent, signal) {
  let res;
  try {
    res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(body),
      signal,
    });
  } catch (e) {
    if (e.name === "AbortError") throw e;
    throw new ApiError("network", "The server could not be reached.");
  }
  if (!res.ok) throw await errorFrom(res);
  let streamError = null;
  try {
    await readStream(res, (ev, data) => {
      if (ev === "error") streamError = new ApiError(data.code || "llm_error", data.message || "");
      else onEvent(ev, data);
    }, signal);
  } catch (e) {
    if (e.name === "AbortError") throw e;
    throw new ApiError("network", "The connection broke before the answer was complete.");
  }
  if (streamError) throw streamError;
}

export async function health() {
  const m = await mock();
  return m ? m.health() : getJSON("/api/health");
}
export async function source() {
  const m = await mock();
  return m ? m.source() : getJSON("/api/source");
}
export async function examples() {
  const m = await mock();
  return m ? m.examples() : getJSON("/api/examples");
}
export async function timeline() {
  const m = await mock();
  return m ? m.timeline() : getJSON("/api/timeline");
}
export async function toc() {
  const m = await mock();
  return m ? m.toc() : getJSON("/api/toc");
}
export async function unit(ref) {
  const m = await mock();
  return m ? m.unit(ref) : getJSON(`/api/unit/${encodeURIComponent(ref)}`);
}
export async function search(q, k = 20, kind = "") {
  const m = await mock();
  if (m) return m.search(q, k, kind);
  const p = new URLSearchParams({ q, k: String(k) });
  if (kind) p.set("kind", kind);
  return getJSON(`/api/search?${p}`);
}

// onStage(stage) per stage; resolves with the ScreenResult.
export async function screen(body, onStage, signal) {
  const m = await mock();
  if (m) return m.screen(body, onStage, signal);
  let result = null;
  await postStream("/api/screen", body, (ev, data) => {
    if (ev === "stage") onStage(data.stage);
    else if (ev === "result") result = data;
  }, signal);
  if (!result) throw new ApiError("llm_error", "The stream ended without a result.");
  return result;
}

// handlers: { onSources(citations), onToken(text) }
export async function ask(body, handlers, signal) {
  const m = await mock();
  if (m) return m.ask(body, handlers, signal);
  await postStream("/api/ask", body, (ev, data) => {
    if (ev === "sources") handlers.onSources(data.citations || []);
    else if (ev === "token") handlers.onToken(data.text || "");
  }, signal);
}

// Resolves with { blob, filename }.
export async function report(body) {
  const m = await mock();
  if (m) return m.report(body);
  let res;
  try {
    res = await fetch("/api/report", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError("network", "The server could not be reached.");
  }
  if (!res.ok) throw await errorFrom(res);
  const cd = res.headers.get("Content-Disposition") || "";
  const fn = cd.match(/filename="?([^";]+)"?/);
  return { blob: await res.blob(), filename: fn ? fn[1] : "eu-ai-act-screening.md" };
}
