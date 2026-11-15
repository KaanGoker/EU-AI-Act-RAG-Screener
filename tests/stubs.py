"""Small stand-ins for app.corpus and app.retrieval that follow the contract's interfaces.

The texts are real excerpts of Regulation (EU) 2024/1689, cut short."""

from __future__ import annotations

import re
from dataclasses import dataclass

PDF_URL = "https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=OJ:L_202401689"
CONSOLIDATED_URL = "https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:02024R1689-20260727"
AMENDED = {"art-5", "art-5-1", "art-6"}


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
    pdf_url: str | None = None
    amended: bool = False


@dataclass(frozen=True)
class Hit:
    ref: str
    unit_id: str
    kind: str
    label: str
    title: str | None
    text: str
    page: int
    score: float


# (unit id, kind, number, title, chapter, page, [(part label, text)])
RAW = [
    ("rec-1", "recital", "1", None, None, 1, [], "The purpose of this Regulation is to improve the functioning of the internal market by laying down a uniform legal framework."),
    ("art-2", "article", "2", "Scope", "I", 45, [
        ("1", "This Regulation applies to: (a) providers placing on the market or putting into service AI systems or placing on the market general-purpose AI models in the Union, irrespective of whether those providers are established or located within the Union or in a third country;\n(b) deployers of AI systems that have their place of establishment or are located within the Union;"),
        ("2", "For AI systems classified as high-risk AI systems in accordance with Article 6(1) related to products covered by the Union harmonisation legislation listed in Section B of Annex I, only Article 6(1), Article 60a and Articles 102 to 112 shall apply."),
        ("3", "This Regulation does not apply to AI systems where and in so far they are placed on the market, put into service, or used with or without modification exclusively for military, defence or national security purposes, regardless of the type of entity carrying out those activities."),
        ("6", "This Regulation does not apply to AI systems or AI models, including their output, specifically developed and put into service for the sole purpose of scientific research and development."),
    ], None),
    ("art-3", "article", "3", "Definitions", "I", 46, [
        ("1", "‘AI system’ means a machine-based system that is designed to operate with varying levels of autonomy and that may exhibit adaptiveness after deployment, and that, for explicit or implicit objectives, infers, from the input it receives, how to generate outputs such as predictions, content, recommendations, or decisions that can influence physical or virtual environments;"),
        ("3", "‘provider’ means a natural or legal person, public authority, agency or other body that develops an AI system or a general-purpose AI model or that has an AI system or a general-purpose AI model developed and places it on the market or puts the AI system into service under its own name or trademark, whether for payment or free of charge;"),
        ("4", "‘deployer’ means a natural or legal person, public authority, agency or other body using an AI system under its authority except where the AI system is used in the course of a personal non-professional activity;"),
        ("63", "‘general-purpose AI model’ means an AI model, including where such an AI model is trained with a large amount of data using self-supervision at scale, that displays significant generality and is capable of competently performing a wide range of distinct tasks;"),
    ], None),
    ("art-5", "article", "5", "Prohibited AI practices", "II", 51, [
        ("1", "The following AI practices shall be prohibited:\n(c) the placing on the market, the putting into service or the use of AI systems for the evaluation or classification of natural persons or groups of persons over a certain period of time based on their social behaviour or known, inferred or predicted personal or personality characteristics;\n(f) the placing on the market, the putting into service for this specific purpose, or the use of AI systems to infer emotions of a natural person in the areas of workplace and education institutions, except where the use of the AI system is intended to be put in place or into the market for medical or safety reasons;"),
    ], None),
    ("art-6", "article", "6", "Classification rules for high-risk AI systems", "III", 53, [
        ("1", "Irrespective of whether an AI system is placed on the market or put into service independently of the products referred to in points (a) and (b), that AI system shall be considered to be high-risk where both of the following conditions are fulfilled:"),
        ("2", "In addition to the high-risk AI systems referred to in paragraph 1, AI systems referred to in Annex III shall be considered to be high-risk."),
        ("3", "By derogation from paragraph 2, an AI system referred to in Annex III shall not be considered to be high-risk where it does not pose a significant risk of harm to the health, safety or fundamental rights of natural persons, including by not materially influencing the outcome of decision making.\nNotwithstanding the first subparagraph, an AI system referred to in Annex III shall always be considered to be high-risk where the AI system performs profiling of natural persons."),
        ("4", "A provider who considers that an AI system referred to in Annex III is not high-risk shall document its assessment before that system is placed on the market or put into service."),
    ], None),
    ("art-9", "article", "9", "Risk management system", "III", 56, [
        ("1", "A risk management system shall be established, implemented, documented and maintained in relation to high-risk AI systems."),
    ], None),
    ("art-26", "article", "26", "Obligations of deployers of high-risk AI systems", "III", 67, [
        ("1", "Deployers of high-risk AI systems shall take appropriate technical and organisational measures to ensure they use such systems in accordance with the instructions for use accompanying the systems, pursuant to paragraphs 3 and 6."),
    ], None),
    ("art-50", "article", "50", "Transparency obligations for providers and deployers of certain AI systems", "IV", 82, [
        ("1", "Providers shall ensure that AI systems intended to interact directly with natural persons are designed and developed in such a way that the natural persons concerned are informed that they are interacting with an AI system, unless this is obvious."),
        ("2", "Providers of AI systems, including general-purpose AI systems, generating synthetic audio, image, video or text content, shall ensure that the outputs of the AI system are marked in a machine-readable format and detectable as artificially generated or manipulated."),
    ], None),
    ("art-53", "article", "53", "Obligations for providers of general-purpose AI models", "V", 84, [
        ("1", "Providers of general-purpose AI models shall: (a) draw up and keep up-to-date the technical documentation of the model, including its training and testing process and the results of its evaluation;"),
    ], None),
    ("art-113", "article", "113", "Entry into force and application", "XIII", 123, [], "This Regulation shall enter into force on the twentieth day following that of its publication in the Official Journal of the European Union. It shall apply from 2 August 2026."),
    ("annex-I", "annex", "I", "List of Union harmonisation legislation", None, 125, [
        ("11", "Regulation (EU) 2017/745 of the European Parliament and of the Council of 5 April 2017 on medical devices;"),
        ("18", "Regulation (EU) 2018/858 of the European Parliament and of the Council of 30 May 2018 on the approval and market surveillance of motor vehicles and their trailers;"),
        ("21", "Regulation (EU) 2023/1230 of the European Parliament and of the Council of 14 June 2023 on machinery;"),
    ], None),
    ("annex-III", "annex", "III", "High-risk AI systems referred to in Article 6(2)", None, 127, [
        ("3", "Education and vocational training: (a) AI systems intended to be used to determine access or admission or to assign natural persons to educational and vocational training institutions at all levels;"),
        ("4", "Employment, workers’ management and access to self-employment: (a) AI systems intended to be used for the recruitment or selection of natural persons, in particular to place targeted job advertisements, to analyse and filter job applications, and to evaluate candidates;"),
        ("5", "Access to and enjoyment of essential private services and essential public services and benefits: (b) AI systems intended to be used to evaluate the creditworthiness of natural persons or establish their credit score, with the exception of AI systems used for the purpose of detecting financial fraud;"),
    ], None),
]

