import json
import re

import pytest

from app.corpus import CORPUS_PATH, Part, Unit, get_corpus


@pytest.fixture(scope="module")
def corpus():
    return get_corpus()


def test_counts(corpus):
    kinds = [u.kind for u in corpus.units.values()]
    assert kinds.count("recital") == 180
    # consolidated version of 27 July 2026: Articles 4a, 60a, 75a to 75d and Annex XIV are new
    assert kinds.count("article") == 119
    assert kinds.count("annex") == 14
    assert len(corpus.units) == 313
    assert sum(len(u.parts) for u in corpus.units.values()) == 699
    toc = corpus.toc()
    assert len(toc["chapters"]) == 13
    assert sum(len(c["articles"]) for c in toc["chapters"]) == 119
    assert len(toc["annexes"]) == 14
    assert toc["recitals"] == {"count": 180}


def test_order_and_numbering(corpus):
    ids = list(corpus.units)
    assert ids[0] == "rec-1" and ids[179] == "rec-180"
    assert ids[180] == "art-1" and ids[298] == "art-113"
    assert ids[299] == "annex-I" and ids[-1] == "annex-XIV"
    for n in range(1, 114):
        assert corpus.units[f"art-{n}"].number == str(n)
    new = ["art-4a", "art-60a", "art-75a", "art-75b", "art-75c", "art-75d"]
    assert [i for i in ids if i.startswith("art-") and not i.split("-")[1].isdigit()] == new
    assert ids.index("art-4a") == ids.index("art-4") + 1
    assert ids.index("art-75d") == ids.index("art-76") - 1


def test_json_shape():
    data = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    src = data["source"]
    assert src["celex"] == "02024R1689-20260727"
    assert src["pdf_url"].endswith("CELEX:02024R1689-20260727")
    assert "documentation tool and has no legal effect" in src["legal_notice"]
    assert src["includes"][0]["celex"] == "32026R1744"
    assert src["recitals"]["pdf_url"].endswith("OJ:L_202401689")
    keys = {"id", "kind", "number", "title", "chapter", "chapter_title", "section", "section_title",
            "page_start", "page_end", "pdf_url", "amended", "text", "parts"}
    for u in data["units"]:
        assert set(u) == keys
        if u["kind"] != "article":
            assert u["chapter"] is None and u["section"] is None
        if u["kind"] == "recital":
            assert u["parts"] == []
            assert u["pdf_url"] == src["recitals"]["pdf_url"] and u["amended"] is False
        else:
            assert u["pdf_url"] == src["pdf_url"]
        for p in u["parts"]:
            assert set(p) == {"id", "label", "text", "page", "amended"}
            assert u["page_start"] <= p["page"] <= u["page_end"]


def test_clean_text(corpus):
    for u in corpus.units.values():
        assert not re.search(r"\b\d{1,3}/144\b", u.text), u.id
        assert "OJ L, 12.7.2024\n" not in u.text
        assert not any(ch in u.text for ch in "\u2014\u2013\u2212\u00ad\u25bc\u25ba\u25c4"), u.id
        assert "___" not in u.text and "02024R1689" not in u.text, u.id
        assert "  " not in u.text, u.id
        assert u.text == u.text.strip()


def test_get_and_parts(corpus):
    art6 = corpus.get("art-6")
    assert isinstance(art6, Unit)
    assert art6.title == "Classification rules for high-risk AI systems"
    assert art6.chapter == "III" and art6.chapter_title == "High-risk AI systems"
    assert art6.section == "1" and art6.section_title == "Classification of AI systems as high-risk"
    assert [p.id for p in art6.parts] == ["art-6-1", "art-6-1a", "art-6-1b", "art-6-1c"] + [f"art-6-{n}" for n in range(2, 9)]
    p = corpus.get("art-6-3")
    assert isinstance(p, Part) and p.unit_id == "art-6" and p.page == 18 and not p.amended
    assert p.text.startswith("By derogation from paragraph 2, an AI system referred to in Annex III")
    assert "(a) the AI system is intended to perform a narrow procedural task;" in p.text.split("\n")
    assert p.text.endswith("where the AI system performs profiling of natural persons.")
    assert corpus.get("ANNEX-iii-4").id == "annex-III-4"
    assert corpus.get("annex-iii").id == "annex-III"
    assert corpus.get("art-999") is None
    assert corpus.unit_of("art-6-3").id == "art-6"
    assert corpus.unit_of("annex-III-4").id == "annex-III"


