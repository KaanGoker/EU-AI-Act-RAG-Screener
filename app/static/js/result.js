// Renders a ScreenResult into #result.
import { h, icon, riskMark, RISK, OUTCOME, ROLE, fmtDate, clear } from "./dom.js";
import { openRef } from "./reader.js";
import { textName, NOTICE_SHORT } from "./textinfo.js";

const BASIS = {
  annex_iii: "Annex III use",
  annex_i: "Annex I product (Section A)",
  annex_i_section_b: "Annex I product (Section B)",
  both: "Annex I and Annex III",
};

// Entries that are about entry into force; every other entry is about when rules apply.
const isEntryIntoForce = (d) => /in-force|entry-into-force/.test(d.id || "") || /enters? into force/i.test(d.label || "");
export function dateStatus(d) {
  if (isEntryIntoForce(d)) return d.status === "in_force" ? "In force" : `In force from ${fmtDate(d.date)}`;
  return d.status === "in_force" ? "Applies now" : `Applies from ${fmtDate(d.date)}`;
}

const STEP_HINT = {
  scope: "Article 2 and the definition in Article 3(1)",
  prohibited: "Article 5",
  high_risk: "Article 6, Annex I and Annex III",
  exemption: "Article 6(3)",
  transparency: "Article 50",
  gpai: "Chapter V",
};

// The step that settles the class: it gets the emphasis on the path.
export function decidingStep(r) {
  const by = Object.fromEntries(r.steps.map((s) => [s.id, s]));
  if (by.scope && by.scope.outcome === "no") return "scope";
  if (r.risk_class === "prohibited") return "prohibited";
  if (r.risk_class === "high") return by.exemption && by.exemption.outcome !== "not_applicable" && by.exemption.outcome !== "no" ? "exemption" : "high_risk";
  if (r.risk_class === "limited") return "transparency";
  if (r.risk_class === "unclear") return (r.steps.find((s) => s.outcome === "unclear") || {}).id || null;
  return null;
}

function section(num, title, id, ...content) {
  return h("section", { class: `rsec rsec--${id}`, "aria-labelledby": `rsec-${id}` },
    h("header", { class: "rsec__head" },
      h("span", { class: "rsec__num mono", text: String(num).padStart(2, "0") }),
      h("h3", { class: "rsec__title", id: `rsec-${id}`, text: title })),
    ...content);
}

function quoteCard(c) {
  return h("button", {
    type: "button",
    class: `quote${c.verified ? "" : " is-unverified"}`,
    onclick: () => openRef(c.ref, c.quote),
    "aria-label": `${c.label}: ${c.verified ? "verified quote" : "quote not found in the cited text"}. Open in the reader.`,
  },
    h("span", { class: "quote__top" },
      h("span", { class: "quote__label mono", text: c.label }),
      h("span", { class: "quote__page mono", text: `p. ${c.page}` })),
    h("span", { class: "quote__text", text: c.quote }),
    h("span", { class: "quote__check" },
      c.verified ? icon("check") : icon("flag"),
      !c.verified ? "Not found in the cited text"
        : /^rec-/.test(c.ref) ? "Found in the 2024 Official Journal text of the recitals"
        : "Found word for word in the consolidated text"));
}

function stationGlyph(outcome) {
  if (outcome === "yes") return icon("check", "station__glyph");
  if (outcome === "no") return h("span", { class: "station__dash", "aria-hidden": "true" });
  if (outcome === "unclear") return h("span", { class: "station__q", "aria-hidden": "true", text: "?" });
  return null;
}

