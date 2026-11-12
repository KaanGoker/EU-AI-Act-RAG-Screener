// Plain-text summary for the clipboard, and a Markdown report used in mock mode.
import { RISK, OUTCOME, ROLE } from "./dom.js";
import { textName } from "./textinfo.js";
import { dateStatus } from "./result.js";

export function summaryText(r) {
  const lines = [];
  lines.push("EU AI Act screening (draft, not legal advice)");
  lines.push("");
  lines.push(`Result: ${RISK[r.risk_class].name}, confidence ${r.confidence}`);
  if (r.headline) lines.push(r.headline);
  if (r.risk_class === "not_covered") lines.push("The AI Act does not apply to this system as described. Other law can still apply.");
  lines.push("");
  if (Array.isArray(r.answers) && r.answers.length) {
    lines.push("Your answers, taken into account:");
    for (const a of r.answers) lines.push(`- ${a.question} ${a.answer}`);
    lines.push("");
  }
  lines.push("Decision path:");
  for (const s of r.steps) lines.push(`- ${s.title}: ${OUTCOME[s.outcome]}`);
  lines.push("");
  lines.push(`Quotes found word for word in ${textName()}: ${r.verification.verified} of ${r.verification.total}`);
  if (r.obligations.length) {
    lines.push("");
    lines.push("Obligations:");
    for (const o of r.obligations) lines.push(`- ${o.title} (${ROLE[o.who]}${o.citation ? ", " + o.citation.label : ""})`);
  }
  lines.push("");
  lines.push(`Source: Regulation (EU) 2024/1689, ${textName()} (EUR-Lex). The Official Journal text is the authentic one.`);
  return lines.join("\n");
}

export function reportMarkdown(description, r) {
  const L = [];
  L.push("# EU AI Act screening report", "");
  L.push(`Draft assessment only. Not legal advice. Created ${r.created}, version ${r.version}.`, "");
  L.push("## System description", "", ...description.split("\n").map((l) => `> ${l}`), "");
  if (!r.in_scope) {
    L.push("## Result", "", r.refusal || "Out of scope.", "");
    return L.join("\n");
  }
  if (r.risk_class === "not_covered") {
    L.push("## Result", "", `**Outside the Act** (confidence: ${r.confidence})`, "", r.headline, "", "The AI Act does not apply to this system as described. Other law can still apply.", "", r.summary, "");
  } else {
    L.push("## Result", "", `**${RISK[r.risk_class].name}** (confidence: ${r.confidence}, role: ${ROLE[r.role]})`, "", r.headline, "", r.summary, "");
  }
  if (Array.isArray(r.answers) && r.answers.length) {
    L.push("## Your answers, taken into account", "");
    for (const a of r.answers) L.push(`- ${a.question}`, `  ${a.answer}`);
    L.push("");
  }
  L.push("## Decision path", "");
  r.steps.forEach((s, i) => {
    L.push(`### ${i + 1}. ${s.title}: ${OUTCOME[s.outcome]}`, "", s.question, "", s.reasoning, "");
    for (const c of s.citations) L.push(`> "${c.quote}"`, `> ${c.label}, page ${c.page}${c.verified ? ", found in the text" : ", NOT found in the cited text"}`, "");
  });
  L.push(`Quotes found word for word in ${textName()}: ${r.verification.verified} of ${r.verification.total}.`, "");
  if (r.obligations.length) {
    L.push("## Obligations", "");
    for (const o of r.obligations) {
      L.push(`- [ ] **${o.title}** (${ROLE[o.who]}${o.citation ? ", " + o.citation.label : ""}): ${o.detail}`);
      if (o.condition) L.push(`  ${o.condition}`);
      if (o.amended) L.push(`  Amended 2026: ${o.amended}`);
    }
    L.push("");
  }
  if (r.deadlines.length) {
    L.push("## Dates", "");
    for (const d of r.deadlines) L.push(`- ${d.date}: ${d.label} (${dateStatus(d)}, ${d.source_label})`);
    L.push("");
  }
  if (r.open_questions.length) {
    L.push("## What would change this result", "");
    for (const q of r.open_questions) L.push(`- ${q.question} ${q.why}`);
    L.push("");
  }
  L.push("## Sources", "");
  for (const s of r.sources) L.push(`- ${s.label}, ${s.title}: ${s.page_url}`);
  L.push("", r.disclaimer, "");
  return L.join("\n");
}
