import random
import re
import time

import pytest
from conftest import REAL_CORPUS

from app.verify import (
    MIN_QUOTE_CHARS,
    MIN_QUOTE_WORDS,
    Located,
    find_quote,
    locate,
    locate_quote,
    normalize,
    split_quote,
)

ART_50_1 = (
    "Providers shall ensure that AI systems intended to interact directly with natural persons are designed and "
    "developed in such a way that the natural persons concerned are informed that they are interacting with an AI "
    "system, unless this is obvious from the point of view of a natural person who is reasonably well-informed."
)
ART_3_1 = (
    "‘AI system’ means a machine-based system that is designed to operate with varying levels of autonomy "
    "and that may exhibit adaptiveness after deployment"
)


# Normalization: only the listed foldings.


def test_normalize_whitespace_case_quotes():
    assert normalize("  The\nAI   System  ") == "the ai system"
    assert normalize("‘AI system’") == normalize("'AI system'") == normalize('"AI system"') == "ai system"
    assert normalize("person’s") == normalize("person's") == "person's"


def test_normalize_keeps_apostrophe_inside_a_word():
    assert normalize("Member State's authority") != normalize("Member States authority")


def test_normalize_soft_hyphen_and_line_break_hyphenation():
    assert normalize("classi\u00adfication") == "classification"
    assert normalize("classifi-\ncation") == "classification"
    assert normalize("general- purpose") == normalize("general -purpose") == "general-purpose"
    assert normalize("high\u2013risk") == normalize("high\u2014risk") == normalize("high\u2212risk") == "high-risk"
    assert normalize("obligations ;") == "obligations;"
    assert normalize("( a )") == "(a)"


def test_normalize_keeps_digits_and_letters():
    assert normalize("Article 6(2)") != normalize("Article 6(3)")
    assert normalize("Annex III") != normalize("Annex II")
    assert normalize("10^25") != normalize("10^26")


# Exact matching


def test_exact_match():
    assert find_quote("interact directly with natural persons", ART_50_1)


def test_exact_after_normalization():
    assert find_quote("“Providers  SHALL ensure that AI systems\nintended to interact”", ART_50_1)


def test_quote_marks_around_a_term_may_be_left_out():
    assert find_quote("AI system means a machine-based system", ART_3_1)
    assert find_quote("'AI system' means a machine-based system", ART_3_1)


def test_dashes_both_ways():
    plain = "the AI system is a safety component of a product - or is itself a product - covered by Annex I"
    for text in (plain.replace(" - ", " \u2014 "), plain.replace(" - ", " \u2013 "), plain):
        assert find_quote(plain[4:], text), text
        assert find_quote(text[4:], plain), text


def test_trailing_punctuation_of_the_quote_is_ignored():
    assert find_quote("unless this is obvious from the point of view of a natural person.", ART_50_1)


def test_one_changed_letter_fails():
    assert not find_quote("AI systems intended to interact directly with natural persons are designed and developped", ART_50_1)
    assert not find_quote("may exhibit adaptiveness after deployment and machinebased", "may exhibit adaptiveness after deployment and machine-based")


def test_replaced_short_word_fails():
    assert not find_quote("designed or developed in such a way that the natural persons", ART_50_1)
    assert not find_quote("interacting with the AI system, unless this is obvious", ART_50_1)


def test_inserted_negation_fails():
    assert not find_quote("AI systems intended to interact directly with natural persons are not designed", ART_50_1)


def test_paraphrase_fails():
    assert not find_quote("Chatbots must tell people that they are talking to a machine", ART_50_1)


def test_match_must_end_on_a_word_boundary():
    text = "the obligation laid down in Article 49 applies to providers of such systems"
    assert not find_quote("the obligation laid down in Article 4", text)
    assert not find_quote("he obligation laid down in Article 49", text)
    assert find_quote("the obligation laid down in Article 49", text)
    assert not find_quote("systems referred to in Annex I", "systems referred to in Annex III shall be considered")


def test_homoglyph_fails():
    assert not find_quote("interact directly with nаtural persons", ART_50_1)


# Length floor


