// The reader: one article or annex at a time, search over the Act, table of contents.
import * as api from "./api.js";
import { h, icon, clear } from "./dom.js";
import { renderWithMark } from "./highlight.js";
import { textName, AMENDED_TITLE, NOTICE_SHORT } from "./textinfo.js";

const body = () => document.getElementById("reader-body");
let tocData = null;
let titles = new Map();
let amendedIds = new Set();
let current = null;
let lastQuery = "";
let ensureOpen = () => {};
let getReturn = () => null;

export function labelOf(id) {
  if (!id) return "";
  let m = id.match(/^art-(\d+[a-z]*)(?:-(\d+[a-z]*))?$/);
  if (m) return `Article ${m[1]}` + (m[2] ? `(${m[2]})` : "");
  m = id.match(/^annex-([ivx]+)(?:-(\d+[a-z]*))?$/i);
  if (m) return `Annex ${m[1].toUpperCase()}` + (m[2] ? `, point ${m[2]}` : "");
  m = id.match(/^rec-(\d+)$/);
  if (m) return `Recital ${m[1]}`;
  return id;
}

async function loadToc() {
  if (tocData) return tocData;
  tocData = await api.toc();
  titles = new Map();
  amendedIds = new Set();
  for (const c of tocData.chapters || []) for (const a of c.articles) { titles.set(a.id, a.title); if (a.amended) amendedIds.add(a.id); }
  for (const a of tocData.annexes || []) { titles.set(a.id, a.title); if (a.amended) amendedIds.add(a.id); }
  return tocData;
}

// Quiet mark for text changed or added by the 2026 amending regulation.
export function amendedMark(small = false) {
  return h("span", { class: `amended${small ? " amended--small" : ""}`, title: AMENDED_TITLE }, small ? "2026" : "Amended 2026");
}

function tocShown(on) {
  const b = document.getElementById("toc-btn");
  if (b) b.setAttribute("aria-expanded", String(on));
}

function status(msg, kind = "") {
  clear(body()).append(h("div", { class: `reader__status ${kind}` }, kind === "is-error" ? icon("alert") : null, h("p", { text: msg })));
}

function crumb(u) {
  if (u.kind === "article" && u.chapter) {
    return [`Chapter ${u.chapter}`, u.chapter_title, u.section ? `Section ${u.section}` : null].filter(Boolean).join("  /  ");
  }
  if (u.kind === "annex") return "Annexes";
  if (u.kind === "recital") return "Recitals";
  return "";
}

