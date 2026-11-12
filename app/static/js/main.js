// Page wiring: theme, terms, panel, form, progress and result.
import * as api from "./api.js";
import { h, icon, clear, toast, storage, RISK } from "./dom.js";
import { initReader, openRef, showHome } from "./reader.js";
import { setTextInfo } from "./textinfo.js";
import { initAsk } from "./ask.js";
import { renderResult, setLawInForce } from "./result.js";
import { summaryText } from "./summary.js";
import { errorText } from "./errors.js";

const $ = (id) => document.getElementById(id);
const TERMS_KEY = "screener-terms-v2";
const WIDE = window.matchMedia("(min-width: 1200px)");

/* Theme */
function currentTheme() {
  const set = document.documentElement.getAttribute("data-theme");
  if (set) return set;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}
function syncThemeButton() {
  const next = currentTheme() === "dark" ? "light" : "dark";
  $("theme-toggle").setAttribute("aria-label", `Switch to ${next} theme`);
  $("theme-toggle").title = `Switch to ${next} theme`;
}
$("theme-toggle").addEventListener("click", () => {
  const next = currentTheme() === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  storage.set("screener-theme", next);
  syncThemeButton();
});
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", syncThemeButton);
syncThemeButton();

/* Terms */
const terms = $("terms");
function termsAccepted() { return storage.get(TERMS_KEY) === "yes" || terms.dataset.accepted === "yes"; }
function showTerms() { if (!terms.open) terms.showModal(); }
terms.addEventListener("cancel", (e) => { if (!termsAccepted()) e.preventDefault(); });
terms.addEventListener("close", () => {
  if (terms.returnValue === "accept") {
    terms.dataset.accepted = "yes";
    storage.set(TERMS_KEY, "yes");
  }
  // On first load nothing had focus before the dialog: start in the description field.
  requestAnimationFrame(() => {
    if (!document.activeElement || document.activeElement === document.body) $("desc").focus();
  });
});
$("terms-reopen").addEventListener("click", showTerms);
function requireTerms() {
  if (termsAccepted()) return true;
  showTerms();
  return false;
}

/* Side panel: reader and ask */
let lastOpener = null;
function setTab(name) {
  const reader = name === "reader";
  $("tab-reader").setAttribute("aria-selected", String(reader));
  $("tab-ask").setAttribute("aria-selected", String(!reader));
  $("tab-reader").tabIndex = reader ? 0 : -1;
  $("tab-ask").tabIndex = reader ? -1 : 0;
  $("pane-reader").hidden = !reader;
  $("pane-ask").hidden = reader;
  $("aside-title").textContent = reader ? "The Act" : "Ask the Act";
  document.querySelectorAll("[data-open]").forEach((b) => b.classList.toggle("is-current", isOpen() && b.dataset.open === name));
}
function isOpen() { return document.documentElement.classList.contains("aside-open"); }