def test_floor_is_20_characters_and_4_words():
    assert MIN_QUOTE_CHARS == 20 and MIN_QUOTE_WORDS == 4
    assert not find_quote("natural persons are", ART_50_1)  # 19 characters
    assert not find_quote("interacting directly", "interacting directly with")  # 2 words
    assert not find_quote("reasonably well-informed", ART_50_1)  # 24 characters, 2 words
    assert find_quote("persons are designed and", ART_50_1)


def test_empty_inputs():
    assert not find_quote("", ART_50_1)
    assert not find_quote("interact directly with natural persons", "")
    assert not find_quote("interact directly with natural persons", None)


# Ellipsis: split, never stitched


def test_split_quote():
    assert split_quote("informed that they are interacting with an AI system...") == ["informed that they are interacting with an AI system"]
    assert split_quote("… informed that they are … interacting with an AI system …") == ["informed that they are", "interacting with an AI system"]
    assert split_quote("Providers shall ensure [...] natural persons are designed") == ["Providers shall ensure", "natural persons are designed"]
    assert split_quote("Providers shall ensure […] natural persons") == ["Providers shall ensure", "natural persons"]
    assert split_quote("Providers shall ensure (...) natural persons") == ["Providers shall ensure", "natural persons"]
    assert split_quote("shall ... not ... be prohibited") == ["shall", "not", "be prohibited"]
    assert split_quote("...") == []
    assert split_quote("") == []


def test_leading_and_trailing_ellipsis_still_verify():
    assert find_quote("... informed that they are interacting with an AI system ...", ART_50_1)


def test_middle_ellipsis_never_verifies_as_one_quote():
    q = "Providers shall ensure that AI systems ... are informed that they are interacting with an AI system"
    assert not find_quote(q, ART_50_1)
    assert locate(q, "art-50-1", ART_50_1) == Located("art-50-1", False, None)
    # Each segment checked on its own, as the pipeline does.
    assert all(find_quote(s, ART_50_1) for s in split_quote(q))


# locate


PARTS = [
    ("art-6-1", "that AI system shall be considered to be high-risk where both of the following conditions are fulfilled"),
    ("art-6-2", "AI systems referred to in Annex III shall be considered to be high-risk."),
    ("art-6-3", "an AI system referred to in Annex III shall always be considered to be high-risk where the AI system performs profiling of natural persons."),
]
UNIT_TEXT = "\n".join(t for _, t in PARTS)


def test_locate_returns_the_corpus_words():
    loc = locate("“ai SYSTEM” MEANS a machine-based system", "art-3-1", ART_3_1)
    assert loc == Located("art-3-1", True, "‘AI system’ means a machine-based system")
    loc = locate("referred to in Annex III shall be considered to be high-risk.", "art-6-2", PARTS[1][1], PARTS)
    assert loc == Located("art-6-2", True, "referred to in Annex III shall be considered to be high-risk")


def test_locate_text_spans_original_whitespace_and_hyphenation():
    text = "the AI system is intended to be used as a safety com-\nponent  of a product"
    loc = locate("used as a safety component of a product", "x", text)
    assert loc.verified and loc.text == "used as a safety com-\nponent  of a product"


def test_locate_moves_ref_to_sibling_part():
    loc = locate("performs profiling of natural persons", "art-6-2", PARTS[1][1], PARTS + [("art-6", UNIT_TEXT)])
    assert loc == Located("art-6-3", True, "performs profiling of natural persons")


def test_locate_first_sibling_part_wins():
    parts = [("art-1-1", "the same words appear here once"), ("art-1-2", "the same words appear here once")]
    assert locate("the same words appear here", "art-1-3", "other text of the cited part", parts).ref == "art-1-1"


def test_locate_narrows_unit_ref_to_part():
    assert locate("performs profiling of natural persons", "art-6", UNIT_TEXT, PARTS).ref == "art-6-3"


def test_locate_never_widens_a_part_to_its_unit():
    q = "both of the following conditions are fulfilled AI systems referred to in Annex III"
    loc = locate(q, "art-6-1", PARTS[0][1], PARTS + [("art-6", UNIT_TEXT)])
    assert loc == Located("art-6-1", False, None)


