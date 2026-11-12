// Find a quote inside a text while ignoring differences in whitespace, quote marks,
// dashes, case and hyphenation at line breaks. Returns [start, end] in the original text or null.

const MAP = {
  "\u2018": "'", "\u2019": "'", "\u201A": "'", "\u201B": "'", "\u2032": "'",
  "\u201C": '"', "\u201D": '"', "\u201E": '"', "\u2033": '"',
  "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-", "\u2212": "-",
  "\u00A0": " ",
};

// Builds the normalized string and, for each of its characters, the index in the original.
function normalize(text) {
  let out = "";
  const idx = [];
  let lastSpace = true;
  for (let i = 0; i < text.length; i++) {
    let ch = MAP[text[i]] || text[i];
    if (/\s/.test(ch)) {
      if (!lastSpace) { out += " "; idx.push(i); }
      lastSpace = true;
      continue;
    }
    // "word- word" from a line break: drop the hyphen and the space.
    if (ch === "-" && /\s/.test(text[i + 1] || "") && /\w/.test(text[i - 1] || "")) {
      let j = i + 1;
      while (j < text.length && /\s/.test(text[j])) j++;
      if (/[a-z]/.test(text[j] || "")) { i = j - 1; continue; }
    }
    lastSpace = false;
    out += ch.toLowerCase();
    idx.push(i);
  }
  if (out.endsWith(" ")) { out = out.slice(0, -1); idx.pop(); }
  return { out, idx };
}

function normQuote(q) {
  return normalize(q).out.replace(/^[\s"'.,;:]+|[\s"'.,;:]+$/g, "");
}

export function findQuote(text, quote) {
  if (!text || !quote) return null;
  const t = normalize(text);
  let q = normQuote(quote);
  if (q.length < 3) return null;
  let at = t.out.indexOf(q);
  if (at < 0) {
    // Hyphenation tolerance: compare with hyphens removed on both sides.
    const tt = t.out.replace(/-/g, "");
    const qq = q.replace(/-/g, "");
    const at2 = tt.indexOf(qq);
    if (at2 < 0) return null;
    // Map back through the hyphen-free string.
    const map = [];
    for (let i = 0; i < t.out.length; i++) if (t.out[i] !== "-") map.push(i);
    const s = map[at2];
    const e = map[at2 + qq.length - 1];
    return [t.idx[s], t.idx[e] + 1];
  }
  return [t.idx[at], t.idx[at + q.length - 1] + 1];
}

// Fills el with text, wrapping the first match of quote in <mark>. Returns the mark or null.
export function renderWithMark(el, text, quote) {
  const range = quote ? findQuote(text, quote) : null;
  if (!range) {
    el.textContent = text;
    return null;
  }
  const [s, e] = range;
  const mark = document.createElement("mark");
  mark.className = "quote-mark";
  mark.textContent = text.slice(s, e);
  el.replaceChildren(document.createTextNode(text.slice(0, s)), mark, document.createTextNode(text.slice(e)));
  return mark;
}
