// Ask the Act: a small streaming chat. History lives in memory only.
import * as api from "./api.js";
import { h, icon, clear, toast } from "./dom.js";
import { openRef } from "./reader.js";
import { errorText } from "./errors.js";

let history = [];
let busy = false;
let getTerms = () => false;

const log = () => document.getElementById("ask-log");

const norm = (s) => s.toLowerCase().replace(/\s+/g, " ").replace(/\barticle\b/g, "art").replace(/\bpoint\b/g, "").replace(/[ ,.]/g, "");

// Turns "[Article 6(3)]" markers into buttons when they match a source label.
function renderAnswer(el, text, sources) {
  const byLabel = new Map(sources.map((s) => [norm(s.label), s]));
  clear(el);
  for (const para of text.split(/\n{2,}/)) {
    const p = h("p");
    const re = /\[([^\]]{3,60})\]/g;
    let last = 0;
    let m;
    while ((m = re.exec(para))) {
      p.append(para.slice(last, m.index));
      const src = byLabel.get(norm(m[1])) || sources.find((s) => norm(m[1]).startsWith(norm(s.label)) || norm(s.label).startsWith(norm(m[1])));
      if (src) {
        p.append(h("button", { type: "button", class: "cite-link mono", onclick: () => openRef(src.ref) }, m[1]));
      } else {
        p.append(m[0]);
      }
      last = re.lastIndex;
    }
    p.append(para.slice(last));
    el.append(p);
  }
}

function emptyState() {
  const qs = [
    "What counts as a deployer?",
    "When does a system listed in Annex III escape the high-risk class?",
    "What must a chatbot tell its users?",
  ];
  clear(log()).append(h("div", { class: "ask-empty" },
    h("p", { class: "ask-empty__kicker mono", text: "Ask the Act" }),
    h("h3", { class: "ask-empty__title", text: "Questions answered from the text, with the articles cited" }),
    h("p", { class: "ask-empty__lede", text: "Answers quote the Regulation and link every reference to the reader. They are a reading aid, not legal advice." }),
    h("ul", { class: "ask-empty__list" }, qs.map((q) => h("li", {},
      h("button", { type: "button", class: "quick quick--q", onclick: () => send(q) }, h("span", { text: q }), icon("arrowRight")))))));
}

async function send(question) {
  question = question.trim();
  const input = document.getElementById("ask-q");
  if (busy) return;
  if (question.length < 5) {
    toast(question.length ? "Write a question of at least five characters." : "Type a question first.");
    input.focus();
    return;
  }
  if (!getTerms()) return;
  busy = true;
  document.getElementById("ask-btn").disabled = true;
  if (log().querySelector(".ask-empty")) clear(log());
  input.value = "";

  const userMsg = h("div", { class: "msg msg--user" }, h("p", { text: question }));
  const answerEl = h("div", { class: "msg__body" }, h("p", { class: "msg__typing", text: "Reading the Act..." }));
  const sourcesEl = h("div", { class: "msg__sources" });
  const botMsg = h("div", { class: "msg msg--bot", "aria-busy": "true" }, answerEl, sourcesEl);
  log().append(userMsg, botMsg);
  // Keep the question at the top of the log so the answer reads from its start.
  log().scrollTo({ top: userMsg.offsetTop - 12, behavior: "auto" });

  let sources = [];
  let text = "";
  try {
    await api.ask({ question, history: history.slice(-6), accepted_terms: true }, {
      onSources(c) {
        sources = c;
        clear(sourcesEl);
        if (c.length) {
          sourcesEl.append(h("p", { class: "msg__sources-head", text: "Sources" }),
            h("ul", {}, c.map((s) => h("li", {}, h("button", { type: "button", class: "src", onclick: () => openRef(s.ref) },
              h("span", { class: "mono", text: s.label }), h("span", { text: s.title || "" }))))));
        }
      },
      onToken(t) {
        text += t;
        renderAnswer(answerEl, text, sources);
      },
    });
    if (!text) answerEl.replaceChildren(h("p", { text: "No answer came back. Try rephrasing the question." }));
    history.push({ role: "user", content: question }, { role: "assistant", content: text });
    history = history.slice(-6);
    document.getElementById("ask-bar").hidden = false;
  } catch (e) {
    answerEl.replaceChildren(h("p", { class: "msg__error" }, icon("alert"), errorText(e).body));
  } finally {
    botMsg.removeAttribute("aria-busy");
    busy = false;
    document.getElementById("ask-btn").disabled = false;
  }
}

export function initAsk(termsOk) {
  getTerms = termsOk;
  emptyState();
  const form = document.getElementById("ask-form");
  const input = document.getElementById("ask-q");
  form.addEventListener("submit", (e) => { e.preventDefault(); send(input.value); });
  document.getElementById("ask-clear").addEventListener("click", () => {
    if (busy) return;
    history = [];
    emptyState();
    document.getElementById("ask-bar").hidden = true;
    input.focus();
  });
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(input.value); }
  });
}
