"""Marshal the B3 shareholder-letter corpus into JSONL chunks.

Three input shapes per `manifest.format`:
  - "html"    — Bezos standalone HTML on aboutamazon.com. Take the
                <article>/<main> body, drop chrome, one chunk per
                letter.
  - "html-ar" — Nadella annual-report HTML on microsoft.com. The
                letter section is anchored at #shareholder-letter
                inside the page; slice that subtree, one chunk per
                letter.
  - "pdf-ar"  — Bezos annual-report PDF on Q4 CDN. The Bezos letter
                runs from page 1 ("To our shareowners:") to a
                "Sincerely, Jeff Bezos" / "Jeffrey P. Bezos / Founder
                & CEO" sign-off, then the AR financials begin. Slice
                between those markers, one chunk per letter.

Output: data/processed/letters/<slug>.chunks.jsonl (one chunk each;
some Bezos AR letters span 4-5 pages and exceed the 800-token cap —
they go into the future re-chunking pass with the other long-form
content).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import fitz
from bs4 import BeautifulSoup

RAW = Path("data/raw/letters")
OUT = Path("data/processed/letters")

DROP_TAGS = (
    "nav", "header", "footer", "aside", "script", "style", "form",
    "iframe", "svg", "button", "noscript",
)


def _normalize(text: str) -> str:
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_html(raw: str) -> str:
    s = BeautifulSoup(raw, "lxml")
    root = s.find("article") or s.find("main") or s.body
    for tag in root.find_all(DROP_TAGS):
        tag.decompose()
    return _normalize(root.get_text("\n"))


def _extract_html_ar(raw: str) -> str:
    """Microsoft annual-report HTML: the letter section is the
    #shareholder-letter element. Fall back to the whole body if absent."""
    s = BeautifulSoup(raw, "lxml")
    sl = s.find(id="shareholder-letter")
    if sl is None:
        # Fall back: find a heading containing "shareholders" and slice from there.
        sl = s.body
    for tag in sl.find_all(DROP_TAGS):
        tag.decompose()
    return _normalize(sl.get_text("\n"))


# Bezos sign-off — appears as the last line of the letter before the
# financial section begins. Spellings vary by year:
#   - "Sincerely, / Jeffrey P. Bezos / Founder and Chief Executive Officer / Amazon.com, Inc."
#   - "Jeff Bezos / Founder & CEO" (2018+)
#   - "Jeff Bezos / Founder and Executive Chairman" (2020 final letter)
# Notably, Bezos often appends the original 1997 letter at the end of
# annual letters — that produces a second sign-off later. We want the
# FIRST match, which `re.search` returns.
SIGNOFF_RE = re.compile(
    r"(Jeff(?:rey)?\s+(?:P\.\s+)?Bezos\s*\n+\s*"
    r"(?:Founder\s*(?:&|and)\s*(?:CEO|Chief\s+Executive\s+Officer|"
    r"Executive\s+Chair(?:man)?))"
    r"(?:\s*\n+\s*Amazon\.com,?\s+Inc\.?)?)",
    re.I,
)


def _extract_pdf_ar(pdf_path: Path) -> str:
    """Bezos annual-report PDF: letter is on the first few pages,
    runs until 'Sincerely, Jeffrey P. Bezos / Founder & CEO'. Walk
    pages until we find the sign-off, then slice the cumulative text
    up to and including that line."""
    doc = fitz.open(pdf_path)
    try:
        chunks: list[str] = []
        signoff_seen = False
        for pi in range(min(15, doc.page_count)):
            page_text = doc[pi].get_text()
            chunks.append(page_text)
            if SIGNOFF_RE.search("\n".join(chunks)):
                signoff_seen = True
                break
        full = "\n".join(chunks)
    finally:
        doc.close()
    if signoff_seen:
        m = SIGNOFF_RE.search(full)
        # Slice from start to end of sign-off match.
        full = full[: m.end()]
    return _normalize(full)


EXTRACTORS = {
    "html": lambda p: _extract_html(p.read_text(errors="replace")),
    "html-ar": lambda p: _extract_html_ar(p.read_text(errors="replace")),
    "pdf-ar": lambda p: _extract_pdf_ar(p),
}


def process_letter(manifest_path: Path) -> tuple[Path, int, int]:
    manifest = json.loads(manifest_path.read_text())
    slug = manifest["doc_id"]
    fmt = manifest["format"]
    file_path = manifest_path.parent / manifest["files"][0]["path"]
    out_path = OUT / f"{slug}.chunks.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    extractor = EXTRACTORS.get(fmt)
    if extractor is None:
        print(f"skip (no extractor for format={fmt})  {slug}")
        return out_path, 0, 0
    text = extractor(file_path)

    if not text or len(text) < 300:
        out_path.write_text("")
        return out_path, 0, len(text)

    chunk = {
        "corpus": "letters",
        "id": f"letters::{slug}",
        "doc_title": manifest["title"],
        "author": manifest["author"],
        "publisher": manifest["publisher"],
        "letter_year": manifest["letter_year"],
        "source_url": manifest["source_url"],
        "fetched_at": manifest["fetched_at"],
        "license": manifest.get("license"),
        "section_path": "letter",
        "text": text,
    }
    with out_path.open("w") as f:
        f.write(json.dumps(chunk, ensure_ascii=False) + "\n")
    return out_path, 1, len(text)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    total = 0
    thin: list[tuple[str, int]] = []
    for m in sorted(RAW.glob("*/manifest.json")):
        out_path, n, prose_len = process_letter(m)
        total += n
        flag = ""
        if prose_len < 1000:
            thin.append((m.parent.name, prose_len))
            flag = "  ⚠ THIN"
        print(f"{out_path}: {n} chunks, {prose_len:>7,} chars{flag}")
    print(f"\nTotal: {total} letter chunks")
    if thin:
        print(f"\n{len(thin)} letter(s) produced <1000 chars (likely extraction issue):")
        for slug, n in thin:
            print(f"  {slug}: {n} chars")


if __name__ == "__main__":
    main()
