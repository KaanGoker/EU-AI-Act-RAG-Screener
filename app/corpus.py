"""The parsed text of Regulation (EU) 2024/1689, loaded from data/corpus.json."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS_PATH = ROOT / "data" / "corpus.json"

ROMAN_RE = r"(?:XIV|XIII|XII|XI|X|IX|VIII|VII|VI|V|IV|III|II|I)"


@dataclass(frozen=True)
class Part:
    id: str
    unit_id: str
    label: str
    text: str
    page: int
    amended: bool = False


@dataclass(frozen=True)
class Unit:
    id: str
    kind: str
    number: str
    title: str | None
    chapter: str | None
    chapter_title: str | None
    section: str | None
    section_title: str | None
    page_start: int
    page_end: int
    text: str
    parts: tuple[Part, ...]
    pdf_url: str | None = None  # the PDF the text and pages come from
    amended: bool = False  # changed or added by Regulation (EU) 2026/1744


# Patterns for normalize_ref, tried in order. Each returns (kind, number, part or None).
_ART = re.compile(
    r"\b(?:article|articles|art\.?|artikel|artículo|articolo|madde)\s*(\d{1,3}[a-z]?)\b"
    r"(?:\s*\(\s*(\d{1,3}[a-z]?)\s*\)"  # Article 6(3), Art. 6 (3), Article 6(1a)
    r"|\s*,?\s*(?:paragraph|para\.?|par\.?|§|lid|absatz|abs\.?)\s*\(?(\d{1,3}[a-z]?)\)?"  # Article 6, paragraph 3
    r"|\s*,?\s*point\s*\((\d{1,3}[a-z]?)\)"  # Article 3, point (1)
    r")?",
    re.IGNORECASE,
)
_ART_ID = re.compile(r"^art-(\d{1,3}[a-z]?)(?:-(\d{1,3}[a-z]?))?$", re.IGNORECASE)
_ANNEX = re.compile(
    r"\b(?:annex|annexe|anhang|bijlage|ek)\s+(" + ROMAN_RE + r")\b"
    r"(?:\s*\(\s*(\d{1,2}[a-z]?)\s*\)"  # Annex III(4)
    r"|\s*,?\s*(?:point|punt|nummer|nr\.?|no\.?)\s*\(?(\d{1,2}[a-z]?)\)?"  # Annex III, point 4
    r"|\s*,?\s*section\s+([A-Z]|\d)\b"  # Annex VIII, Section A
    r")?",
    re.IGNORECASE,
)
_ANNEX_ID = re.compile(r"^annex-(" + ROMAN_RE + r")(?:-([0-9]{1,2}[a-z]?|[A-Za-z]))?$", re.IGNORECASE)
_REC = re.compile(r"\b(?:recitals?|rec\.?|considerans|considérant|erwägungsgrund)\s*\(?(\d{1,3})\)?", re.IGNORECASE)
_REC_ID = re.compile(r"^rec-(\d{1,3})$", re.IGNORECASE)


class Corpus:
    def __init__(self, data: dict):
        self.source: dict = data["source"]
        self.units: dict[str, Unit] = {}
        self._lookup: dict[str, Unit | Part] = {}
        self._parts: dict[str, Part] = {}
        self._chapters: list[dict] = data.get("chapters", [])
        for u in data["units"]:
            parts = tuple(
                Part(
                    id=p["id"],
                    unit_id=u["id"],
                    label=p["label"],
                    text=p["text"],
                    page=p["page"],
                    amended=bool(p.get("amended", False)),
                )
                for p in u["parts"]
            )
            unit = Unit(
                id=u["id"],
                kind=u["kind"],
                number=u["number"],
                title=u["title"],
                chapter=u["chapter"],
                chapter_title=u["chapter_title"],
                section=u["section"],
                section_title=u["section_title"],
                page_start=u["page_start"],
                page_end=u["page_end"],
                text=u["text"],
                parts=parts,
                pdf_url=u.get("pdf_url"),
                amended=bool(u.get("amended", False)),
            )
            self.units[unit.id] = unit
            self._lookup[unit.id.lower()] = unit
            for p in parts:
                self._parts[p.id] = p
                self._lookup[p.id.lower()] = p
        self._by_kind: dict[str, list[str]] = {}
        for uid, u in self.units.items():
            self._by_kind.setdefault(u.kind, []).append(uid)

    # lookups

    def get(self, ref: str) -> Unit | Part | None:
        if not ref:
            return None
        hit = self._lookup.get(ref.strip().lower())
        if hit is None:
            norm = self.normalize_ref(ref)
            hit = self._lookup.get(norm.lower()) if norm else None
        return hit

    def unit_of(self, ref: str) -> Unit | None:
        hit = self.get(ref)
        if hit is None:
            return None
        if isinstance(hit, Part):
            return self.units[hit.unit_id]
        return hit

    def text_of(self, ref: str) -> str | None:
        hit = self.get(ref)
        return hit.text if hit is not None else None

    def label(self, ref: str) -> str:
        hit = self.get(ref)
        if hit is None:
            return ref
        if isinstance(hit, Part):
            unit = self.units[hit.unit_id]
            if unit.kind == "article":
                return f"Article {unit.number}({hit.label})"
            if hit.label.startswith("Section"):
                return f"Annex {unit.number}, {hit.label}"
            return f"Annex {unit.number}, point {hit.label}"
        if hit.kind == "article":
            return f"Article {hit.number}"
        if hit.kind == "annex":
            return f"Annex {hit.number}"
        return f"Recital {hit.number}"

    def title(self, ref: str) -> str | None:
        unit = self.unit_of(ref)
        return unit.title if unit else None

    def page(self, ref: str) -> int:
        hit = self.get(ref)
        if hit is None:
            return 1
        return hit.page if isinstance(hit, Part) else hit.page_start

    def page_url(self, ref: str) -> str:
        unit = self.unit_of(ref)
        base = (unit.pdf_url if unit else None) or self.source["pdf_url"]
        return f"{base}#page={self.page(ref)}"

    def amended(self, ref: str) -> bool:
        """True when Regulation (EU) 2026/1744 changed or added this unit or part."""
        hit = self.get(ref)
        return bool(hit and hit.amended)

    def neighbors(self, unit_id: str) -> tuple[str | None, str | None]:
        unit = self.unit_of(unit_id)
        if unit is None:
            return None, None
        ids = self._by_kind[unit.kind]
        i = ids.index(unit.id)
        prev_id = ids[i - 1] if i > 0 else None
        next_id = ids[i + 1] if i + 1 < len(ids) else None
        return prev_id, next_id

    def toc(self) -> dict:
        chapters: list[dict] = []
        index: dict[str, dict] = {}
        for c in self._chapters:
            entry = {"number": c["number"], "title": c["title"], "articles": []}
            chapters.append(entry)
            index[c["number"]] = entry
        for uid in self._by_kind.get("article", []):
            u = self.units[uid]
            entry = index.get(u.chapter or "")
            if entry is None:
                entry = {"number": u.chapter, "title": u.chapter_title, "articles": []}
                chapters.append(entry)
                index[u.chapter or ""] = entry
            entry["articles"].append(
                {
                    "id": u.id,
                    "number": u.number,
                    "title": u.title,
                    "section": u.section,
                    "section_title": u.section_title,
                    "amended": u.amended,
                }
            )
        annexes = [
            {"id": uid, "number": self.units[uid].number, "title": self.units[uid].title, "amended": self.units[uid].amended}
            for uid in self._by_kind.get("annex", [])
        ]
        return {"chapters": chapters, "annexes": annexes, "recitals": {"count": len(self._by_kind.get("recital", []))}}

    # references

    def normalize_ref(self, text: str) -> str | None:
        """Turn a written reference into a unit id or part id of this corpus, or None.

        A paragraph or point that does not exist falls back to its unit ("Article 4(1)" -> "art-4").
        """
        if not text:
            return None
        t = text.strip()
        m = _ART_ID.match(t)
        if m:
            return self._article(m.group(1), m.group(2))
        m = _ANNEX_ID.match(t)
        if m:
            return self._annex(m.group(1), m.group(2))
        m = _REC_ID.match(t)
        if m:
            return self._existing(f"rec-{int(m.group(1))}")

        found = []
        for pattern, kind in ((_ART, "art"), (_ANNEX, "annex"), (_REC, "rec")):
            m = pattern.search(t)
            if m:
                found.append((m.start(), kind, m))
        if not found:
            return None
        _, kind, m = min(found, key=lambda f: f[0])
        if kind == "art":
            return self._article(m.group(1), m.group(2) or m.group(3) or m.group(4))
        if kind == "annex":
            return self._annex(m.group(1), m.group(2) or m.group(3) or m.group(4))
        return self._existing(f"rec-{int(m.group(1))}")

    def _existing(self, uid: str) -> str | None:
        hit = self._lookup.get(uid.lower())
        return hit.id if hit is not None else None

    @staticmethod
    def _num(value: str) -> str:
        m = re.match(r"(\d+)([a-z]?)", value.lower())
        return f"{int(m.group(1))}{m.group(2)}"

    def _article(self, number: str, part: str | None) -> str | None:
        uid = f"art-{self._num(number)}"
        if uid not in self.units:
            return None
        if part:
            pid = f"{uid}-{self._num(part)}"
            if pid in self._parts:
                return pid
        return uid

    def _annex(self, roman: str, part: str | None) -> str | None:
        uid = f"annex-{roman.upper()}"
        if uid not in self.units:
            return None
        if part:
            p = part.upper() if part.isalpha() else self._num(part)
            pid = f"{uid}-{p}"
            if pid in self._parts:
                return pid
        return uid


@lru_cache(maxsize=1)
def get_corpus() -> Corpus:
    return Corpus(json.loads(CORPUS_PATH.read_text(encoding="utf-8")))
