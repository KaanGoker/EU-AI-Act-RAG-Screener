"""Parse Regulation (EU) 2024/1689 into data/corpus.json.

Run from the repo root:  python -m ingest.build_corpus
Exits non-zero when the counts or the numbering are wrong.

Sources:
- Articles and annexes: the EUR-Lex consolidated version of 27 July 2026 (CELEX 02024R1689-20260727,
  data/eu_ai_act_consolidated_2026-07-27.pdf), which includes Regulation (EU) 2026/1744.
- Recitals: the original Official Journal PDF (data/eu_ai_act.pdf). Consolidated versions do not
  reproduce recitals.
Every unit carries the pdf_url of the PDF its text and pages come from.

How a PDF is read:
- Page header and footer are dropped (y < 70, y > 803).
- Footnotes sit below a short rule near the page bottom; everything below it is dropped.
- Footnote markers are superscript spans inside brackets, "(1)"; they are removed with the brackets.
  The only other superscript in the Act is "10^25" in Article 51, kept as "10^25".
- Consolidation markers (the arrows with B, M1 that mark the origin of a passage) are dropped, and so
  are the "__________" lines that mark deleted text. A unit or part that holds text from an amending
  act (any origin other than B) gets "amended": true; a unit with a deleted passage too.
- Lines on one baseline are merged; lines are joined into blocks. A new block starts when the
  vertical gap is larger than a normal line, or, across a page break, when the last line of the
  previous page is short (justified text fills the line unless the paragraph ends there).
  A soft hyphen at a line end joins the word; a plain hyphen at a line end joins without a space.
- Blocks become newlines in the text, so paragraphs, points (a), (b) and subparagraphs keep
  their own lines.
- Em dashes and en dashes are written as a plain hyphen (project rule); Annex II uses them as list bullets.

Parts:
- Articles: numbered paragraphs "1.", "1a.", "2." become parts art-N-1, art-N-1a, art-N-2. Article 3 has
  no paragraphs; its numbered definitions become parts art-3-1 ... (cited as Article 3(1)).
- Annexes: top-level numbered points become parts annex-III-1 ... Annex I numbers its points across
  Section A and Section B, so its parts are annex-I-<n>; the section headings stay in the annex text but
  outside the parts. Annexes whose numbering restarts in each section (VIII, XI) get one part per
  section instead: annex-VIII-A, annex-XI-1 ... with label "Section A".
- A deleted paragraph or point leaves a gap in the numbering (for example Annex I starts at point 2).
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent.parent
OJ_PDF = ROOT / "data" / "eu_ai_act.pdf"
CONS_PDF = ROOT / "data" / "eu_ai_act_consolidated_2026-07-27.pdf"
OUT = ROOT / "data" / "corpus.json"

OJ_URL = "https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=OJ:L_202401689"
CONS_URL = "https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:02024R1689-20260727"

SOURCE = {
    "title": "Regulation (EU) 2024/1689 (Artificial Intelligence Act), consolidated version of 27 July 2026",
    "celex": "02024R1689-20260727",
    "eli": "http://data.europa.eu/eli/reg/2024/1689/oj",
    "consolidated_version": "2026-07-27",
    "includes": [
        {
            "title": "Regulation (EU) 2026/1744 of the European Parliament and of the Council of 8 July 2026 (Digital Omnibus on AI)",
            "celex": "32026R1744",
            "oj": "OJ L, 2026/1744, 24.7.2026",
            "eli": "http://data.europa.eu/eli/reg/2026/1744/oj",
        }
    ],
    "pdf_url": CONS_URL,
    "html_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:02024R1689-20260727",
    "legal_notice": (
        "This text is meant purely as a documentation tool and has no legal effect. The Union's institutions "
        "do not assume any liability for its contents. The authentic versions of the relevant acts, including "
        "their preambles, are those published in the Official Journal of the European Union and available in EUR-Lex."
    ),
    "recitals": {
        "source": "Regulation (EU) 2024/1689 as published in OJ L, 2024/1689, 12.7.2024",
        "celex": "32024R1689",
        "pdf_url": OJ_URL,
        "note": "The consolidated version does not reproduce the recitals; they are taken from the original act.",
    },
}

EXPECTED = {"recital": 180, "article": 119, "annex": 14, "chapter": 13}

LINE_GAP = 13.0  # normal line pitch is about 10.5
SUP = "\x01"
SUP_END = "\x02"

ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV"]


@dataclass(frozen=True)
class Layout:
    header_y: float
    footer_y: float
    rule_x0: float  # the short rule above the footnotes
    rule_x1: float
    right_edge: float  # a justified full line ends here or later
    col_x0: float
    col_x1: float


OJ = Layout(header_y=70, footer_y=803, rule_x0=67.4, rule_x1=118.4, right_edge=528, col_x0=67, col_x1=530)
CONS = Layout(header_y=70, footer_y=803, rule_x0=107.0, rule_x1=158.3, right_edge=388, col_x0=107, col_x1=391)


@dataclass
class Line:
    page: int
    y0: float
    x0: float
    x1: float
    size: float
    bold: bool
    italic: bool
    text: str
    amended: bool = False
    deletion_before: bool = False  # a deleted passage sits just before this line


@dataclass
class Block:
    page: int
    x0: float
    text: str
    amended: bool = False


@dataclass
class RawUnit:
    kind: str
    number: str
    page_start: int
    title_lines: list[str] = field(default_factory=list)
    lines: list[Line] = field(default_factory=list)
    chapter: str | None = None
    chapter_title: str | None = None
    section: str | None = None
    section_title: str | None = None
    amended: bool = False


def clean(text: str) -> str:
    text = text.replace("\u2014", "-").replace("\u2013", "-").replace("\u2212", "-")
    text = text.replace(" ", " ")
    return re.sub(r"[ \t]+", " ", text).strip()


def footnote_rule_y(page: pymupdf.Page, layout: Layout) -> float | None:
    """The rule above real footnotes: the first line below it starts with a superscript number.
    The same rule also sits above the "(*)" notes inside quoted amendments (Articles 102 to 110),
    which are part of the text."""
    lines = [ln for b in page.get_text("dict")["blocks"] for ln in b.get("lines", [])]
    for dr in page.get_drawings():
        r = dr["rect"]
        if abs(r.x0 - layout.rule_x0) < 0.5 and abs(r.x1 - layout.rule_x1) < 0.5 and r.height < 1.5:
            below = sorted((ln for ln in lines if ln["bbox"][1] > r.y0 - 2), key=lambda ln: ln["bbox"][1])
            if below and any(s["size"] < 7 and s["text"].strip() for s in below[0]["spans"][:4]):
                return r.y0
    return None


def join_spans(spans: list[dict]) -> str:
    out = ""
    prev_x1 = None
    for s in spans:
        t = s["text"]
        if s["size"] < 7 and t.strip():
            t = SUP + t.strip() + SUP_END
        if prev_x1 is not None and out and t:
            gap = s["bbox"][0] - prev_x1
            if gap > 0.8 and not out[-1].isspace() and not t[0].isspace() and not t.startswith(SUP):
                out += " "
        out += t
        prev_x1 = s["bbox"][2]
    # footnote markers: "(" superscript ")" with the space before it
    out = re.sub(r"\s*\(\s*" + SUP + r"[^" + SUP_END + r"]*" + SUP_END + r"\s*\)", "", out)
    # the one real superscript: 10^25
    out = re.sub(r"\s*" + SUP + r"(\d+)" + SUP_END, r"^\1", out)
    if SUP in out:
        raise ValueError(f"unhandled superscript in line: {out!r}")
    return out


# consolidation markers: an arrow with the code of the act the passage comes from
_MARK = re.compile(r"[▼►◄]\s*(B|M\d+|C\d+|A\d+|E\d+)?")


def extract_lines(doc: pymupdf.Document, layout: Layout) -> list[Line]:
    lines: list[Line] = []
    origin = "B"
    after_deletion = False
    for pno, page in enumerate(doc, start=1):
        rule_y = footnote_rule_y(page, layout)
        raw = []
        for b in page.get_text("dict")["blocks"]:
            for ln in b.get("lines", []):
                spans = [s for s in ln["spans"] if s["text"]]
                if not spans:
                    continue
                y0 = ln["bbox"][1]
                if y0 < layout.header_y or y0 > layout.footer_y:
                    continue
                if rule_y is not None and y0 > rule_y - 2:
                    continue
                raw.append((ln["bbox"], spans))
        # merge pymupdf lines that share a baseline
        raw.sort(key=lambda r: (round(r[0][3]), r[0][0]))
        groups: list[list] = []
        for bbox, spans in raw:
            if groups and abs(groups[-1][0][3] - bbox[3]) < 3.0:
                g = groups[-1]
                g[0] = (min(g[0][0], bbox[0]), min(g[0][1], bbox[1]), max(g[0][2], bbox[2]), max(g[0][3], bbox[3]))
                g[1].extend(spans)
            else:
                groups.append([tuple(bbox), list(spans)])
        for bbox, spans in groups:
            spans.sort(key=lambda s: s["bbox"][0])
            text = join_spans(spans)
            # consolidation markers set the origin of what follows
            codes = [m.group(1) for m in _MARK.finditer(text)]
            rest = _MARK.sub("", text)
            if codes:
                last = [c for c in codes if c]
                if last:
                    origin = last[-1]
                elif "►" in text:
                    origin = "M"
            if re.fullmatch(r"[\s_]*", rest):
                if "___" in rest:
                    after_deletion = True
                continue
            text_spans = [s for s in spans if not _MARK.fullmatch(s["text"].strip() or "x")]
            main = max(text_spans or spans, key=lambda s: len(s["text"].strip()))
            lines.append(
                Line(
                    page=pno,
                    y0=bbox[1],
                    x0=min(s["bbox"][0] for s in text_spans) if text_spans else bbox[0],
                    x1=bbox[2],
                    size=round(main["size"], 1),
                    bold="Bold" in main["font"],
                    italic="Ital" in main["font"],
                    text=rest,
                    amended=origin != "B",
                    deletion_before=after_deletion,
                )
            )
            after_deletion = False
    return lines


MARKER = re.compile(r"^(\d+[a-z]?\.|\([a-z]{1,4}\)|\(\d+[a-z]?\))\s")


def make_blocks(lines: list[Line], layout: Layout) -> list[Block]:
    blocks: list[Block] = []
    parts: list[str] = []
    prev: Line | None = None
    for ln in lines:
        text = ln.text
        if prev is None:
            new = True
        elif ln.page != prev.page:
            prev_text = prev.text.rstrip()
            ends = prev_text.endswith((".", ";", ":")) or prev_text.endswith((" or", " and"))
            new = prev.x1 < layout.right_edge or (MARKER.match(text.lstrip()) is not None and ends)
        else:
            new = (ln.y0 - prev.y0) > LINE_GAP
        if new:
            if parts:
                blocks[-1].text = join_text(parts)
            blocks.append(Block(page=ln.page, x0=ln.x0, text="", amended=ln.amended))
            parts = [text]
        else:
            parts.append(text)
            blocks[-1].amended = blocks[-1].amended or ln.amended
        prev = ln
    if parts:
        blocks[-1].text = join_text(parts)
    return [b for b in blocks if b.text]


def join_text(parts: list[str]) -> str:
    out = ""
    for p in parts:
        p = p.strip()
        if not out:
            out = p
        elif out.endswith("\u00ad"):
            out = out[:-1] + p
        elif out.endswith("-") and not out.endswith(" -"):
            out = out + p
        else:
            out = out + " " + p
    out = out.replace("\u00ad", "")
    # a URL broken across lines
    out = re.sub(r"(https?://\S*[./]) (\S*/oj\))", r"\1\2", out)
    out = re.sub(r"10\s*\^(\d+)\s*(?=[.,;])", r"10^\1", out)
    out = re.sub(r"10\s*\^(\d+)", r"10^\1", out)
    return clean(out)


def sentence_case(title: str) -> str:
    words = title.lower().split()
    fixed = []
    for w in words:
        core = w.strip(",")
        if core in {"ai", "eu"}:
            w = w.replace(core, core.upper())
        fixed.append(w)
    s = " ".join(fixed)
    return s[:1].upper() + s[1:]


def is_centered(ln: Line, layout: Layout) -> bool:
    return ln.x0 > layout.col_x0 + 30 and ln.x1 < layout.col_x1 - 30


def num_key(label: str) -> tuple[int, str]:
    m = re.match(r"(\d+)([a-z]*)", label)
    return (int(m.group(1)), m.group(2)) if m else (0, "")


def parse_recitals(lines: list[Line]) -> list[RawUnit]:
    recitals: list[RawUnit] = []
    i = 0
    n = len(lines)
    while i < n and lines[i].text.strip() != "Whereas:":
        i += 1
    i += 1
    cur: RawUnit | None = None
    while i < n and lines[i].text.strip() != "HAVE ADOPTED THIS REGULATION:":
        ln = lines[i]
        m = re.match(r"^\((\d+)\)\s", ln.text)
        if m and ln.x0 < OJ.col_x0 + 5 and int(m.group(1)) == len(recitals) + 1:
            cur = RawUnit(kind="recital", number=m.group(1), page_start=ln.page)
            recitals.append(cur)
        if cur is None:
            raise ValueError(f"text before recital 1 on page {ln.page}: {ln.text!r}")
        cur.lines.append(ln)
        i += 1
    return recitals


def parse_enacting(lines: list[Line], layout: Layout):
    """Chapters, articles and annexes, from CHAPTER I to the end."""
    articles: list[RawUnit] = []
    annexes: list[RawUnit] = []
    chapters: list[dict] = []
    n = len(lines)
    i = 0
    while i < n and not (lines[i].text.strip() == "CHAPTER I" and is_centered(lines[i], layout)):
        i += 1
    chapter = chapter_title = section = section_title = None
    cur: RawUnit | None = None
    last_key = (0, "")
    while i < n:
        ln = lines[i]
        t = ln.text.strip()
        if t.startswith("This Regulation shall be binding in its entirety"):
            break
        m = re.match(r"^CHAPTER ([IVXLC]+)$", t)
        if m and ln.size < 9 and is_centered(ln, layout):
            chapter = m.group(1)
            i += 1
            title = []
            while i < n and lines[i].bold and lines[i].size < 9:
                title.append(lines[i].text.strip())
                i += 1
            chapter_title = sentence_case(" ".join(title))
            section = section_title = None
            chapters.append({"number": chapter, "title": chapter_title})
            continue
        m = re.match(r"^SECTION (\d+)$", t)
        if m and ln.size < 9 and is_centered(ln, layout):
            section = m.group(1)
            i += 1
            title = []
            while i < n and lines[i].bold:
                title.append(lines[i].text.strip())
                i += 1
            section_title = clean(" ".join(title))
            continue
        m = re.match(r"^Article (\d+[a-z]?)$", t)
        if m and is_centered(ln, layout):
            key = num_key(m.group(1))
            if key > last_key and key[0] <= last_key[0] + 1:
                last_key = key
                cur = RawUnit(
                    kind="article",
                    number=m.group(1),
                    page_start=ln.page,
                    chapter=chapter,
                    chapter_title=chapter_title,
                    section=section,
                    section_title=section_title,
                    amended=ln.amended,
                )
                articles.append(cur)
                i += 1
                while i < n and lines[i].bold and not lines[i].italic:
                    cur.title_lines.append(lines[i].text.strip())
                    cur.amended = cur.amended or lines[i].amended
                    i += 1
                continue
        if cur is None:
            raise ValueError(f"text before Article 1 on page {ln.page}: {t!r}")
        cur.lines.append(ln)
        i += 1

    # skip the closing formula and signatures
    while i < n and not (re.match(r"^ANNEX [IVX]+$", lines[i].text.strip()) and lines[i].size < 9):
        i += 1
    cur = None
    while i < n:
        ln = lines[i]
        t = ln.text.strip()
        m = re.match(r"^ANNEX ([IVX]+)$", t)
        if m and ln.size < 9 and is_centered(ln, layout) and m.group(1) == ROMAN[len(annexes)]:
            cur = RawUnit(kind="annex", number=m.group(1), page_start=ln.page, amended=ln.amended)
            annexes.append(cur)
            i += 1
            while i < n and (lines[i].bold or (lines[i].italic and lines[i].size < 9)):
                cur.title_lines.append(lines[i].text.strip())
                cur.amended = cur.amended or lines[i].amended
                i += 1
            if not cur.title_lines:
                # a title in plain type: the first block
                prev = None
                while i < n and (prev is None or lines[i].y0 - prev.y0 <= LINE_GAP) and lines[i].page == ln.page:
                    cur.title_lines.append(lines[i].text.strip())
                    cur.amended = cur.amended or lines[i].amended
                    prev = lines[i]
                    i += 1
            continue
        cur.lines.append(ln)
        i += 1
    return articles, annexes, chapters


def split_parts(unit_id: str, blocks: list[Block], pattern: str, top_x: float):
    """Numbered parts in increasing order; a deleted number may be skipped."""
    parts = []
    last = (0, "")
    for b in blocks:
        m = re.match(pattern, b.text)
        if m and b.x0 < top_x:
            key = num_key(m.group(1))
            if key > last and key[0] <= last[0] + 2:
                last = key
                body = b.text[m.end():].lstrip()
                parts.append({"id": f"{unit_id}-{m.group(1)}", "label": m.group(1), "texts": [body], "page": b.page, "amended": b.amended})
                continue
        if parts:
            parts[-1]["texts"].append(b.text)
            parts[-1]["amended"] = parts[-1]["amended"] or b.amended
    return parts


SECTION_HEAD = re.compile(r"^Section ([A-Z]|\d+)(?:\.|\s-|$)")


def annex_parts(unit_id: str, blocks: list[Block], top_x: float):
    sections = [b for b in blocks if SECTION_HEAD.match(b.text)]
    nums = []
    for b in blocks:
        m = re.match(r"^(\d+[a-z]?)\.\s", b.text)
        if m and b.x0 < top_x:
            nums.append(num_key(m.group(1)))
    restarts = any(b <= a for a, b in zip(nums, nums[1:]))
    if sections and restarts:
        parts = []
        for b in blocks:
            m = SECTION_HEAD.match(b.text)
            if m:
                parts.append({"id": f"{unit_id}-{m.group(1)}", "label": f"Section {m.group(1)}", "texts": [b.text], "page": b.page, "amended": b.amended})
            elif parts:
                parts[-1]["texts"].append(b.text)
                parts[-1]["amended"] = parts[-1]["amended"] or b.amended
        return parts
    parts: list = []
    last = (0, "")
    for b in blocks:
        m = re.match(r"^(\d+[a-z]?)\.\s", b.text)
        if m and b.x0 < top_x:
            key = num_key(m.group(1))
            if key > last and key[0] <= last[0] + 2:
                last = key
                parts.append({"id": f"{unit_id}-{m.group(1)}", "label": m.group(1), "texts": [b.text[m.end():].lstrip()], "page": b.page, "amended": b.amended})
                continue
        if SECTION_HEAD.match(b.text):
            parts.append(None)  # a section heading closes the open point
        elif parts and parts[-1] is not None:
            parts[-1]["texts"].append(b.text)
            parts[-1]["amended"] = parts[-1]["amended"] or b.amended
    return [p for p in parts if p is not None]


def finish_parts(parts):
    return [
        {"id": p["id"], "label": p["label"], "text": "\n".join(p["texts"]), "page": p["page"], "amended": bool(p["amended"])}
        for p in parts
    ]


def unit_dict(uid: str, raw: RawUnit, title, text, parts, lines, pdf_url: str, amended: bool):
    return {
        "id": uid,
        "kind": raw.kind,
        "number": raw.number,
        "title": title,
        "chapter": raw.chapter,
        "chapter_title": raw.chapter_title,
        "section": raw.section,
        "section_title": raw.section_title,
        "page_start": raw.page_start,
        "page_end": lines[-1].page if lines else raw.page_start,
        "pdf_url": pdf_url,
        "amended": amended,
        "text": text,
        "parts": parts,
    }


def build() -> dict:
    oj_lines = extract_lines(pymupdf.open(OJ_PDF), OJ)
    cons_lines = extract_lines(pymupdf.open(CONS_PDF), CONS)
    recitals = parse_recitals(oj_lines)
    articles, annexes, chapters = parse_enacting(cons_lines, CONS)
    top_x = CONS.col_x0 + 5
    units = []
    for r in recitals:
        blocks = make_blocks(r.lines, OJ)
        text = "\n".join(b.text for b in blocks)
        text = re.sub(r"^\(\d+\)\s", "", text)
        units.append(unit_dict(f"rec-{r.number}", r, None, text, [], r.lines, OJ_URL, False))
    for a in articles:
        uid = f"art-{a.number}"
        blocks = make_blocks(a.lines, CONS)
        text = "\n".join(b.text for b in blocks)
        if a.number == "3":
            parts = split_parts(uid, blocks, r"^\((\d+[a-z]?)\)\s", top_x)
        else:
            parts = split_parts(uid, blocks, r"^(\d+[a-z]?)\.\s", top_x)
        title = clean(" ".join(a.title_lines)).rstrip("`'’").strip()
        amended = a.amended or any(b.amended for b in blocks) or any(ln.deletion_before for ln in a.lines)
        units.append(unit_dict(uid, a, title, text, finish_parts(parts), a.lines, CONS_URL, amended))
    for x in annexes:
        uid = f"annex-{x.number}"
        blocks = make_blocks(x.lines, CONS)
        text = "\n".join(b.text for b in blocks)
        parts = annex_parts(uid, blocks, top_x)
        title = clean(" ".join(x.title_lines))
        amended = x.amended or any(b.amended for b in blocks) or any(ln.deletion_before for ln in x.lines)
        units.append(unit_dict(uid, x, title, text, finish_parts(parts), x.lines, CONS_URL, amended))
    return {"source": SOURCE, "chapters": chapters, "units": units}


def check(corpus: dict) -> list[str]:
    problems = []
    units = corpus["units"]
    by_kind: dict[str, list] = {}
    for u in units:
        by_kind.setdefault(u["kind"], []).append(u)
    for kind in ("recital", "article", "annex"):
        got = len(by_kind.get(kind, []))
        if got != EXPECTED[kind]:
            problems.append(f"{kind}: {got} units, expected {EXPECTED[kind]}")
    if len(corpus["chapters"]) != EXPECTED["chapter"]:
        problems.append(f"chapters: {len(corpus['chapters'])}, expected {EXPECTED['chapter']}")
    rec = [int(u["number"]) for u in by_kind.get("recital", [])]
    if rec != list(range(1, len(rec) + 1)):
        problems.append("recital: numbering gap")
    arts = [num_key(u["number"])[0] for u in by_kind.get("article", [])]
    if sorted(set(arts)) != list(range(1, 114)):
        problems.append("article: numbers 1 to 113 not all present")
    ids = [u["id"] for u in units] + [p["id"] for u in units for p in u["parts"]]
    if len(ids) != len(set(ids)):
        problems.append("duplicate ids")
    for u in units:
        if u["kind"] != "recital" and not u["title"]:
            problems.append(f"{u['id']}: no title")
        if any(ch in u["text"] for ch in "\u2014\u2013\u2212\u00ad\u25bc\u25ba\u25c4"):
            problems.append(f"{u['id']}: dash, soft hyphen or marker left in text")
        if re.search(r"\b\d{1,3}/144\b|02024R1689 - EN|(?<!2024/1689, )OJ L, 12\.7\.2024", u["text"]):
            problems.append(f"{u['id']}: page header or footer in text")
        if re.search(r"___", u["text"]):
            problems.append(f"{u['id']}: deletion line in text")
    a3 = next((u for u in units if u["id"] == "annex-III"), None)
    if a3 and [p["id"] for p in a3["parts"]] != [f"annex-III-{k}" for k in range(1, 9)]:
        problems.append("annex-III: points 1 to 8 not found")
    return problems


def summary(corpus: dict) -> None:
    units = corpus["units"]
    counts: dict[str, int] = {}
    for u in units:
        counts[u["kind"]] = counts.get(u["kind"], 0) + 1
    nparts = sum(len(u["parts"]) for u in units)
    print(f"units: {len(units)}  {counts}  parts: {nparts}  chapters: {len(corpus['chapters'])}")
    lens = sorted(len(u["text"]) for u in units)
    print(f"unit length: min {lens[0]}, median {lens[len(lens) // 2]}, max {lens[-1]}")
    for u in units:
        size = len(u["text"])
        if size < 120 or size > 20000:
            print(f"  suspicious length: {u['id']} ({size} chars)")
    for u in units:
        labels = [p["label"] for p in u["parts"]]
        nums = [num_key(x)[0] for x in labels if x[:1].isdigit()]
        gaps = sorted(set(range(1, max(nums) + 1)) - set(nums)) if nums else []
        if gaps:
            print(f"  numbering gap in {u['id']}: {gaps} (deleted or not numbered)")
    amended = [u["id"] for u in units if u["amended"]]
    print(f"amended units ({len(amended)}): {' '.join(amended)}")
    for u in units:
        if u["kind"] == "annex":
            print(f"  {u['id']}: {u['title'][:70]!r} pages {u['page_start']}-{u['page_end']}, parts {[p['label'] for p in u['parts']]}")


def main() -> int:
    corpus = build()
    OUT.write_text(json.dumps(corpus, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    summary(corpus)
    problems = check(corpus)
    for p in problems:
        print("PROBLEM:", p)
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
