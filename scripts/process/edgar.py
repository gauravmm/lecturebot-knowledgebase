"""Marshal SEC EDGAR 10-K/10-Q filings into per-Item JSONL chunks.

10-K and 10-Q filings are filed as inline-XBRL HTML — a giant single
document where structure is communicated mostly by `Item N. <Title>`
section headings repeated in a TOC and again as body headers.

Strategy:
  1. Strip iXBRL noise + render to plain text.
  2. Find every `Item N` occurrence (line-anchored).
  3. For each Item number, take the SECOND occurrence as the section
     body start (first is the TOC entry, second is the body header).
     If there's only one occurrence, use that.
  4. The section body runs from its body-start to the next section's
     body-start. Slice and emit one chunk per section.
  5. Tag each chunk with ticker, form, period, and a priority flag for
     the canonical investor sections (1, 1A, 7, 7A, 8 for 10-K;
     part1.1, part1.2, part1.3, part1.4, part2.1, part2.1A for 10-Q).

For 10-Q the same `Item N` regex catches Part I and Part II items;
they're disambiguated by which Part heading precedes them.

Output: data/processed/edgar/<TICKER>/<form>_<period>.chunks.jsonl
"""

from __future__ import annotations

import json
import re
import warnings
from pathlib import Path

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

RAW = Path("data/raw/edgar")
OUT = Path("data/processed/edgar")

# Priority sections per spec/ROUGH.md §2.2 — the ones investors and
# students actually read. Tag chunks so retrieval can boost them.
PRIORITY_10K = {"1", "1A", "7", "7A", "8"}
PRIORITY_10Q = {"part1.1", "part1.2", "part1.3", "part1.4", "part2.1", "part2.1A"}

# Loose `Item N.` line matcher (handles "Item", "ITEM", varying punctuation).
ITEM_LINE_RE = re.compile(
    r"(?im)^\s*item\s+(\d+[A-Z]?)\.?\s*[—\-:]?\s*(.{0,200})$"
)
# `PART I` / `PART II` headings used by 10-Q to disambiguate Items.
PART_LINE_RE = re.compile(r"(?im)^\s*part\s+(I|II|III|IV)\b\s*(.{0,80})$")


def _normalize(text: str) -> str:
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _html_to_text(html: str) -> str:
    s = BeautifulSoup(html, "lxml")
    # Drop script/style; keep tables (financial summary text is in tables).
    for tag in s.find_all(["script", "style"]):
        tag.decompose()
    return _normalize(s.get_text("\n"))


def _slice_sections_10k(text: str) -> list[tuple[str, int, int, str]]:
    """Returns [(item_id, start_pos, end_pos, heading_line)] for a 10-K.

    item_id is the Item number ("1", "1A", "7", ...). Section runs from
    its body-header start to the next section's body-header start, or to
    end of text for the last section.
    """
    matches = list(ITEM_LINE_RE.finditer(text))
    # Group by item_id, preserving order.
    by_item: dict[str, list[re.Match]] = {}
    for m in matches:
        by_item.setdefault(m.group(1).upper(), []).append(m)
    # Take the second occurrence as body start (first = TOC), or first if singular.
    body_starts: list[tuple[str, int, str]] = []
    for item_id, occs in by_item.items():
        body_match = occs[1] if len(occs) >= 2 else occs[0]
        body_starts.append((item_id, body_match.start(), body_match.group(0).strip()))
    # Sort by position so we can slice.
    body_starts.sort(key=lambda t: t[1])
    # Build sections: start to next section's start.
    sections: list[tuple[str, int, int, str]] = []
    for i, (item_id, start, heading) in enumerate(body_starts):
        end = body_starts[i + 1][1] if i + 1 < len(body_starts) else len(text)
        sections.append((item_id, start, end, heading))
    return sections


