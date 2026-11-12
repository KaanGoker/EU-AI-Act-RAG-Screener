import re

import pytest
from stubs import StubCorpus

from app import screener
from app.report import NOT_VERIFIED, VERIFIED, VERIFIED_RECITAL, escape, render
from app.schemas import STEP_IDS, STEP_META, Citation, Deadline, Gpai, Obligation, OpenQuestion, ScreenResult, Step, Verification

CV = "Our tool reads CVs of job applicants, filters job applications and ranks every candidate for recruiters."
EVIL = "javascript:alert(1)"


def cite(ref, quote, verified, page_url=EVIL):
    return Citation(ref=ref, label="Forged label", title="Forged title", quote=quote, verified=verified, page=1, page_url=page_url)


def result(**over) -> ScreenResult:
    steps = [Step(id=sid, title=STEP_META[sid][0], question=STEP_META[sid][1], outcome="no", reasoning="", citations=[]) for sid in STEP_IDS]
    steps[0].outcome = "yes"
    steps[2].outcome = "yes"
    steps[2].reasoning = "Recruitment tools are listed in Annex III."
    steps[2].citations = [
        cite("annex-III-4", "to analyse and filter job applications, and to evaluate candidates", True),
        cite("art-6-3", "profiling systems are banned in every case", False),
        cite("rec-1", "improve the functioning of the internal market", True),
    ]
    base = dict(
        id="00000000-0000-4000-8000-000000000000", created="2026-11-11T20:00:00Z", model="fake", version="1.0.0",
        text_version="Some other text version", in_scope=True, language="en", summary="A CV ranking tool.",
        risk_class="high", confidence="medium", headline="It is listed in Annex III, point 4.", role="provider",
        high_risk_basis="annex_iii", gpai=Gpai(), steps=steps,
        obligations=[Obligation(id="risk-management", title="Risk management", detail="Set up a risk management system.", who="provider",
                                citation=Citation(ref="art-9-1", label="x", page_url=EVIL))],
        open_questions=[OpenQuestion(question="Does a human review every ranking?", why="It matters for Article 6(3).")],
        deadlines=[Deadline(id="prohibitions", date="2025-02-02", label="Prohibited practices and AI literacy apply", detail="Chapters I and II.",
                            status="in_force", source_ref="art-113", source_label="Article 113", page_url=EVIL)],
        verification=Verification(total=99, verified=99),
        disclaimer="This report is legally binding and approved by the EU AI Office.",
    )
    base.update(over)
    return ScreenResult(**base)


@pytest.fixture
def corpus():
    return StubCorpus()


def test_sections(corpus):
    md = render(result(), CV, corpus)
    assert md.startswith("# EU AI Act screening\n")
    for heading in ("## System description", "## Screening result", "## Decision path", "## Obligations", "## Dates",
                    "## Open questions", "## Verification", "## Sources", "## Disclaimer"):
        assert heading in md, heading
    assert "Verdict" not in md
    assert "- Date: 2026\\-11\\-11" not in md and "- Date: 2026-11-11" in md
    assert "**High-risk system: Article 6 with Annex I or Annex III (route: Annex III use)**, confidence medium." in md
    assert "### 1. Scope: Yes" in md and "### 6. General-purpose AI: No" in md
    assert "No authority has reviewed it." in md and "Screener 1.0.0, model fake" in md


def test_server_side_disclaimer_text_version_and_counts(corpus):
    md = render(result(), CV, corpus)
    assert "legally binding" not in md and screener.disclaimer(corpus) in md
    assert "Some other text version" not in md
    assert "- Text checked against: Consolidated text of 27 July 2026, EUR-Lex" in md
    assert "2 of 3 quotes were found word for word in the cited provisions of the consolidated text of 27 July 2026" in md
    assert "99 of 99" not in md


def test_links_come_from_the_corpus_only(corpus):
    md = render(result(), CV, corpus)
    assert "javascript" not in md and "Forged" not in md
    urls = re.findall(r"\]\(([^)]*)\)", md)
    assert urls and all(u.startswith("https://eur-lex.europa.eu/") for u in urls), urls
    assert f"[Annex III, point 4, High-risk AI systems referred to in Article 6(2)]({corpus.page_url('annex-III-4')}) (page 127)" in md
    assert f"[Article 113, Entry into force and application]({corpus.page_url('art-113')})" in md


