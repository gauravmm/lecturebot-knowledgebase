"""Marshal Our World in Data topic pages into JSONL chunks.

Currently handles a single page: Artificial Intelligence
(https://ourworldindata.org/artificial-intelligence). The OWID "topic
page" is a hub: it has its own lead prose plus a list of linked
sub-articles (each rendered as an H3 card with a short summary).

We emit two chunks per topic page:
  1. `prose` — the lead + chart-grid prose (excludes the H3-card list,
     navigation, footer endnotes/cite/reuse).
  2. `linked_articles` — the list of linked OWID articles, with their
     titles, summaries, and slugs. Useful when the bot wants to
     surface "OWID also writes about X" as a follow-on suggestion.

Plus the list of OWID Grapher chart slugs the page references is
inlined into the prose chunk so retrieval can match on chart names.

Citation deep-link: section anchor IDs are JS-rendered and not in
static HTML, so chunks cite the page URL only.

Output: data/processed/owid/<slug>.chunks.jsonl
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag

RAW = Path("data/raw/owid")
OUT = Path("data/processed/owid")

# H3 headings that mark sections we never want to ingest as content.
FOOTER_HEADINGS = {
    "endnotes",
    "cite this work",
    "reuse this work freely",
}


def _normalize(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _grapher_slugs(node: Tag) -> list[str]:
    slugs: list[str] = []
    for a in node.find_all("a", href=re.compile(r"/grapher/")):
        m = re.search(r"/grapher/([^?#\"']+)", a.get("href", ""))
        if m:
            slug = m.group(1)
            if slug not in slugs:
                slugs.append(slug)
    return slugs


def _strip_footer_sections(article: Tag) -> None:
    """Remove H3-headed sections whose title is in FOOTER_HEADINGS, in place."""
    for h3 in list(article.find_all("h3")):
        title = h3.get_text(" ", strip=True).lower()
        if title in FOOTER_HEADINGS:
            section = h3.find_parent("section") or h3.parent
            if section:
                section.decompose()


def _extract_linked_articles(article: Tag) -> tuple[list[dict], list[Tag]]:
    """Find the H3 cards that link to other OWID articles. Each card is an
    <a> wrapping an <h3> + summary <p>; href points at the linked article.
    Returns (cards, the_card_tags_to_remove)."""
    cards: list[dict] = []
    to_remove: list[Tag] = []
    for h3 in article.find_all("h3"):
        a = h3.find_parent("a")
        if not a or not a.get("href"):
            continue
        href = a["href"]
        # Skip same-page anchors / non-OWID-article links.
        if href.startswith("#") or "/grapher/" in href:
            continue
        title = h3.get_text(" ", strip=True)
        if not title:
            continue
        # Summary: find the first <p> sibling-ish in the card.
        summary = ""
        card_root = a if a.parent and a.parent.name in ("div", "section") else a
        p = card_root.find("p") if card_root else None
        if p:
            summary = p.get_text(" ", strip=True)
        cards.append({
            "title": title,
            "url": href if href.startswith("http") else f"https://ourworldindata.org{href}",
            "summary": summary,
        })
        # Mark the card's outer container for removal so it doesn't pollute prose.
        to_remove.append(card_root)
    return cards, to_remove


def process_page(html_path: Path, page_slug: str, base_meta: dict) -> tuple[Path, int]:
    out_path = OUT / f"{page_slug}.chunks.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    soup = BeautifulSoup(html_path.read_text(), "lxml")
    article = soup.find("article") or soup.find("main") or soup.body

    # Drop scripts, styles, nav, header, footer wrappers wholesale.
    for tag in article.find_all(["script", "style", "nav", "header", "footer"]):
        tag.decompose()

    _strip_footer_sections(article)
    cards, card_roots = _extract_linked_articles(article)

    # Compute prose BEFORE removing cards (we want their summary text gone
    # but the lead prose kept).
    for root in card_roots:
        root.decompose()

    prose_text = _normalize(article.get_text("\n"))
    slugs = _grapher_slugs(article)
    if slugs:
        prose_text += "\n\nReferenced OWID Grapher charts: " + ", ".join(slugs)

    chunks: list[dict] = []
    if prose_text:
        chunks.append({
            **base_meta,
            "id": f"owid::{page_slug}::prose",
            "section_path": "prose",
            "grapher_slugs": slugs,
            "text": prose_text,
        })

    if cards:
        card_lines = ["OWID articles linked from this topic page:\n"]
        for c in cards:
            line = f"- {c['title']}"
            if c["summary"]:
                line += f" — {c['summary']}"
            line += f" ({c['url']})"
            card_lines.append(line)
        chunks.append({
            **base_meta,
            "id": f"owid::{page_slug}::linked-articles",
            "section_path": "linked-articles",
            "linked_articles": cards,
            "text": "\n".join(card_lines),
        })

    with out_path.open("w") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    return out_path, len(chunks)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((RAW / "manifest.json").read_text())
    base_meta = {
        "corpus": "owid",
        "doc_title": manifest["title"],
        "source_url": manifest["source_url"],
        "publisher": manifest.get("publisher"),
        "fetched_at": manifest["fetched_at"],
        "license": manifest.get("license"),
    }
    page_slug = manifest["doc_id"]
    html_path = RAW / manifest["files"][0]["path"]
    out_path, n = process_page(html_path, page_slug, base_meta)
    print(f"{out_path}: {n} chunks")


if __name__ == "__main__":
    main()
