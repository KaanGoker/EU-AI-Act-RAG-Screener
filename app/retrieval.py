"""Hybrid search over the Act: BM25 in memory plus local dense vectors in ChromaDB, fused with RRF."""

from __future__ import annotations

import os
import re
import threading
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from rank_bm25 import BM25Okapi

from app.corpus import Corpus, Part, get_corpus

ROOT = Path(__file__).resolve().parent.parent
CHROMA_DIR = ROOT / "chroma_db"
COLLECTION = "eu_ai_act"

# Chosen by measuring on eval/retrieval_eval.py (multilingual, 768 dimensions, 1.24 GB ONNX).
EMBED_MODEL = "google/embeddinggemma-300m"
# the prompt formats this model was trained with
QUERY_PREFIX = "task: search result | query: "

# Chunks are parts (paragraphs, points); longer ones are split at sentence ends.
MAX_CHARS = 700
# Reciprocal rank fusion. The BM25 weight is scaled down by how many query words occur in the Act,
# so a query in Dutch or Turkish is ranked by the dense side.
RRF_K = 60
DENSE_WEIGHT = 2.0
BM25_WEIGHT = 1.0
CANDIDATES = 60
# Relevance floor, measured on the 69 queries of eval/retrieval_eval.py and 36 nonsense and
# off-topic queries: a query gets hits only when the best dense match reaches DENSE_FLOOR
# (cosine similarity) or when at least COVERAGE_FLOOR of its words occur in the Act.
# Lowest eval query 0.242 (kept by its word share 0.75); highest nonsense query 0.261.
DENSE_FLOOR = 0.28
COVERAGE_FLOOR = 0.65


def cache_dir() -> str:
    return os.environ.get("FASTEMBED_CACHE_PATH") or str(ROOT / "models")


def embed_threads() -> int | None:
    value = os.environ.get("EMBED_THREADS")
    return int(value) if value else None


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


@dataclass(frozen=True)
class Chunk:
    id: str
    ref: str
    unit_id: str
    kind: str
    text: str
    page: int


# chunking

_SENTENCE_END = re.compile(r"(?<=[.;:])\s+(?=[A-Z(‘])|\n")


def split_text(text: str, max_chars: int = MAX_CHARS) -> list[str]:
    """Split at sentence ends or line breaks into pieces of at most about max_chars."""
    if len(text) <= max_chars:
        return [text]
    # every piece is a slice of the original text, so it can be quoted as it is
    cuts = [m.start() for m in _SENTENCE_END.finditer(text)] + [len(text)]
    out: list[str] = []
    start = 0
    last = 0
    for cut in cuts:
        if cut - start > max_chars and last > start:
            out.append(text[start:last].strip())
            start = last
        last = cut
    out.append(text[start:].strip())
    return [p for p in out if p]


def build_chunks(corpus: Corpus, max_chars: int = MAX_CHARS) -> list[Chunk]:
    chunks: list[Chunk] = []
    for unit in corpus.units.values():
        sources: list[tuple[str, str, int]] = []
        if unit.parts:
            intro = unit.text
            first = unit.parts[0].text.split("\n", 1)[0]
            cut = intro.find(first)
            intro = intro[:cut].strip() if cut > 0 else ""
            # drop the marker of the first part ("1.") from the intro
            intro = re.sub(r"\n?(\d+\.|\(\d+\))\s*$", "", intro).strip()
            if intro:
                sources.append((unit.id, intro, unit.page_start))
            for p in unit.parts:
                sources.append((p.id, p.text, p.page))
        else:
            sources.append((unit.id, unit.text, unit.page_start))
        for ref, text, page in sources:
            for i, piece in enumerate(split_text(text, max_chars)):
                chunks.append(Chunk(id=f"{ref}#{i}", ref=ref, unit_id=unit.id, kind=unit.kind, text=piece, page=page))
    return chunks


def chunk_head(corpus: Corpus, chunk: Chunk) -> str:
    title = corpus.title(chunk.ref)
    head = corpus.label(chunk.ref)
    return f"{head}: {title}" if title else head


def embed_text(corpus: Corpus, chunk: Chunk) -> str:
    """The text BM25 indexes: label and title give the chunk its context."""
    return f"{chunk_head(corpus, chunk)}\n{chunk.text}"


def document_input(corpus: Corpus, chunk: Chunk) -> str:
    """The text the embedding model sees for a chunk, in its document prompt format."""
    return f"title: {chunk_head(corpus, chunk)} | text: {chunk.text}"


