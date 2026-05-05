"""Marshal consulting AI reports into per-page JSONL chunks.

For each subdir of data/raw/consulting/<slug>/:
  - read manifest.json
  - emit one chunk per page from report.pdf

Output: data/processed/consulting/<slug>.chunks.jsonl

Same per-page deep-link convention as the AI Index processor: bot
renders citations as <source_url>#page=<slide_number>.
"""

from __future__ import annotations

import json
from pathlib import Path

import fitz

RAW = Path("data/raw/consulting")
OUT = Path("data/processed/consulting")


def extract_pdf(path: Path):
    doc = fitz.open(path)
    try:
        for i, page in enumerate(doc, 1):
            yield i, page.get_text()
    finally:
        doc.close()


def process_report(manifest_path: Path) -> tuple[Path, int]:
    manifest = json.loads(manifest_path.read_text())
    slug = manifest["doc_id"]
    out_path = OUT / f"{slug}.chunks.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    base = {
        "corpus": "consulting",
        "doc_title": manifest["title"],
        "source_url": manifest["source_url"],
        "publisher": manifest.get("publisher"),
        "fetched_at": manifest["fetched_at"],
        "published_at": manifest.get("published_at"),
        "license": manifest.get("license"),
    }

    pdf_path = manifest_path.parent / "report.pdf"
    chunks: list[dict] = []
    for n, text in extract_pdf(pdf_path):
        if not text.strip():
            continue
        chunks.append({
            **base,
            "id": f"{slug}::page-{n:03d}",
            "section_path": f"page:{n}",
            "slide_number": n,
            "text": text,
        })

    with out_path.open("w") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    return out_path, len(chunks)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    total = 0
    manifests = sorted(RAW.glob("*/manifest.json"))
    for m in manifests:
        out_path, n = process_report(m)
        total += n
        print(f"{out_path}: {n} chunks")
    print(f"\nTotal: {total} chunks across {len(manifests)} report(s)")


if __name__ == "__main__":
    main()
