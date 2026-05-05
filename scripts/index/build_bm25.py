"""Build the BM25 index over every chunk in data/processed/.

Output: data/index/bm25/ — `bm25s` native dump (index.json + npy
sidecars) plus `meta.json` carrying chunk count, build time, git sha,
and the rechunked-aware file list so consumers can validate they're
loading against the same processed snapshot.

Row order is the same `lecture_knowledge.chunks.iter_chunks` order
that the dense index uses, so BM25 row IDs and FAISS row IDs are
interchangeable.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import bm25s

from lecture_knowledge.chunks import index_files, load_chunks
from lecture_knowledge.tokenize_text import tokenize

OUT_DIR = Path("data/index/bm25")


def _git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except subprocess.CalledProcessError:
        return "unknown"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Loading chunks…")
    chunks = load_chunks()
    print(f"  {len(chunks)} chunks")

    print("Tokenizing…")
    t0 = time.time()
    tokenized = [tokenize(c.get("text", "")) for c in chunks]
    print(f"  {time.time() - t0:.1f}s")

    print("Building BM25…")
    t0 = time.time()
    retriever = bm25s.BM25()
    retriever.index(tokenized)
    print(f"  {time.time() - t0:.1f}s")

    print(f"Writing → {OUT_DIR}")
    retriever.save(str(OUT_DIR), corpus=None)

    meta = {
        "n_chunks": len(chunks),
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_sha": _git_sha(),
        "tokenizer": "lecture_knowledge.tokenize_text.tokenize (a-z0-9, len>=2, lowercase)",
        "source_files": [str(p) for p in index_files()],
    }
    (OUT_DIR / "meta.json").write_text(json.dumps(meta, indent=2))
    print("Done.")


if __name__ == "__main__":
    main()
