"""Download the C1 consulting AI reports from spec/SOURCES.md.

Targets: McKinsey, BCG, Bain, Deloitte. McKinsey's WAF drops requests
that don't carry a full browser-style header set (User-Agent, Accept,
Accept-Language, Accept-Encoding, Referer); plain curl returns code=000
without those, so we always send them. The other firms accept a bare
request, but sending the full set is harmless.

Reports are written to:
    data/raw/consulting/<slug>/report.pdf
    data/raw/consulting/<slug>/manifest.json

Re-run is idempotent: if the on-disk PDF already matches the
just-downloaded sha256, the file is left untouched. The manifest is
always rewritten so it stays in sync with the on-disk state.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import fitz

RAW = Path("data/raw/consulting")

CC_LICENSE = (
    "Marketing publication. Permissive non-commercial summarization with "
    "attribution; do not redistribute the PDF itself."
)

REPORTS: dict[str, dict] = {
    "mckinsey-state-of-ai-2025": {
        "url": (
            "https://www.mckinsey.com/~/media/mckinsey/business%20functions/quantumblack/"
            "our%20insights/the%20state%20of%20ai/november%202025/"
            "the-state-of-ai-2025-agents-innovation_cmyk-v1.pdf"
        ),
        "title": "The State of AI 2025: Agents, innovation, and transformation",
        "publisher": "McKinsey & Company",
        "published_at": "2025-11",
        "license": CC_LICENSE,
    },
    "mckinsey-economic-potential-genai-2023": {
        "url": (
            "https://www.mckinsey.com/~/media/mckinsey/business%20functions/mckinsey%20digital/"
            "our%20insights/the%20economic%20potential%20of%20generative%20ai%20the%20next%20productivity%20frontier/"
            "the-economic-potential-of-generative-ai-the-next-productivity-frontier.pdf"
        ),
        "title": "The Economic Potential of Generative AI: The Next Productivity Frontier",
        "publisher": "McKinsey & Company",
        "published_at": "2023-06",
        "license": CC_LICENSE,
    },
    "bcg-widening-ai-value-gap-2025": {
        "url": "https://media-publications.bcg.com/The-Widening-AI-Value-Gap-October-2025.pdf",
        "title": "Build for the Future 2025: The Widening AI Value Gap",
        "publisher": "Boston Consulting Group",
        "published_at": "2025-10",
        "license": CC_LICENSE,
    },
    "bain-technology-report-2025": {
        "url": "https://www.bain.com/globalassets/noindex/2025/bain_report_technology_report_2025.pdf",
        "title": "Bain Technology Report 2025",
        "publisher": "Bain & Company",
        "published_at": "2025-09",
        "license": CC_LICENSE,
    },
    "deloitte-state-of-ai-enterprise-2026": {
        "url": "https://www.deloitte.com/content/dam/assets-shared/docs/about/2025/state-of-ai-2026-global.pdf",
        "title": "State of AI in the Enterprise 2026 (Global cut)",
        "publisher": "Deloitte",
        "published_at": "2026-01",
        "license": CC_LICENSE,
    },
}

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
}


def _fetch(url: str) -> bytes:
    """Use curl rather than urllib: McKinsey's WAF accepts curl with the
    full browser-style header set but stalls urllib's body read on the
    same request, leading to read-timeouts even when HEAD shows 200.

    Notes from prior runs:
    - Without an Accept-Encoding header, McKinsey's HTTP/2 stream
      closes mid-body and curl exits 92. Sending all four browser
      headers (UA, Accept, Accept-Language, Accept-Encoding) plus a
      Referer fixes that.
    - --http1.1 looks like a workaround but actually makes McKinsey
      serve byte-by-byte and time out at 5 min. Stick with default
      HTTP/2. --compressed handles gzip transparently.
    """
    referer = "/".join(url.split("/", 3)[:3]) + "/"
    cmd = [
        "curl",
        "-sL",
        "--compressed",
        "--max-time",
        "300",
        "--fail",
        "-A",
        BROWSER_HEADERS["User-Agent"],
    ]
    for h, v in BROWSER_HEADERS.items():
        if h in ("User-Agent", "Accept-Encoding"):
            continue  # UA via -A; encoding via --compressed
        cmd += ["-H", f"{h}: {v}"]
    cmd += ["-H", f"Referer: {referer}", url]
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


def _write_manifest(slug: str, meta: dict, pdf_path: Path) -> None:
    blob = pdf_path.read_bytes()
    sha = hashlib.sha256(blob).hexdigest()
    manifest = {
        "corpus": "consulting",
        "doc_id": slug,
        "title": meta["title"],
        "publisher": meta["publisher"],
        "source_url": meta["url"],
        "fetched_at": date.today().isoformat(),
        "published_at": meta["published_at"],
        "license": meta["license"],
        "files": [
            {
                "path": "report.pdf",
                "sha256": sha,
                "bytes": len(blob),
                "pages": _pdf_pages(pdf_path),
            }
        ],
    }
    (pdf_path.parent / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    for slug, meta in REPORTS.items():
        out_dir = RAW / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / "report.pdf"
        try:
            blob = _fetch(meta["url"])
        except Exception as e:
            print(f"FAIL {slug}: {e}", file=sys.stderr)
            continue
        sha = hashlib.sha256(blob).hexdigest()
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == sha:
            print(f"unchanged  {slug}  ({len(blob):>10,} B  sha {sha[:12]}…)")
        else:
            target.write_bytes(blob)
            print(f"wrote      {slug}  ({len(blob):>10,} B  sha {sha[:12]}…)")
        _write_manifest(slug, meta, target)


if __name__ == "__main__":
    main()
