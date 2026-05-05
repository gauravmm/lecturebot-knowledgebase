"""Download the Epoch AI notable-models dataset and overview page."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

RAW = Path("data/raw/epoch_models")

CSV_URL = "https://epoch.ai/data/notable_ai_models.csv"
LANDING_URL = "https://epoch.ai/data/ai-models"
DOC_URL = "https://epoch.ai/data/ai-models-documentation"
CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)


def _fetch(url: str, accept: str) -> bytes:
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
        f"Accept: {accept}",
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


def _write_if_changed(path: Path, blob: bytes) -> tuple[str, str]:
    sha = hashlib.sha256(blob).hexdigest()
    if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == sha:
        status = "unchanged"
    else:
        path.write_bytes(blob)
        status = "wrote"
    return status, sha


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    csv_blob = _fetch(CSV_URL, "text/csv,*/*;q=0.8")
    doc_blob = _fetch(DOC_URL, "text/html,application/xhtml+xml,*/*;q=0.8")
    csv_status, csv_sha = _write_if_changed(RAW / "notable_ai_models.csv", csv_blob)
    doc_status, doc_sha = _write_if_changed(RAW / "documentation.html", doc_blob)
    print(f"{csv_status:<10} epoch_models csv   ({len(csv_blob):>9,} B  sha {csv_sha[:12]}…)")
    print(f"{doc_status:<10} epoch_models docs  ({len(doc_blob):>9,} B  sha {doc_sha[:12]}…)")

    manifest = {
        "corpus": "epoch_models",
        "doc_id": "epoch_notable_models",
        "title": "Epoch AI — Notable AI Models database",
        "publisher": "Epoch AI",
        "source_url": CSV_URL,
        "landing_url": LANDING_URL,
        "documentation_url": DOC_URL,
        "fetched_at": date.today().isoformat(),
        "license": "CC BY 4.0",
        "files": [
            {
                "path": "notable_ai_models.csv",
                "sha256": csv_sha,
                "bytes": len(csv_blob),
            },
            {
                "path": "documentation.html",
                "sha256": doc_sha,
                "bytes": len(doc_blob),
            },
        ],
        "notes": (
            "Curated frontier-model database with training compute, parameters, "
            "dataset size, training cost. The 'notable' subset is the canonical "
            "Epoch citation. Documentation page is a Next.js shell; only the "
            "Overview tab is available in static HTML."
        ),
    }
    (RAW / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
