"""Marshal the C2 + C3 essay corpus into per-essay JSONL chunks.

For each subdir under data/raw/essays/<slug>/:
  - read manifest.json
  - extract clean prose from page.html using bs4 (drop nav, header,
    footer, aside, script, style, form, iframe, figure, svg, button)
  - emit one chunk per essay to data/processed/essays/<slug>.chunks.jsonl

Single-chunk-per-essay; some long essays (Sequoia $600B, a16z
"New Business of AI") will exceed the 800-token cap. The token-aware
re-chunking pass (PROGRESS.md "Not done" §3) will handle them along
with the other over-cap chunks already accumulated in the corpus.

A best-effort common-content selector tries (in order):
    <article> → <main> → div.post / div.entry-content /
    div.post-content / div.article-body / div.content → body
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from bs4 import BeautifulSoup, Tag

RAW = Path("data/raw/essays")
OUT = Path("data/processed/essays")

DROP_TAGS = (
    "nav",
    "header",
    "footer",
    "aside",
    "script",
    "style",
    "form",
    "iframe",
    "figure",
    "svg",
    "button",
    "noscript",
)
CONTENT_CLASS_RE = re.compile(
    r"(post-content|entry-content|article-body|article-content|"
    r"main-content|prose|post|entry|article)\b",
    re.I,
)


def _normalize(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _content_root(soup: BeautifulSoup) -> Tag:
    article = soup.find("article")
    if article is not None:
        return article
    main = soup.find("main")
    if main is not None:
        return main
    for class_attr in (
        "entry-content",
        "post-content",
        "article-body",
        "article-content",
        "main-content",
        "prose",
        "post",
        "entry",
        "article",
    ):
        node = soup.find("div", class_=class_attr)
        if node is not None:
            return node
    # Last resort: any div whose class matches the regex.
    for div in soup.find_all("div"):
        klass = " ".join(div.get("class") or [])
        if klass and CONTENT_CLASS_RE.search(klass):
            return div
    return soup.body or soup


def _extract_prose(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    root = _content_root(soup)
    for tag in root.find_all(DROP_TAGS):
        tag.decompose()
    return _normalize(root.get_text("\n"))


def process_essay(manifest_path: Path) -> tuple[Path, int, int, str | None]:
    manifest = json.loads(manifest_path.read_text())
    slug = manifest["doc_id"]
    out_path = OUT / f"{slug}.chunks.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    page_path = manifest_path.parent / "page.html"
    if not page_path.exists():
        if out_path.exists():
            out_path.unlink()
        return out_path, 0, 0, "missing page.html"

    prose = _extract_prose(page_path.read_text(errors="replace"))

    base = {
        "corpus": "essays",
        "doc_title": manifest["title"],
        "author": manifest.get("author"),
        "publisher": manifest.get("publisher"),
        "category": manifest.get("category"),
        "source_url": manifest["source_url"],
        "fetched_at": manifest["fetched_at"],
        "published_at": manifest.get("published_at"),
        "license": manifest.get("license"),
    }

    chunks: list[dict] = []
    if prose:
        chunks.append({
            **base,
            "id": f"essays::{slug}",
            "section_path": "prose",
            "text": prose,
        })

    with out_path.open("w") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    return out_path, len(chunks), len(prose), None


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    total_chunks = 0
    thin: list[tuple[str, int]] = []
    skipped: list[tuple[str, str]] = []
    for m in sorted(RAW.glob("*/manifest.json")):
        out_path, n, prose_len, skip_reason = process_essay(m)
        if skip_reason is not None:
            skipped.append((m.parent.name, skip_reason))
            print(f"skip  {m.parent.name}: {skip_reason}")
            continue
        total_chunks += n
        flag = ""
        if prose_len < 500:
            thin.append((m.parent.name, prose_len))
            flag = "  ⚠ THIN"
        print(f"{out_path}: {n} chunks, {prose_len:>7,} chars of prose{flag}")
    print(
        f"\nTotal: {total_chunks} chunks across "
        f"{len(list(RAW.glob('*/manifest.json'))) - len(skipped)} processed essays"
    )
    if skipped:
        print(f"\n{len(skipped)} essays skipped:")
        for slug, reason in skipped:
            print(f"  {slug}: {reason}")
    if thin:
        print(f"\n{len(thin)} essays produced <500 chars of prose:")
        for slug, n in thin:
            print(f"  {slug}: {n} chars")


if __name__ == "__main__":
    main()
