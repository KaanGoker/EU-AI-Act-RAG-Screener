// Fixture answers for ?mock=1. Loaded only by api.js.
import { ApiError } from "./api.js";

const cache = new Map();
function fixture(name) {
  if (!cache.has(name)) {
    cache.set(name, fetch(new URL(`../fixtures/${name}`, import.meta.url)).then((r) => {
      if (!r.ok) throw new ApiError("not_found", `Missing fixture ${name}`, 404);
      return r.json();
    }));
  }
  return cache.get(name).then((x) => structuredClone(x));
}

function wait(ms, signal) {
  return new Promise((resolve, reject) => {
    const t = setTimeout(resolve, ms);
    if (signal) signal.addEventListener("abort", () => { clearTimeout(t); reject(new DOMException("Aborted", "AbortError")); }, { once: true });
  });
}

// Rejects when this server has no fixtures (they are not shipped in the Docker image).
export const available = () => fixture("health.json");
export const health = () => wait(80).then(() => fixture("health.json"));
export const source = () => fixture("source.json");
export const examples = () => wait(120).then(() => fixture("examples.json"));
export const timeline = () => fixture("timeline.json");
export const toc = () => wait(60).then(() => fixture("toc.json"));

export async function unit(ref) {
  const units = await fixture("units.json");
  const id = String(ref).replace(/^annex-([ivx]+)/i, (_, r) => `annex-${r.toUpperCase()}`);
  const m = id.match(/^(art-\d+[a-z]*|annex-[IVX]+|rec-\d+)(?:-(\d+[a-z]*))?$/);
  // The mock holds a sample of units only.
  if (!m || !units[m[1]]) throw new ApiError("not_found", `No unit ${ref} in the mock sample`, 404);
  const u = units[m[1]];
  u.focus = m[2] ? id : null;
  await wait(90);
  return u;
}

export async function search(q, k = 20, kind = "") {
  const units = await fixture("units.json");
  const terms = q.toLowerCase().split(/\W+/).filter((t) => t.length > 2);
  const hits = [];
  for (const u of Object.values(units)) {
    if (kind && u.kind !== kind) continue;
    const chunks = u.parts.length ? u.parts.map((p) => ({ ref: p.id, label: p.label, text: p.text, page: p.page })) : [{ ref: u.id, text: u.text, page: u.page_start }];
    for (const c of chunks) {
      const low = c.text.toLowerCase();
      let score = 0;
      for (const t of terms) { let i = -1; while ((i = low.indexOf(t, i + 1)) >= 0) score++; }
      if (u.title && terms.some((t) => u.title.toLowerCase().includes(t))) score += 3;
      if (!score) continue;
      const first = Math.max(0, Math.min(...terms.map((t) => { const i = low.indexOf(t); return i < 0 ? 1e9 : i; })) - 60);
      const label = c.ref === u.id ? u.label : (u.kind === "annex" ? `${u.label}, point ${c.label}` : `${u.label}(${c.label})`);
      hits.push({ ref: c.ref, unit_id: u.id, kind: u.kind, label, title: u.title,
        snippet: (first > 0 ? "..." : "") + c.text.slice(first, first + 240).replace(/\s+/g, " ") + "...",
        page: c.page, page_url: `${u.page_url.split("#")[0]}#page=${c.page}`, score });
    }
  }
  hits.sort((a, b) => b.score - a.score);
  await wait(150);
  return { query: q, hits: hits.slice(0, k) };
}

// Pick a fixture from words in the description. "[error:code]" in the text forces that error.
function pick(desc) {
  const d = desc.toLowerCase();
  const forced = d.match(/\[error:(\w+)\]/);
  if (forced) return { error: forced[1] };
  if (/recipe|lasagne|poem|ignore (all|previous)/.test(d)) return { name: "screen-out-of-scope.json" };
  if (/military|defen[cs]e|targeting|national security/.test(d)) return { name: "screen-not-covered.json" };
  if (/vehicle|braking|aircraft|aviation|marine|machinery/.test(d)) return { name: "screen-section-b.json" };
  if (/emotion|facial expression|frustrat/.test(d)) return { name: "screen-prohibited.json" };
  if (/intimate|nude|nudify|undress|explicit/.test(d)) return { name: "screen-intimate.json" };
  if (/chatbot|customer service/.test(d)) return { name: "screen-limited.json" };
  if (/stock|inventory|forecast|warehouse/.test(d)) return { name: "screen-minimal.json" };
  return { name: "screen-high.json" };
}

const MESSAGES = {
  busy: "The server is busy with other requests. Please try again in a moment.",
  too_large: "The request is too large.",
  rate_limited: "Too many requests from this address.",
  quota: "The daily budget is used up.",
  not_configured: "GOOGLE_API_KEY is not set.",
  llm_error: "The model returned an invalid response.",
  network: "The server could not be reached.",
};

export async function screen(body, onStage, signal) {
  if (!body.accepted_terms) throw new ApiError("terms_required", "Accept the terms first.", 403);
  const p = pick(body.description);
  if (p.error === "busy") throw new ApiError("busy", MESSAGES.busy, 429);
  if (p.error === "too_large") throw new ApiError("invalid_input", MESSAGES.too_large, 413);
  onStage("retrieving");
  await wait(900, signal);
  if (p.error === "network") throw new ApiError("network", MESSAGES.network);
  if (p.error === "rate_limited" || p.error === "quota") throw new ApiError(p.error, MESSAGES[p.error], 429);
  if (p.error === "not_configured") throw new ApiError(p.error, MESSAGES[p.error], 503);
  onStage("reasoning");
  await wait(1600, signal);
  if (p.error) throw new ApiError(p.error, MESSAGES[p.error] || "Error");
  onStage("verifying");
  await wait(700, signal);
  const r = await fixture(p.name);
  r.role = body.role;
  r.created = new Date().toISOString().replace(/\.\d+Z$/, "Z");
  r.answers = r.in_scope && Array.isArray(body.answers) ? body.answers : [];
  if (r.answers.length) r.confidence = "high";
  return r;
}

export async function ask(body, handlers, signal) {
  const a = await fixture("ask.json");
  await wait(500, signal);
  if (/\[error:(\w+)\]/.test(body.question)) {
    const code = body.question.match(/\[error:(\w+)\]/)[1];
    throw new ApiError(code, MESSAGES[code] || "Error");
  }
  handlers.onSources(a.citations);
  const words = a.answer.split(/(\s+)/);
  for (let i = 0; i < words.length; i += 4) {
    await wait(35, signal);
    handlers.onToken(words.slice(i, i + 4).join(""));
  }
}

export async function report(body) {
  const { reportMarkdown } = await import("./summary.js");
  await wait(200);
  const md = reportMarkdown(body.description, body.result);
  return { blob: new Blob([md], { type: "text/markdown" }), filename: "eu-ai-act-screening.md" };
}