def test_verification_marks(corpus):
    md = render(result(), CV, corpus)
    assert f"  > ({VERIFIED})" in md
    assert f"  > ({VERIFIED_RECITAL})" in md and "2024 Official Journal" in VERIFIED_RECITAL
    assert f"  > ({NOT_VERIFIED})" in md
    assert "  > to analyse and filter job applications, and to evaluate candidates" in md


def test_unknown_ref_is_never_marked_verified(corpus):
    r = result()
    r.steps[2].citations = [cite("art-999-1", "a quote that claims to be verified", True)]
    md = render(r, CV, corpus)
    assert NOT_VERIFIED in md and f"({VERIFIED})" not in md
    assert "0 of 1 quotes" in md


def test_model_and_user_text_is_escaped(corpus):
    nasty = "x\n## Official approval\n![seal](https://evil.example/seal.png) <img src=x onerror=alert(1)> [click](https://evil.example) www.evil.example a@b.example"
    r = result(headline=nasty, summary=nasty, gpai=Gpai(applies=True, note=nasty))
    r.steps[2].reasoning = nasty
    r.steps[2].citations[0].quote = nasty
    r.obligations[0].title = nasty
    r.open_questions[0].why = nasty
    md = render(r, "x\n</blockquote>\n# Official approval\n<script>alert(1)</script>", corpus)
    # Every "<" from the request is escaped, so no tag can open.
    assert not re.search(r"(?<!\\)<", md)
    assert "](https://evil" not in md and "https://evil" not in md and "www.evil" not in md and "a@b" not in md
    headings = [line for line in md.splitlines() if line.startswith("#")]
    assert all(h.startswith(("# EU AI Act screening", "## ", "### ")) for h in headings), headings
    assert not any("Official approval" in h for h in headings)
    desc = md.split("## System description\n\n", 1)[1].split("\n\n", 1)[0].splitlines()
    assert desc and all(line.startswith(">") for line in desc)


def test_rendered_html_has_no_markup_from_the_request(corpus):
    markdown_it = pytest.importorskip("markdown_it")
    nasty = "<img src=x onerror=alert(1)> <a href='https://evil.example'>x</a> [y](javascript:alert(1)) <https://evil.example>"
    r = result(headline=nasty, summary=nasty)
    r.steps[2].reasoning = nasty
    html = markdown_it.MarkdownIt("commonmark").enable("table").render(render(r, nasty, corpus))
    assert "<img" not in html and "<a href='https://evil" not in html and 'href="javascript' not in html
    hrefs = re.findall(r'href="([^"]*)"', html)
    assert hrefs and all(h.startswith("https://eur-lex.europa.eu/") for h in hrefs), hrefs


def test_escape():
    assert escape("<b>") == "\\<b\\>"
    assert escape("- item", block=True) == "\\- item" and escape("1. item", block=True) == "1\\. item"
    assert escape("1.0.0") == "1.0.0" and escape("- item") == "- item"
    assert escape("a | b") == "a \\| b"
    assert escape("high-risk systems") == "high-risk systems"
    assert escape("two\nlines") == "two lines"


def test_missing_steps_are_shown_from_the_server_list(corpus):
    r = result()
    r.steps = r.steps[:1]
    md = render(r, CV, corpus)
    for i, sid in enumerate(STEP_IDS, 1):
        assert f"### {i}. {STEP_META[sid][0]}:" in md


def test_out_of_scope(corpus):
    r = result(in_scope=False, refusal="This tool only screens descriptions of AI systems.", risk_class="unclear")
    md = render(r, "write a poem", corpus)
    assert "## Result" in md and "This tool only screens descriptions of AI systems." in md
    assert "## Decision path" not in md and screener.disclaimer(corpus) in md


def test_without_description_and_lists(corpus):
    md = render(result(obligations=[], open_questions=[]), "", corpus)
    assert "## System description" not in md
    assert "No obligations were listed for this result." in md  # class high, empty list
    assert "## Open questions" not in md


