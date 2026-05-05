"""Marshal the F2 regulation corpus into JSONL chunks.

Five `manifest.format` shapes:
  - "pdf-nist"        — NIST AI RMF / NIST.AI.600-1. Per-page chunking
                        like the AI Index processor; deep-link via
                        <source_url>#page=N.
  - "pdf-eo"          — Biden EO 14110 (Federal Register PDF). Per-page
                        chunking; same deep-link convention.
  - "pdf-action-plan" — White House America's AI Action Plan PDF.
                        Per-page chunking.
  - "html-eo"         — Trump 2025 AI executive orders on whitehouse.gov.
                        Single chunk per EO from the <main> body.
  - "html-eu"         — EU AI Act articles + annexes via the FoLI
                        explorer. Single chunk per article/annex from
                        `div.et_pb_post_content` (Divi WordPress theme).
  - "html-iso"        — ISO/IEC 42001 abstract page. Single chunk from
                        the <main> block.

Output: data/processed/regulation/<slug>.chunks.jsonl
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import fitz
from bs4 import BeautifulSoup

RAW = Path("data/raw/regulation")
OUT = Path("data/processed/regulation")

DROP_TAGS = (
    "nav", "header", "footer", "aside", "script", "style", "form",
    "iframe", "svg", "button", "noscript", "figure",
)


def _normalize(text: str) -> str:
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_html_eo(raw: str) -> str:
    s = BeautifulSoup(raw, "lxml")
    root = s.find("main") or s.body
    for tag in root.find_all(DROP_TAGS):
        tag.decompose()
    return _normalize(root.get_text("\n"))


def _extract_html_eu(raw: str) -> str:
    s = BeautifulSoup(raw, "lxml")
    root = s.select_one("div.et_pb_post_content") or s.find("main") or s.body
    for tag in root.find_all(DROP_TAGS):
        tag.decompose()
    return _normalize(root.get_text("\n"))


def _extract_html_iso(raw: str) -> str:
    s = BeautifulSoup(raw, "lxml")
    root = s.find("main") or s.body
    for tag in root.find_all(DROP_TAGS):
        tag.decompose()
    return _normalize(root.get_text("\n"))


def _process_pdf_per_page(manifest: dict, slug: str, pdf_path: Path) -> list[dict]:
    base = {
        "corpus": "regulation",
        "doc_title": manifest["title"],
        "author": manifest.get("author"),
        "publisher": manifest["publisher"],
        "category": manifest["category"],
        "source_url": manifest["source_url"],
        "fetched_at": manifest["fetched_at"],
        "published_at": manifest.get("published_at"),
        "license": manifest["license"],
    }
    chunks: list[dict] = []
    doc = fitz.open(pdf_path)
    try:
        for n, page in enumerate(doc, 1):
            text = page.get_text()
            if not text.strip():
                continue
            chunks.append({
                **base,
                "id": f"regulation::{slug}::page-{n:03d}",
                "section_path": f"page:{n}",
                "slide_number": n,
                "text": _normalize(text),
            })
    finally:
        doc.close()
    return chunks


def _process_html_one_chunk(manifest: dict, slug: str, html_path: Path, extractor) -> list[dict]:
    text = extractor(html_path.read_text(errors="replace"))
    if not text or len(text) < 200:
        return []
    chunk = {
        "corpus": "regulation",
        "id": f"regulation::{slug}",
        "doc_title": manifest["title"],
        "author": manifest.get("author"),
        "publisher": manifest["publisher"],
        "category": manifest["category"],
        "source_url": manifest["source_url"],
        "fetched_at": manifest["fetched_at"],
        "published_at": manifest.get("published_at"),
        "license": manifest["license"],
        "section_path": manifest.get("section_kind") or "body",
        "text": text,
    }
    if manifest.get("section_kind"):
        chunk["section_kind"] = manifest["section_kind"]
        chunk["section_number"] = manifest["section_number"]
    return [chunk]


PDF_FORMATS = {"pdf-nist", "pdf-eo", "pdf-action-plan"}
HTML_EXTRACTORS = {
    "html-eo": _extract_html_eo,
    "html-eu": _extract_html_eu,
    "html-iso": _extract_html_iso,
}


def process_doc(manifest_path: Path) -> tuple[Path, int, int]:
    manifest = json.loads(manifest_path.read_text())
    slug = manifest["doc_id"]
    fmt = manifest["format"]
    file_path = manifest_path.parent / manifest["files"][0]["path"]
    out_path = OUT / f"{slug}.chunks.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if fmt in PDF_FORMATS:
        chunks = _process_pdf_per_page(manifest, slug, file_path)
    elif fmt in HTML_EXTRACTORS:
        chunks = _process_html_one_chunk(
            manifest, slug, file_path, HTML_EXTRACTORS[fmt]
        )
    else:
        print(f"skip (no extractor for format={fmt})  {slug}")
        return out_path, 0, 0

    total_chars = sum(len(c["text"]) for c in chunks)
    with out_path.open("w") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    return out_path, len(chunks), total_chars


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    total = 0
    thin: list[tuple[str, int]] = []
    manifests = sorted(RAW.glob("*/manifest.json"))
    for m in manifests:
        out_path, n, prose_len = process_doc(m)
        total += n
        flag = ""
        if n == 1 and prose_len < 500:
            thin.append((m.parent.name, prose_len))
            flag = "  ⚠ THIN"
        print(f"{out_path}: {n} chunks, {prose_len:>7,} chars{flag}")
    print(f"\nTotal: {total} regulation chunks across {len(manifests)} docs")
    if thin:
        print(f"\n{len(thin)} doc(s) produced <500 chars (likely extraction issue):")
        for slug, n in thin:
            print(f"  {slug}: {n} chars")


if __name__ == "__main__":
    main()