// Opens a unit or part id. quote, when given, is highlighted inside the focused paragraph.
export async function openRef(ref, quote = "", opts = {}) {
  ensureOpen();
  tocShown(false);
  status("Opening the text...");
  let u;
  try {
    u = await api.unit(ref);
  } catch (e) {
    status(e.code === "not_found" ? `${labelOf(ref)} could not be found in the text of the Act.` : "The text could not be loaded. Try again.", "is-error");
    return;
  }
  current = { ref, quote };
  try { await loadToc(); } catch { /* marks from the unit itself only */ }
  const unitAmended = u.amended === true || (u.amended === undefined && amendedIds.has(u.id));
  const focusId = u.focus || (opts.focus ?? null);
  const focusPart = u.parts.find((p) => p.id === focusId);
  const page = focusPart ? focusPart.page : u.page_start;
  const pdfBase = (u.pdf_url || u.page_url || "").split("#")[0];
  const pdfUrl = `${pdfBase}#page=${page}`;
  const consolidated = /CELEX:0/i.test(pdfBase);
  const pdfText = consolidated ? `Open page ${page} of the consolidated PDF` : `Open page ${page} of the Official Journal PDF`;

  const head = h("header", { class: "unit__head" },
    h("p", { class: "unit__crumb", text: crumb(u) }),
    h("p", { class: "unit__label" }, h("span", { class: "mono", text: u.label || labelOf(u.id) }), unitAmended ? amendedMark() : null),
    h("h3", { class: "unit__title", id: "unit-title", text: u.title || "" }),
    h("p", { class: "unit__meta" },
      h("span", { text: u.page_start === u.page_end ? `Page ${u.page_start}` : `Pages ${u.page_start} to ${u.page_end}` }),
      h("a", { href: pdfUrl, target: "_blank", rel: "noopener", class: "unit__pdf" }, pdfText, icon("external"))),
  );

  const text = h("div", { class: "unit__text" });
  let mark = null;
  let focusEl = null;
  if (u.parts.length) {
    // Intro text before paragraph 1, if any.
    const firstLabel = `${u.parts[0].label}. `;
    const introEnd = u.text.indexOf(`\n${firstLabel}`);
    if (introEnd > 0) text.append(h("p", { class: "para para--intro", text: u.text.slice(0, introEnd) }));
    for (const p of u.parts) {
      const isFocus = p.id === focusId;
      const t = h("p", { class: "para__text" });
      const m = renderWithMark(t, p.text, isFocus || (!focusId && quote) ? quote : "");
      if (m && !mark) mark = m;
      const el = h("div", { class: `para${isFocus ? " is-focus" : ""}`, id: `para-${p.id}` },
        h("span", { class: "para__num mono", text: `${p.label}.` }), h("div", { class: "para__body" }, p.amended ? amendedMark() : null, t));
      if (isFocus) focusEl = el;
      text.append(el);
    }
    // Quote not found in the focused paragraph: try the whole unit.
    if (quote && !mark) {
      for (const p of u.parts) {
        const t = text.querySelector(`#para-${CSS.escape(p.id)} .para__text`);
        const m = renderWithMark(t, p.text, quote);
        if (m) { mark = m; break; }
      }
    }
  } else {
    for (const chunk of u.text.split(/\n+/)) {
      const t = h("p", { class: "para para--plain" });
      const m = renderWithMark(t, chunk, mark ? "" : quote);
      if (m) mark = m;
      text.append(t);
    }
  }

  const notice = quote && !mark
    ? h("p", { class: "unit__notice" }, icon("flag"), "The quoted words were not found in this text. The citation may point to the wrong paragraph.")
    : null;

  // Articles, annexes and recitals are separate chains in the data. At the end of one, the step
  // continues in the order of the Official Journal: recitals, articles, annexes.
  const ends = chainEnds();
  let prev = u.prev ? { ref: u.prev, small: "Previous" } : null;
  let next = u.next ? { ref: u.next, small: "Next" } : null;
  if (!prev && u.id === ends.firstArticle && ends.lastRecital) prev = { ref: ends.lastRecital, small: "Previous: recitals" };
  if (!prev && u.id === ends.firstAnnex && ends.lastArticle) prev = { ref: ends.lastArticle, small: "Previous: articles" };
  if (!next && u.id === ends.lastRecital && ends.firstArticle) next = { ref: ends.firstArticle, small: "Next: articles" };
  if (!next && u.id === ends.lastArticle && ends.firstAnnex) next = { ref: ends.firstAnnex, small: "Next: annexes" };
  const step = (s, isNext) => h("button", { type: "button", class: `unit__step${isNext ? " unit__step--next" : ""}`, onclick: () => openRef(s.ref) },
    isNext ? null : icon("arrowLeft"), h("span", {}, h("small", { text: s.small }), h("span", { text: labelOf(s.ref) })), isNext ? icon("arrowRight") : null);
  const nav = h("nav", { class: "unit__nav", "aria-label": "Previous and next" },
    prev ? step(prev, false) : h("span"),
    next ? step(next, true)
      : h("button", { type: "button", class: "unit__step unit__step--next unit__step--end", onclick: showToc },
        h("span", {}, h("small", { text: u.kind === "annex" ? "Last annex" : u.kind === "recital" ? "Last recital" : "End" }), h("span", { text: "Contents" })), icon("book")));
  const ret = getReturn();
  const back2 = ret ? h("button", { type: "button", class: "linkbtn reader__return", onclick: ret }, icon("arrowLeft"), "Back to your result") : null;

  const back = lastQuery && opts.fromSearch
    ? h("button", { type: "button", class: "linkbtn reader__back", onclick: () => runSearch(lastQuery) }, icon("arrowLeft"), `Back to results for "${lastQuery}"`)
    : null;

  // Running head, like a printed book: stays at the top while the text scrolls.
  const run = h("div", { class: "unit__run", "aria-hidden": "true" },
    h("span", { class: "mono", text: u.label || labelOf(u.id) }), h("span", { class: "unit__run-title", text: u.title || "" }));
  clear(body()).append(run, h("article", { class: "unit", "aria-labelledby": "unit-title" }, back, head, notice, text, nav, back2));
  const b = body();
  requestAnimationFrame(() => {
    const rel = (el) => el.getBoundingClientRect().top - b.getBoundingClientRect().top + b.scrollTop;
    const shown = b.querySelector(".unit__notice");
    const anchor = shown ? null : focusEl || (mark && mark.closest(".para, p"));
    if (anchor) {
      let top = rel(anchor) - 52;
      // A long paragraph: make sure the marked words are in view.
      if (mark && rel(mark) - top > b.clientHeight - 80) top = rel(mark) - 140;
      b.scrollTo({ top: Math.max(0, top), behavior: "auto" });
    } else b.scrollTop = 0;
    if (opts.focusPanel !== false) b.focus({ preventScroll: true });
  });
}

