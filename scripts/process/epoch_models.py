"""Marshal the Epoch AI Notable AI Models CSV into per-model JSONL chunks.

Output: data/processed/epoch_models/notable.chunks.jsonl

Schema:
- One chunk per model row, formatted as a readable block of populated
  fields (empty fields and "<col>_notes" annotations are skipped or
  folded into the parent field).
- One leading chunk for the documentation overview (Next.js page; only
  the Overview tab survives a plain curl, but it covers the audience's
  question of "what's in this database").
"""

from __future__ import annotations

import csv
import json
import re
from html.parser import HTMLParser
from pathlib import Path

RAW = Path("data/raw/epoch_models")
OUT = Path("data/processed/epoch_models/notable.chunks.jsonl")


class _Strip(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "nav", "header", "footer"):
            self.skip_depth += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav", "header", "footer") and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data):
        if not self.skip_depth:
            self.parts.append(data)


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()
    return s or "model"


def _doc_overview_text(html_path: Path) -> str:
    p = _Strip()
    p.feed(html_path.read_text())
    return re.sub(r"\s+", " ", " ".join(p.parts)).strip()


# CSV columns we surface in the chunk text, in display order. The "_notes"
# columns are folded into the preceding column as parenthetical context.
_DISPLAY_FIELDS: list[tuple[str, str | None]] = [
    ("Model", None),
    ("Organization", None),
    ("Organization categorization", None),
    ("Country (of organization)", None),
    ("Publication date", None),
    ("Domain", None),
    ("Task", None),
    ("Parameters", "Parameters notes"),
    ("Training compute (FLOP)", "Training compute notes"),
    ("Training dataset", None),
    ("Training dataset size (total)", "Dataset size notes"),
    ("Training compute cost (2023 USD)", "Compute cost notes"),
    ("Training compute cost (cloud)", None),
    ("Training compute cost (upfront)", None),
    ("Training time (hours)", "Training time notes"),
    ("Training hardware", None),
    ("Hardware quantity", None),
    ("Hardware utilization (MFU)", None),
    ("Training power draw (W)", None),
    ("Base model", None),
    ("Finetune compute (FLOP)", "Finetune compute notes"),
    ("Numerical format", None),
    ("Frontier model", None),
    ("Notability criteria", "Notability criteria notes"),
    ("Confidence", None),
    ("Model accessibility", None),
    ("Open model weights?", None),
    ("Authors", None),
    ("Reference", None),
    ("Link", None),
    ("Citations", None),
    ("Abstract", None),
]


def _format_row(row: dict[str, str]) -> str:
    lines: list[str] = []
    for field, notes_field in _DISPLAY_FIELDS:
        val = (row.get(field) or "").strip()
        if not val:
            continue
        notes = (row.get(notes_field) or "").strip() if notes_field else ""
        if notes:
            lines.append(f"{field}: {val}  ({notes})")
        else:
            lines.append(f"{field}: {val}")
    return "\n".join(lines)


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((RAW / "manifest.json").read_text())

    base = {
        "corpus": "epoch_models",
        "doc_title": manifest["title"],
        "source_url": manifest["source_url"],
        "landing_url": manifest["landing_url"],
        "publisher": manifest.get("publisher"),
        "fetched_at": manifest["fetched_at"],
        "license": manifest.get("license"),
    }

    chunks: list[dict] = []

    overview = _doc_overview_text(RAW / "documentation.html")
    if overview:
        chunks.append({
            **base,
            "id": "epoch_models::documentation-overview",
            "section_path": "documentation/overview",
            "source_url": manifest["documentation_url"],
            "text": f"Epoch AI Models Documentation — Overview:\n\n{overview}",
        })

    with (RAW / "notable_ai_models.csv").open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("Model") or "").strip()
            if not name:
                continue
            text = _format_row(row)
            if not text:
                continue
            org = (row.get("Organization") or "").strip()
            pub = (row.get("Publication date") or "").strip()
            link = (row.get("Link") or "").strip()
            chunks.append({
                **base,
                "id": f"epoch_models::{_slugify(name)}",
                "section_path": f"model:{name}",
                "model_name": name,
                "organization": org or None,
                "published_at": pub or None,
                "model_link": link or None,
                "text": text,
            })

    with OUT.open("w") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"{OUT}: {len(chunks)} chunks (1 documentation + {len(chunks) - 1} models)")


if __name__ == "__main__":
    main()
