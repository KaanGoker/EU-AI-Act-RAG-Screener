// Which version of the Act the app reads, for the wording around verified quotes.
import { fmtDate } from "./dom.js";

const AMENDING = "Regulation (EU) 2026/1744 (Digital Omnibus on AI)";
const state = {
  version: "",        // "27 July 2026" once known
  htmlUrl: "https://eur-lex.europa.eu/eli/reg/2024/1689/oj",
  notice: "",
};

// Accepts "2026-07-27" or a phrase such as "Consolidated text of 27 July 2026"; returns "27 July 2026".
function readable(v) {
  if (!v) return "";
  const iso = String(v).match(/(\d{4}-\d{2}-\d{2})/);
  if (iso) return fmtDate(iso[1], { day: "numeric", month: "long", year: "numeric" });
  const words = String(v).match(/\b(\d{1,2} [A-Z][a-z]+ \d{4})\b/);
  return words ? words[1] : "";
}

// health: /api/health, source: /api/source; either may be missing.
export function setTextInfo(health, source) {
  state.version = readable(source && source.consolidated_version) || readable(health && health.text_version);
  if (source && source.html_url) state.htmlUrl = source.html_url;
  if (source && source.legal_notice) state.notice = source.legal_notice;
  document.querySelectorAll("[data-text-version]").forEach((el) => { el.textContent = textName(); });
  const link = document.getElementById("text-link");
  if (link) link.href = state.htmlUrl;
}

// "the consolidated text of 27 July 2026", or without a date when unknown.
export function textName() {
  return state.version ? `the consolidated text of ${state.version}` : "the consolidated text on EUR-Lex";
}
export function versionLabel() { return state.version; }
export const AMENDED_TITLE = `Changed or added by ${AMENDING}`;
export const NOTICE_SHORT = "A consolidated text is a documentation tool. The authentic text is the one published in the Official Journal.";