# Query expansion. Some everyday words for AI systems never occur in the Act, which describes them
# in its own terms (a chatbot is "an AI system intended to interact directly with natural persons").
# A query that names one of them gets the Act's wording appended, for both BM25 and the dense side.
GLOSSARY: list[tuple[re.Pattern, str]] = [
    (
        re.compile(
            r"chat\s?bots?|sohbet robot|konuşma robot|conversational (agent|ai)|virtual assistant|"
            r"voice assistant|sanal asistan|assistant virtuel|agent conversationnel|sprachassistent|"
            r"spraakassistent|virtuele assistent|chatassistent",
            re.IGNORECASE,
        ),
        "AI system intended to interact directly with natural persons, informed that they are interacting with an AI system",
    ),
    (
        re.compile(
            r"\bcv'?s?\b|curriculum vitae|r[ée]sum[ée]s?\b|lebensl[äa]uf|özgeçmiş|sollicitant|bewerber|"
            r"job applicant|candidat|iş başvuru",
            re.IGNORECASE,
        ),
        "recruitment or selection of natural persons, to analyse and filter job applications, and to evaluate candidates",
    ),
    (
        re.compile(r"deep\s?fakes?|hypertrucage|derin sahte", re.IGNORECASE),
        "deep fake: image, audio or video content artificially generated or manipulated",
    ),
    (
        re.compile(
            r"\bllms?\b|large language model|sprachmodell|taalmodel|dil modeli|modèle de langage|"
            r"foundation model",
            re.IGNORECASE,
        ),
        "general-purpose AI model",
    ),
]


def expand_query(query: str) -> str:
    extra = [text for pattern, text in GLOSSARY if pattern.search(query)]
    return query if not extra else query + "\n" + "\n".join(extra)


# BM25

_STOP = set(
    """a an and are as at be been by can for from has have if in into is it its may must not of on or other
    such than that the their them these they this those to under was were where which while who will with
    shall should any all also be been being both each referred pursuant regulation article articles paragraph
    point points annex""".split()
)
_TOKEN = re.compile(r"[a-z0-9]+")


def _stem(tok: str) -> str:
    for suf in ("ations", "ation", "ments", "ment", "ings", "ing", "ies", "es", "s", "ed", "ly"):
        if len(tok) > len(suf) + 3 and tok.endswith(suf):
            return tok[: -len(suf)] + ("y" if suf == "ies" else "")
    return tok


def tokenize(text: str) -> list[str]:
    text = text.lower().replace("’", "'")
    return [_stem(t) for t in _TOKEN.findall(text) if t not in _STOP and len(t) > 1]


class BM25Index:
    def __init__(self, texts: list[str]):
        self.bm25 = BM25Okapi([tokenize(t) for t in texts])

    def coverage(self, query: str) -> float:
        """Share of the query tokens that occur in the Act. Low for a query in another language."""
        toks = tokenize(query)
        if not toks:
            return 0.0
        return sum(1 for t in toks if t in self.bm25.idf) / len(toks)

    def scores(self, query: str):
        toks = tokenize(query)
        if not toks:
            return None
        return self.bm25.get_scores(toks)


# dense

class FastEmbedder:
    """Local ONNX embeddings through fastembed, in the langchain Embeddings shape."""

    def __init__(self, model: str = EMBED_MODEL, query_prefix: str = QUERY_PREFIX):
        from fastembed import TextEmbedding

        self.model_name = model
        self.query_prefix = query_prefix
        self.model = TextEmbedding(model_name=model, cache_dir=cache_dir(), threads=embed_threads())

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        # texts are already in the document format (see document_input)
        return [v.tolist() for v in self.model.embed(texts, batch_size=32)]

    def embed_query(self, text: str) -> list[float]:
        return next(iter(self.model.embed([self.query_prefix + text]))).tolist()


def chroma_client_settings():
    from chromadb.config import Settings

    return Settings(anonymized_telemetry=False, is_persistent=True, persist_directory=str(CHROMA_DIR))


def open_store(embedder: FastEmbedder, metadata: dict | None = None):
    """The ChromaDB collection through langchain-chroma. metadata is set only when the index is built."""
    from langchain_chroma import Chroma

    return Chroma(
        collection_name=COLLECTION,
        embedding_function=embedder,
        persist_directory=str(CHROMA_DIR),
        client_settings=chroma_client_settings(),
        collection_metadata=metadata,
    )


def rrf(rankings: list[tuple[list[str], float]], k: int = RRF_K) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ranked, weight in rankings:
        for rank, key in enumerate(ranked):
            scores[key] = scores.get(key, 0.0) + weight / (k + rank + 1)
    return scores