function path(r) {
  const deciding = decidingStep(r);
  const ol = h("ol", { class: "path" });
  r.steps.forEach((s, i) => {
    const reached = s.outcome !== "not_applicable";
    const isDec = s.id === deciding;
    const li = h("li", {
      class: `station station--${s.outcome}${isDec ? ` is-deciding is-deciding--${r.risk_class}` : ""}`,
      dataset: { step: s.id },
    });
    li.style.setProperty("--i", String(i));
    li.append(
      h("span", { class: "station__node", "aria-hidden": "true" }, stationGlyph(s.outcome)),
      h("div", { class: "station__body" },
        h("div", { class: "station__head" },
          h("span", { class: "station__num mono", text: `Check ${i + 1}` }),
          h("h4", { class: "station__title", text: s.title }),
          h("span", { class: `outcome outcome--${s.outcome}` }, OUTCOME[s.outcome]),
          isDec ? h("span", { class: "station__decides" }, "Deciding step") : null),
        h("p", { class: "station__question" }, s.question, h("span", { class: "station__hint mono", text: STEP_HINT[s.id] || "" })),
        reached || (s.reasoning && !/^Not reached/.test(s.reasoning)) ? h("p", { class: "station__reason", text: s.reasoning }) : null,
        s.citations.length ? h("div", { class: "quotes" }, s.citations.map(quoteCard)) : null),
    );
    ol.append(li);
  });
  ol.append(h("li", { class: `station station--end station--end-${r.risk_class}` },
    h("span", { class: "station__node station__node--end", "aria-hidden": "true" }, riskMark(r.risk_class)),
    h("div", { class: "station__body" },
      h("div", { class: "station__head" },
        h("span", { class: "station__num mono", text: "Result" }),
        h("h4", { class: "station__title", text: RISK[r.risk_class].long })),
      h("p", { class: "station__question", text: RISK[r.risk_class].note }))));
  ol.lastChild.style.setProperty("--i", String(r.steps.length));
  return ol;
}

function verifyLine(v, hasRecital) {
  const all = v.total > 0 && v.verified === v.total;
  const ticks = h("span", { class: "vline__ticks", "aria-hidden": "true" });
  for (let i = 0; i < v.total; i++) ticks.append(h("span", { class: i < v.verified ? "is-ok" : "is-miss" }));
  const text = v.total === 0
    ? "No quotes to verify for this result"
    : `${v.verified} of ${v.total} quotes found word for word in ${textName()}${hasRecital ? ", recitals in the 2024 Official Journal text" : ""}`;
  return h("p", { class: `vline${all ? " is-all" : ""}${v.verified < v.total ? " has-miss" : ""}` },
    icon(v.verified < v.total ? "flag" : "check", "vline__icon"), h("span", { class: "vline__text", text }), ticks,
    h("span", { class: "vline__note" },
      v.total ? h("span", { class: "vline__caveat", text: "A found quote shows that the words are in the Act, not that the conclusion is right." }) : null,
      (v.verified < v.total ? "Flagged quotes are shown as given. Read them in the source before you rely on them. " : "") + NOTICE_SHORT));
}

function confidenceMeter(c) {
  const n = { low: 1, medium: 2, high: 3 }[c] || 0;
  return h("span", { class: "meter", "aria-hidden": "true" }, [1, 2, 3].map((i) => h("span", { class: i <= n ? "is-on" : "" })));
}

function scale(cls) {
  const order = ["prohibited", "high", "limited", "minimal"];
  const outside = cls === "not_covered";
  const rungs = h("ol", { class: `scale${outside ? " scale--none" : ""}`, "aria-label": "Risk classes of the Act" }, order.map((k) =>
    h("li", { class: `scale__rung scale__rung--${k}${k === cls ? " is-active" : ""}`, "aria-current": k === cls ? "true" : null },
      riskMark(k), h("span", { text: RISK[k].name }))));
  if (!outside) return rungs;
  return h("div", { class: "scale-wrap" },
    h("p", { class: "scale__caption" }, riskMark("not_covered"), "Not placed in any of the four risk classes: the Act does not apply to the system as described."),
    rungs);
}

function verdict(r) {
  const meta = [
    ["Confidence", h("span", { class: "fact__val" }, confidenceMeter(r.confidence), r.confidence)],
    r.risk_class === "high" && BASIS[r.high_risk_basis] ? ["Route", BASIS[r.high_risk_basis]] : null,
    ["Role", ROLE[r.role] || r.role],
    ["Language", (r.language || "").toUpperCase()],
  ];
  return h("header", { class: `verdict verdict--${r.risk_class}` },
    h("div", { class: "verdict__main" },
      h("div", { class: "verdict__mark" }, riskMark(r.risk_class, "riskmark--xl")),
      h("div", { class: "verdict__text" },
        h("p", { class: "verdict__kicker mono", text: "Screening result" }),
        h("h2", { class: "verdict__class", id: "verdict-title", text: RISK[r.risk_class].long }),
        h("p", { class: "verdict__headline", text: r.headline }),
        r.risk_class === "not_covered" ? h("p", { class: "verdict__outside" }, icon("info"),
          "The AI Act does not apply to this system as described. Other law can still apply, such as data protection, product safety or rules for the sector.") : null,
        h("dl", { class: "facts" }, meta.filter(Boolean).map(([k, v]) => h("div", { class: "fact" }, h("dt", { text: k }), h("dd", {}, v)))))),
    scale(r.risk_class));
}

