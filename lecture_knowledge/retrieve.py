"""Public retrieval surface: `search` and `fetch_doc`.

Hybrid BM25 + dense → reciprocal rank fusion → per-corpus boost.
The chat layer (out of scope here) is the only intended consumer.

```python
from lecture_knowledge.retrieve import search, fetch_doc
hits = search("what does GPT-4 cost", k=6)
full = fetch_doc(hits[0]["id"])
```

Both indexes (BM25 + FAISS) and the chunk_meta parquet are loaded
lazily on first call and cached on the module. Subsequent queries
amortize.
"""

from __future__ import annotations

import threading
from typing import Any

import bm25s
import faiss
import numpy as np
import pyarrow.parquet as pq
from sentence_transformers import SentenceTransformer

from lecture_knowledge.config import (
    BM25_DIR,
    CHUNK_META_PATH,
    CORPUS_BOOSTS,
    DEFAULT_CORPUS_BOOST,
    DENSE_DIR,
    EMBEDDING_MODEL_ID,
)
from lecture_knowledge.tokenize_text import tokenize

# RRF k-constant. 60 is the long-standing default from Cormack et al. (2009).
_RRF_K = 60
_DEFAULT_K = 6
_PER_INDEX_TOPK = 50  # candidates pulled from each side before fusion
_SNIPPET_CHARS = 240

_lock = threading.Lock()
_state: dict[str, Any] = {}


def _load() -> dict[str, Any]:
    if _state:
        return _state
    with _lock:
        if _state:
            return _state
        meta_table = pq.read_table(CHUNK_META_PATH)
        meta = meta_table.to_pydict()
        n = len(meta["id"])

        bm25 = bm25s.BM25.load(str(BM25_DIR), load_corpus=False)

        faiss_index = faiss.read_index(str(DENSE_DIR / "faiss.index"))

        model = SentenceTransformer(EMBEDDING_MODEL_ID)

        _state.update(
            n=n,
            meta=meta,
            id_to_row={cid: i for i, cid in enumerate(meta["id"])},
            bm25=bm25,
            faiss=faiss_index,
            model=model,
        )
        return _state


def _snippet(text: str) -> str:
    text = " ".join(text.split())
    if len(text) <= _SNIPPET_CHARS:
        return text
    return text[: _SNIPPET_CHARS - 1].rstrip() + "…"


def _bm25_topk(query: str, k: int) -> list[tuple[int, float]]:
    s = _load()
    tokens = tokenize(query)
    if not tokens:
        return []
    results, scores = s["bm25"].retrieve([tokens], k=k)
    return [(int(idx), float(scores[0][i])) for i, idx in enumerate(results[0])]


def _dense_topk(query: str, k: int) -> list[tuple[int, float]]:
    s = _load()
    qvec = s["model"].encode(
        [query], normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False
    ).astype(np.float32)
    scores, idxs = s["faiss"].search(qvec, k)
    return [(int(idx), float(scores[0][i])) for i, idx in enumerate(idxs[0]) if idx >= 0]


def _rrf(rankings: list[list[tuple[int, float]]]) -> dict[int, float]:
    """Reciprocal rank fusion. Returns row -> fused score (higher better)."""
    out: dict[int, float] = {}
    for ranking in rankings:
        for rank, (row, _score) in enumerate(ranking):
            out[row] = out.get(row, 0.0) + 1.0 / (_RRF_K + rank + 1)
    return out


def _row_to_hit(row: int) -> dict[str, Any]:
    s = _load()
    meta = s["meta"]
    return {
        "id": meta["id"][row],
        "corpus": meta["corpus"][row],
        "title": meta["doc_title"][row],
        "source": meta["source_url"][row],
        "section_path": meta["section_path"][row],
        "citation_url": meta["citation_url"][row],
        "citation_text": meta["citation_text"][row],
        "citation_html": meta["citation_html"][row],
        "snippet": "",
        "score": 0.0,
    }


def _attach_snippet_and_score(hit: dict[str, Any], row: int, score: float) -> dict[str, Any]:
    s = _load()
    hit["snippet"] = _snippet(s["meta"]["text"][row])
    hit["score"] = round(score, 6)
    return hit


def search(
    query: str,
    corpus: str | list[str] | None = None,
    k: int = _DEFAULT_K,
) -> list[dict[str, Any]]:
    """Hybrid search. Returns top-k chunks ordered by fused + boosted score.

    Each result carries: id, corpus, title, source (URL), section_path,
    citation_url, citation_text, citation_html, snippet, score.
    """
    s = _load()
    bm25_hits = _bm25_topk(query, _PER_INDEX_TOPK)
    dense_hits = _dense_topk(query, _PER_INDEX_TOPK)
    fused = _rrf([bm25_hits, dense_hits])

    if corpus is not None:
        wanted = {corpus} if isinstance(corpus, str) else set(corpus)
        meta_corpus = s["meta"]["corpus"]
        fused = {row: sc for row, sc in fused.items() if meta_corpus[row] in wanted}

    meta_corpus = s["meta"]["corpus"]
    boosted = {
        row: sc * CORPUS_BOOSTS.get(meta_corpus[row], DEFAULT_CORPUS_BOOST)
        for row, sc in fused.items()
    }

    top = sorted(boosted.items(), key=lambda kv: kv[1], reverse=True)[:k]
    return [_attach_snippet_and_score(_row_to_hit(row), row, score) for row, score in top]


def fetch_doc(chunk_id: str) -> dict[str, Any]:
    """Return the full text of one chunk plus title, source, and citation.

    Reads from the in-memory parquet — no JSONL access needed at
    query time, so the export tarball is self-contained.
    """
    s = _load()
    row = s["id_to_row"].get(chunk_id)
    if row is None:
        raise KeyError(f"Unknown chunk id: {chunk_id}")
    meta = s["meta"]
    return {
        "id": chunk_id,
        "title": meta["doc_title"][row],
        "source": meta["source_url"][row],
        "citation_url": meta["citation_url"][row],
        "citation_text": meta["citation_text"][row],
        "citation_html": meta["citation_html"][row],
        "full_text": meta["text"][row],
    }
