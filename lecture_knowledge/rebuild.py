"""End-to-end rebuild of the retrieval index.

Chains the five build stages in order:

  1. scripts/process/rechunk.py   — split overlong chunks (sidecars)
  2. scripts/index/build_bm25.py  — BM25 dump
  3. scripts/index/build_dense.py — FAISS flat-IP, embedding cache
  4. scripts/index/build_meta.py  — chunk_meta.parquet (text folded in)
  5. scripts/index/package.py     — data/exports/index_<date>.tar.zst

Each stage is independently idempotent; this script just removes the
need to remember the order. Wired up as `uv run rebuild`.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

STAGES: list[tuple[str, list[str]]] = [
    ("rechunk", ["scripts/process/rechunk.py"]),
    ("build_bm25", ["scripts/index/build_bm25.py"]),
    ("build_dense", ["scripts/index/build_dense.py"]),
    ("build_meta", ["scripts/index/build_meta.py"]),
    ("package", ["scripts/index/package.py"]),
]


def main() -> int:
    overall = time.time()
    for name, args in STAGES:
        print(f"\n==> {name}")
        t0 = time.time()
        result = subprocess.run([sys.executable, *args], cwd=REPO_ROOT)
        if result.returncode != 0:
            print(f"\n!! {name} failed (exit {result.returncode}). Stopping.")
            return result.returncode
        print(f"<== {name}: {time.time() - t0:.1f}s")
    print(f"\nDone in {time.time() - overall:.1f}s.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
