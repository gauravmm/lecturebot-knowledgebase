"""Chunk loader. Single source of truth for which JSONL files feed the index.

Walks `data/processed/` and yields chunks in deterministic order. When a
`*.rechunked.jsonl` sidecar sits next to a `*.chunks.jsonl`, the sidecar
replaces the original — that's the contract the rechunker relies on.

Per-corpus chunk schemas are not uniform; consumers should treat the
returned dict as a superset and pull only the fields they need.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

DEFAULT_PROCESSED = Path("data/processed")


def _index_files(root: Path) -> list[Path]:
    """Return the JSONLs that feed the index, preferring rechunked sidecars."""
    chunks = sorted(root.rglob("*.chunks.jsonl"))
    rechunked = sorted(root.rglob("*.rechunked.jsonl"))
    rechunked_stems = {p.with_suffix("").stem for p in rechunked}
    out: list[Path] = []
    for p in chunks:
        stem = p.with_suffix("").stem.removesuffix(".chunks")
        if stem in rechunked_stems:
            continue
        out.append(p)
    out.extend(rechunked)
    return sorted(out)


def iter_chunks(processed_root: Path = DEFAULT_PROCESSED) -> Iterator[dict]:
    """Yield every chunk dict that should land in the index, deterministically."""
    for path in _index_files(processed_root):
        for line in path.open():
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def load_chunks(processed_root: Path = DEFAULT_PROCESSED) -> list[dict]:
    return list(iter_chunks(processed_root))


def index_files(processed_root: Path = DEFAULT_PROCESSED) -> list[Path]:
    """Public wrapper for the rechunked-aware file list (used by manifests)."""
    return _index_files(processed_root)
