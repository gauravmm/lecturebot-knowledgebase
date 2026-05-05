"""Marshal the B2 earnings-call corpus into JSONL chunks.

Four input shapes per `manifest.transcript_kind`:

  - "full_qanda"        — Microsoft .docx with full transcript including
                          Q&A. Chunk on speaker-turn boundaries
                          (paragraphs whose first run is the speaker's
                          name in caps), tag each chunk with
                          speaker_role: prepared | analyst | operator |
                          ceo | cfo.

  - "prepared_remarks"  — IBM .pdf (prepared remarks only, no Q&A).
                          PyMuPDF text extraction; chunk by paragraph
                          windows of ~250 words.

  - "cfo_commentary"    — NVIDIA HTML (8-K Exhibit 99.2). Section-aware
                          chunking by H2/H3 in the HTML.

  - "ceo_quote_article" — Amazon `aboutamazon.com` short article with
                          embedded Andy Jassy quotes. One chunk per
                          article (similar to essays).

Output: data/processed/earnings/<slug>.chunks.jsonl
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import fitz
from bs4 import BeautifulSoup
from docx import Document

RAW = Path("data/raw/earnings")
OUT = Path("data/processed/earnings")

# ~250 words per chunk for prepared-remarks paragraphs without speaker
# turns. ~280-word ceiling matches the YouTube processor.
WORD_TARGET = 220
WORD_MAX = 320

DROP_TAGS = (
    "nav", "header", "footer", "aside", "script", "style", "form",
    "iframe", "svg", "button", "noscript",
)


def _normalize(text: str) -> str:
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# --- MSFT .docx ----------------------------------------------------------- #


# Speaker-line patterns at the start of a transcript paragraph. MSFT's
# transcripts use mixed-case names and the word "Operator" before colons.
# Examples:
#   "Brett Iversen, Vice President of Investor Relations:"
#   "Satya Nadella, Chairman and Chief Executive Officer:"
#   "Operator:"
SPEAKER_RE = re.compile(
    r"^([A-Z][A-Za-z'\.\- ]{2,80}?)(?:,\s*[A-Z][A-Za-z &'\.\-,]+)?\s*:\s*"
)


def _classify_speaker(name: str, title: str) -> str:
    nm = name.lower()
    ttl = (title or "").lower()
    if "operator" in nm:
        return "operator"
    if "chief executive" in ttl or "ceo" in ttl or "chairman" in ttl:
        return "ceo"
    if "chief financial" in ttl or "cfo" in ttl:
        return "cfo"
    if "investor relations" in ttl or "head of ir" in ttl:
        return "investor-relations"
    # Any name + no-MSFT-title is most likely a sell-side analyst.
    return "analyst"


def _extract_docx_turns(path: Path) -> list[tuple[str, str, str]]:
    """Return [(speaker_name, role, text)] for each speaker turn in
    a MSFT-style transcript. Consecutive paragraphs from the same
    speaker are merged into one turn."""
    doc = Document(path)
    turns: list[list[str]] = []
    last_speaker: tuple[str, str] | None = None
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        m = SPEAKER_RE.match(text)
        if m:
            speaker = m.group(1).strip()
            # Title is whatever's between speaker name and the colon.
            colon = text.find(":")
            full_prefix = text[:colon]
            title_part = full_prefix[len(speaker):].lstrip(",").strip()
            role = _classify_speaker(speaker, title_part)
            body = text[colon + 1 :].strip()
            if last_speaker == (speaker, role):
                if body:
                    turns[-1].append(body)
            else:
                last_speaker = (speaker, role)
                turns.append([f"__SPEAKER__{speaker}|{role}", body] if body else [f"__SPEAKER__{speaker}|{role}"])
        else:
            # Continuation of previous turn (paragraph break inside speaker block)
            if turns:
                turns[-1].append(text)
            else:
                # Pre-amble before any speaker line — bucket as preamble
                turns.append(["__SPEAKER__Preamble|prepared", text])
                last_speaker = ("Preamble", "prepared")
    out: list[tuple[str, str, str]] = []
    for chunks in turns:
        header = chunks[0]
        if not header.startswith("__SPEAKER__"):
            speaker, role = "Unknown", "prepared"
            body = " ".join(chunks)
        else:
            tag = header[len("__SPEAKER__"):]
            speaker, role = tag.split("|", 1)
            body = " ".join(chunks[1:]).strip()
        if body:
            out.append((speaker, role, body))
    return out


def _process_docx(slug: str, base: dict, file_path: Path) -> list[dict]:
    turns = _extract_docx_turns(file_path)
    chunks: list[dict] = []
    for i, (speaker, role, body) in enumerate(turns):
        # Sub-chunk overlong turns
        for j, sub in enumerate(_split_words(body)):
            chunks.append({
                **base,
                "id": f"earnings::{slug}::{i:03d}-{j:02d}",
                "section_path": f"{speaker}",
                "speaker_name": speaker,
                "speaker_role": role,
                "turn_index": i,
                "text": sub,
            })
    return chunks


def _split_words(text: str) -> list[str]:
    words = text.split()
    if len(words) <= WORD_MAX:
        return [text]
    out: list[str] = []
    cur: list[str] = []
    for w in words:
        cur.append(w)
        if len(cur) >= WORD_TARGET:
            out.append(" ".join(cur))
            cur = []
    if cur:
        out.append(" ".join(cur))
    return out


# --- IBM .pdf ------------------------------------------------------------- #


def _process_pdf(slug: str, base: dict, file_path: Path) -> list[dict]:
    doc = fitz.open(file_path)
    try:
        full = "\n".join(_normalize(doc[pi].get_text()) for pi in range(doc.page_count))
    finally:
        doc.close()
    # Split into paragraphs, then group into ~220-word windows.
    paras = [p for p in re.split(r"\n{2,}", full) if p.strip()]
    chunks: list[dict] = []
    cur: list[str] = []
    cur_words = 0
    chunk_idx = 0
    for p in paras:
        cur.append(p)
        cur_words += len(p.split())
        if cur_words >= WORD_TARGET:
            chunks.append({
                **base,
                "id": f"earnings::{slug}::{chunk_idx:03d}",
                "section_path": f"window {chunk_idx + 1}",
                "speaker_role": "prepared",
                "text": "\n\n".join(cur),
            })
            chunk_idx += 1
            cur = []
            cur_words = 0
    if cur:
        chunks.append({
            **base,
            "id": f"earnings::{slug}::{chunk_idx:03d}",
            "section_path": f"window {chunk_idx + 1}",
            "speaker_role": "prepared",
            "text": "\n\n".join(cur),
        })
    return chunks


# --- NVDA cfo_commentary HTML --------------------------------------------- #


# NVDA's CFO commentary HTML is heavily-tabled iXBRL with NO h1/h2/h3
# and no <p> tags — section structure is implicit in bold-faced row
# titles inside the tables. Heuristic: split on heading-shaped lines
# (capitalized phrases of 3-12 words, no terminal punctuation, often
# starting with "Q<n>" / "Outlook" / "Highlights" / "Summary").
NVDA_HEADING_RE = re.compile(
    r"\b("
    r"(?:Q[1-4]\s+(?:Fiscal\s+)?\d{4}\s+(?:Summary|Highlights|Outlook|Cash\s+Flow|Return\s+to\s+Shareholders))"
    r"|Outlook"
    r"|Capital\s+Return"
    r"|GAAP\s+Tax\s+Rate"
    r"|Quarterly\s+(?:Cash\s+Flow|Return\s+to\s+Shareholders|Highlights)"
    r")\b"
)


def _process_cfo_html(slug: str, base: dict, file_path: Path) -> list[dict]:
    s = BeautifulSoup(file_path.read_text(errors="replace"), "lxml")
    body = s.body or s
    for tag in body.find_all(DROP_TAGS):
        tag.decompose()
    full = _normalize(body.get_text(" "))
    # Find heading positions; slice the doc into sections at those points.
    matches = list(NVDA_HEADING_RE.finditer(full))
    sections: list[tuple[str, str]] = []
    if matches:
        # Pre-amble before first heading.
        if matches[0].start() > 200:
            sections.append(("Preamble", full[: matches[0].start()].strip()))
        for i, m in enumerate(matches):
            heading = m.group(0)
            start = m.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(full)
            sections.append((heading, full[start:end].strip()))
    else:
        sections.append(("Document", full))
    chunks: list[dict] = []
    chunk_idx = 0
    for heading, body_text in sections:
        # Sub-chunk if section blows past WORD_MAX.
        for sub in _split_words(body_text):
            if len(sub) < 80:
                continue
            chunks.append({
                **base,
                "id": f"earnings::{slug}::{chunk_idx:03d}",
                "section_path": heading[:120],
                "speaker_role": "prepared",
                "text": sub,
            })
            chunk_idx += 1
    return chunks


# --- AMZN ceo_quote_article HTML ------------------------------------------ #


def _process_amzn_html(slug: str, base: dict, file_path: Path) -> list[dict]:
    s = BeautifulSoup(file_path.read_text(errors="replace"), "lxml")
    root = s.find("article") or s.find("main") or s.body
    for tag in root.find_all(DROP_TAGS):
        tag.decompose()
    text = _normalize(root.get_text("\n"))
    if len(text) < 200:
        return []
    return [{
        **base,
        "id": f"earnings::{slug}",
        "section_path": "article",
        "speaker_role": "ceo",
        "speaker_name": "Andy Jassy",
        "text": text,
    }]


# --- Driver --------------------------------------------------------------- #


KIND_PROCESSORS = {
    "full_qanda": _process_docx,
    "prepared_remarks": _process_pdf,
    "cfo_commentary": _process_cfo_html,
    "ceo_quote_article": _process_amzn_html,
}


def process_filing(manifest_path: Path) -> tuple[Path, int]:
    manifest = json.loads(manifest_path.read_text())
    slug = manifest["doc_id"]
    kind = manifest["transcript_kind"]
    file_path = manifest_path.parent / manifest["files"][0]["path"]
    out_path = OUT / f"{slug}.chunks.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    base = {
        "corpus": "earnings",
        "doc_title": manifest["title"],
        "ticker": manifest["ticker"],
        "company_name": manifest["company_name"],
        "fiscal_period": manifest["fiscal_period"],
        "calendar_quarter_end": manifest["calendar_quarter_end"],
        "transcript_kind": kind,
        "source_url": manifest["source_url"],
        "fetched_at": manifest["fetched_at"],
        "license": manifest.get("license"),
    }

    proc = KIND_PROCESSORS.get(kind)
    if proc is None:
        print(f"skip (no processor for kind={kind})  {slug}")
        return out_path, 0
    chunks = proc(slug, base, file_path)
    with out_path.open("w") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    return out_path, len(chunks)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    total = 0
    for m in sorted(RAW.glob("*/manifest.json")):
        out_path, n = process_filing(m)
        print(f"{out_path}: {n} chunks")
        total += n
    print(f"\nTotal: {total} earnings chunks")


if __name__ == "__main__":
    main()