function obligations(r, onChange) {
  const cols = r.role === "deployer" ? ["deployer", "provider"] : ["provider", "deployer"];
  const state = new Array(r.obligations.length).fill(false);
  const grid = h("div", { class: "obl" });
  const progress = h("p", { class: "obl__progress mono", "aria-live": "polite" });
  const update = () => {
    const done = state.filter(Boolean).length;
    progress.textContent = `${done} of ${state.length} checked`;
    grid.querySelectorAll("input[data-idx]").forEach((cb) => { cb.checked = state[Number(cb.dataset.idx)]; });
    onChange && onChange(state);
  };
  for (const who of cols) {
    const items = r.obligations.map((o, i) => [o, i]).filter(([o]) => o.who === who || o.who === "both");
    if (!items.length) continue;
    const ul = h("ul", { class: "obl__list" });
    for (const [o, i] of items) {
      const id = `ob-${who}-${i}`;
      const cb = h("input", { type: "checkbox", id, dataset: { idx: String(i) } });
      cb.addEventListener("change", () => { state[i] = cb.checked; update(); });
      ul.append(h("li", { class: "obl__item" },
        cb,
        h("label", { for: id, class: "obl__label" },
          h("span", { class: "obl__box", "aria-hidden": "true" }, icon("check")),
          h("span", { class: "obl__title", text: o.title }),
          o.who === "both" ? h("span", { class: "obl__both", text: "Both roles" }) : null),
        h("p", { class: "obl__detail", text: o.detail }),
        o.condition ? h("p", { class: "obl__condition", text: o.condition }) : null,
        o.amended ? h("p", { class: "obl__amended" }, h("span", { class: "amended", title: o.amended }, "Amended 2026"), h("span", { text: o.amended })) : null,
        o.citation ? h("button", { type: "button", class: "obl__ref mono", onclick: () => openRef(o.citation.ref, o.citation.quote) }, o.citation.label, icon("arrowRight")) : null));
    }
    grid.append(h("div", { class: `obl__col obl__col--${who}${who === r.role ? " is-yours" : ""}` },
      h("h4", { class: "obl__head" }, icon(who === "provider" ? "building" : "user"), who === "provider" ? "Provider" : "Deployer",
        who === r.role ? h("span", { class: "obl__yours", text: "Your role" }) : null),
      ul));
  }
  if (grid.children.length === 1) grid.classList.add("obl--single");
  update();
  return [h("p", { class: "rsec__lede", text: "Ticking is only for you, in this tab. Nothing is saved." }), progress, grid];
}

// Dots closer than this share one dot on the line (percent of the line).
const MIN_GAP = 4.5;
// Today in the reader's own time zone, as YYYY-MM-DD.
function localToday() {
  const t = new Date();
  return `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, "0")}-${String(t.getDate()).padStart(2, "0")}`;
}
function fmtCreated(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return `${d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}, ${d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })} local time`;
}

let lawInForce = "";
export function setLawInForce(t) { lawInForce = t || ""; }