ROMAN = {"III": "III", "I": "I"}


def _label(ref: str) -> str:
    m = re.match(r"^art-(\d+)(?:-(\d+))?$", ref)
    if m:
        return f"Article {m.group(1)}" + (f"({m.group(2)})" if m.group(2) else "")
    m = re.match(r"^annex-([IVX]+)(?:-(\d+))?$", ref)
    if m:
        return f"Annex {m.group(1)}" + (f", point {m.group(2)}" if m.group(2) else "")
    m = re.match(r"^rec-(\d+)$", ref)
    if m:
        return f"Recital {m.group(1)}"
    return ref


class StubCorpus:
    def __init__(self) -> None:
        self.source = {"title": "Regulation (EU) 2024/1689 (Artificial Intelligence Act), consolidated version of 27 July 2026",
                       "consolidated_version": "2026-07-27", "pdf_url": CONSOLIDATED_URL,
                       "legal_notice": "This text is meant purely as a documentation tool and has no legal effect.",
                       "recitals": {"pdf_url": PDF_URL}}
        self.units: dict[str, Unit] = {}
        self._parts: dict[str, Part] = {}
        for uid, kind, number, title, chapter, page, parts, text in RAW:
            ps = tuple(Part(f"{uid}-{lab}", uid, lab, t, page, f"{uid}-{lab}" in AMENDED) for lab, t in parts)
            full = text if text is not None else "\n".join(f"{p.label}. {p.text}" for p in ps)
            pdf = PDF_URL if kind == "recital" else CONSOLIDATED_URL
            self.units[uid] = Unit(uid, kind, number, title, chapter, None, None, None, page, page + 1, full, ps, pdf, uid in AMENDED)
            for p in ps:
                self._parts[p.id] = p

    def _key(self, ref: str) -> str:
        ref = ref.strip()
        m = re.match(r"^(annex-)([ivxlc]+)(.*)$", ref, re.IGNORECASE)
        if m:
            return "annex-" + m.group(2).upper() + m.group(3)
        return ref.lower()

    def get(self, ref: str):
        k = self._key(ref)
        return self.units.get(k) or self._parts.get(k)

    def unit_of(self, ref: str):
        obj = self.get(ref)
        if obj is None:
            return None
        return obj if isinstance(obj, Unit) else self.units[obj.unit_id]

    def text_of(self, ref: str):
        obj = self.get(ref)
        return obj.text if obj is not None else None

    def label(self, ref: str) -> str:
        return _label(self._key(ref))

    def title(self, ref: str):
        u = self.unit_of(ref)
        return u.title if u else None

    def page(self, ref: str) -> int:
        obj = self.get(ref)
        if obj is None:
            return 1
        return obj.page if isinstance(obj, Part) else obj.page_start

    def page_url(self, ref: str) -> str:
        u = self.unit_of(ref)
        base = (u.pdf_url if u else None) or CONSOLIDATED_URL
        return f"{base}#page={self.page(ref)}"

    def amended(self, ref: str) -> bool:
        obj = self.get(ref)
        return bool(getattr(obj, "amended", False))

    def neighbors(self, unit_id: str):
        u = self.units.get(unit_id)
        same = [k for k, v in self.units.items() if u and v.kind == u.kind]
        if unit_id not in same:
            return None, None
        i = same.index(unit_id)
        return (same[i - 1] if i > 0 else None, same[i + 1] if i + 1 < len(same) else None)

    def toc(self) -> dict:
        arts = [u for u in self.units.values() if u.kind == "article"]
        return {
            "chapters": [{"number": "I", "title": "General provisions",
                          "articles": [{"id": u.id, "number": u.number, "title": u.title} for u in arts]}],
            "annexes": [{"id": u.id, "number": u.number, "title": u.title} for u in self.units.values() if u.kind == "annex"],
            "recitals": {"count": sum(1 for u in self.units.values() if u.kind == "recital")},
        }

    def normalize_ref(self, text: str):
        t = text.strip()
        if self.get(t) is not None:
            return self.get(t).id
        m = re.match(r"^art(?:icle|\.)?\s*(\d+)\s*(?:\((\d+)\))?$", t, re.IGNORECASE)
        if m:
            ref = f"art-{m.group(1)}" + (f"-{m.group(2)}" if m.group(2) else "")
            return ref if self.get(ref) is not None else None
        m = re.match(r"^annex\s+([ivxlc]+)(?:,?\s*point\s*(\d+))?$", t, re.IGNORECASE)
        if m:
            ref = f"annex-{m.group(1).upper()}" + (f"-{m.group(2)}" if m.group(2) else "")
            return ref if self.get(ref) is not None else None
        return None


