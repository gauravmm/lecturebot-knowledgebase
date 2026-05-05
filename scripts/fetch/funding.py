"""Download the E3 (Crunchbase News — AI funding articles) corpus.

Per spec/SOURCES.md §E: E1 (Dealroom / PitchBook) and E2 (CB Insights)
were dropped at fetch time — Dealroom's report PDFs are gated behind
HubSpot lead-capture forms, PitchBook's `files.pitchbook.com` is
Cloudflare-walled to plain curl, CB Insights' `cbinsights.com` returns
AWS-WAF challenges (HTTP 202). The Stanford AI Index Report (already
in the corpus) covers the canonical funding numbers in its dedicated
Investment chapter, so we lean on that and supplement with E3 narrative.

E3 picks: 12 Crunchbase News articles spanning AI-funding annual
recaps (2023–2025), quarterly recaps (2025–2026), regional breakouts
(global / North America / Europe), and theme pieces (capital
concentration, big-dollar investors, seed averages). All hosted on
`news.crunchbase.com` (server-rendered WordPress, plain curl works).

Outputs:
    data/raw/funding/<slug>/page.html
    data/raw/funding/<slug>/manifest.json

Re-run is idempotent on sha256.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

RAW = Path("data/raw/funding")

CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)
LICENSE_TEXT = (
    "Public web — Crunchbase News article. Quote with attribution + link."
)

ARTICLES: dict[str, dict] = {
    # ---------------- Annual recaps ----------------
    "cb-global-eoy-2023-ai": {
        "url": "https://news.crunchbase.com/venture/global-funding-data-analysis-ai-eoy-2023/",
        "title": "Global Startup Funding In 2023 Clocked In At Lowest Level In 5 Years As AI Bucked The Trend",
        "category": "annual_recap",
        "geography": "global",
        "year_or_period": "2023",
    },
    "cb-global-eoy-2024-ai": {
        "url": "https://news.crunchbase.com/venture/global-funding-data-analysis-ai-eoy-2024/",
        "title": "Global Startup Funding In 2024 — AI's Outsized Share",
        "category": "annual_recap",
        "geography": "global",
        "year_or_period": "2024",
    },
    "cb-global-2025-third-largest-year": {
        "url": "https://news.crunchbase.com/venture/funding-data-third-largest-year-2025/",
        "title": "Global Startup Funding 2025 — Third-Largest Year On Record",
        "category": "annual_recap",
        "geography": "global",
        "year_or_period": "2025",
    },
    # ---------------- Quarterly recaps (2025) ----------------
    "cb-global-q1-2025-ai": {
        "url": "https://news.crunchbase.com/venture/global-funding-strong-q1-2025-ai-data/",
        "title": "Global Startup Funding Strong In Q1 2025, Led By AI",
        "category": "quarterly_recap",
        "geography": "global",
        "year_or_period": "2025-Q1",
    },
    "cb-global-q2-2025-ai-ma": {
        "url": "https://news.crunchbase.com/venture/global-funding-climbs-q2-2025-ai-ma-data/",
        "title": "Global Funding Climbs In Q2 2025, AI And M&A Lead",
        "category": "quarterly_recap",
        "geography": "global",
        "year_or_period": "2025-Q2",
    },
    "cb-global-q3-2025-ai-ma": {
        "url": "https://news.crunchbase.com/venture/global-vc-funding-biggest-deals-q3-2025-ai-ma-data/",
        "title": "Global VC Funding And Biggest Deals — Q3 2025 AI / M&A",
        "category": "quarterly_recap",
        "geography": "global",
        "year_or_period": "2025-Q3",
    },
    # ---------------- Quarterly recaps (2026) ----------------
    "cb-na-q1-2026-ai": {
        "url": "https://news.crunchbase.com/venture/funding-surges-all-stages-ai-north-america-q1-2026/",
        "title": "Funding Surges Across All Stages In North America In Q1 2026, AI-Led",
        "category": "quarterly_recap",
        "geography": "north_america",
        "year_or_period": "2026-Q1",
    },
    "cb-europe-q1-2026-ai": {
        "url": "https://news.crunchbase.com/venture/funding-picked-up-ai-led-europe-q1-2026/",
        "title": "European Funding Picked Up In Q1 2026, AI-Led",
        "category": "quarterly_recap",
        "geography": "europe",
        "year_or_period": "2026-Q1",
    },
    "cb-capital-concentrated-ai-q1-2026": {
        "url": "https://news.crunchbase.com/venture/capital-concentrated-ai-global-q1-2026/",
        "title": "Capital Is Concentrated In AI — Global Q1 2026",
        "category": "theme",
        "geography": "global",
        "year_or_period": "2026-Q1",
    },
    # ---------------- Theme pieces ----------------
    "cb-big-dollar-ai-investors-2025": {
        "url": "https://news.crunchbase.com/venture/big-dollar-ai-investors-2025-softbank/",
        "title": "The Big-Dollar AI Investors Of 2025 — SoftBank And Friends",
        "category": "theme",
        "geography": "global",
        "year_or_period": "2025",
    },
    "cb-biggest-rounds-ai-autonomy-biotech": {
        "url": "https://news.crunchbase.com/venture/biggest-funding-rounds-ai-autonomy-biotech-anthropic/",
        "title": "The Week's 10 Biggest Funding Rounds: AI, Autonomy And Biotech Top The Ranks",
        "category": "theme",
        "geography": "us",
        "year_or_period": "2026",
    },
    "cb-seed-amounts-grew-2025": {
        "url": "https://news.crunchbase.com/venture/average-seed-funding-amounts-deals-grew-2025/",
        "title": "Average Seed Funding Amounts And Deals Grew In 2025",
        "category": "theme",
        "geography": "global",
        "year_or_period": "2025",
    },
}


def _fetch(url: str) -> bytes:
    cmd = [
        "curl", "-sL", "--compressed", "--max-time", "120", "--fail",
        "-A", CHROME_UA,
        "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
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


def _write_manifest(slug: str, meta: dict, page_path: Path) -> None:
    blob = page_path.read_bytes()
    sha = hashlib.sha256(blob).hexdigest()
    manifest = {
        "corpus": "funding",
        "doc_id": slug,
        "title": meta["title"],
        "publisher": "Crunchbase News",
        "category": meta["category"],
        "geography": meta["geography"],
        "year_or_period": meta["year_or_period"],
        "source_url": meta["url"],
        "fetched_at": date.today().isoformat(),
        "license": LICENSE_TEXT,
        "files": [{"path": "page.html", "sha256": sha, "bytes": len(blob)}],
    }
    (page_path.parent / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    args = set(sys.argv[1:])
    failures: list[str] = []
    for slug, meta in ARTICLES.items():
        if args and slug not in args:
            continue
        out_dir = RAW / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        page_path = out_dir / "page.html"
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
        if page_path.exists() and hashlib.sha256(page_path.read_bytes()).hexdigest() == sha:
            print(f"unchanged  {slug}  ({len(blob):>9,} B)")
        else:
            page_path.write_bytes(blob)
            print(f"wrote      {slug}  ({len(blob):>9,} B)")
        _write_manifest(slug, meta, page_path)
    if failures:
        print(f"\n{len(failures)} failed: {' '.join(failures)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
