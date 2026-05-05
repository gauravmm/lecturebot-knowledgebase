"""Token-aware re-chunking pass for overlong chunks.

For every `*.chunks.jsonl` under `data/processed/`, split any chunk
whose `text` exceeds the 800-token cap (cl100k_base) into ~800-token
windows with a 100-token overlap. Output is a sidecar
`*.rechunked.jsonl` next to the original whenever at least one chunk
in that file needed splitting; downstream indexers prefer the
rechunked sidecar when present.

Each split part inherits the parent chunk's metadata, gets a new id
of the form `<original_id>::p<N>` (zero-padded), and adds:

  - `part_of`: the original chunk id (so citations still resolve to
    the natural unit — PDF page, EU AI Act article, EDGAR Item, etc.)
  - `part_index` / `part_count`: 0-based index and total count
  - `n_tokens`: token count of this part

Original chunks that fit under the cap are passed through unchanged.

Usage:
    uv run python scripts/process/rechunk.py [path-glob ...]
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterable
from pathlib import Path

import tiktoken

DEFAULT_ROOT = Path("data/processed")
TOKEN_CAP = 800
OVERLAP = 100

_ENC = tiktoken.get_encoding("cl100k_base")


def _split_tokens(text: str) -> list[str]:
    """Encode text once, slide an 800-token window with 100-token overlap."""
    ids = _ENC.encode(text, disallowed_special=())
    if len(ids) <= TOKEN_CAP:
        return [text]
    step = TOKEN_CAP - OVERLAP
    parts: list[str] = []
    start = 0
    while start < len(ids):
        window = ids[start : start + TOKEN_CAP]
        parts.append(_ENC.decode(window))
        if start + TOKEN_CAP >= len(ids):
            break
        start += step
    return parts


def _rechunk_file(path: Path) -> tuple[int, int, int]:
    """Returns (n_chunks_in, n_chunks_out, n_split_parents)."""
    rows = [json.loads(line) for line in path.open()]
    n_split = 0
    out: list[dict] = []
    for row in rows:
        text = row.get("text", "")
        ids = _ENC.encode(text, disallowed_special=())
        if len(ids) <= TOKEN_CAP:
            row["n_tokens"] = len(ids)
            out.append(row)
            continue
        parts = _split_tokens(text)
        n_split += 1
        original_id = row["id"]
        width = max(2, len(str(len(parts) - 1)))
        for i, part_text in enumerate(parts):
            child = dict(row)
            child["text"] = part_text
            child["id"] = f"{original_id}::p{i:0{width}d}"
            child["part_of"] = original_id
            child["part_index"] = i
            child["part_count"] = len(parts)
            child["n_tokens"] = len(_ENC.encode(part_text, disallowed_special=()))
            out.append(child)
    sidecar = path.with_suffix("").with_suffix(".rechunked.jsonl")
    # path is e.g. foo.chunks.jsonl -> with_suffix("") -> foo.chunks
    # then with_suffix(".rechunked.jsonl") -> foo.rechunked.jsonl
    if n_split == 0:
        if sidecar.exists():
            sidecar.unlink()
        return len(rows), len(rows), 0
    with sidecar.open("w") as fh:
        for row in out:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(rows), len(out), n_split


def _iter_paths(args: list[str]) -> Iterable[Path]:
    if not args:
        yield from sorted(DEFAULT_ROOT.rglob("*.chunks.jsonl"))
        return
    for a in args:
        if "*" in a or "?" in a:
            yield from sorted(Path().glob(a))
            continue
        p = Path(a)
        if p.is_dir():
            yield from sorted(p.rglob("*.chunks.jsonl"))
        else:
            yield p


def main() -> None:
    paths = [p for p in _iter_paths(sys.argv[1:]) if p.name.endswith(".chunks.jsonl")]
    if not paths:
        print("No *.chunks.jsonl files matched.")
        sys.exit(1)
    total_in = total_out = total_split = files_rewritten = 0
    for p in paths:
        n_in, n_out, n_split = _rechunk_file(p)
        total_in += n_in
        total_out += n_out
        total_split += n_split
        if n_split:
            files_rewritten += 1
            sidecar = p.with_suffix("").with_suffix(".rechunked.jsonl")
            print(
                f"{p.relative_to(Path.cwd()) if p.is_absolute() else p}: "
                f"{n_split} parents → {n_out - (n_in - n_split)} parts "
                f"(sidecar: {sidecar.name})"
            )
    print(
        f"\n{files_rewritten} files rewritten. "
        f"{total_in} input chunks → {total_out} output chunks "
        f"({total_split} parents split into {total_out - (total_in - total_split)} parts)."
    )


if __name__ == "__main__":
    main()
