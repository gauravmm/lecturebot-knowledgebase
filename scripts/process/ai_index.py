"""Marshal the Stanford HAI AI Index PDF into per-page JSONL chunks.

For each year subdir under data/raw/ai_index/<year>/:
  - read manifest.json
  - emit one chunk per PDF page from report.pdf

Output: data/processed/ai_index/<year>.chunks.jsonl

Citation deep-link convention: bot renders the source as
`<source_url>#page=<slide_number>`. Most PDF viewers (Chrome, Adobe,
Telegram in-app preview) honor the fragment.
"""

from __future__ import annotations

import json
from pathlib import Path

import fitz

RAW = Path("data/raw/ai_index")
OUT = Path("data/processed/ai_index")


def extract_pdf(path: Path):
    doc = fitz.open(path)
    try:
        for i, page in enumerate(doc, 1):
            yield i, page.get_text()
    finally:
        doc.close()


def process_year(manifest_path: Path) -> tuple[Path, int]:
    manifest = json.loads(manifest_path.read_text())
    year_dir = manifest_path.parent
    year = year_dir.name
    out_path = OUT / f"{year}.chunks.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    base = {
        "corpus": "ai_index",
        "doc_title": manifest["title"],
        "source_url": manifest["source_url"],
        "publisher": manifest.get("publisher"),
        "fetched_at": manifest["fetched_at"],
        "published_at": manifest.get("published_at"),
        "license": manifest.get("license"),
    }

    pdf_path = year_dir / "report.pdf"
    chunks: list[dict] = []
    for n, text in extract_pdf(pdf_path):
        if not text.strip():
            continue
        chunks.append({
            **base,
            "id": f"ai_index_{year}::page-{n:03d}",
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
        out_path, n = process_year(m)
        total += n
        print(f"{out_path}: {n} chunks")
    print(f"\nTotal: {total} chunks across {len(manifests)} year(s)")


if __name__ == "__main__":
    main()
