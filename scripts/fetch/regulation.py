"""Download the F2 (AI regulation & governance) corpus per spec/SOURCES.md.

Sources, four shapes:

  - **NIST AI RMF + GenAI Profile** — PDFs on `nvlpubs.nist.gov`. The
    server's HEAD response lies (returns 404), but a full GET with a
    `Referer: https://www.nist.gov/itl/ai-risk-management-framework`
    header returns the PDF body. Always GET, never HEAD-probe.
  - **EU AI Act** — `artificialintelligenceact.eu` (FoLI explorer)
    serves the consolidated text article-by-article at `/article/N/`
    for N=1..113 plus annexes at `/annex/N/` for N=1..13. EUR-Lex
    itself is AWS-WAF-walled to plain curl, so we use the FoLI mirror.
  - **US AI executive orders + AI Action Plan** — Trump's 4 2025 AI
    EOs as HTML on `whitehouse.gov`, the July 2025 "America's AI
    Action Plan" PDF, and Biden's revoked-but-historically-important
    EO 14110 via `govinfo.gov` (whitehouse.gov scrubbed it).
  - **ISO/IEC 42001** — abstract page only at `iso.org/standard/42001`
    (the standard text itself is paywalled / copyrighted).

Outputs:
    data/raw/regulation/<slug>/page.{html,pdf}
    data/raw/regulation/<slug>/manifest.json

Re-run is idempotent on sha256. Pass slug args on the command line to
retry just specific entries (handy when a flaky fetch needs a redo).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

RAW = Path("data/raw/regulation")

CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)

NIST_LICENSE = "Public domain (US gov publication)."
EU_LICENSE = (
    "EU AI Act, Regulation (EU) 2024/1689, © European Union 2024. "
    "Canonical: https://eur-lex.europa.eu/eli/reg/2024/1689/oj. "
    "Re-use under Decision 2011/833/EU (Commission decision on the re-use "
    "of Commission documents). Fetched via artificialintelligenceact.eu "
    "(Future of Life Institute) mirror; EUR-Lex blocks programmatic access."
)
USGOV_LICENSE = "Public domain (US Federal government publication)."
ISO_LICENSE = (
    "Abstract / scope summary only — ISO/IEC 42001 standard text "
    "is copyrighted and not redistributed here."
)


def _eu_articles() -> dict[str, dict]:
    """Articles 1..113 of the EU AI Act (Regulation 2024/1689)."""
    out: dict[str, dict] = {}
    for n in range(1, 114):
        slug = f"eu-ai-act-article-{n:03d}"
        out[slug] = {
            "url": f"https://artificialintelligenceact.eu/article/{n}/",
            "filename": "page.html",
            "title": f"EU AI Act — Article {n}",
            "category": "eu_ai_act",
            "format": "html-eu",
            "section_kind": "article",
            "section_number": n,
            "publisher": "European Union (Regulation 2024/1689)",
            "license": EU_LICENSE,
            "published_at": "2024-07",
        }
    return out


def _eu_annexes() -> dict[str, dict]:
    """Annexes 1..13 of the EU AI Act."""
    out: dict[str, dict] = {}
    for n in range(1, 14):
        slug = f"eu-ai-act-annex-{n:02d}"
        out[slug] = {
            "url": f"https://artificialintelligenceact.eu/annex/{n}/",
            "filename": "page.html",
            "title": f"EU AI Act — Annex {n}",
            "category": "eu_ai_act",
            "format": "html-eu",
            "section_kind": "annex",
            "section_number": n,
            "publisher": "European Union (Regulation 2024/1689)",
            "license": EU_LICENSE,
            "published_at": "2024-07",
        }
    return out


SOURCES: dict[str, dict] = {
    # ---------------- NIST ----------------
    "nist-ai-rmf-100-1": {
        "url": "https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf",
        "filename": "report.pdf",
        "title": "NIST AI Risk Management Framework (AI RMF 1.0)",
        "author": "National Institute of Standards and Technology",
        "publisher": "NIST",
        "category": "nist",
        "format": "pdf-nist",
        "license": NIST_LICENSE,
        "published_at": "2023-01",
        # nvlpubs.nist.gov returns 404 to HEAD and to GET without a
        # Referer header; sending the NIST hub page as Referer flips
        # it back to a normal 200 + application/pdf.
        "extra_headers": {
            "Referer": "https://www.nist.gov/itl/ai-risk-management-framework",
        },
    },
    "nist-ai-genai-profile-600-1": {
        "url": "https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf",
        "filename": "report.pdf",
        "title": "NIST AI 600-1 — Generative AI Profile (companion to AI RMF 1.0)",
        "author": "National Institute of Standards and Technology",
        "publisher": "NIST",
        "category": "nist",
        "format": "pdf-nist",
        "license": NIST_LICENSE,
        "published_at": "2024-07",
        "extra_headers": {
            "Referer": "https://www.nist.gov/itl/ai-risk-management-framework",
        },
    },
    # ---------------- US Executive Orders ----------------
    "biden-eo-14110-ai-2023": {
        # Trump scrubbed EO 14110 from whitehouse.gov on 2025-01-20;
        # the canonical archived copy is the Federal Register PDF on
        # govinfo.gov, which is the legal-of-record version anyway.
        "url": "https://www.govinfo.gov/content/pkg/FR-2023-11-01/pdf/2023-24283.pdf",
        "filename": "report.pdf",
        "title": (
            "EO 14110 — Safe, Secure, and Trustworthy Development and Use "
            "of Artificial Intelligence (Biden, Oct 2023; revoked Jan 2025)"
        ),
        "author": "Executive Office of the President (Biden)",
        "publisher": "Federal Register / govinfo.gov",
        "category": "us_eo",
        "format": "pdf-eo",
        "license": USGOV_LICENSE,
        "published_at": "2023-10-30",
    },
    "trump-eo-removing-barriers-ai-2025-01": {
        "url": (
            "https://www.whitehouse.gov/presidential-actions/2025/01/"
            "removing-barriers-to-american-leadership-in-artificial-intelligence/"
        ),
        "filename": "page.html",
        "title": "EO — Removing Barriers to American Leadership in AI (Trump, Jan 2025)",
        "author": "Executive Office of the President (Trump)",
        "publisher": "The White House",
        "category": "us_eo",
        "format": "html-eo",
        "license": USGOV_LICENSE,
        "published_at": "2025-01-23",
    },
    "trump-eo-ai-education-2025-04": {
        "url": (
            "https://www.whitehouse.gov/presidential-actions/2025/04/"
            "advancing-artificial-intelligence-education-for-american-youth/"
        ),
        "filename": "page.html",
        "title": "EO — Advancing AI Education for American Youth (Trump, Apr 2025)",
        "author": "Executive Office of the President (Trump)",
        "publisher": "The White House",
        "category": "us_eo",
        "format": "html-eo",
        "license": USGOV_LICENSE,
        "published_at": "2025-04",
    },
    "trump-eo-ai-pediatric-cancer-2025-09": {
        "url": (
            "https://www.whitehouse.gov/presidential-actions/2025/09/"
            "unlocking-cures-for-pediatric-cancer-with-artificial-intelligence/"
        ),
        "filename": "page.html",
        "title": "EO — Unlocking Cures for Pediatric Cancer with AI (Trump, Sep 2025)",
        "author": "Executive Office of the President (Trump)",
        "publisher": "The White House",
        "category": "us_eo",
        "format": "html-eo",
        "license": USGOV_LICENSE,
        "published_at": "2025-09",
    },
    "trump-eo-ai-state-law-preemption-2025-12": {
        "url": (
            "https://www.whitehouse.gov/presidential-actions/2025/12/"
            "eliminating-state-law-obstruction-of-national-artificial-intelligence-policy/"
        ),
        "filename": "page.html",
        "title": (
            "EO — Eliminating State Law Obstruction of National AI Policy "
            "(Trump, Dec 2025)"
        ),
        "author": "Executive Office of the President (Trump)",
        "publisher": "The White House",
        "category": "us_eo",
        "format": "html-eo",
        "license": USGOV_LICENSE,
        "published_at": "2025-12",
    },
    "trump-ai-action-plan-2025": {
        "url": "https://www.whitehouse.gov/wp-content/uploads/2025/07/Americas-AI-Action-Plan.pdf",
        "filename": "report.pdf",
        "title": "America's AI Action Plan (White House, July 2025)",
        "author": "The White House (Trump administration)",
        "publisher": "The White House",
        "category": "us_eo",
        "format": "pdf-action-plan",
        "license": USGOV_LICENSE,
        "published_at": "2025-07",
    },
    # ---------------- ISO/IEC 42001 ----------------
    "iso-iec-42001-abstract": {
        "url": "https://www.iso.org/standard/42001",
        "filename": "page.html",
        "title": (
            "ISO/IEC 42001:2023 — Information technology — AI Management "
            "System (public abstract / scope summary)"
        ),
        "author": "ISO/IEC JTC 1/SC 42",
        "publisher": "ISO",
        "category": "iso",
        "format": "html-iso",
        "license": ISO_LICENSE,
        "published_at": "2023-12",
    },
    # ---------------- EU AI Act ----------------
    **_eu_articles(),
    **_eu_annexes(),
}


def _fetch(url: str, extra_headers: dict[str, str] | None = None) -> bytes:
    cmd = [
        "curl", "-sL", "--compressed", "--max-time", "120", "--fail",
        "-A", CHROME_UA,
        "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf,*/*;q=0.8",
        "-H", "Accept-Language: en-US,en;q=0.5",
    ]
    for h, v in (extra_headers or {}).items():
        cmd += ["-H", f"{h}: {v}"]
    cmd.append(url)
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
        "corpus": "regulation",
        "doc_id": slug,
        "title": meta["title"],
        "author": meta.get("author"),
        "publisher": meta["publisher"],
        "category": meta["category"],
        "format": meta["format"],
        "source_url": meta["url"],
        "fetched_at": date.today().isoformat(),
        "published_at": meta.get("published_at"),
        "license": meta["license"],
        "files": [{"path": meta["filename"], "sha256": sha, "bytes": len(blob)}],
    }
    if meta.get("section_kind"):
        manifest["section_kind"] = meta["section_kind"]
        manifest["section_number"] = meta["section_number"]
    (file_path.parent / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    args = set(sys.argv[1:])
    failures: list[str] = []
    eu_count = 0
    for slug, meta in SOURCES.items():
        if args and slug not in args:
            continue
        out_dir = RAW / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / meta["filename"]
        try:
            blob = _fetch(meta["url"], meta.get("extra_headers"))
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
        # Throttle on EU AI Act fetches (126 articles+annexes); don't
        # hammer FoLI's WordPress.
        if meta["category"] == "eu_ai_act":
            eu_count += 1
            time.sleep(0.3)
    if failures:
        print(f"\n{len(failures)} failed: {' '.join(failures)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