def test_locate_unit_ref_keeps_a_quote_found_in_the_unit_text():
    # Cited to the whole unit and found there as one passage; no single part holds it.
    q = "both of the following conditions are fulfilled AI systems referred to in Annex III"
    assert locate(q, "art-6", UNIT_TEXT, PARTS) == Located("art-6", True, "both of the following conditions are fulfilled\nAI systems referred to in Annex III")


def test_locate_not_found_keeps_ref():
    assert locate("this sentence is not in the Act at all", "art-6-2", PARTS[1][1], PARTS) == Located("art-6-2", False, None)


def test_locate_without_text():
    assert locate("performs profiling of natural persons", "art-6-3", None, []) == Located("art-6-3", False, None)
    assert locate("performs profiling of natural persons", "art-6-3", None, PARTS).ref == "art-6-3"


def test_locate_quote_wrapper():
    assert locate_quote("performs profiling of natural persons", "art-6-2", PARTS[1][1], PARTS) == ("art-6-3", True)
    assert locate_quote("this sentence is not in the Act at all", "art-6-2", PARTS[1][1], PARTS) == ("art-6-2", False)


# Real corpus


real = pytest.mark.skipif(not REAL_CORPUS.exists(), reason="data/corpus.json is missing")


@pytest.fixture(scope="module")
def corpus():
    from app.corpus import get_corpus

    return get_corpus()


def check(corpus, ref: str, quote: str) -> Located:
    """The same inputs the pipeline gives: the parts of the unit, and the unit for a part ref."""
    unit = corpus.unit_of(ref)
    siblings = [(p.id, p.text) for p in unit.parts]
    if ref != unit.id:
        siblings.append((unit.id, unit.text))
    return locate(quote, ref, corpus.text_of(ref), siblings)


ATTACKS = [
    # review C2 and audit C1: stitched with an ellipsis
    ("art-5-1", "The following AI practices shall ... not ... be prohibited"),
    ("art-6-2", "AI systems referred to in Annex III shall ... not ... be considered to be high-risk"),
    ("art-6-3", "an AI system referred to in Annex III shall not be considered to be high-risk ... where the AI system performs profiling of natural persons"),
    ("art-2-1", "This Regulation applies to ... AI systems released under free and open-source licences"),
    ("art-50-4", "Deployers ... shall disclose that the content has been artificially generated ... This obligation shall not apply"),
    # review C1: numbers, dates, amounts, article and annex numbers, point letters
    ("art-6-2", "In addition to the high-risk AI systems referred to in paragraph 1, AI systems referred to in Annex II shall be considered to be high-risk"),
    ("art-6-2", "In addition to the high-risk AI systems referred to in paragraph 2, AI systems referred to in Annex III shall be considered to be high-risk"),
    ("art-6-1", "covered by the Union harmonisation legislation listed in Annex III"),
    ("art-51-2", "measured in floating point operations is greater than 10^26"),
    ("art-51-2", "measured in floating point operations is greater than 10^23"),
    ("art-51-2", "measured in floating point operations is greater than 10^2"),
    ("art-113", "(i) 2 August 2027 as regards AI systems classified as high-risk"),
    ("art-113", "(i) 3 December 2027 as regards AI systems classified as high-risk"),
    ("art-113", "(i) 2 December 2028 as regards AI systems classified as high-risk"),
    ("art-113", "(i) 12 December 2027 as regards AI systems classified as high-risk"),
    ("art-113", "(ii) 2 August 2027 as regards AI systems classified as high-risk pursuant to Article 6(1)"),
    ("art-99-4", "shall be subject to administrative fines of up to EUR 1 000 000 or"),
    ("art-99-4", "if the offender is an undertaking, up to 2 % of its total worldwide annual turnover"),
    ("art-99-4", "other than those laid down in Articles 6, shall be subject to administrative fines"),
    ("annex-III-4", "(b) AI systems intended to be used for the recruitment or selection of natural persons"),
    ("art-6-1", "(a) the AI system is intended to be used as a safety component of a product, and the AI system is itself a product"),
    ("art-6-1", "where one of the following conditions are fulfilled"),
    # review L1: short words
    ("art-6-1", "the AI system is intended to be used as a safety component of the product"),
    ("art-6-1", "placed in the market or put into service independently"),
    # homoglyph (Cyrillic a)
    ("art-6-2", "AI systems referred to in Annex III shall be considered to be high-risk".replace("a", "а", 1)),
    # fabricated
    ("art-3", ("The provider shall publish the full source code and the training data of every model within thirty days " * 4)[:300]),
    ("art-6-3", "profiling of n"),
]


