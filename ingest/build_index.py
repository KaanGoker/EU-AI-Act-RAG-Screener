"""Build the dense index in chroma_db/ from data/corpus.json with local fastembed embeddings.

Run from the repo root:  python -m ingest.build_index
The folder is wiped and rebuilt every time, so the result does not depend on what was there.
"""

from __future__ import annotations

import shutil
import sqlite3
import sys
import time

from chromadb.api.client import SharedSystemClient

from app.corpus import get_corpus
from app.retrieval import (
    CHROMA_DIR,
    EMBED_MODEL,
    MAX_CHARS,
    FastEmbedder,
    build_chunks,
    document_input,
    open_store,
)


def main() -> int:
    corpus = get_corpus()
    chunks = build_chunks(corpus)
    ids = [c.id for c in chunks]
    if len(set(ids)) != len(ids):
        print("duplicate chunk ids")
        return 1

    if CHROMA_DIR.exists():
        shutil.rmtree(CHROMA_DIR)
    CHROMA_DIR.mkdir(parents=True)

    t0 = time.perf_counter()
    embedder = FastEmbedder()
    print(f"model {EMBED_MODEL} loaded in {time.perf_counter() - t0:.1f}s")
    texts = [document_input(corpus, c) for c in chunks]
    t0 = time.perf_counter()
    vectors = embedder.embed_documents(texts)
    print(f"embedded {len(texts)} chunks in {time.perf_counter() - t0:.1f}s, dimension {len(vectors[0])}")

    store = open_store(
        embedder,
        metadata={
            "hnsw:space": "cosine",
            "embed_model": EMBED_MODEL,
            "max_chars": MAX_CHARS,
            "chunks": len(chunks),
        },
    )
    collection = store._collection
    metadatas = [{"ref": c.ref, "unit_id": c.unit_id, "kind": c.kind, "page": c.page} for c in chunks]
    # no documents: the text comes from data/corpus.json at run time, which keeps the folder small
    collection.add(ids=ids, embeddings=vectors, metadatas=metadatas)
    count = collection.count()
    name = collection.name
    del store, collection
    SharedSystemClient.clear_system_cache()
    con = sqlite3.connect(CHROMA_DIR / "chroma.sqlite3")
    con.execute("VACUUM")
    con.close()
    print(f"collection {name}: {count} vectors in {CHROMA_DIR.name}/")
    return 0 if count == len(chunks) else 1


if __name__ == "__main__":
    sys.exit(main())