class StubRetriever:
    """Word overlap ranking over parts, enough for tests."""

    def __init__(self, corpus: StubCorpus, ready: bool = True) -> None:
        self.corpus = corpus
        self._ready = ready
        self.calls: list[str] = []

    def _chunks(self, kinds):
        for u in self.corpus.units.values():
            if kinds and u.kind not in kinds:
                continue
            if u.parts:
                for p in u.parts:
                    yield p.id, u, p.text, p.page
            else:
                yield u.id, u, u.text, u.page_start

    def _rank(self, query: str, k: int, kinds):
        words = set(re.findall(r"\w{4,}", query.lower()))
        scored = []
        for ref, u, text, page in self._chunks(kinds):
            score = len(words & set(re.findall(r"\w{4,}", text.lower())))
            if score:
                scored.append((score, ref, u, text, page))
        scored.sort(key=lambda x: -x[0])
        return [Hit(ref, u.id, u.kind, self.corpus.label(ref), u.title, text, page, float(s)) for s, ref, u, text, page in scored[:k]]

    def search(self, query: str, k: int = 8, kinds=None):
        self.calls.append("search")
        return self._rank(query, k, kinds)

    def keyword_search(self, query: str, k: int = 20, kinds=None):
        self.calls.append("keyword")
        return self._rank(query, k, kinds)

    def ready(self) -> bool:
        return self._ready


