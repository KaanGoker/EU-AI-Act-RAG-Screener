import statistics
import time

import pytest

from app.corpus import get_corpus
from app.retrieval import MAX_CHARS, Hit, build_chunks, get_retriever, split_text, tokenize


@pytest.fixture(scope="module")
def retriever():
    r = get_retriever()
    assert r.ready(), r.error
    r.search("warm up")
    return r


def refs(hits):
    return [h.ref for h in hits]


def units(hits):
    return [h.unit_id for h in hits]


def test_chunks_cover_every_unit():
    corpus = get_corpus()
    chunks = build_chunks(corpus)
    ids = [c.id for c in chunks]
    assert len(ids) == len(set(ids))
    assert {c.unit_id for c in chunks} == set(corpus.units)
    parts = {p.id for u in corpus.units.values() for p in u.parts}
    assert parts <= {c.ref for c in chunks}
    # every chunk is cut from the text of its ref, word for word
    for c in chunks:
        assert c.text in corpus.text_of(c.ref), c.id
    # the Annex III intro line is its own chunk
    assert any(c.ref == "annex-III" and c.text.startswith("High-risk AI systems pursuant to Article 6(2)") for c in chunks)


def test_split_text():
    text = "First sentence here. " * 80
    pieces = split_text(text.strip(), 300)
    assert all(len(p) <= 300 for p in pieces)
    assert " ".join(p.replace("\n", " ") for p in pieces) == text.strip()
    assert split_text("short", MAX_CHARS) == ["short"]


def test_tokenize():
    assert "recruit" in tokenize("Recruitment of natural persons")
    assert "the" not in tokenize("the system")


def test_hit_shape(retriever):
    hits = retriever.search("emotion recognition at the workplace", k=5)
    assert 0 < len(hits) <= 5
    h = hits[0]
    assert isinstance(h, Hit)
    corpus = get_corpus()
    assert h.label == corpus.label(h.ref)
    assert h.title == corpus.title(h.ref)
    assert h.text in corpus.text_of(h.ref)
    assert len(set(refs(hits))) == len(hits)
    assert [x.score for x in hits] == sorted((x.score for x in hits), reverse=True)


@pytest.mark.parametrize(
    "query,expected",
    [
        ("CV screening tool that ranks job applicants and filters applications", "annex-III-4"),
        ("Software that recognises the emotions of employees at the workplace", "art-5"),
        ("A customer service chatbot that talks to consumers on our website", "art-50"),
        ("Credit scoring model that decides whether a consumer gets a loan", "annex-III-5"),
        ("Real-time facial recognition of people in public spaces by the police", "art-5"),
        ("Een tool die cv's van sollicitanten automatisch screent en rangschikt", "annex-III-4"),
        ("Chatbot voor klantenservice op onze website", "art-50"),
        ("Système de reconnaissance faciale en temps réel dans l'espace public par la police", "art-5"),
        ("KI-System zur Bewertung der Kreditwürdigkeit von Verbrauchern", "annex-III-5"),
    ],
)
def test_search_expectations(retriever, query, expected):
    hits = retriever.search(query, k=8, kinds=("article", "annex"))
    assert expected in refs(hits) or expected in units(hits), refs(hits)


def test_kinds_filter(retriever):
    hits = retriever.search("high-risk AI systems in employment", k=10, kinds=("recital",))
    assert hits and all(h.kind == "recital" for h in hits)
    hits = retriever.search("high-risk AI systems in employment", k=10, kinds=("article", "annex"))
    assert hits and all(h.kind in ("article", "annex") for h in hits)
    hits = retriever.keyword_search("deep fake", k=10, kinds=("article",))
    assert hits and all(h.kind == "article" for h in hits)


def test_keyword_search(retriever):
    hits = retriever.keyword_search("deep fake", k=20)
    assert "art-3-60" in refs(hits)
    assert "art-50-4" in refs(hits)
    assert retriever.keyword_search("", k=5) == []
    assert retriever.keyword_search("the of and", k=5) == []
    # keyword mode: below the word share floor there are no hits
    assert retriever.keyword_search("xyzzyqwertyfoo", k=5) == []


def test_empty_query(retriever):
    assert retriever.search("   ") == []


NONSENSE = [
    "xyzzyqwertyfoo", "asdfghjkl", "lorem ipsum dolor sit amet", "banana",
    "Recipe for chocolate chip cookies with brown butter", "Who won the Champions League final in 2023?",
    "football match results Anderlecht Club Brugge", "def fibonacci(n): return n if n < 2 else fibonacci(n-1)",
    "Recette de la tarte tatin aux pommes", "En iyi kahvaltı mekanları İstanbul",
]


@pytest.mark.parametrize("query", NONSENSE)
def test_nonsense_finds_nothing(retriever, query):
    assert retriever.search(query, k=20) == []
    assert retriever.keyword_search(query, k=20) == []


@pytest.mark.parametrize("query", ["toys", "military", "Article 5", "Annex I", "deployer", "kredietwaardigheid van natuurlijke personen"])
def test_short_queries_still_find(retriever, query):
    assert retriever.search(query, k=20)


def test_every_eval_query_passes_the_floor(retriever):
    from eval.retrieval_eval import QUERIES

    assert all(retriever.search(q, k=8) for q, _, _ in QUERIES)


def test_search_speed(retriever):
    queries = [
        "AI system that screens CVs of job applicants",
        "chatbot voor klantenservice",
        "reconnaissance des émotions au travail",
        "general-purpose AI model with systemic risk",
        "yüz tanıma sistemi",
    ] * 4
    times = []
    for q in queries:
        t = time.perf_counter()
        retriever.search(q, k=8)
        times.append(time.perf_counter() - t)
    assert statistics.median(times) < 0.3, times
