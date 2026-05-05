"""Marshal meme corpus into a single JSONL of one-chunk-per-meme.

Each chunk concatenates caption + joke + OCR + topics into a single text
field — the retriever matches student questions against any of these.
The image_path and image_sha256 let the bot attach the actual image when
the chunk is cited.

Output: data/processed/memes/memes.chunks.jsonl
"""

from __future__ import annotations

import json
from pathlib import Path

RAW = Path("data/raw/memes")
OUT = Path("data/processed/memes/memes.chunks.jsonl")


def chunk_text(meme: dict) -> str:
    parts: list[str] = []
    if meme.get("caption"):
        parts.append(f"Caption: {meme['caption']}")
    if meme.get("joke_summary"):
        parts.append(f"Joke: {meme['joke_summary']}")
    ocr = meme.get("ocr_text", "")
    if ocr and ocr not in ("<no-text>", "<refused>"):
        parts.append(f"Text on image:\n{ocr}")
    if meme.get("topics"):
        parts.append("Topics: " + ", ".join(meme["topics"]))
    return "\n\n".join(parts)


def process_one(sidecar: Path) -> dict:
    m = json.loads(sidecar.read_text())
    return {
        "id": f"meme::{m['id']}",
        "corpus": "memes",
        "doc_title": m.get("proposed_filename") or m["original_filename"],
        "source_url": None,
        "fetched_at": m.get("added_at"),
        "image_path": f"data/raw/memes/{m['original_filename']}",
        "image_sha256": m["sha256"],
        "format": m.get("format"),
        "topics": m.get("topics", []),
        "text": chunk_text(m),
    }


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    chunks = [process_one(s) for s in sorted(RAW.glob("*.json"))]
    with OUT.open("w") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"{OUT}: {len(chunks)} chunks")


if __name__ == "__main__":
    main()