function timeline(input, cls) {
  if (!input.length) {
    return h("p", { class: "rsec__empty" }, icon("info"), cls === "not_covered"
      ? "No dates of application, because the Act does not apply to the system as described."
      : "No dates of application are tied to this result.");
  }
  const deadlines = [...input].sort((a, b) => a.date.localeCompare(b.date));
  const today = localToday();
  const all = deadlines.map((d) => d.date).concat(today).sort();
  const t0 = Date.parse(all[0]);
  const t1 = Date.parse(all[all.length - 1]);
  const pos = (iso) => (t1 === t0 ? 50 : ((Date.parse(iso) - t0) / (t1 - t0)) * 100);
  const track = h("div", { class: "tl__track", "aria-hidden": "true" }, h("span", { class: "tl__line" }));
  const done = h("span", { class: "tl__done" });
  done.style.setProperty("--w", `${pos(today)}%`);
  track.append(done);
  // One dot per date; dates too close to tell apart on the line share a dot (for example "4-5").
  const groups = [];
  deadlines.forEach((d, i) => {
    const g = groups[groups.length - 1];
    if (g && pos(d.date) - g.x < MIN_GAP) { g.nums.push(i + 1); if (d.status === "upcoming") g.status = "upcoming"; }
    else groups.push({ x: pos(d.date), nums: [i + 1], status: d.status });
  });
  for (const g of groups) {
    const n = g.nums;
    const dot = h("span", { class: `tl__dot tl__dot--${g.status}${n.length > 1 ? " tl__dot--multi" : ""}`, text: n.length > 1 ? `${n[0]}-${n[n.length - 1]}` : String(n[0]) });
    dot.style.setProperty("--x", `${g.x}%`);
    track.append(dot);
  }
  const now = h("span", { class: "tl__today" }, h("span", { class: "tl__today-label", text: `Today, ${fmtDate(today)}` }));
  now.style.setProperty("--x", `${pos(today)}%`);
  if (pos(today) > 75) now.classList.add("is-right");
  if (pos(today) < 15) now.classList.add("is-left");
  track.append(now);
  const years = h("div", { class: "tl__years", "aria-hidden": "true" });
  const y0 = new Date(t0).getUTCFullYear();
  const y1 = new Date(t1).getUTCFullYear();
  for (let y = y0 + 1; y <= y1; y++) {
    const s = h("span", { text: String(y) });
    s.style.setProperty("--x", `${pos(`${y}-01-01`)}%`);
    years.append(s);
  }
  const list = h("ol", { class: "tl__list" }, deadlines.map((d, i) => h("li", { class: `tl__item tl__item--${d.status}` },
    h("span", { class: "tl__n mono", "aria-hidden": "true", text: String(i + 1) }),
    h("time", { class: "tl__date mono", datetime: d.date, text: fmtDate(d.date) }),
    h("div", { class: "tl__what" },
      h("p", { class: "tl__label" }, d.label, h("span", { class: `pill pill--${d.status}`, text: dateStatus(d) })),
      h("p", { class: "tl__detail" }, d.detail, " ",
        d.source_ref ? h("button", { type: "button", class: "linkbtn mono", onclick: () => openRef(d.source_ref) }, d.source_label || d.source_ref) : null)))));
  const law = lawInForce ? h("p", { class: "tl__law" }, icon("info"), `Dates follow ${lawInForce}.`) : null;
  return h("div", { class: "tl" }, track, years, list, law);
}

function openQuestions(r, onRescreen) {
  if (!r.open_questions.length) return h("p", { class: "rsec__lede rsec__lede--keep", text: "The description gave enough to decide. No open questions." });
  const form = h("form", { class: "oq" });
  const fields = [];
  r.open_questions.forEach((q, i) => {
    const ta = h("textarea", { id: `oq-${i}`, rows: "2", maxlength: "500", placeholder: "Your answer (optional)" });
    fields.push([q, ta]);
    form.append(h("div", { class: "oq__item" },
      h("label", { for: `oq-${i}`, class: "oq__q" }, h("span", { class: "oq__n mono", text: `Q${i + 1}` }), q.question),
      h("p", { class: "oq__why", text: q.why }),
      ta));
  });
  const btn = h("button", { type: "submit", class: "btn btn--secondary", disabled: true }, icon("refresh"), "Screen again with these answers");
  form.addEventListener("input", () => { btn.disabled = !fields.some(([, ta]) => ta.value.trim()); });
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const answers = fields.filter(([, ta]) => ta.value.trim()).map(([q, ta]) => ({ question: q.question, answer: ta.value.trim() }));
    if (answers.length) onRescreen(answers);
  });
  form.append(h("div", { class: "oq__actions" }, btn));
  return [h("p", { class: "rsec__lede", text: "Answer what you can. The screener runs again with your answers added to the description." }), form];
}

function sources(r) {
  return h("ul", { class: "srcs" }, r.sources.map((s) => h("li", {},
    h("button", { type: "button", class: "srcs__open", onclick: () => openRef(s.ref) },
      h("span", { class: "mono", text: s.label }), h("span", { text: s.title || "" })),
    h("a", { class: "srcs__pdf", href: s.page_url, target: "_blank", rel: "noopener" }, `PDF p. ${s.page}`, icon("external")))));
}

