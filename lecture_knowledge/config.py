"""Single source of truth for paths + the dense embedding model id."""

from __future__ import annotations

from pathlib import Path

EMBEDDING_MODEL_ID = "BAAI/bge-base-en-v1.5"

DATA_ROOT = Path("data")
PROCESSED_ROOT = DATA_ROOT / "processed"
INDEX_ROOT = DATA_ROOT / "index"
BM25_DIR = INDEX_ROOT / "bm25"
DENSE_DIR = INDEX_ROOT / "dense"
CHUNK_META_PATH = INDEX_ROOT / "chunk_meta.parquet"
INDEX_MANIFEST_PATH = INDEX_ROOT / "manifest.json"
EMBED_CACHE_DIR = DATA_ROOT / "cache" / "embeddings"
EXPORTS_DIR = DATA_ROOT / "exports"

# Per-corpus retrieval boost (RRF score multiplier). Spec: G > B > C > rest.
# Keys must match the `corpus` field actually written into chunk JSONLs;
# the lecturer processor stamps "lecturer/lectures" (not "lecturer"), so
# we key on that.
CORPUS_BOOSTS: dict[str, float] = {
    "lecturer/lectures": 1.40,
    "edgar": 1.20,
    "earnings": 1.20,
    "letters": 1.20,
    "consulting": 1.05,
    "essays": 1.05,
    "vendors": 1.05,
    "ai_index": 1.05,
    # everything else (youtube, regulation, funding, epoch_models, owid,
    # memes) gets the default 1.00
}
DEFAULT_CORPUS_BOOST = 1.0