def test_definitions(corpus):
    art3 = corpus.units["art-3"]
    # 68 definitions plus (14a) SME and (14b) SMC from Regulation (EU) 2026/1744
    assert len(art3.parts) == 70
    labels = [p.label for p in art3.parts]
    assert labels[:17] == ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "14a", "14b", "15"]
    assert labels[-1] == "68"
    assert corpus.text_of("art-3-1").startswith("‘AI system’ means a machine-based system")
    assert corpus.text_of("art-3-68").startswith("‘downstream provider’ means")
    assert corpus.text_of("art-3-60").startswith("‘deep fake’ means")
    assert corpus.text_of("art-3-14").endswith("intended purpose is to prevent or mitigate risks to health and safety of persons or property;")
    assert corpus.text_of("art-3-14b").startswith("‘small mid-cap enterprise’ or ‘SMC’ means")
    assert corpus.amended("art-3-14a") and not corpus.amended("art-3-13")
    assert art3.page_start == 5 and art3.page_end == 11


def test_known_text(corpus):
    assert "(f) the placing on the market, the putting into service for this specific purpose, or the use of AI systems to infer emotions of a natural person in the areas of workplace and education institutions" in corpus.text_of("art-5")
    assert "informed that they are interacting with an AI system" in corpus.text_of("art-50-1")
    assert corpus.text_of("art-51-2").endswith("measured in floating point operations is greater than 10^25.")
    art113 = corpus.text_of("art-113")
    assert art113.startswith("This Regulation shall enter into force on the twentieth day")
    assert "(i) 2 December 2027 as regards AI systems classified as high-risk pursuant to Article 6(2) and Annex III; and" in art113.split("\n")
    assert "(ii) 2 August 2028 as regards AI systems classified as high-risk pursuant to Article 6(1) and Annex I;" in art113.split("\n")
    assert art113.endswith("(d) Articles 102 to 110 shall apply from 27 July 2026.")
    assert "binding in its entirety" not in art113
    assert "2 August 2027" not in art113
    assert corpus.text_of("rec-1").startswith("The purpose of this Regulation is to improve the functioning of the internal market")
    assert corpus.text_of("rec-180").endswith("delivered their joint opinion on 18 June 2021,")
    # footnote text and markers are gone
    assert "Regulation (EC) No 765/2008 of the European Parliament and of the Council, Decision No 768/2008/EC" in corpus.text_of("rec-9")
    assert "OJ C 517" not in corpus.text_of("rec-1")
    assert "Commission Decision of 24 January 2024;" in corpus.text_of("art-3-47")
    # words split by a soft hyphen at a line end are joined
    assert "trustworthy artificial intelligence" in corpus.text_of("art-1-1")
    assert "harmonisation legislation" in corpus.text_of("art-2-2")
    # a quoted "(*)" note inside an amending article stays; a real footnote does not
    assert "(*) Regulation (EU) 2024/1689 of the European Parliament" in corpus.text_of("art-103")
    assert "Regulation (EU) No 1025/2012 of the European Parliament and of the (ii)" not in corpus.text_of("art-41")