// Below 1200 px the panel is a modal sheet: the rest of the page is inert while it is open.
const OUTSIDE = () => [document.querySelector(".masthead"), $("main"), document.querySelector(".footer")];
function syncModal() {
  const modal = isOpen() && !WIDE.matches;
  const panel = $("aside-panel");
  for (const el of OUTSIDE()) el.inert = modal;
  if (modal) {
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-modal", "true");
    panel.setAttribute("aria-labelledby", "aside-title");
  } else {
    panel.removeAttribute("role");
    panel.removeAttribute("aria-modal");
    panel.removeAttribute("aria-labelledby");
  }
}
// Keeps Tab inside the sheet even where inert is not supported.
$("aside-panel").addEventListener("keydown", (e) => {
  if (e.key !== "Tab" || WIDE.matches || !isOpen()) return;
  const items = [...$("aside-panel").querySelectorAll('button, [href], input, textarea, select, summary, [tabindex]:not([tabindex="-1"])')]
    .filter((el) => !el.disabled && (el.checkVisibility ? el.checkVisibility() : el.offsetParent !== null) && !el.closest("details:not([open]) > :not(summary)"));
  if (!items.length) return;
  const first = items[0], last = items[items.length - 1];
  if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
  else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
});
WIDE.addEventListener("change", syncModal);
function openAside(tab = "reader") {
  if (!isOpen()) lastOpener = document.activeElement;
  document.documentElement.classList.add("aside-open");
  $("aside").setAttribute("aria-hidden", "false");
  setTab(tab);
  syncModal();
  if (!WIDE.matches && !$("aside-panel").contains(document.activeElement)) $("aside-panel").querySelector('[role="tab"][aria-selected="true"]').focus();
}
function closeAside() {
  document.documentElement.classList.remove("aside-open");
  $("aside").setAttribute("aria-hidden", "true");
  document.querySelectorAll("[data-open]").forEach((b) => b.classList.remove("is-current"));
  syncModal();
  if (lastOpener && document.contains(lastOpener)) lastOpener.focus();
}
document.querySelectorAll("[data-open]").forEach((b) => b.addEventListener("click", () => {
  const tab = b.dataset.open;
  const visibleTab = $("pane-reader").hidden ? "ask" : "reader";
  if (isOpen() && visibleTab === tab && !WIDE.matches) { closeAside(); return; }
  lastOpener = b;
  openAside(tab);
  if (tab === "ask") $("ask-q").focus();
  else $("search-q").focus();
}));
document.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", closeAside));
$("tab-reader").addEventListener("click", () => setTab("reader"));
$("tab-ask").addEventListener("click", () => setTab("ask"));
document.querySelector(".tabs").addEventListener("keydown", (e) => {
  if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
    const toAsk = $("tab-reader").getAttribute("aria-selected") === "true";
    setTab(toAsk ? "ask" : "reader");
    $(toAsk ? "tab-ask" : "tab-reader").focus();
  }
});
// Back from the panel to the control that opened it (a quote, a source, a button).
function returnToOpener() {
  if (!WIDE.matches) { closeAside(); return; }
  if (lastOpener && document.contains(lastOpener)) lastOpener.focus();
}
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape" || !isOpen() || terms.open) return;
  // On wide screens the panel is a column beside the result: Escape only takes focus back.
  if (WIDE.matches) {
    if ($("aside-panel").contains(document.activeElement)) { e.preventDefault(); returnToOpener(); }
    return;
  }
  e.preventDefault();
  closeAside();
});
if (WIDE.matches) openAside("reader");
else $("aside").setAttribute("aria-hidden", "true");

initReader(() => {
  const a = document.activeElement;
  if (a && a !== document.body && !$("aside-panel").contains(a)) lastOpener = a;
  if (!isOpen()) openAside("reader"); else setTab("reader");
}, () => (lastOpener && document.contains(lastOpener) && $("result").contains(lastOpener) ? returnToOpener : null));
initAsk(requireTerms);

/* Form */
const desc = $("desc");
const counter = $("desc-counter");
function updateCounter() {
  const n = desc.value.length;
  counter.textContent = `${n} / 4000`;
  counter.classList.toggle("is-short", n > 0 && n < 30);
  counter.classList.toggle("is-near", n > 3600);
  if (n >= 30) hideFieldError();
}
function fieldError(msg) {
  $("desc-error").textContent = msg;
  $("desc-error").hidden = false;
  desc.setAttribute("aria-invalid", "true");
  desc.focus();
}
function hideFieldError() {
  $("desc-error").hidden = true;
  desc.removeAttribute("aria-invalid");
}
desc.addEventListener("input", updateCounter);
desc.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); $("screen-form").requestSubmit(); }
});
const role = () => document.querySelector('input[name="role"]:checked').value;

async function loadExamples() {
  let ex;
  try { ex = await api.examples(); } catch { return; }
  if (!Array.isArray(ex) || !ex.length) return;
  const list = document.querySelector(".examples__list");
  for (const e of ex) {
    list.append(h("button", { type: "button", class: "chip", onclick: () => {
      desc.value = e.description;
      const r = document.querySelector(`input[name="role"][value="${e.role}"]`);
      if (r) r.checked = true;
      updateCounter();
      desc.focus();
    } }, e.title));
  }
  $("examples").hidden = false;
}