// First and last ids of each chain, from the table of contents (fallbacks match the corpus).
function chainEnds() {
  const ch = (tocData && tocData.chapters) || [];
  const arts = ch.flatMap((c) => c.articles || []);
  const ax = (tocData && tocData.annexes) || [];
  const recN = tocData && tocData.recitals && tocData.recitals.count;
  return {
    firstArticle: arts.length ? arts[0].id : "art-1",
    lastArticle: arts.length ? arts[arts.length - 1].id : "art-113",
    firstAnnex: ax.length ? ax[0].id : "annex-I",
    lastRecital: recN ? `rec-${recN}` : null,
  };
}

const SEARCH_EXAMPLES = ["emotion recognition", "biometric identification", "transparency obligations"];

export async function runSearch(q) {
  q = q.trim();
  if (q.length < 2) {
    ensureOpen();
    tocShown(false);
    status(q.length ? "Type at least two characters to search." : "Type a word or a phrase to search the Act.");
    document.getElementById("search-q").focus();
    return;
  }
  ensureOpen();
  lastQuery = q;
  tocShown(false);
  document.getElementById("search-q").value = q;
  status("Searching the Act...");
  let res;
  try {
    res = await api.search(q, 20);
  } catch (e) {
    status(e.code === "rate_limited" ? "Too many searches at once. Wait a few seconds." : "Search failed. Try again.", "is-error");
    return;
  }
  const list = h("ol", { class: "hits" });
  for (const hit of (res && res.hits) || []) {
    list.append(h("li", {},
      h("button", { type: "button", class: "hit", onclick: () => openRef(hit.ref, "", { fromSearch: true }) },
        h("span", { class: "hit__label mono", text: hit.label }),
        h("span", { class: "hit__title", text: hit.title || "" }),
        h("span", { class: "hit__snippet", text: hit.snippet }),
        h("span", { class: "hit__page", text: `Page ${hit.page}` }))));
  }
  const hits = Array.isArray(res && res.hits) ? res.hits : [];
  const empty = hits.length ? null : h("div", { class: "search-empty" },
    h("p", { class: "search-empty__title", text: "Nothing in the Act matches that." }),
    h("p", { class: "search-empty__text" }, "Try the words the Act uses, for example ",
      SEARCH_EXAMPLES.map((x, i) => [i ? (i === SEARCH_EXAMPLES.length - 1 ? " or " : ", ") : "",
        h("button", { type: "button", class: "linkbtn", onclick: () => runSearch(x) }, x)]),
      ". The text is in English."),
    h("button", { type: "button", class: "btn btn--ghost", onclick: showToc }, icon("book"), "Browse the contents"));
  clear(body()).append(h("section", { class: "search-results", "aria-label": `Results for ${q}` },
    h("p", { class: "search-results__count", role: "status", text: hits.length ? `${hits.length} passage${hits.length === 1 ? "" : "s"} for "${q}"` : `No passages for "${q}"` }),
    hits.length ? list : empty));
  body().scrollTop = 0;
}

