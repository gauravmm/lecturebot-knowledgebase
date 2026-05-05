"""Build chunk_meta.parquet — row-aligned with FAISS / BM25.

Carries the metadata superset called out in spec/ROUGH.md §2.2:
`corpus, doc_title, source_url, published_at, fetched_at,
section_path, slide_number, t_start_seconds, speaker_role`. Plus
per-corpus extras already present in the chunk JSONLs:
`is_priority_section`, `category`, `ticker`, `form`, `filing_date`,
`channel`, `video_id`, `subs_kind`, `author`, `letter_year`,
`speaker_name`, `transcript_kind`, `model_id` (vendors), `topics`
(memes), `image_path`, `part_of`, `part_index`, `part_count`,
`n_tokens`, the chunk `text` itself (so the export tarball is
self-contained — `fetch_doc` reads from this parquet, never from
`processed/`), derived `citation_url` / `citation_text` /
`citation_html`, plus a `source_path` audit pointer to the JSONL the
chunk came from.

The parquet is the only chunk store the retriever loads at query
time — FAISS and BM25 themselves stay metadata-free.
"""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from lecture_knowledge.citations import build_citation
from lecture_knowledge.chunks import index_files
from lecture_knowledge.config import CHUNK_META_PATH, PROCESSED_ROOT

# Columns: keep types stable (None → null in parquet). Ordering is the
# row order the indexes already use (== iter_chunks).

_STRING_FIELDS = (
    "id",
    "corpus",
    "doc_title",
    "source_url",
    "published_at",
    "fetched_at",
    "section_path",
    "speaker_role",
    "speaker_name",
    "category",
    "ticker",
    "company_name",
    "form",
    "filing_date",
    "channel",
    "video_id",
    "subs_kind",
    "author",
    "letter_year",
    "transcript_kind",
    "model_id",
    "image_path",
    "part_of",
    "fiscal_period",
    "publisher",
    "citation_url",
    "citation_text",
    "citation_html",
)
_INT_FIELDS = ("slide_number", "t_start_seconds", "part_index", "part_count", "n_tokens")
_BOOL_FIELDS = ("is_priority_section",)


def _as_str(v) -> str | None:
    if v is None:
        return None
    return str(v)


def _as_int(v) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _as_bool(v) -> bool | None:
    if v is None:
        return None
    return bool(v)


def main() -> None:
    CHUNK_META_PATH.parent.mkdir(parents=True, exist_ok=True)
    paths = index_files(PROCESSED_ROOT)
    cols: dict[str, list] = {f: [] for f in (*_STRING_FIELDS, *_INT_FIELDS, *_BOOL_FIELDS, "text", "source_path")}
    n = 0
    for p in paths:
        rel = str(p.relative_to(Path.cwd())) if p.is_absolute() else str(p)
        for line in p.open():
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            citation_url, citation_text, citation_html = build_citation(row)
            row["citation_url"] = citation_url
            row["citation_text"] = citation_text
            row["citation_html"] = citation_html
            for f in _STRING_FIELDS:
                cols[f].append(_as_str(row.get(f)))
            for f in _INT_FIELDS:
                cols[f].append(_as_int(row.get(f)))
            for f in _BOOL_FIELDS:
                cols[f].append(_as_bool(row.get(f)))
            cols["text"].append(row.get("text", ""))
            cols["source_path"].append(rel)
            n += 1
    print(f"Building chunk_meta.parquet with {n} rows × {len(cols)} columns…")
    table = pa.table(cols)
    pq.write_table(table, CHUNK_META_PATH, compression="zstd")
    print(f"Wrote {CHUNK_META_PATH} ({CHUNK_META_PATH.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