/* Progress */
const STAGES = ["retrieving", "reasoning", "verifying"];
const STAGE_TEXT = { retrieving: "Retrieving the relevant text of the Act", reasoning: "Reasoning through the six checks", verifying: "Verifying every quote" };
let timer = 0;
function startProgress() {
  const p = $("progress");
  p.hidden = false;
  p.querySelectorAll("li").forEach((li) => li.classList.remove("is-active", "is-done"));
  const t0 = performance.now();
  clearInterval(timer);
  timer = setInterval(() => { $("progress-time").textContent = `${((performance.now() - t0) / 1000).toFixed(1)} s`; }, 100);
  $("progress-live").textContent = "Starting the screening";
}
function setStage(stage) {
  const k = STAGES.indexOf(stage);
  $("progress").querySelectorAll("li").forEach((li, i) => {
    li.classList.toggle("is-done", i < k);
    li.classList.toggle("is-active", i === k);
  });
  $("progress-live").textContent = STAGE_TEXT[stage] || "";
}
function stopProgress(ok) {
  clearInterval(timer);
  if (ok) $("progress").querySelectorAll("li").forEach((li) => { li.classList.remove("is-active"); li.classList.add("is-done"); });
  $("progress").hidden = true;
}

/* Screening */
let last = null; // { description, role, answers, result } in memory only
let running = null;

function showError(e, retry) {
  const t = errorText(e);
  const el = $("result");
  el.hidden = false;
  el.className = "result result--error";
  clear(el).append(h("div", { class: `errbox errbox--${t.code}`, role: "alert" },
    h("span", { class: "errbox__icon" }, icon(t.icon)),
    h("div", {},
      h("h2", { class: "errbox__title", text: t.title }),
      h("p", { class: "errbox__text", text: t.body }),
      h("div", { class: "errbox__actions" },
        ["rate_limited", "busy", "llm_error", "network"].includes(t.code) ? h("button", { type: "button", class: "btn btn--secondary", onclick: retry }, icon("refresh"), "Try again") : null,
        ["not_configured", "quota"].includes(t.code) ? h("button", { type: "button", class: "btn btn--ghost", onclick: () => { openAside("reader"); $("search-q").focus(); } }, icon("book"), "Browse the Act") : null))));
  $("result-live").textContent = t.title;
}

