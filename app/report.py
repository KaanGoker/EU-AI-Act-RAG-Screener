"""Markdown report of a signed ScreenResult.

Every string written by the model or the user is escaped for Markdown and HTML. Links,
labels, titles, the verification marks and counts, the text version and the disclaimer are
rebuilt here from the corpus and the citation flags, never taken from the request.
"""

from __future__ import annotations

import re

from app.schemas import STEP_IDS, STEP_META, Citation, ScreenResult

# The same names as the page (app/static/js/dom.js, RISK), each with its note.
CLASS_LABELS = {
    "prohibited": "Prohibited practice: banned under Article 5",
    "high": "High-risk system: Article 6 with Annex I or Annex III",
    "limited": "Limited risk: transparency duties under Article 50 only",
    "minimal": "Minimal risk: no specific duties beyond AI literacy",
    "not_covered": "Outside the Act: the Act does not apply as described (Article 2 or Article 3(1)); other law can still apply",
    "unclear": "Unclear: not enough to decide",
}
# The high-risk route, as the page names it (app/static/js/result.js, BASIS).
BASIS_LABELS = {
    "annex_iii": "Annex III use",
    "annex_i": "Annex I product (Section A)",
    "annex_i_section_b": "Annex I product (Section B)",
    "both": "Annex I and Annex III",
    "none": "route not named",
}
NO_OBLIGATIONS = {
    "unclear": "No obligations are listed because the class is not decided.",
    "not_covered": "No obligations are listed because the Act does not apply to the system as described.",
}
OUTCOME_LABELS = {"yes": "Yes", "no": "No", "unclear": "Unclear", "not_applicable": "Not reached"}
ROLE_LABELS = {"provider": "Provider", "deployer": "Deployer", "unknown": "Not sure"}
WHO_LABELS = {"provider": "Provider", "deployer": "Deployer", "both": "Provider and deployer"}
CONFIDENCE_LABELS = {"low": "low", "medium": "medium", "high": "high"}

VERIFIED = "found word for word in the cited text"
VERIFIED_RECITAL = "found word for word in the cited text of the 2024 Official Journal version"
NOT_VERIFIED = "NOT verified: not found word for word in the cited text"

# Characters with a meaning in Markdown or HTML. CommonMark turns a backslash before any
# ASCII punctuation into the plain character, so "\<" shows "<" and never opens a tag.
_MD_SPECIAL = re.compile(r"([\\`*_{}\[\]<>#|~&@])")
# Bare URLs that GitHub-flavored Markdown would turn into links.
_URLISH = re.compile(r"(?i)\b(https?|ftp|mailto|javascript|data|file|www)(?=[:.])")


def escape(text: str | None, block: bool = False) -> str:
    """One line of model or user text, safe inline. With `block`, it is also safe at the start
    of a line or of a quote line."""
    line = " ".join((text or "").split())
    line = _MD_SPECIAL.sub(r"\\\1", line)
    line = _URLISH.sub(lambda m: m.group(0) + "\\", line)
    if not block:
        return line
    # A line that starts with "-", "+", "=" or "1." would become a list item or a heading line.
    line = re.sub(r"^([-+=])", r"\\\1", line)
    return re.sub(r"^(\d+)([.)])", r"\1\\\2", line)


def _quote_block(text: str) -> list[str]:
    lines = [escape(line, block=True) for line in text.splitlines()]
    return ["> " + line if line else ">" for line in lines]


def _is_recital(corpus, ref: str) -> bool:
    unit = corpus.unit_of(ref) if ref else None
    return unit is not None and unit.kind == "recital"


def _link(corpus, ref: str | None) -> str:
    """Label, title and page link of a ref, from the corpus only."""
    if not ref or corpus.get(ref) is None:
        return escape(ref or "unknown reference")
    label = corpus.label(ref)
    title = corpus.title(ref)
    text = escape(label + (f", {title}" if title else ""))
    page = corpus.page(ref)
    return f"[{text}]({corpus.page_url(ref)}) (page {page})"


def _citation_lines(corpus, c: Citation) -> list[str]:
    lines = [f"- {_link(corpus, c.ref)}"]
    if c.quote:
        if c.verified is True and corpus.get(c.ref) is not None:
            mark = VERIFIED_RECITAL if _is_recital(corpus, c.ref) else VERIFIED
        else:
            mark = NOT_VERIFIED
        lines.append(f"  > {escape(c.quote, block=True)}")
        lines.append(f"  > ({mark})")
    return lines


def _counts(result: ScreenResult, corpus) -> tuple[int, int]:
    cites = [c for s in result.steps for c in s.citations if c.quote]
    verified = [c for c in cites if c.verified is True and corpus.get(c.ref) is not None]
    return len(verified), len(cites)


_ENTRY_INTO_FORCE = re.compile(r"in-force|entry-into-force")
_ENTERS_INTO_FORCE = re.compile(r"enters? into force", re.IGNORECASE)


def date_status(d) -> str:
    """The page's wording: entry into force is "In force", every other date is about application."""
    if _ENTRY_INTO_FORCE.search(d.id or "") or _ENTERS_INTO_FORCE.search(d.label or ""):
        return "In force" if d.status == "in_force" else f"In force from {escape(d.date)}"
    return "Applies now" if d.status == "in_force" else f"Applies from {escape(d.date)}"