def test_annexes(corpus):
    a3 = corpus.units["annex-III"]
    assert a3.title == "High-risk AI systems referred to in Article 6(2)"
    assert [p.id for p in a3.parts] == [f"annex-III-{n}" for n in range(1, 9)]
    assert corpus.text_of("annex-III-4").startswith("Employment, workers’ management and access to self-employment:")
    assert "to analyse and filter job applications, and to evaluate candidates;" in corpus.text_of("annex-III-4")
    assert corpus.text_of("annex-III-8").startswith("Administration of justice and democratic processes:")
    assert (a3.page_start, a3.page_end) == (131, 133)
    assert not a3.amended
    a1 = corpus.units["annex-I"]
    # point 1 (Machinery Directive) deleted, point 21 (Regulation (EU) 2023/1230) added
    assert [p.label for p in a1.parts] == [str(n) for n in range(2, 22)]
    assert a1.amended and corpus.amended("annex-I-21") and not corpus.amended("annex-I-2")
    assert "2006/42/EC of the European Parliament and of the Council of 17 May 2006" not in a1.text
    assert corpus.text_of("annex-I-21").startswith("Regulation (EU) 2023/1230 of the European Parliament and of the Council of 14 June 2023 on machinery")
    assert "Section B. List of other Union harmonisation legislation" in a1.text
    assert "Section B" not in corpus.text_of("annex-I-12")
    assert corpus.text_of("annex-I-11").startswith("Regulation (EU) 2017/745")
    assert corpus.text_of("annex-I-13").startswith("Regulation (EC) No 300/2008")
    assert [p.id for p in corpus.units["annex-VIII"].parts] == ["annex-VIII-A", "annex-VIII-B", "annex-VIII-C"]
    # Section B, points 7 and 9 deleted
    b = corpus.text_of("annex-VIII-B")
    assert "\n6. " in b and "\n7. " not in b and "\n8. " in b and "\n9. " not in b
    a14 = corpus.units["annex-XIV"]
    assert a14.title.startswith("The list of codes, categories and corresponding types of AI systems")
    assert [p.id for p in a14.parts] == [f"annex-XIV-{n}" for n in range(1, 5)]
    assert "AIP 0102 AI systems subject to point 2 of Section A of Annex I" in a14.text
    assert "- terrorism," in corpus.text_of("annex-II").split("\n")
    assert corpus.units["annex-XIII"].title.startswith("Criteria for the designation of general-purpose AI models")


def test_titles(corpus):
    assert corpus.title("art-1") == "Subject matter"
    assert corpus.title("art-50") == "Transparency obligations for providers and deployers of certain AI systems"
    assert corpus.title("art-59").endswith("in the AI regulatory sandbox")
    assert corpus.title("art-113") == "Entry into force and application"
    assert corpus.title("art-4a") == "Processing of special categories of personal data for bias detection and correction"
    assert corpus.title("art-75") == "Market surveillance and control of AI systems and mutual assistance"
    assert corpus.title("art-75a") == "Supervisory and enforcement powers of the AI Office"
    for u in corpus.units.values():
        if u.kind != "recital":
            assert u.title, u.id
        else:
            assert u.title is None


def test_labels(corpus):
    assert corpus.label("art-6") == "Article 6"
    assert corpus.label("art-6-3") == "Article 6(3)"
    assert corpus.label("annex-III") == "Annex III"
    assert corpus.label("annex-III-4") == "Annex III, point 4"
    assert corpus.label("annex-VIII-A") == "Annex VIII, Section A"
    assert corpus.label("rec-53") == "Recital 53"
    assert corpus.label("art-3-1") == "Article 3(1)"
    assert corpus.label("art-6-1a") == "Article 6(1a)"
    assert corpus.label("art-4a") == "Article 4a"
    assert corpus.label("art-4a-2") == "Article 4a(2)"
    assert corpus.label("art-3-14a") == "Article 3(14a)"
    assert corpus.label("annex-XIV-2") == "Annex XIV, point 2"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Article 6(3)", "art-6-3"),
        ("Art. 6 (3)", "art-6-3"),
        ("article 6, paragraph 3", "art-6-3"),
        ("Article 5(1)(f)", "art-5-1"),
        ("Article 3(1)", "art-3-1"),
        ("Article 3, point (60)", "art-3-60"),
        ("Article 4(1)", "art-4-1"),
        ("Article 113(1)", "art-113"),
        ("Article 10(5)", "art-10"),
        ("Article 6(1a)", "art-6-1a"),
        ("Art. 6 (1b)", "art-6-1b"),
        ("Article 6, paragraph 1c", "art-6-1c"),
        ("Article 5(1)(ba)", "art-5-1"),
        ("Article 5(1a)", "art-5-1a"),
        ("Article 4a", "art-4a"),
        ("Article 4a(2)", "art-4a-2"),
        ("article 75c", "art-75c"),
        ("art-75C-3", "art-75c-3"),
        ("Article 3(14a)", "art-3-14a"),
        ("Annex XIV", "annex-XIV"),
        ("Annex XIV, point 3", "annex-XIV-3"),
        ("Annex I, point 21", "annex-I-21"),
        ("Annex I, point 1", "annex-I"),
        ("Article 50", "art-50"),
        ("art-6-3", "art-6-3"),
        ("ART-6", "art-6"),
        ("Annex III point 4", "annex-III-4"),
        ("annex iii point 4", "annex-III-4"),
        ("Annex III(4)", "annex-III-4"),
        ("Annex III, point 4(a)", "annex-III-4"),
        ("annex-iii-4", "annex-III-4"),
        ("Annex I", "annex-I"),
        ("Annex XIII", "annex-XIII"),
        ("Annex VIII, Section B", "annex-VIII-B"),
        ("recital 53", "rec-53"),
        ("Recital (180)", "rec-180"),
        ("rec-1", "rec-1"),
        ("see Article 6(2) and Annex III", "art-6-2"),
        ("Article 114", None),
        ("Annex XV", None),
        ("recital 181", None),
        ("nothing here", None),
        ("", None),
    ],
)
def test_normalize_ref(corpus, text, expected):
    assert corpus.normalize_ref(text) == expected