@real
@pytest.mark.parametrize("ref,quote", ATTACKS)
def test_attack_is_not_verified(corpus, ref, quote):
    assert corpus.get(ref) is not None, ref
    assert not check(corpus, ref, quote).verified


@real
@pytest.mark.parametrize("ref,quote", [
    ("art-6-3", "an AI system referred to in Annex III shall always be considered to be high-risk where the AI system performs profiling of natural persons"),
    ("art-2-12", "This Regulation does not apply to AI systems released under free and open-source licences"),
    ("art-51-2", "measured in floating point operations is greater than 10^25."),
    ("art-113", "(i) 2 December 2027 as regards AI systems classified as high-risk"),
    ("art-99-4", "shall be subject to administrative fines of up to EUR 15 000 000 or"),
    ("art-3", "‘AI system’ means a machine-based system that is designed to operate"),
    ("art-3-1", "means a machine- based system that is designed to operate with varying levels"),
    ("art-6-1", "conditions are fulfilled: (a) the AI system is intended to be used as a safety component of a product"),
])
def test_real_quote_verifies(corpus, ref, quote):
    assert check(corpus, ref, quote).verified


@real
def test_unit_ref_is_narrowed_to_part(corpus):
    loc = check(corpus, "art-3", "‘AI system’ means a machine-based system that is designed to operate")
    assert loc.ref == "art-3-1" and loc.text == "‘AI system’ means a machine-based system that is designed to operate"


@real
def test_forty_long_fabricated_quotes_at_article_3_are_fast(corpus):
    rng = random.Random(3)
    words = re.findall(r"[a-z]+", corpus.text_of("art-3"))
    quotes = [" ".join(rng.choice(words) for _ in range(80))[:300] for _ in range(40)]
    check(corpus, "art-3-1", "warm up the cache of folded corpus text")
    t0 = time.perf_counter()
    results = [check(corpus, ref, q) for q in quotes for ref in ("art-3",)]
    elapsed = time.perf_counter() - t0
    assert not any(r.verified for r in results)
    assert elapsed < 1.0, elapsed


SHORT_SWAP = {"and": "or", "or": "and", "for": "to", "by": "to", "to": "by", "of": "to", "in": "on", "on": "in",
              "at": "in", "the": "a", "a": "the", "an": "the", "not": "now", "shall": "may", "may": "shall",
              "is": "are", "are": "is", "be": "by"}
ROMAN = {"i": "ii", "ii": "iii", "iii": "ii", "iv": "v", "v": "vi", "vi": "v", "x": "xi", "xi": "x"}


def _spans(corpus, n: int, seed: int):
    rng = random.Random(seed)
    items = []
    for u in corpus.units.values():
        for ref, text in ([(p.id, p.text) for p in u.parts] if u.parts else [(u.id, u.text)]):
            if len(text) >= 120:
                items.append((ref, text))
    vocab = sorted({w for _, t in items for w in re.findall(r"[a-z]{5,}", t)})
    out = []
    while len(out) < n:
        ref, text = rng.choice(items)
        size = rng.randint(60, 300)
        s = rng.randint(0, len(text) - size) if len(text) > size else 0
        sub = text[s : s + size]
        if s > 0 and " " in sub:
            sub = sub.split(" ", 1)[1]
        if " " in sub:
            sub = sub.rsplit(" ", 1)[0]
        sub = sub.strip()
        if len(sub) >= 30:
            out.append((ref, text, sub))
    return out, vocab, rng


