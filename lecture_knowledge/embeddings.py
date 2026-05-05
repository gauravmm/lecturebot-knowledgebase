"""Content-hashed embedding cache.

`embed_texts(texts, model)` returns a row-aligned (N, D) float32 array,
embedding only cache misses. Cache key is `sha256(text + model_id)`,
stored as `data/cache/embeddings/<sha>.npy`. The cache is shared across
the dense build and any ad-hoc embedding (e.g. query encoding at search
time, though queries aren't worth caching individually).

The "5-minute rebuild vs. 3-hour rebuild" wording in LAYOUT.md is the
design intent: re-running a corpus's processing script changes a few
chunks, the rest hit cache.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

DEFAULT_CACHE = Path("data/cache/embeddings")


def _key(text: str, model_id: str) -> str:
    h = hashlib.sha256()
    h.update(model_id.encode("utf-8"))
    h.update(b"\x00")
    h.update(text.encode("utf-8"))
    return h.hexdigest()


def _cache_path(cache_root: Path, key: str) -> Path:
    # Two-char shard so a single dir doesn't end up with 15k files.
    return cache_root / key[:2] / f"{key}.npy"


def embed_texts(
    texts: list[str],
    model,
    *,
    model_id: str,
    cache_root: Path = DEFAULT_CACHE,
    batch_size: int = 32,
) -> np.ndarray:
    """Embed `texts` via `model.encode`, caching by sha256(text + model_id).

    `model` only needs an `encode(list[str], ...) -> np.ndarray` method
    matching sentence-transformers' interface. Embeddings are written
    L2-normalized (so FAISS flat-IP behaves as cosine similarity).
    """
    cache_root.mkdir(parents=True, exist_ok=True)
    keys = [_key(t, model_id) for t in texts]
    paths = [_cache_path(cache_root, k) for k in keys]

    miss_idx: list[int] = []
    miss_texts: list[str] = []
    for i, p in enumerate(paths):
        if not p.exists():
            miss_idx.append(i)
            miss_texts.append(texts[i])

    if miss_texts:
        print(f"Embedding {len(miss_texts)} cache misses ({len(texts) - len(miss_texts)} hits)…")
        encoded = model.encode(
            miss_texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=True,
            convert_to_numpy=True,
        ).astype(np.float32)
        for local_i, global_i in enumerate(miss_idx):
            paths[global_i].parent.mkdir(parents=True, exist_ok=True)
            np.save(paths[global_i], encoded[local_i])
    else:
        print(f"All {len(texts)} embeddings hit cache.")

    # Probe one cached vector for the dim, then assemble row-aligned.
    sample = np.load(paths[0])
    dim = int(sample.shape[-1])
    out = np.empty((len(texts), dim), dtype=np.float32)
    for i, p in enumerate(paths):
        out[i] = np.load(p)
    return out
