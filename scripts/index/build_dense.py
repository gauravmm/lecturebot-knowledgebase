"""Build the dense FAISS index over every chunk in data/processed/.

Uses sentence-transformers + the content-hashed embedding cache; only
cache misses get re-embedded. Output:
- data/index/dense/embeddings.npy  (N, D) float32, L2-normalized
- data/index/dense/faiss.index     IndexFlatIP (cosine via L2 norm)
- data/index/dense/meta.json       chunk count, model id, build time

Row order matches `lecture_knowledge.chunks.iter_chunks` (== BM25
order), so FAISS row i and BM25 row i refer to the same chunk.
"""

from __future__ import annotations

import json
import os
import subprocess
import time

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
import torch

from lecture_knowledge.chunks import load_chunks
from lecture_knowledge.config import DENSE_DIR, EMBED_CACHE_DIR, EMBEDDING_MODEL_ID
from lecture_knowledge.embeddings import embed_texts


def _git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except subprocess.CalledProcessError:
        return "unknown"


def _preferred_device() -> str:
    forced = os.environ.get("LECTURE_KNOWLEDGE_EMBED_DEVICE")
    if forced:
        return forced
    return "cuda" if torch.cuda.is_available() else "cpu"


def main() -> None:
    DENSE_DIR.mkdir(parents=True, exist_ok=True)
    print("Loading chunks…")
    chunks = load_chunks()
    texts = [c.get("text", "") for c in chunks]
    print(f"  {len(chunks)} chunks")

    device = _preferred_device()
    print(f"Loading model: {EMBEDDING_MODEL_ID} on {device}")
    model = SentenceTransformer(EMBEDDING_MODEL_ID, device=device)

    t0 = time.time()
    try:
        embeddings = embed_texts(
            texts, model, model_id=EMBEDDING_MODEL_ID, cache_root=EMBED_CACHE_DIR
        )
    except torch.OutOfMemoryError:
        if device == "cpu":
            raise
        print("CUDA OOM during embedding; retrying on CPU.")
        torch.cuda.empty_cache()
        model = SentenceTransformer(EMBEDDING_MODEL_ID, device="cpu")
        embeddings = embed_texts(
            texts, model, model_id=EMBEDDING_MODEL_ID, cache_root=EMBED_CACHE_DIR
        )
    print(f"  embed total: {time.time() - t0:.1f}s, shape={embeddings.shape}")

    np.save(DENSE_DIR / "embeddings.npy", embeddings)

    print("Building FAISS IndexFlatIP…")
    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)
    faiss.write_index(index, str(DENSE_DIR / "faiss.index"))

    meta = {
        "n_chunks": len(chunks),
        "dim": int(embeddings.shape[1]),
        "model_id": EMBEDDING_MODEL_ID,
        "index_type": "IndexFlatIP",
        "normalized": True,
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_sha": _git_sha(),
    }
    (DENSE_DIR / "meta.json").write_text(json.dumps(meta, indent=2))
    print("Done.")


if __name__ == "__main__":
    main()