def test_pages_and_neighbors(corpus):
    assert corpus.page("art-6") == 17
    assert corpus.page("art-6-3") == 18
    assert corpus.page("art-50") == 59
    assert corpus.page("art-113") == 127
    assert corpus.page("annex-III-4") == 131
    assert corpus.page("rec-1") == 1
    assert corpus.page_url("art-6-3").endswith("?uri=CELEX:02024R1689-20260727#page=18")
    # recitals point into the original Official Journal PDF
    assert corpus.page_url("rec-1").endswith("?uri=OJ:L_202401689#page=1")
    assert corpus.neighbors("art-1") == (None, "art-2")
    assert corpus.neighbors("art-6-3") == ("art-5", "art-7")
    assert corpus.neighbors("art-4") == ("art-3", "art-4a")
    assert corpus.neighbors("art-75d") == ("art-75c", "art-76")
    assert corpus.neighbors("annex-XIII") == ("annex-XII", "annex-XIV")
    assert corpus.neighbors("rec-180") == ("rec-179", None)


def test_amended_by_2026_1744(corpus):
    amended = {uid for uid, u in corpus.units.items() if u.amended}
    for uid in ["art-4", "art-4a", "art-5", "art-6", "art-10", "art-11", "art-17", "art-27", "art-43", "art-50",
                "art-72", "art-111", "art-113", "annex-I", "annex-XIV"]:
        assert uid in amended, uid
    for uid in ["art-7", "art-9", "art-14", "art-26", "art-51", "art-53", "art-55", "annex-III", "rec-1"]:
        assert uid not in amended, uid
    assert corpus.text_of("art-4-1").endswith("This obligation does not require providers or deployers to guarantee any specific level of AI literacy of any individual.")
    a5 = corpus.text_of("art-5-1").split("\n")
    i = a5.index(next(x for x in a5 if x.startswith("(ba) ")))
    assert a5[i - 1].startswith("(b) ") and a5[i + 1].startswith("(bb) ") and a5[i + 2].startswith("(c) ")
    assert "intimate parts" in a5[i] and "Directive 2011/93/EU" in a5[i + 1]
    assert corpus.amended("art-5-1") and not corpus.amended("art-5-2")
    assert corpus.text_of("art-6-1a").startswith("For the purposes of this Regulation, including paragraph 1 of this Article, AI systems that are solely used for non-safety related aspects")
    assert corpus.text_of("art-6-1b") == "Notwithstanding paragraph 1a, AI systems the failure or malfunctioning of which would endanger health and safety shall qualify as safety components."
    assert "electromagnetic interference" in corpus.text_of("art-6-1c")
    assert "Article 50(2) by 2 December 2026." in corpus.text_of("art-111-4")
    assert "techniques involving the training of AI models with data" in corpus.text_of("art-10-1")
    assert [p.label for p in corpus.units["art-10"].parts] == ["1", "2", "3", "4", "6"]
