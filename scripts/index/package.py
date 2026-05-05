"""Bundle the index into data/exports/index_<date>.tar.zst.

Pipeline (each step idempotent, safe to re-run):

  1. scripts/process/rechunk.py  (split overlong chunks)
  2. scripts/index/build_bm25.py
  3. scripts/index/build_dense.py
  4. scripts/index/build_meta.py
  5. scripts/index/package.py    (this script)

Downstream consumers (the chat layer) only ever load the tarball;
they never read processed/ or index/ directly. The tarball contains:

  bm25/                   # bm25s native dump + meta.json
  dense/faiss.index
  dense/embeddings.npy
  dense/meta.json
  chunk_meta.parquet
  manifest.json           # git sha, build time, corpora + chunk counts,
                          # embedding model id

The chunk text itself is NOT bundled (parquet only carries metadata).
The chat layer is expected to call `lecture_knowledge.retrieve.fetch_doc`
which reads from `data/processed/`, OR to bundle processed/ separately
if they want a self-contained drop. Open question — flag if needed.
"""

from __future__ import annotations

import json
import subprocess
import tarfile
import time
from collections import Counter
from pathlib import Path

import pyarrow.parquet as pq
import zstandard as zstd

from lecture_knowledge.config import (
    BM25_DIR,
    CHUNK_META_PATH,
    DENSE_DIR,
    EMBEDDING_MODEL_ID,
    EXPORTS_DIR,
    INDEX_MANIFEST_PATH,
    INDEX_ROOT,
)


def _git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except subprocess.CalledProcessError:
        return "unknown"


def _git_dirty() -> bool:
    try:
        out = subprocess.check_output(["git", "status", "--porcelain"], text=True)
        return bool(out.strip())
    except subprocess.CalledProcessError:
        return False


def _write_manifest() -> dict:
    table = pq.read_table(CHUNK_META_PATH, columns=["corpus"])
    counts = Counter(table.column("corpus").to_pylist())
    manifest = {
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_sha": _git_sha(),
        "git_dirty": _git_dirty(),
        "embedding_model_id": EMBEDDING_MODEL_ID,
        "n_chunks": int(sum(counts.values())),
        "corpora": {k: counts[k] for k in sorted(counts)},
    }
    INDEX_MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
    return manifest


def _add_to_tar(tar: tarfile.TarFile, path: Path, arcname: str) -> None:
    tar.add(path, arcname=arcname, recursive=False)


def main() -> None:
    if not CHUNK_META_PATH.exists():
        raise SystemExit("chunk_meta.parquet missing — run scripts/index/build_meta.py first")
    if not (DENSE_DIR / "faiss.index").exists():
        raise SystemExit("faiss.index missing — run scripts/index/build_dense.py first")
    if not (BM25_DIR / "params.index.json").exists() and not (BM25_DIR / "data.csc.index.npy").exists():
        # bm25s file naming varies between versions; just smoke-check the dir
        if not any(BM25_DIR.iterdir()):
            raise SystemExit("bm25/ empty — run scripts/index/build_bm25.py first")

    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    manifest = _write_manifest()

    date = time.strftime("%Y-%m-%d", time.gmtime())
    out_path = EXPORTS_DIR / f"index_{date}.tar.zst"
    print(f"Packaging → {out_path}")

    cctx = zstd.ZstdCompressor(level=10)
    with out_path.open("wb") as raw, cctx.stream_writer(raw) as compressor:
        with tarfile.open(fileobj=compressor, mode="w|") as tar:
            tar.add(BM25_DIR, arcname="bm25", recursive=True)
            for name in ("faiss.index", "embeddings.npy", "meta.json"):
                p = DENSE_DIR / name
                if p.exists():
                    _add_to_tar(tar, p, f"dense/{name}")
            _add_to_tar(tar, CHUNK_META_PATH, "chunk_meta.parquet")
            _add_to_tar(tar, INDEX_MANIFEST_PATH, "manifest.json")

    size_mb = out_path.stat().st_size / 1024 / 1024
    print(f"  {size_mb:.1f} MB")
    print(f"  {manifest['n_chunks']} chunks across {len(manifest['corpora'])} corpora")
    for corpus, n in sorted(manifest["corpora"].items()):
        print(f"    {corpus:<20} {n:>5}")
    print(f"  git: {manifest['git_sha'][:12]}{' (dirty)' if manifest['git_dirty'] else ''}")
    print(f"  model: {manifest['embedding_model_id']}")


if __name__ == "__main__":
    main()