def class_line(r: ScreenResult) -> str:
    label = CLASS_LABELS[r.risk_class]
    if r.risk_class == "high":
        label += f" (route: {BASIS_LABELS[r.high_risk_basis]})"
    return f"**{label}**, confidence {CONFIDENCE_LABELS[r.confidence]}."


def render(result: ScreenResult, description: str, corpus) -> str:
    from app import screener

    r = result
    version = screener.text_version(corpus)
    out: list[str] = ["# EU AI Act screening", ""]
    out.append(f"- Date: {escape(r.created[:10])} (UTC)")
    out.append("- Regulation: Regulation (EU) 2024/1689 (Artificial Intelligence Act)")
    out.append(f"- Text checked against: {escape(version)}, EUR-Lex")
    out.append(f"- Tool: EU AI Act Screener {escape(r.version)}, model {escape(r.model)}")
    out.append(f"- Role: {ROLE_LABELS[r.role]}")
    out.append("- This report was produced by the EU AI Act Screener from a result of the same server. No authority has reviewed it.")
    out.append("")
    if description.strip():
        out += ["## System description", "", *_quote_block(description.strip()), ""]
    if r.answers:
        out += ["## Answers given by the user", ""]
        for i, qa in enumerate(r.answers, 1):
            out += [f"{i}. Question: {escape(qa.question)}", f"   Answer: {escape(qa.answer)}"]
        out.append("")

    disclaimer = ["## Disclaimer", "", screener.disclaimer(corpus), ""]
    if not r.in_scope:
        out += ["## Result", "", escape(r.refusal, block=True) or "The text was not screened.", "", *disclaimer]
        return "\n".join(out)

    out += ["## Screening result", ""]
    out.append(class_line(r))
    out.append("")
    if r.headline:
        out += [escape(r.headline, block=True), ""]
    if r.summary:
        out += [f"System as understood: {escape(r.summary)}", ""]
    if r.gpai.applies:
        note = f" {escape(r.gpai.note)}" if r.gpai.note else ""
        out += ["General-purpose AI model: Chapter V obligations apply to the model provider." + note, ""]

    out += ["## Decision path", ""]
    steps = {s.id: s for s in r.steps}
    for i, sid in enumerate(STEP_IDS, 1):
        title, question = STEP_META[sid]
        s = steps.get(sid)
        outcome = OUTCOME_LABELS.get(s.outcome, "Unclear") if s else "Unclear"
        out += [f"### {i}. {title}: {outcome}", "", f"*{question}*", ""]
        if s is None:
            continue
        if s.reasoning:
            out += [escape(s.reasoning, block=True), ""]
        for c in s.citations:
            out += _citation_lines(corpus, c)
        if s.citations:
            out.append("")

    out += ["## Obligations", ""]
    if r.obligations:
        for o in r.obligations:
            ref = f" ({_link(corpus, o.citation.ref)})" if o.citation else ""
            out.append(f"- **{escape(o.title)}** \\[{WHO_LABELS[o.who]}\\]{ref}: {escape(o.detail)}")
            if o.condition:
                out.append(f"  - Only when: {escape(o.condition)}")
            if o.amended:
                out.append(f"  - Amended by Regulation (EU) 2026/1744: {escape(o.amended)}")
    else:
        out.append(NO_OBLIGATIONS.get(r.risk_class, "No obligations were listed for this result."))
    out.append("")

    out += ["## Dates", ""]
    if r.deadlines:
        out += ["| Date | What applies | Status | Source |", "| --- | --- | --- | --- |"]
        for d in r.deadlines:
            status = date_status(d)
            what = escape(d.label + (f". {d.detail}" if d.detail else ""))
            src = _link(corpus, d.source_ref) if d.source_ref else ""
            out.append(f"| {escape(d.date)} | {what} | {status} | {src} |")
    else:
        out.append("No dates were attached.")
    out.append("")

    if r.open_questions:
        out += ["## Open questions", ""]
        for q in r.open_questions:
            out.append(f"- {escape(q.question, block=True)}" + (f" ({escape(q.why)})" if q.why else ""))
        out.append("")

    verified, total = _counts(r, corpus)
    prefix = "Consolidated text of "
    where = f"the consolidated text of {version[len(prefix):]}" if version.startswith(prefix) else "the text of the Act"
    out += ["## Verification", ""]
    out.append(
        f"{verified} of {total} quotes were found word for word in the cited provisions of {where} "
        "(recitals: the 2024 Official Journal version). A found quote shows that these words are in the cited "
        "text; it does not show that the conclusion drawn from them is right."
    )
    out.append("")

    refs = []
    for s in r.steps:
        for c in s.citations:
            if c.ref not in refs and corpus.get(c.ref) is not None:
                refs.append(c.ref)
    for o in r.obligations:
        if o.citation and o.citation.ref not in refs and corpus.get(o.citation.ref) is not None:
            refs.append(o.citation.ref)
    if refs:
        out += ["## Sources", ""]
        out += [f"- {_link(corpus, ref)}" for ref in refs]
        out.append("")

    out += disclaimer
    return "\n".join(out)
