"""Central citation builder for retrieval metadata.

Citations are derived from stable chunk metadata rather than baked into
each processor. That keeps the formatting repeatable as the corpus
shifts and lets us evolve citation policy in one place.
"""

from __future__ import annotations

from html import escape
from urllib.parse import urlparse


def _is_pdf_url(url: str | None) -> bool:
    if not url:
        return False
    return urlparse(url).path.lower().endswith(".pdf")


def _format_timestamp(seconds: int | float | None) -> str | None:
    if seconds is None:
        return None
    total = int(seconds)
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _link(url: str | None, text: str | None) -> str | None:
    if not url or not text:
        return None
    return f'<a href="{escape(url, quote=True)}">{escape(text)}</a>'


def _doc_title(row: dict) -> str | None:
    title = row.get("doc_title")
    if title is None:
        return None
    title = str(title).strip()
    return title or None


def build_citation(row: dict) -> tuple[str | None, str | None, str | None]:
    """Return `(citation_url, citation_text, citation_html)` for one chunk."""
    corpus = row.get("corpus")
    title = _doc_title(row)
    source_url = row.get("source_url")
    slide_number = row.get("slide_number")
    t_start_seconds = row.get("t_start_seconds")

    if corpus == "memes":
        return None, None, None

    if corpus == "lecturer/lectures":
        text = title
        if text and slide_number is not None:
            text = f"{text}, slide {int(slide_number)}"
        return source_url, text, _link(source_url, text)

    if corpus == "youtube":
        timestamp = _format_timestamp(t_start_seconds)
        text = title
        if text and timestamp:
            text = f"{text}, {timestamp}"
        return source_url, text, _link(source_url, text)

    if _is_pdf_url(source_url) and slide_number is not None:
        citation_url = f"{source_url}#page={int(slide_number)}"
        text = title
        if text:
            text = f"{text}, p. {int(slide_number)}"
        return citation_url, text, _link(citation_url, text)

    return source_url, title, _link(source_url, title)
