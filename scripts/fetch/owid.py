"""Download the OWID AI topic page used by the corpus."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

RAW = Path("data/raw/owid")
SOURCE_URL = "https://ourworldindata.org/artificial-intelligence"
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
        "120",
        "--fail",
        "-A",
        CHROME_UA,
        "-H",
        "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
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


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    target = RAW / "artificial-intelligence.html"
    blob = _fetch(SOURCE_URL)
    sha = hashlib.sha256(blob).hexdigest()
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == sha:
        print(f"unchanged  owid/artificial-intelligence  ({len(blob):>9,} B  sha {sha[:12]}…)")
    else:
        target.write_bytes(blob)
        print(f"wrote      owid/artificial-intelligence  ({len(blob):>9,} B  sha {sha[:12]}…)")

    manifest = {
        "corpus": "owid",
        "doc_id": "artificial-intelligence",
        "title": "Our World in Data — Artificial Intelligence (topic page)",
        "publisher": "Our World in Data",
        "source_url": SOURCE_URL,
        "fetched_at": date.today().isoformat(),
        "license": "CC BY 4.0",
        "files": [
            {
                "path": "artificial-intelligence.html",
                "sha256": sha,
                "bytes": len(blob),
            }
        ],
        "notes": (
            "Single OWID topic-page snapshot. Chunk text inlines the linked chart "
            "slugs as references, but does not mirror every Grapher CSV."
        ),
    }
    (RAW / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
