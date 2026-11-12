"""Quote verification: is a quote, word for word, in the cited text? Pure functions, no I/O.

A quote verifies only when, after normalization of both sides, it is one contiguous
substring of the cited text. Normalization folds Unicode form (NFKC), whitespace runs and
line breaks, quote-mark variants (quotation marks around a term are dropped, an apostrophe
inside a word is kept), hyphen and dash variants, soft hyphens and zero-width characters,
hyphenation at a line break, spaces around hyphens and next to brackets and closing
punctuation, and letter case. Nothing else: no similarity ratio, no word tolerance. A match
must start and end on a word boundary.

An ellipsis in the middle of a quote is never stitched over: `split_quote` returns the
continuous segments and each one is checked as its own quote. One check is a substring
search on normalized strings, so it runs in linear time in practice.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

MIN_QUOTE_CHARS = 20
MIN_QUOTE_WORDS = 4

_QUOTE_CHARS = "\"'`\u2018\u2019\u201a\u201b\u201c\u201d\u201e\u201f\u2032\u2033\u00ab\u00bb\u2039\u203a"
_DASHES = "\u2010\u2011\u2012\u2013\u2014\u2015\u2212\ufe58\ufe63\uff0d"
_DROP = "\u00ad\u200b\u200c\u200d\u2060\ufeff"
_ELLIPSIS = re.compile(r"\s*(?:\u2026|\.\s*\.\s*\.|\[\s*(?:\.\s*){3}\]|\[\u2026\]|\(\s*(?:\.\s*){3}\))\s*")
_EDGE = " ,;:."

# Applied in order to the per-character folded text; each keeps an offset map.
_STEPS: list[tuple[re.Pattern[str], str]] = [
    # Hyphenation at a line break: "classifi-\ncation" -> "classification".
    (re.compile(r"(?<=\w)-[ \t]*\r?\n\s*(?=\w)"), ""),
    # Quotation marks around a term ("'AI system' means") are dropped; an apostrophe
    # inside a word ("Member State's") is kept.
    (re.compile(r"(?<!\w)'|'(?!\w)"), ""),
    (re.compile(r"\s+"), " "),
    # "general- purpose", "general -purpose" -> "general-purpose".
    (re.compile(r"(?<=\w) ?- ?(?=\w)"), "-"),
    # Space before closing or after opening punctuation: "obligations ;", "( a )".
    (re.compile(r" (?=[,.;:)\]])"), ""),
    (re.compile(r"(?<=[(\[]) "), ""),
]


@dataclass(frozen=True)
class Located:
    ref: str  # where the quote was found: the cited ref, or another part of the same unit
    verified: bool
    text: str | None  # the passage exactly as it stands in the corpus text, when verified; else None


@dataclass(frozen=True)
class _Folded:
    text: str
    start: list[int]  # original start offset of each folded character
    end: list[int]  # original end offset of each folded character


def _fold_chars(text: str) -> _Folded:
    out: list[str] = []
    start: list[int] = []
    end: list[int] = []
    for i, ch in enumerate(text):
        if ch in _DROP:
            continue
        for c in unicodedata.normalize("NFKC", ch):
            if c in _DASHES:
                c = "-"
            elif c in _QUOTE_CHARS:
                c = "'"
            for low in c.lower():
                out.append(low)
                start.append(i)
                end.append(i + 1)
    return _Folded("".join(out), start, end)


def _apply(f: _Folded, pattern: re.Pattern[str], repl: str) -> _Folded:
    out: list[str] = []
    start: list[int] = []
    end: list[int] = []
    pos = 0
    for m in pattern.finditer(f.text):
        out.append(f.text[pos : m.start()])
        start.extend(f.start[pos : m.start()])
        end.extend(f.end[pos : m.start()])
        if repl and m.end() > m.start():
            out.append(repl)
            start.extend([f.start[m.start()]] * len(repl))
            end.extend([f.end[m.end() - 1]] * len(repl))
        pos = m.end()
    out.append(f.text[pos:])
    start.extend(f.start[pos:])
    end.extend(f.end[pos:])
    return _Folded("".join(out), start, end)


def _fold(text: str) -> _Folded:
    f = _fold_chars(text or "")
    for pattern, repl in _STEPS:
        f = _apply(f, pattern, repl)
    return f


@lru_cache(maxsize=2048)
def _fold_corpus(text: str) -> _Folded:
    """Folded corpus text. Only corpus text is cached, never a quote."""
    return _fold(text)


def normalize(text: str) -> str:
    """The folded form of a text that both sides are compared in."""
    return _fold(text).text.strip()


def split_quote(quote: str) -> list[str]:
    """The continuous segments of a quote, split at every ellipsis, in original form.

    A leading or trailing ellipsis is dropped. Each segment is a quote of its own and is
    checked on its own; segments are never joined back into one verified passage."""
    parts = _ELLIPSIS.split(quote or "")
    return [p.strip() for p in parts if normalize(p).strip(_EDGE)]


def _needle(quote: str) -> str | None:
    """The normalized quote to search for, or None when it is too short or not one segment."""
    segments = split_quote(quote)
    if len(segments) != 1:
        return None
    needle = normalize(segments[0]).strip(_EDGE)
    if len(needle) < MIN_QUOTE_CHARS or len(re.findall(r"\w+", needle)) < MIN_QUOTE_WORDS:
        return None
    return needle


_OPENING = "\u2018\u201c\u201a\u201e\u00ab\u2039"
_CLOSING = "\u2019\u201d\u00bb\u203a"
_STRAIGHT = "'\""
_BRACKETS = {")": "(", "]": "["}


def _closing_marks(cut: str) -> int:
    """Closing typographic marks in `cut` that are not apostrophes inside a word."""
    n = 0
    for k, ch in enumerate(cut):
        if ch in _CLOSING:
            inside = 0 < k < len(cut) - 1 and cut[k - 1].isalnum() and cut[k + 1].isalnum()
            n += not inside
    return n


def _widen(text: str, start: int, end: int) -> str:
    """The cut text[start:end], widened by a quote mark or bracket that sits directly at its
    edges, so the passage reads as printed. Display only: it never changes a decision."""
    # An opening quote mark directly before the first character.
    if start > 0 and (text[start - 1] in _OPENING or (text[start - 1] in _STRAIGHT and (start < 2 or not text[start - 2].isalnum()))):
        start -= 1
    # A closing quote mark, or a bracket the cut opened, directly after the last character.
    if end < len(text):
        ch = text[end]
        cut = text[start:end]
        if ch in _CLOSING or (ch in _STRAIGHT and (end + 1 >= len(text) or not text[end + 1].isalnum())):
            end += 1
        elif ch in _BRACKETS and cut.count(_BRACKETS[ch]) > cut.count(ch):
            end += 1
    # Balance of typographic marks: take in the partner that sits right outside the cut.
    cut = text[start:end]
    opening = sum(cut.count(m) for m in _OPENING)
    closing = _closing_marks(cut)
    if closing > opening and start > 0 and text[start - 1] in _OPENING:
        start -= 1
    elif opening > closing and end < len(text) and text[end] in _CLOSING:
        end += 1
    return text[start:end]


def _find(needle: str, text: str | None) -> str | None:
    """The original passage of `text` that matches `needle`, or None."""
    if not text:
        return None
    f = _fold_corpus(text)
    hay = f.text
    # The match must start and end on a word boundary, so "Article 4" does not match
    # inside "Article 49" and "Annex I" not inside "Annex III".
    head = needle[0].isalnum()
    tail = needle[-1].isalnum()
    i = hay.find(needle)
    while i >= 0:
        j = i + len(needle)
        if not (head and i > 0 and hay[i - 1].isalnum()) and not (tail and j < len(hay) and hay[j].isalnum()):
            return _widen(text, f.start[i], f.end[j - 1])
        i = hay.find(needle, i + 1)
    return None


def find_quote(quote: str, text: str | None) -> bool:
    """True when the quote, as one segment, is word for word in `text`."""
    needle = _needle(quote)
    return needle is not None and _find(needle, text) is not None


def locate(quote: str, ref: str, text: str | None, siblings: list[tuple[str, str]] | None = None) -> Located:
    """Verify a quote against its cited text, else against the other parts of the same unit.

    `siblings` are (ref, text) pairs of the other parts of the same unit. A quote cited to
    a whole unit is narrowed to the first part that holds it. A quote not in the cited text
    moves to the first sibling part that holds it. A part ref is never widened to its unit,
    so a quote that only matches across two parts does not verify."""
    needle = _needle(quote)
    if needle is None:
        return Located(ref, False, None)
    parts = [(r, t) for r, t in (siblings or []) if r != ref and not ref.startswith(r + "-")]
    found = _find(needle, text)
    if found is not None:
        for r, t in parts:
            if r.startswith(ref + "-"):
                hit = _find(needle, t)
                if hit is not None:
                    return Located(r, True, hit)
        return Located(ref, True, found)
    for r, t in parts:
        hit = _find(needle, t)
        if hit is not None:
            return Located(r, True, hit)
    return Located(ref, False, None)


def locate_quote(
    quote: str,
    ref: str,
    text: str | None,
    siblings: list[tuple[str, str]] | None = None,
) -> tuple[str, bool]:
    """Thin wrapper over `locate` returning (ref, verified)."""
    loc = locate(quote, ref, text, siblings)
    return loc.ref, loc.verified
