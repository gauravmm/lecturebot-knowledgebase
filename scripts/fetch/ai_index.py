"""Download the Stanford HAI AI Index report used by the corpus."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import fitz

RAW = Path("data/raw/ai_index/2026")

SOURCE_URL = "https://hai.stanford.edu/assets/files/ai_index_report_2026.pdf"
LANDING_URL = "https://hai.stanford.edu/ai-index/2026-ai-index-report"
TITLE = "AI Index Report 2026"
PUBLISHER = "Stanford HAI"
PUBLISHED_AT = "2026-04-28"
LICENSE = "CC BY-ND 4.0"
CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)


def _fetch(url: str) -> bytes:
    cmd = [
        "curl",
        "-sL",
        "--compressed",
        "--max-time",
        "300",
        "--fail",
        "-A",
        CHROME_UA,
        "-H",
        "Accept: application/pdf,application/octet-stream,*/*;q=0.8",
        "-H",
        "Accept-Language: en-US,en;q=0.5",
        url,
    ]
    res = subprocess.run(cmd, capture_output=True, check=False)
    if res.returncode != 0:
        raise RuntimeError(
            f"curl failed (exit {res.returncode}): "
            f"{res.stderr.decode(errors='replace').strip() or '<no stderr>'}"
        )
    return res.stdout


def _pdf_pages(path: Path) -> int:
    doc = fitz.open(path)
    try:
        return doc.page_count
    finally:
        doc.close()


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    target = RAW / "report.pdf"
    blob = _fetch(SOURCE_URL)
    sha = hashlib.sha256(blob).hexdigest()
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == sha:
        print(f"unchanged  ai_index_2026  ({len(blob):>10,} B  sha {sha[:12]}…)")
    else:
        target.write_bytes(blob)
        print(f"wrote      ai_index_2026  ({len(blob):>10,} B  sha {sha[:12]}…)")

    manifest = {
        "corpus": "ai_index",
        "doc_id": "ai_index_2026",
        "title": TITLE,
        "publisher": PUBLISHER,
        "source_url": SOURCE_URL,
        "landing_url": LANDING_URL,
        "fetched_at": date.today().isoformat(),
        "published_at": PUBLISHED_AT,
        "license": LICENSE,
        "files": [
            {
                "path": "report.pdf",
                "sha256": sha,
                "bytes": len(blob),
                "pages": _pdf_pages(target),
            }
        ],
        "notes": (
            "Annual canonical AI metrics: compute, funding, capability benchmarks, "
            "hiring, regulation, public opinion. Per-page chunking for v1; bot can "
            "deep-link to a specific page via <source_url>#page=<slide_number>. "
            "Section-aware chunking and figure-caption extraction deferred."
        ),
    }
    (RAW / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