class Retriever:
    def __init__(self, corpus: Corpus | None = None):
        self.corpus = corpus or get_corpus()
        self.chunks = build_chunks(self.corpus)
        self._by_id = {c.id: c for c in self.chunks}
        self._index = {c.id: i for i, c in enumerate(self.chunks)}
        self.bm25 = BM25Index([embed_text(self.corpus, c) for c in self.chunks])
        self._lock = threading.Lock()
        self._error: str | None = None
        self.embedder: FastEmbedder | None = None
        self.store = None
        try:
            if not (CHROMA_DIR / "chroma.sqlite3").exists():
                raise RuntimeError("chroma_db is missing. Run python -m ingest.build_index")
            self.embedder = FastEmbedder()
            self.store = open_store(self.embedder)
            meta = self.store._collection.metadata or {}
            count = self.store._collection.count()
            if meta.get("embed_model") != EMBED_MODEL or count != len(self.chunks):
                raise RuntimeError(
                    f"chroma_db does not match: model {meta.get('embed_model')!r}, {count} vectors; "
                    f"expected {EMBED_MODEL!r}, {len(self.chunks)}. Run python -m ingest.build_index"
                )
        except Exception as exc:  # the app still serves keyword search
            self._error = str(exc)
            self.store = None

    def ready(self) -> bool:
        return self.store is not None

    @property
    def error(self) -> str | None:
        return self._error

    # ranking helpers

    def _allowed(self, chunk: Chunk, kinds: tuple[str, ...] | None) -> bool:
        return kinds is None or chunk.kind in kinds

    def _bm25_ranking(self, query: str, kinds, depth: int) -> list[tuple[str, float]]:
        scores = self.bm25.scores(query)
        if scores is None:
            return []
        order = sorted(range(len(scores)), key=lambda i: (-scores[i], i))
        out = []
        for i in order:
            if scores[i] <= 0:
                break
            c = self.chunks[i]
            if self._allowed(c, kinds):
                out.append((c.id, float(scores[i])))
                if len(out) >= depth:
                    break
        return out

    def _dense_ranking(self, query: str, kinds, depth: int) -> list[tuple[str, float]]:
        if self.store is None:
            return []
        flt = None
        if kinds:
            flt = {"kind": kinds[0]} if len(kinds) == 1 else {"kind": {"$in": list(kinds)}}
        with self._lock:
            vec = self.embedder.embed_query(query)
        res = self.store._collection.query(query_embeddings=[vec], n_results=depth, where=flt, include=["distances"])
        ids = res["ids"][0]
        dists = res["distances"][0]
        return [(cid, 1.0 - float(d)) for cid, d in zip(ids, dists)]

    def _hits(self, scored: list[tuple[str, float]], k: int) -> list[Hit]:
        hits: list[Hit] = []
        seen: set[str] = set()
        for cid, score in scored:
            c = self._by_id[cid]
            if c.ref in seen:
                continue
            seen.add(c.ref)
            hits.append(
                Hit(
                    ref=c.ref,
                    unit_id=c.unit_id,
                    kind=c.kind,
                    label=self.corpus.label(c.ref),
                    title=self.corpus.title(c.ref),
                    text=c.text,
                    page=c.page,
                    score=round(score, 6),
                )
            )
            if len(hits) >= k:
                break
        return hits

    # public

    def search(self, query: str, k: int = 8, kinds: tuple[str, ...] | None = None) -> list[Hit]:
        """Hybrid hits, or none when the query is below the relevance floor."""
        query = (query or "").strip()
        if not query:
            return []
        kinds = tuple(kinds) if kinds else None
        query = expand_query(query)
        dense = self._dense_ranking(query, kinds, CANDIDATES)
        coverage = self.bm25.coverage(query)
        top = dense[0][1] if dense else 0.0
        if top < DENSE_FLOOR and coverage < COVERAGE_FLOOR:
            return []
        bm = self._bm25_ranking(query, kinds, CANDIDATES)
        bm_weight = BM25_WEIGHT * coverage ** 2
        fused = rrf([([cid for cid, _ in dense], DENSE_WEIGHT), ([cid for cid, _ in bm], bm_weight)])
        ordered = sorted(fused.items(), key=lambda kv: (-kv[1], self._index[kv[0]]))
        return self._hits(ordered, k)

    def keyword_search(self, query: str, k: int = 20, kinds: tuple[str, ...] | None = None) -> list[Hit]:
        query = (query or "").strip()
        if not query:
            return []
        kinds = tuple(kinds) if kinds else None
        if self.bm25.coverage(expand_query(query)) < COVERAGE_FLOOR:
            return []
        return self._hits(self._bm25_ranking(query, kinds, max(k * 4, CANDIDATES)), k)

    def dense_search(self, query: str, k: int = 8, kinds: tuple[str, ...] | None = None) -> list[Hit]:
        query = (query or "").strip()
        if not query:
            return []
        kinds = tuple(kinds) if kinds else None
        return self._hits(self._dense_ranking(expand_query(query), kinds, max(k * 4, CANDIDATES)), k)


@lru_cache(maxsize=1)
def get_retriever() -> Retriever:
    return Retriever()