def _mutations(quote: str, vocab: list[str], rng: random.Random):
    """Every single-number and single-word change of a quote."""
    for m in re.finditer(r"\d+", quote):
        v = int(m.group(0))
        for new in {v + 1, v - 1 if v > 0 else v + 2, v * 10}:
            yield quote[: m.start()] + str(new) + quote[m.end() :]
    for m in re.finditer(r"[A-Za-z]+", quote):
        w = m.group(0)
        low = w.lower()
        if low in ROMAN and (w.isupper() or quote[max(0, m.start() - 1) : m.start()] == "("):
            new = ROMAN[low].upper() if w.isupper() else ROMAN[low]
        elif low in SHORT_SWAP:
            new = SHORT_SWAP[low]
        elif len(w) == 1:
            new = chr((ord(low) - 97 + 1) % 26 + 97)
        else:
            new = rng.choice(vocab)
            while new == low:
                new = rng.choice(vocab)
        yield quote[: m.start()] + new + quote[m.end() :]


@real
def test_random_real_spans_verify_and_every_mutation_fails(corpus):
    spans, vocab, rng = _spans(corpus, 300, seed=7)
    tried = 0
    real_elsewhere = []
    for ref, text, q in spans:
        assert check(corpus, ref, q).verified, (ref, q)
        for mutated in _mutations(q, vocab, rng):
            if normalize(mutated) == normalize(q):
                continue
            tried += 1
            loc = check(corpus, ref, mutated)
            if loc.verified:
                # The only allowed case: the change produced another real passage of the same part.
                assert loc.ref == ref and normalize(mutated).strip(" ,;:.") in normalize(text), (ref, q, mutated, loc)
                real_elsewhere.append((ref, mutated))
    assert tried > 5000
    assert len(real_elsewhere) <= tried // 500, real_elsewhere


# Display text: quote marks at the edges of the cut


def test_display_text_keeps_quote_marks_and_brackets_at_the_edges():
    text = "the term ‘deployer’ is defined in Article 3 (see point (4)) of this Regulation"
    assert locate("deployer is defined in Article 3", "x", text).text == "‘deployer’ is defined in Article 3"
    assert locate("the term deployer is defined", "x", text).text == "the term ‘deployer’ is defined"
    assert locate("is defined in Article 3 (see point (4)", "x", text).text == "is defined in Article 3 (see point (4))"
    assert locate("is defined in Article 3 (see", "x", text).text == "is defined in Article 3 (see"


def test_display_text_never_changes_the_decision():
    text = "‘AI system’ means a machine-based system"
    for q in ("AI system means a machine-based system", "'AI system' means a machine-based", "AI system means a machine-based systems"):
        assert locate(q, "x", text).verified == find_quote(q, text)


def _balanced(t: str) -> bool:
    opening = t.count("‘") + t.count("“")
    closing = sum(1 for k, ch in enumerate(t) if ch in "’”" and not (0 < k < len(t) - 1 and t[k - 1].isalnum() and t[k + 1].isalnum()))
    return opening == closing


@real
def test_article_3_1_display_text_starts_with_the_opening_mark(corpus):
    for q in ("AI system means a machine-based system that is designed to operate with varying levels of autonomy",
              "'AI system' means a machine-based system"):
        loc = check(corpus, "art-3-1", q)
        assert loc.verified and loc.ref == "art-3-1"
        assert loc.text.startswith("‘AI system’ means a machine-based system"), loc.text


@real
def test_mid_sentence_quote_is_unchanged(corpus):
    q = "means a machine-based system that is designed to operate with varying levels of autonomy"
    assert check(corpus, "art-3-1", q).text == q


@real
def test_quote_ending_before_a_closing_mark_includes_it(corpus):
    loc = check(corpus, "art-3-63", "general-purpose AI model")
    assert loc.verified and loc.text == "\u2018general-purpose AI model\u2019"
    text = "is referred to as the \u2018general-purpose AI model\u2019 in this text"
    assert locate("referred to as the general-purpose AI model", "x", text).text == "referred to as the \u2018general-purpose AI model\u2019"


@real
def test_article_3_definitions_have_balanced_marks(corpus):
    defs = list(corpus.get("art-3").parts)
    assert len(defs) >= 70
    for p in defs:
        plain = re.sub("(?<!\\w)[‘’“”]|[‘’“”](?!\\w)", "", p.text)
        q = " ".join(plain.split()[:12])
        loc = check(corpus, p.id, q)
        assert loc.verified and loc.ref == p.id, (p.id, q)
        assert _balanced(loc.text), (p.id, loc.text)
