// Small DOM helpers, icons and labels. Data is always set as text, never as HTML.

export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "text") el.textContent = v;
    else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
    else if (k === "dataset") Object.assign(el.dataset, v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  append(el, children);
  return el;
}

function append(el, children) {
  for (const c of children.flat(Infinity)) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
}

const SVG_NS = "http://www.w3.org/2000/svg";

// Icons as path lists, drawn with stroke unless noted.
const ICONS = {
  check: ["M5 12.5l4.5 4.5L19 7.5"],
  flag: ["M6 21V4", "M6 4h11l-2.5 4L17 12H6"],
  arrowRight: ["M5 12h13", "M13 6l6 6-6 6"],
  arrowLeft: ["M19 12H6", "M11 6l-6 6 6 6"],
  external: ["M14 5h5v5", "M19 5l-8 8", "M17 14v5H5V7h5"],
  download: ["M12 4v11", "M7 10l5 5 5-5", "M5 20h14"],
  print: ["M7 9V4h10v5", "M7 17H5v-7h14v7h-2", "M7 14h10v6H7z"],
  copy: ["M9 9h10v11H9z", "M5 15V4h10"],
  book: ["M4 5.5C6.5 4.5 9.5 4.5 12 6c2.5-1.5 5.5-1.5 8-.5v13c-2.5-1-5.5-1-8 .5-2.5-1.5-5.5-1.5-8-.5z", "M12 6v13.5"],
  alert: ["M12 4l9 16H3z", "M12 10v4", "M12 17v.5"],
  info: ["M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18", "M12 11v6", "M12 7.5v.5"],
  refresh: ["M19 8a8 8 0 1 0 1 6", "M19 3v5h-5"],
  clock: ["M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18", "M12 7v5l3 2"],
  wifiOff: ["M3 3l18 18", "M8.5 16.5a5 5 0 0 1 7 0", "M5 13a10 10 0 0 1 5-2.7", "M14 10.3A10 10 0 0 1 19 13", "M12 20v.5"],
  key: ["M14 4a6 6 0 1 1-5.3 8.8L3 18.5V21h3v-2h2v-2h2l1.2-1.2", "M15.5 8.5v.5"],
  chevron: ["M9 6l6 6-6 6"],
  user: ["M12 12a4 4 0 1 0 0-8a4 4 0 1 0 0 8", "M4 21c1-4 4.5-6 8-6s7 2 8 6"],
  building: ["M4 21V5l8-2v18", "M12 9h8v12", "M7 8v.5M7 12v.5M7 16v.5M16 13v.5M16 17v.5"],
};

export function icon(name, cls = "") {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("class", `icon ${cls}`.trim());
  for (const d of ICONS[name] || []) {
    const p = document.createElementNS(SVG_NS, "path");
    p.setAttribute("d", d);
    svg.append(p);
  }
  return svg;
}

// Risk class marks: a distinct shape per class, so the class reads without color.
const SHAPES = {
  prohibited: { shape: "M8.3 2h7.4L22 8.3v7.4L15.7 22H8.3L2 15.7V8.3z", glyph: "M7 12h10" },
  high: { shape: "M12 2.5L22.5 20.5H1.5z", glyph: "M12 9v5.5M12 17.2v.3" },
  limited: { shape: "M12 1.8L22.2 12 12 22.2 1.8 12z", glyph: "M8 12.2h.1M12 12.2h.1M16 12.2h.1" },
  minimal: { shape: "M12 2a10 10 0 1 0 0 20a10 10 0 1 0 0-20", glyph: "M7.5 12.3l3 3 6-6.3" },
  not_covered: { shape: "M3.5 3.5h17v17h-17z", glyph: "M8 12h8.5M13.5 8.8 16.7 12l-3.2 3.2" },
  unclear: { shape: "M12 2a10 10 0 1 0 0 20a10 10 0 1 0 0-20", glyph: "M9.5 9.5a2.6 2.6 0 1 1 3.6 2.4c-.8.4-1.1.9-1.1 1.8M12 16.8v.3", dashed: true },
};

export function riskMark(cls, extra = "") {
  const s = SHAPES[cls] || SHAPES.unclear;
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("class", `riskmark riskmark--${cls} ${extra}`.trim());
  const a = document.createElementNS(SVG_NS, "path");
  a.setAttribute("d", s.shape);
  a.setAttribute("class", "riskmark__shape" + (s.dashed ? " riskmark__shape--dashed" : ""));
  const b = document.createElementNS(SVG_NS, "path");
  b.setAttribute("d", s.glyph);
  b.setAttribute("class", "riskmark__glyph");
  svg.append(a, b);
  return svg;
}

export const RISK = {
  prohibited: { name: "Prohibited", long: "Prohibited practice", note: "Banned under Article 5" },
  high: { name: "High-risk", long: "High-risk system", note: "Article 6 with Annex I or Annex III" },
  limited: { name: "Limited risk", long: "Limited risk", note: "Transparency duties under Article 50 only" },
  minimal: { name: "Minimal risk", long: "Minimal risk", note: "No specific duties beyond AI literacy" },
  not_covered: { name: "Outside the Act", long: "Outside the Act", note: "The Act does not apply as described" },
  unclear: { name: "Unclear", long: "Not enough to decide", note: "The description leaves it open" },
};

export const OUTCOME = {
  yes: "Yes",
  no: "No",
  unclear: "Unclear",
  not_applicable: "Not reached",
};

export const ROLE = { provider: "Provider", deployer: "Deployer", unknown: "Not sure", both: "Provider and deployer" };

export function fmtDate(iso, opts = { day: "numeric", month: "short", year: "numeric" }) {
  const d = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-GB", { ...opts, timeZone: "UTC" });
}

export function clear(el) {
  while (el.firstChild) el.firstChild.remove();
  return el;
}

let toastTimer = 0;
export function toast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.hidden = false;
  t.classList.add("is-on");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    t.classList.remove("is-on");
    setTimeout(() => { t.hidden = true; }, 250);
  }, 2600);
}

export function prefersReducedMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export const storage = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* blocked */ } },
};