export async function showToc() {
  ensureOpen();
  tocShown(true);
  status("Loading the contents...");
  let t;
  try { t = await loadToc(); } catch { status("The contents could not be loaded.", "is-error"); return; }
  const wrap = h("nav", { class: "toc", id: "reader-toc", "aria-label": "Contents of the Act" });
  wrap.append(h("p", { class: "toc__head", text: "Regulation (EU) 2024/1689" }));
  for (const c of t.chapters) {
    const d = h("details", { class: "toc__chapter" },
      h("summary", {}, h("span", { class: "mono", text: `Chapter ${c.number}` }), h("span", { text: c.title })),
      h("ul", {}, c.articles.map((a) => h("li", {}, h("button", { type: "button", class: "toc__item", onclick: () => openRef(a.id) },
        h("span", { class: "mono", text: a.number }), h("span", {}, a.title, a.amended ? amendedMark(true) : null))))));
    if (current && c.articles.some((a) => current.ref.startsWith(a.id + "-") || current.ref === a.id)) d.open = true;
    wrap.append(d);
  }
  const ax = h("details", { class: "toc__chapter" },
    h("summary", {}, h("span", { class: "mono", text: "Annexes" }), h("span", { text: `${t.annexes.length} annexes` })),
    h("ul", {}, t.annexes.map((a) => h("li", {}, h("button", { type: "button", class: "toc__item", onclick: () => openRef(a.id) },
      h("span", { class: "mono", text: a.number }), h("span", {}, a.title, a.amended ? amendedMark(true) : null))))));
  if (current && /^annex-/.test(current.ref)) ax.open = true;
  wrap.append(ax);
  const recN = t.recitals && t.recitals.count;
  if (recN) {
    const rec = h("details", { class: "toc__chapter toc__chapter--recitals" },
      h("summary", {}, h("span", { class: "mono", text: "Recitals" }), h("span", { text: `${recN} recitals, 2024 Official Journal text` })),
      h("ul", { class: "toc__recitals", "aria-label": "Recitals" }, Array.from({ length: recN }, (_, i) => h("li", {},
        h("button", { type: "button", class: "toc__rec mono", "aria-label": `Recital ${i + 1}`, onclick: () => openRef(`rec-${i + 1}`) }, String(i + 1))))));
    if (current && /^rec-/.test(current.ref)) rec.open = true;
    wrap.append(rec);
  }
  clear(body()).append(wrap);
  body().scrollTop = 0;
}

export function showHome() {
  tocShown(false);
  const quick = [
    ["art-3", "Definitions"], ["art-5", "Prohibited AI practices"], ["art-6", "High-risk classification"],
    ["annex-III", "High-risk areas"], ["art-50", "Transparency duties"], ["art-113", "Dates of application"],
  ];
  clear(body()).append(h("div", { class: "reader-home" },
    h("p", { class: "reader-home__kicker mono", text: "Regulation (EU) 2024/1689" }),
    h("h3", { class: "reader-home__title", text: "The text of the Act, beside your result" }),
    h("p", { class: "reader-home__lede", text: "Every citation in a result opens here with the quoted words marked. You can also search the whole Act or browse it by chapter, no screening needed." }),
    h("p", { class: "reader-home__note" }, `Articles and annexes follow ${textName()}, including Regulation (EU) 2026/1744. Changed parts carry `, amendedMark(), `. Recitals come from the 2024 Official Journal text. ${NOTICE_SHORT}`),
    h("ul", { class: "reader-home__quick" }, quick.map(([id, t]) => h("li", {},
      h("button", { type: "button", class: "quick", onclick: () => openRef(id) }, h("span", { class: "mono", text: labelOf(id) }), h("span", { text: t }))))),
    h("button", { type: "button", class: "btn btn--ghost", onclick: showToc }, icon("book"), "Browse all chapters")));
}

export function initReader(open, returner) {
  ensureOpen = open;
  if (returner) getReturn = returner;
  showHome();
  document.getElementById("search-form").addEventListener("submit", (e) => {
    e.preventDefault();
    runSearch(document.getElementById("search-q").value);
  });
  const tocBtn = document.getElementById("toc-btn");
  tocBtn.addEventListener("click", () => {
    if (tocBtn.getAttribute("aria-expanded") !== "true") { showToc(); return; }
    if (current) openRef(current.ref, current.quote);
    else showHome();
  });
}