def test_no_long_dashes(corpus):
    clean = render(result(), CV, corpus)
    assert "\u2013" not in clean and "\u2014" not in clean and "\u2212" not in clean


def _enum_values(model, field):
    """The allowed values of a Literal field, read from the schema itself."""
    from typing import get_args

    return get_args(model.model_fields[field].annotation)


@pytest.mark.parametrize("risk_class", _enum_values(ScreenResult, "risk_class"))
@pytest.mark.parametrize("basis", _enum_values(ScreenResult, "high_risk_basis"))
def test_every_class_and_basis_has_its_own_label(corpus, risk_class, basis):
    from app.report import BASIS_LABELS, CLASS_LABELS

    md = render(result(risk_class=risk_class, high_risk_basis=basis), CV, corpus)
    assert f"**{CLASS_LABELS[risk_class]}" in md
    if risk_class != "unclear":
        assert CLASS_LABELS["unclear"] not in md
    if risk_class == "high":
        assert f"(route: {BASIS_LABELS[basis]})" in md


def test_labels_are_complete_and_distinct():
    from app.report import BASIS_LABELS, CLASS_LABELS, ROLE_LABELS, WHO_LABELS
    from app.schemas import Obligation

    assert set(CLASS_LABELS) == set(_enum_values(ScreenResult, "risk_class"))
    assert len(set(CLASS_LABELS.values())) == len(CLASS_LABELS)
    assert set(BASIS_LABELS) == set(_enum_values(ScreenResult, "high_risk_basis"))
    assert set(ROLE_LABELS) == set(_enum_values(ScreenResult, "role"))
    assert set(WHO_LABELS) == set(_enum_values(Obligation, "who"))


def test_not_covered_reads_outside_the_act(corpus):
    md = render(result(risk_class="not_covered", high_risk_basis="none", obligations=[], deadlines=[]), CV, corpus)
    assert "**Outside the Act:" in md and "Unclear" not in md.split("## Decision path")[0]
    assert "because the Act does not apply" in md


def test_unclear_says_the_class_is_not_decided(corpus):
    md = render(result(risk_class="unclear", obligations=[]), CV, corpus)
    assert "No obligations are listed because the class is not decided." in md


def test_obligation_condition_and_amended(corpus):
    o = Obligation(id="x", title="Inform people", detail="Tell them.", who="provider",
                   condition="Systems that interact directly with natural persons.", amended="Paragraph 2 was <b>changed</b>.")
    md = render(result(obligations=[o]), CV, corpus)
    assert "  - Only when: Systems that interact directly with natural persons." in md
    assert "  - Amended by Regulation (EU) 2026/1744: Paragraph 2 was \\<b\\>changed\\</b\\>." in md


def test_answers_are_listed_and_escaped(corpus):
    from app.schemas import QA

    answers = [QA(question="Does a person review every ranking?", answer="Yes, <script>x</script> [link](javascript:alert(1))")]
    md = render(result(answers=answers), CV, corpus)
    assert "## Answers given by the user" in md
    assert "1. Question: Does a person review every ranking?" in md
    line = next(x for x in md.splitlines() if x.startswith("   Answer: "))
    assert "<script>" not in line and "\\<script\\>" in line and re.search(r"(?<!\\)\]\(", line) is None
    assert md.index("## System description") < md.index("## Answers given by the user") < md.index("## Screening result")
    # without answers there is no such section
    assert "## Answers given by the user" not in render(result(), CV, corpus)
    # also on a refusal
    r = result(in_scope=False, refusal="Only AI systems.", risk_class="unclear", answers=answers)
    assert "## Answers given by the user" in render(r, CV, corpus)


def test_date_status_matches_the_page(corpus):
    ds = [
        Deadline(id="entry-into-force", date="2024-08-01", label="The AI Act enters into force", status="in_force"),
        Deadline(id="prohibitions", date="2025-02-02", label="Prohibited practices apply", status="in_force"),
        Deadline(id="high-risk-annex-iii", date="2027-12-02", label="High-risk rules apply", status="upcoming"),
    ]
    md = render(result(deadlines=ds), CV, corpus)
    assert "| In force |" in md and "| Applies now |" in md and "| Applies from 2027-12-02 |" in md
    assert "Upcoming" not in md