function actions(handlers) {
  return h("div", { class: "ractions", role: "group", "aria-label": "Report actions" },
    h("button", { type: "button", class: "btn btn--ghost", onclick: handlers.download }, icon("download"), "Download report"),
    h("button", { type: "button", class: "btn btn--ghost", onclick: () => window.print() }, icon("print"), "Print"),
    h("button", { type: "button", class: "btn btn--ghost", onclick: handlers.copy }, icon("copy"), "Copy summary"),
    h("button", { type: "button", class: "btn btn--ghost ractions__new", onclick: handlers.newScreen }, icon("arrowLeft"), "Edit the description"));
}

export function renderResult(el, r, description, handlers, animate = true) {
  clear(el);
  el.className = `result result--${r.risk_class}`;
  const printHead = h("div", { class: "print-only print-head" },
    h("p", { class: "mono", text: "EU AI Act screening report, draft, not legal advice" }),
    h("p", { text: `Regulation (EU) 2024/1689, quotes checked against ${textName()}. Created ${fmtCreated(r.created)}. Version ${r.version}.` }),
    h("h2", { text: "System description" }),
    h("blockquote", { class: "print-desc", text: description }));

  if (!r.in_scope) {
    el.append(h("div", { class: "refusal" },
      h("div", { class: "refusal__icon" }, riskMark("unclear", "riskmark--xl")),
      h("div", {},
        h("p", { class: "verdict__kicker mono", text: "Nothing to screen" }),
        h("h2", { class: "refusal__title", text: "This does not read as an AI system" }),
        h("p", { class: "refusal__text", text: r.refusal || "Describe an AI system and try again." }),
        h("button", { type: "button", class: "btn btn--secondary", onclick: handlers.newScreen }, icon("arrowLeft"), "Edit the description"))));
    return;
  }

  el.append(printHead, verdict(r));
  if (r.risk_class === "high" && r.high_risk_basis === "annex_i_section_b") {
    el.append(h("p", { class: "basis-note" }, icon("info"),
      h("span", {}, "For this product group, ",
        h("button", { type: "button", class: "linkbtn mono", onclick: () => openRef("art-2-2") }, "Article 2(2)"),
        " applies only a few provisions of the Act directly.")));
  }
  el.append(h("div", { class: "readas" },
    h("p", { class: "readas__k mono", text: "How the system was read" }),
    h("p", { class: "readas__v", text: r.summary })));
  const given = Array.isArray(r.answers) ? r.answers : [];
  if (given.length) {
    el.append(h("div", { class: "given" },
      h("p", { class: "given__k mono", text: "Your answers, taken into account" }),
      h("dl", { class: "given__list" }, given.map((a) => h("div", { class: "given__item" },
        h("dt", { text: a.question }), h("dd", { text: a.answer }))))));
  }
  const cited = r.steps.flatMap((s) => s.citations || []);
  el.append(verifyLine(r.verification, cited.some((c) => c.verified && /^rec-/.test(c.ref || ""))));
  if (r.gpai && r.gpai.applies) {
    el.append(h("p", { class: "gpai-note" }, icon("info"), h("strong", { text: "General-purpose AI: " }), r.gpai.note || "Chapter V duties apply to the model provider."));
  }
  el.append(actions(handlers), h("div", { class: "rnotice-slot" }));
  const p = path(r);
  if (animate) p.classList.add("is-arriving");
  el.append(section(1, "Decision path", "path",
    h("p", { class: "rsec__lede", text: "Six checks that follow the structure of the Act. Open any quote to read it in context." }), p));
  el.append(section(2, "Obligations", "obl", r.obligations.length ? obligations(r)
    : h("p", { class: "rsec__empty" }, icon("info"), r.risk_class === "not_covered"
      ? "No obligations under the AI Act, because the Act does not apply to the system as described."
      : r.risk_class === "unclear"
        ? `No obligations are listed, because the class is not decided. ${r.open_questions.length ? "Answer the open questions below and screen again." : "Add detail to the description and screen again."}`
        : "No obligations from the Act's list were found for this result.")));
  el.append(section(3, "Dates that apply", "dates", timeline(r.deadlines, r.risk_class)));
  el.append(section(4, "What would change this result", "oq", openQuestions(r, handlers.rescreen)));
  el.append(section(5, "Sources", "src", r.sources.length ? sources(r) : h("p", { class: "rsec__empty", text: "No sources were cited." })));
  el.append(h("p", { class: "rdisclaimer" }, icon("info"), r.disclaimer));
}
