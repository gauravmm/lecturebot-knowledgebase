"""Quick statistics over the processed JSONL chunks.

Usage:
    uv run python scripts/inspect/chunk_stats.py [path-glob ...]

Defaults to scanning every *.chunks.jsonl under data/processed/ plus
any *.rechunked.jsonl sidecars (the rechunker writes those alongside
the originals; when present they replace the original in the index).
Reports per-corpus chunk counts and a true tiktoken cl100k_base token
distribution. Flags any chunks above the 800-token soft cap from
spec/ROUGH.md §2.2.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import tiktoken

DEFAULT_ROOT = Path("data/processed")
TOKEN_CAP = 800

_ENC = tiktoken.get_encoding("cl100k_base")


def _est_tokens(text: str) -> int:
    return len(_ENC.encode(text, disallowed_special=()))


def _percentile(values: list[int], p: float) -> int:
    if not values:
        return 0
    s = sorted(values)
    idx = min(len(s) - 1, int(len(s) * p))
    return s[idx]


def _scan(paths: list[Path]) -> None:
    by_corpus: dict[str, list[int]] = defaultdict(list)
    by_file: dict[Path, list[int]] = defaultdict(list)
    biggest: tuple[int, str, Path] = (0, "", Path())
    for p in paths:
        for line in p.open():
            c = json.loads(line)
            t = _est_tokens(c.get("text", ""))
            corpus = c.get("corpus", "?")
            by_corpus[corpus].append(t)
            by_file[p].append(t)
            if t > biggest[0]:
                biggest = (t, c.get("id", "?"), p)

    print(f"{'file':<60} {'n':>5} {'p50':>5} {'p90':>5} {'p99':>5} {'max':>5} {'>800':>5}")
    print("-" * 96)
    for p in sorted(by_file):
        toks = by_file[p]
        over = sum(1 for t in toks if t > TOKEN_CAP)
        rel = str(p.relative_to(Path.cwd())) if p.is_absolute() else str(p)
        if len(rel) > 58:
            rel = "…" + rel[-57:]
        print(
            f"{rel:<60} {len(toks):>5} "
            f"{_percentile(toks, 0.50):>5} {_percentile(toks, 0.90):>5} "
            f"{_percentile(toks, 0.99):>5} {max(toks):>5} {over:>5}"
        )

    print()
    print("Per corpus:")
    grand_total = 0
    grand_over = 0
    for corpus in sorted(by_corpus):
        toks = by_corpus[corpus]
        over = sum(1 for t in toks if t > TOKEN_CAP)
        grand_total += len(toks)
        grand_over += over
        print(
            f"  {corpus:<24} {len(toks):>5} chunks   "
            f"p50={_percentile(toks, 0.50):>4}  p90={_percentile(toks, 0.90):>4}  "
            f"p99={_percentile(toks, 0.99):>4}  max={max(toks):>5}  over-{TOKEN_CAP}={over}"
        )
    print(f"\nTotal: {grand_total} chunks, {grand_over} over the {TOKEN_CAP}-token cap.")
    if biggest[0]:
        print(f"Biggest single chunk: {biggest[0]} tokens — {biggest[1]} ({biggest[2]})")


def _prefer_rechunked(paths: list[Path]) -> list[Path]:
    """Drop a *.chunks.jsonl when its sibling *.rechunked.jsonl is present."""
    rechunked_stems = {p.with_suffix("").stem for p in paths if p.name.endswith(".rechunked.jsonl")}
    out: list[Path] = []
    for p in paths:
        if p.name.endswith(".chunks.jsonl") and p.with_suffix("").stem.removesuffix(".chunks") in rechunked_stems:
            continue
        out.append(p)
    return out


def main() -> None:
    args = sys.argv[1:]
    paths: list[Path] = []
    if args:
        for a in args:
            if "*" in a or "?" in a:
                paths.extend(sorted(Path().glob(a)))
            else:
                p = Path(a)
                if p.is_dir():
                    paths.extend(sorted(p.rglob("*.chunks.jsonl")))
                    paths.extend(sorted(p.rglob("*.rechunked.jsonl")))
                else:
                    paths.append(p)
    else:
        paths = sorted(DEFAULT_ROOT.rglob("*.chunks.jsonl"))
        paths.extend(sorted(DEFAULT_ROOT.rglob("*.rechunked.jsonl")))
    paths = _prefer_rechunked(paths)
    if not paths:
        print("No JSONL files matched. Try: scripts/inspect/chunk_stats.py data/processed/")
        sys.exit(1)
    _scan(paths)


if __name__ == "__main__":
    main()
