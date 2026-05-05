"""Download the B3 shareholder-letter corpus per spec/SOURCES.md.

Two authors, three formats:

  - Jeff Bezos (AMZN): 6 standalone HTML pages on aboutamazon.com
    (1997 + 2016-2020) + 4 annual-report PDFs on the Q4 CDN
    (2013, 2015, 2016, 2018) where the letter is on the first few
    pages of the AR.

  - Satya Nadella (MSFT): 6 annual-report HTML pages at
    microsoft.com/investor/reports/arNN/index.html. The letter
    section is anchored at #shareholder-letter inside the page.

NVDA: Jensen Huang doesn't publish a separate shareholder letter; his
content is in the 10-K already (covered by B1, see scripts/fetch/edgar.py).

Outputs:
    data/raw/letters/<slug>/page.{html,pdf}
    data/raw/letters/<slug>/manifest.json

Re-run is idempotent on sha256.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

RAW = Path("data/raw/letters")

CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)
LICENSE_TEXT = (
    "Public web; canonical IR-site publication. Quote with attribution."
)

LETTERS: dict[str, dict] = {
    # ---------- Bezos / AMZN — standalone HTML on aboutamazon.com ----------
    "bezos-1997-day-1": {
        "url": "https://www.aboutamazon.com/news/company-news/amazons-original-1997-letter-to-shareholders",
        "filename": "page.html",
        "title": "Amazon's Original 1997 Letter to Shareholders ('It's Day 1')",
        "author": "Jeff Bezos",
        "publisher": "Amazon",
        "letter_year": 1997,
        "format": "html",
    },
    "bezos-2016": {
        "url": "https://www.aboutamazon.com/news/company-news/2016-letter-to-shareholders",
        "filename": "page.html",
        "title": "2016 Letter to Shareholders",
        "author": "Jeff Bezos",
        "publisher": "Amazon",
        "letter_year": 2016,
        "format": "html",
    },
    "bezos-2017": {
        "url": "https://www.aboutamazon.com/news/company-news/2017-letter-to-shareholders",
        "filename": "page.html",
        "title": "2017 Letter to Shareholders",
        "author": "Jeff Bezos",
        "publisher": "Amazon",
        "letter_year": 2017,
        "format": "html",
    },
    "bezos-2018": {
        "url": "https://www.aboutamazon.com/news/company-news/2018-letter-to-shareholders",
        "filename": "page.html",
        "title": "2018 Letter to Shareholders",
        "author": "Jeff Bezos",
        "publisher": "Amazon",
        "letter_year": 2018,
        "format": "html",
    },
    "bezos-2019": {
        "url": "https://www.aboutamazon.com/news/company-news/2019-letter-to-shareholders",
        "filename": "page.html",
        "title": "2019 Letter to Shareholders",
        "author": "Jeff Bezos",
        "publisher": "Amazon",
        "letter_year": 2019,
        "format": "html",
    },
    "bezos-2020": {
        "url": "https://www.aboutamazon.com/news/company-news/2020-letter-to-shareholders",
        "filename": "page.html",
        "title": "2020 Letter to Shareholders ('Day 1' / final letter as CEO)",
        "author": "Jeff Bezos",
        "publisher": "Amazon",
        "letter_year": 2020,
        "format": "html",
    },
    # ---------- Bezos / AMZN — Annual Report PDFs (letter on page 1) ----------
    # The processor slices the Bezos letter section out of these AR PDFs;
    # we keep the full AR locally for inspection but only the letter
    # section is chunked.
    "bezos-2013-ar": {
        "url": "https://s2.q4cdn.com/299287126/files/doc_financials/annual/2013-Annual-Report.pdf",
        "filename": "report.pdf",
        "title": "2013 Letter to Shareholders (in 2013 Annual Report)",
        "author": "Jeff Bezos",
        "publisher": "Amazon",
        "letter_year": 2013,
        "format": "pdf-ar",
    },
    "bezos-2015-ar": {
        "url": "https://s2.q4cdn.com/299287126/files/doc_financials/annual/2015-Annual-Report.pdf",
        "filename": "report.pdf",
        "title": "2015 Letter to Shareholders (in 2015 Annual Report)",
        "author": "Jeff Bezos",
        "publisher": "Amazon",
        "letter_year": 2015,
        "format": "pdf-ar",
    },
    # 2016 letter is also available standalone HTML above; the AR is a
    # bonus copy with full annual-report context (skip duplicate? — keep
    # for the AR-context surrounding the letter, processor de-dupes via
    # source_url so chunks are distinct).
    "bezos-2016-ar": {
        "url": "https://s2.q4cdn.com/299287126/files/doc_financials/annual/2016-Annual-Report.pdf",
        "filename": "report.pdf",
        "title": "2016 Letter to Shareholders (in 2016 Annual Report)",
        "author": "Jeff Bezos",
        "publisher": "Amazon",
        "letter_year": 2016,
        "format": "pdf-ar",
    },
    "bezos-2018-ar": {
        "url": "https://s2.q4cdn.com/299287126/files/doc_financials/annual/2018-Annual-Report.pdf",
        "filename": "report.pdf",
        "title": "2018 Letter to Shareholders (in 2018 Annual Report)",
        "author": "Jeff Bezos",
        "publisher": "Amazon",
        "letter_year": 2018,
        "format": "pdf-ar",
    },
    # ---------- Nadella / MSFT — Annual Report HTML, #shareholder-letter ----
    "nadella-fy20": {
        "url": "https://www.microsoft.com/investor/reports/ar20/index.html",
        "filename": "page.html",
        "title": "Microsoft FY20 Annual Report — Letter from Satya Nadella",
        "author": "Satya Nadella",
        "publisher": "Microsoft",
        "letter_year": 2020,
        "format": "html-ar",
    },
    "nadella-fy21": {
        "url": "https://www.microsoft.com/investor/reports/ar21/index.html",
        "filename": "page.html",
        "title": "Microsoft FY21 Annual Report — Letter from Satya Nadella",
        "author": "Satya Nadella",
        "publisher": "Microsoft",
        "letter_year": 2021,
        "format": "html-ar",
    },
    "nadella-fy22": {
        "url": "https://www.microsoft.com/investor/reports/ar22/index.html",
        "filename": "page.html",
        "title": "Microsoft FY22 Annual Report — Letter from Satya Nadella",
        "author": "Satya Nadella",
        "publisher": "Microsoft",
        "letter_year": 2022,
        "format": "html-ar",
    },
    "nadella-fy23": {
        "url": "https://www.microsoft.com/investor/reports/ar23/index.html",
        "filename": "page.html",
        "title": "Microsoft FY23 Annual Report — Letter from Satya Nadella",
        "author": "Satya Nadella",
        "publisher": "Microsoft",
        "letter_year": 2023,
        "format": "html-ar",
    },
    "nadella-fy24": {
        "url": "https://www.microsoft.com/investor/reports/ar24/index.html",
        "filename": "page.html",
        "title": "Microsoft FY24 Annual Report — Letter from Satya Nadella",
        "author": "Satya Nadella",
        "publisher": "Microsoft",
        "letter_year": 2024,
        "format": "html-ar",
    },
    "nadella-fy25": {
        "url": "https://www.microsoft.com/investor/reports/ar25/index.html",
        "filename": "page.html",
        "title": "Microsoft FY25 Annual Report — Letter from Satya Nadella",
        "author": "Satya Nadella",
        "publisher": "Microsoft",
        "letter_year": 2025,
        "format": "html-ar",
    },
}


def _fetch(url: str) -> bytes:
    cmd = [
        "curl", "-sL", "--compressed", "--max-time", "120", "--fail",
        "-A", CHROME_UA,
        "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf,*/*;q=0.8",
        "-H", "Accept-Language: en-US,en;q=0.5",
        url,
    ]
    res = subprocess.run(cmd, capture_output=True, check=False)
    if res.returncode != 0:
        raise RuntimeError(
            f"curl failed (exit {res.returncode}): "
            f"{res.stderr.decode(errors='replace').strip() or '<no stderr>'}"
        )
    return res.stdout


def _write_manifest(slug: str, meta: dict, file_path: Path) -> None:
    blob = file_path.read_bytes()
    sha = hashlib.sha256(blob).hexdigest()
    manifest = {
        "corpus": "letters",
        "doc_id": slug,
        "title": meta["title"],
        "author": meta["author"],
        "publisher": meta["publisher"],
        "letter_year": meta["letter_year"],
        "format": meta["format"],
        "source_url": meta["url"],
        "fetched_at": date.today().isoformat(),
        "license": LICENSE_TEXT,
        "files": [{"path": meta["filename"], "sha256": sha, "bytes": len(blob)}],
    }
    (file_path.parent / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    args = set(sys.argv[1:])
    failures: list[str] = []
    for slug, meta in LETTERS.items():
        if args and slug not in args:
            continue
        out_dir = RAW / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / meta["filename"]
        try:
            blob = _fetch(meta["url"])
        except Exception as e:
            print(f"FAIL  {slug}: {e}", file=sys.stderr)
            failures.append(slug)
            continue
        if not blob:
            print(f"FAIL  {slug}: empty body", file=sys.stderr)
            failures.append(slug)
            continue
        sha = hashlib.sha256(blob).hexdigest()
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == sha:
            print(f"unchanged  {slug}  ({len(blob):>9,} B)")
        else:
            target.write_bytes(blob)
            print(f"wrote      {slug}  ({len(blob):>9,} B)")
        _write_manifest(slug, meta, target)
    if failures:
        print(f"\n{len(failures)} failed: {' '.join(failures)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