async function runScreen(description, roleVal, answers = []) {
  if (!requireTerms()) return;
  if (running) running.abort();
  const ctrl = new AbortController();
  running = ctrl;
  const btn = $("screen-btn");
  btn.disabled = true;
  btn.querySelector("span").textContent = "Screening...";
  $("result").hidden = true;
  startProgress();
  $("progress").scrollIntoView({ block: "nearest", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  try {
    const r = await api.screen({ description, role: roleVal, answers, accepted_terms: true }, setStage, ctrl.signal);
    stopProgress(true);
    last = { description, role: roleVal, answers, result: r };
    const el = $("result");
    el.hidden = false;
    renderResult(el, r, description, {
      download: downloadReport,
      copy: copySummary,
      rescreen: (ans) => runScreen(description, roleVal, ans),
      newScreen: () => { desc.focus(); desc.scrollIntoView({ block: "center" }); },
    });
    $("result-live").textContent = r.in_scope
      ? `Result: ${RISK[r.risk_class].long}. ${r.headline} ${r.verification.verified} of ${r.verification.total} quotes verified.`
      : `Nothing to screen. ${r.refusal || ""}`;
    el.focus({ preventScroll: true });
    el.scrollIntoView({ block: "start", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  } catch (e) {
    if (e.name === "AbortError") return;
    stopProgress(false);
    if (e.code === "terms_required") { storage.set(TERMS_KEY, ""); delete terms.dataset.accepted; showTerms(); }
    showError(e, () => runScreen(description, roleVal, answers));
  } finally {
    if (running === ctrl) running = null;
    btn.disabled = screeningOff;
    btn.querySelector("span").textContent = "Screen the system";
  }
}

$("screen-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const d = desc.value.trim();
  if (d.length < 30) { fieldError(`Write at least 30 characters so there is something to screen (now ${d.length}).`); return; }
  if (d.length > 4000) { fieldError("Keep it under 4000 characters."); return; }
  hideFieldError();
  runScreen(d, role());
});

// A message under the report actions, with an action that fixes it when there is one.
function reportNotice(e) {
  const slot = document.querySelector("#result .rnotice-slot");
  const t = errorText(e);
  if (!slot) { toast(t.title); return; }
  const again = t.code === "invalid_signature" && last
    ? h("button", { type: "button", class: "btn btn--secondary", onclick: () => { const l = last; runScreen(l.description, l.role, l.answers); } }, icon("refresh"), "Screen again")
    : ["rate_limited", "busy", "network"].includes(t.code) ? h("button", { type: "button", class: "btn btn--ghost", onclick: downloadReport }, icon("refresh"), "Try again") : null;
  clear(slot).append(h("div", { class: `rnotice rnotice--${t.code}`, role: "alert" },
    icon(t.icon, "rnotice__icon"),
    h("div", { class: "rnotice__body" },
      h("p", { class: "rnotice__title", text: t.title }),
      t.body !== t.title ? h("p", { class: "rnotice__text", text: t.body }) : null,
      again ? h("div", { class: "rnotice__actions" }, again) : null)));
  if (again) again.focus({ preventScroll: true });
}

async function downloadReport() {
  if (!last) return;
  const slot = document.querySelector("#result .rnotice-slot");
  if (slot) clear(slot);
  try {
    const { blob, filename } = await api.report({ description: last.description, result: last.result });
    const url = URL.createObjectURL(blob);
    const a = h("a", { href: url, download: filename });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    toast("Report saved as Markdown");
  } catch (e) {
    reportNotice(e);
  }
}

async function copySummary() {
  if (!last) return;
  const text = summaryText(last.result);
  try {
    await navigator.clipboard.writeText(text);
    toast("Summary copied");
  } catch {
    const ta = h("textarea", { class: "visually-hidden" });
    ta.value = text;
    document.body.append(ta);
    ta.select();
    const ok = document.execCommand && document.execCommand("copy");
    ta.remove();
    toast(ok ? "Summary copied" : "Copy is blocked in this browser");
  }
}

/* Server without a model key: say so before anyone tries. */
let screeningOff = false;
function switchOffScreening() {
  screeningOff = true;
  $("screen-btn").disabled = true;
  const note = $("screen-note");
  note.classList.add("is-off");
  clear(note).append(icon("key"), h("span", { text: "Screening is switched off on this server: it has no Gemini API key. You can still read and search the Act." }));
  const q = $("ask-q");
  q.disabled = true;
  q.placeholder = "Questions are switched off on this server";
  $("ask-btn").disabled = true;
}

/* Start */
updateCounter();
loadExamples();
Promise.all([api.health().catch(() => null), api.source().catch(() => null)]).then(([hl, src]) => {
  setTextInfo(hl, src);
  if (document.querySelector(".reader-home")) showHome();
  if (!hl) return;
  if (hl.llm_ready === false) switchOffScreening();
  $("version").textContent = `v${hl.version}${api.MOCK ? " (mock)" : hl.fake_llm ? " (fake model)" : ""}`;
  // "retrieval" replaced "retriever"; an older backend may still send the old field.
  const retrieval = hl.retrieval || (hl.retriever === "missing" ? "keyword" : "hybrid");
  if (retrieval === "none") {
    const q = $("search-q");
    q.disabled = true;
    q.placeholder = "Search is not available on this server";
  } else if (retrieval === "keyword") {
    $("search-q").title = "Keyword search only on this server";
  }
});
api.mockReady.then((ok) => {
  if (ok || new URLSearchParams(location.search).get("mock") !== "1") return;
  $("main").prepend(h("p", { class: "mock-note", role: "status", text: "Mock data is not available on this server" }));
});
api.timeline().then((t) => setLawInForce(t && t.law_in_force)).catch(() => {});
if (!termsAccepted()) showTerms();

// For screenshots and manual checks: ?ref=art-6-3 opens the reader on load.
const startRef = new URLSearchParams(location.search).get("ref");
if (startRef) openRef(startRef, new URLSearchParams(location.search).get("quote") || "", { focusPanel: false });