TIMELINE = {
    "as_of": "2026-11-11",
    "entries": [
        {"id": "prohibitions", "date": "2025-02-02", "label": "Prohibited practices and AI literacy apply",
         "detail": "Chapters I and II.", "applies_to": ["all"], "source_ref": "art-113",
         "sources": [{"title": "EUR-Lex", "url": "https://eur-lex.europa.eu/eli/reg/2024/1689/oj"}]},
        {"id": "gpai", "date": "2025-08-02", "label": "Obligations for general-purpose AI models apply",
         "detail": "Chapter V.", "applies_to": ["gpai"], "source_ref": "art-113", "sources": []},
        {"id": "penalties", "date": "2025-08-02", "label": "Penalty rules apply",
         "detail": "Chapter XII.", "applies_to": ["prohibited", "high", "limited"], "source_ref": "art-113", "sources": []},
        {"id": "sectoral", "date": "2026-07-27", "label": "Amendments to the Section B sectoral acts apply",
         "detail": "", "applies_to": ["high_annex_i_b"], "source_ref": "art-113", "sources": []},
        {"id": "transparency", "date": "2026-08-02", "label": "Transparency obligations apply",
         "detail": "Article 50.", "applies_to": ["limited", "high"], "source_ref": "art-50", "sources": []},
        {"id": "new-prohibitions", "date": "2026-12-02", "label": "New prohibitions apply",
         "detail": "", "applies_to": ["prohibited", "generative"], "source_ref": "art-113", "sources": []},
        {"id": "high-annex-iii", "date": "2027-12-02", "label": "High-risk rules for Annex III systems apply",
         "detail": "", "applies_to": ["high_annex_iii"], "source_ref": "art-113", "sources": []},
        {"id": "high-annex-i", "date": "2028-08-02", "label": "High-risk rules for Annex I products apply",
         "detail": "", "applies_to": ["high_annex_i"], "source_ref": "art-113", "sources": []},
        {"id": "section-b", "date": "2028-08-02", "label": "Article 6(1) classification for Annex I Section B products",
         "detail": "", "applies_to": ["high_annex_i_b"], "source_ref": "art-2-2", "sources": []},
        {"id": "public-authorities", "date": "2030-08-02", "label": "Existing systems of public authorities",
         "detail": "", "applies_to": ["public_authority"], "source_ref": "art-113", "sources": []},
        {"id": "large-scale-it", "date": "2030-12-31", "label": "Large-scale IT systems",
         "detail": "", "applies_to": ["large_scale_it"], "source_ref": "art-113", "sources": []},
    ],
    "notes": [],
}

OBLIGATIONS = {
    "prohibited": {
        "provider": [{"id": "stop-prohibited", "title": "Do not place it on the market", "detail": "The practice is banned.", "ref": "art-5"}],
        "deployer": [{"id": "stop-use", "title": "Do not use it", "detail": "The practice is banned.", "ref": "art-5"}],
    },
    "high": {
        "provider": [
            {"id": "risk-management", "title": "Risk management system", "detail": "Set up a risk management system.", "ref": "art-9"},
            {"id": "registration", "title": "Registration", "detail": "Register the system.", "ref": "art-6-4"},
        ],
        "deployer": [
            {"id": "use-per-instructions", "title": "Use per instructions", "detail": "Use it as instructed.", "ref": "art-26"},
            {"id": "risk-management", "title": "Risk management system", "detail": "Shared item for the both case.", "ref": "art-9"},
        ],
    },
    "high_annex_i_b": {
        "provider": [{"id": "section-b-limited-application", "title": "Only a few AI Act provisions apply",
                      "detail": "Article 2(2) limits the Act for Section B products.", "ref": "art-2-2"}],
        "deployer": [{"id": "section-b-no-deployer-duties", "title": "No AI Act deployer duties",
                      "detail": "Article 2(2).", "ref": "art-2-2"}],
    },
    "limited": {
        "provider": [{"id": "inform-interaction", "title": "Tell people they talk to an AI", "detail": "Article 50(1).", "ref": "art-50-1",
                      "amended": "Not changed, test note."},
                     {"id": "prevent-prohibited-content", "title": "Safeguards against prohibited sexual content",
                      "detail": "Article 5(1a).", "ref": "art-5"}],
        "deployer": [],
    },
    "minimal": {
        "provider": [{"id": "exemption-documentation", "title": "Document and register an Article 6(3) assessment",
                      "detail": "Document the assessment and register under Article 49(2).", "ref": "art-6-4",
                      "condition": "Only if the provider relies on the Article 6(3) exemption."},
                     {"id": "voluntary-codes", "title": "Voluntary codes of conduct", "detail": "Article 95.", "ref": "art-9"}],
        "deployer": [],
    },
    "gpai": {"provider": [{"id": "gpai-docs", "title": "Technical documentation", "detail": "Article 53(1)(a).", "ref": "art-53-1"}]},
    "not_covered": {"provider": [], "deployer": []},
}