def _slice_sections_10q(text: str) -> list[tuple[str, int, int, str]]:
    """Like _slice_sections_10k but disambiguates Items by Part. The 10-Q
    has Part I (Financial Information) Items 1-4 and Part II (Other
    Information) Items 1-6.

    Returns item_ids like "part1.1", "part1.2", "part2.1" etc.
    """
    # Locate Part headings — second occurrence is the body header (first is TOC).
    part_matches = list(PART_LINE_RE.finditer(text))
    part_by_num: dict[str, list[re.Match]] = {}
    for m in part_matches:
        roman = m.group(1).upper()
        part_num = {"I": "1", "II": "2", "III": "3", "IV": "4"}[roman]
        part_by_num.setdefault(part_num, []).append(m)
    # Body-start for each Part = second occurrence (or first if singular).
    part_body_starts: list[tuple[str, int]] = []
    for part_num, occs in part_by_num.items():
        body = occs[1] if len(occs) >= 2 else occs[0]
        part_body_starts.append((part_num, body.start()))
    part_body_starts.sort(key=lambda t: t[1])
    # Pre-build a lookup: which Part is in effect at position p?
    def part_at(pos: int) -> str:
        last = "1"
        for part_num, p in part_body_starts:
            if p <= pos:
                last = part_num
            else:
                break
        return last

    matches = list(ITEM_LINE_RE.finditer(text))
    # Group by (part, item_id). Within each group, second occurrence is body.
    by_key: dict[str, list[re.Match]] = {}
    for m in matches:
        key = f"part{part_at(m.start())}.{m.group(1).upper()}"
        by_key.setdefault(key, []).append(m)
    body_starts: list[tuple[str, int, str]] = []
    for key, occs in by_key.items():
        body = occs[1] if len(occs) >= 2 else occs[0]
        body_starts.append((key, body.start(), body.group(0).strip()))
    body_starts.sort(key=lambda t: t[1])
    sections: list[tuple[str, int, int, str]] = []
    for i, (key, start, heading) in enumerate(body_starts):
        end = body_starts[i + 1][1] if i + 1 < len(body_starts) else len(text)
        sections.append((key, start, end, heading))
    return sections


def process_filing(manifest_path: Path) -> tuple[Path, int]:
    manifest = json.loads(manifest_path.read_text())
    ticker = manifest["ticker"]
    form = manifest["form"]
    period = manifest["report_date"]
    out_path = OUT / ticker / f"{form}_{period}.chunks.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    htm_path = manifest_path.parent / manifest["files"][0]["path"]
    if not htm_path.exists():
        # Raw is gitignored; if it's not on disk, nothing to do.
        out_path.write_text("")
        return out_path, 0

    text = _html_to_text(htm_path.read_text(errors="replace"))

    if form == "10-K":
        sections = _slice_sections_10k(text)
        priority = PRIORITY_10K
    else:  # 10-Q
        sections = _slice_sections_10q(text)
        priority = PRIORITY_10Q

    base = {
        "corpus": "edgar",
        "doc_title": f"{ticker} {form} {period}",
        "ticker": ticker,
        "company_name": manifest["company_name"],
        "form": form,
        "filing_date": manifest["filing_date"],
        "report_date": period,
        "accession": manifest["accession"],
        "source_url": manifest["source_url"],
        "fetched_at": manifest["fetched_at"],
        "license": manifest.get("license"),
    }

    chunks: list[dict] = []
    for item_id, start, end, heading in sections:
        body = text[start:end].strip()
        if len(body) < 200:  # skip TOC-only sections
            continue
        is_priority = item_id in priority
        chunks.append({
            **base,
            "id": f"edgar::{ticker}::{form}::{period}::item{item_id.lower()}",
            "section_path": heading[:120],
            "item": item_id,
            "is_priority_section": is_priority,
            "text": body,
        })

    with out_path.open("w") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    return out_path, len(chunks)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    total = 0
    skipped = 0
    for manifest_path in sorted(RAW.glob("*/*.json")):
        out_path, n = process_filing(manifest_path)
        if n == 0:
            skipped += 1
            print(f"skip  {manifest_path.parent.name}/{manifest_path.stem}")
            continue
        total += n
        print(f"  {manifest_path.parent.name}/{manifest_path.stem}: {n} chunks")
    print(f"\nTotal: {total} chunks ({skipped} filings skipped)")


if __name__ == "__main__":
    main()
