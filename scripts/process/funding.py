"""Marshal the E3 funding/Crunchbase News corpus into JSONL chunks.

For each subdir under data/raw/funding/<slug>/:
  - read manifest.json
  - extract clean prose from page.html using bs4 — Crunchbase News
    uses a standard `<article>` container, drop nav/header/footer/etc.
  - emit one chunk per article to data/processed/funding/<slug>.chunks.jsonl
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from bs4 import BeautifulSoup

RAW = Path("data/raw/funding")
OUT = Path("data/processed/funding")

DROP_TAGS = (
    "nav", "header", "footer", "aside", "script", "style", "form",
    "iframe", "svg", "button", "noscript", "figure",
)


def _normalize(text: str) -> str:
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_prose(html: str) -> str:
    s = BeautifulSoup(html, "lxml")
    root = s.find("article") or s.find("main") or s.body
    for tag in root.find_all(DROP_TAGS):
        tag.decompose()
    return _normalize(root.get_text("\n"))


def process_article(manifest_path: Path) -> tuple[Path, int, int]:
    manifest = json.loads(manifest_path.read_text())
    slug = manifest["doc_id"]
    out_path = OUT / f"{slug}.chunks.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    page_path = manifest_path.parent / "page.html"
    prose = _extract_prose(page_path.read_text(errors="replace"))

    chunks: list[dict] = []
    if prose:
        chunks.append({
            "corpus": "funding",
            "id": f"funding::{slug}",
            "doc_title": manifest["title"],
            "publisher": manifest["publisher"],
            "category": manifest["category"],
            "geography": manifest.get("geography"),
            "year_or_period": manifest.get("year_or_period"),
            "source_url": manifest["source_url"],
            "fetched_at": manifest["fetched_at"],
            "license": manifest.get("license"),
            "section_path": "article",
            "text": prose,
        })

    with out_path.open("w") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    return out_path, len(chunks), len(prose)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    total = 0
    thin: list[tuple[str, int]] = []
    manifests = sorted(RAW.glob("*/manifest.json"))
    for m in manifests:
        out_path, n, prose_len = process_article(m)
        total += n
        flag = ""
        if prose_len < 1000:
            thin.append((m.parent.name, prose_len))
            flag = "  ⚠ THIN"
        print(f"{out_path}: {n} chunks, {prose_len:>7,} chars{flag}")
    print(f"\nTotal: {total} funding chunks across {len(manifests)} articles")
    if thin:
        print(f"\n{len(thin)} article(s) produced <1000 chars (likely extraction issue):")
        for slug, n in thin:
            print(f"  {slug}: {n} chars")


if __name__ == "__main__":
    main()
