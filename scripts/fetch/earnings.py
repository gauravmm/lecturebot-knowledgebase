"""Download the scripted B2 earnings corpus used by the repo."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

RAW = Path("data/raw/earnings")

CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)
SEC_UA = "lecture-knowledge research maneks@gmail.com"
LICENSE_IR = "Public IR-site publication. Quote with attribution."
LICENSE_SEC = "Public domain (US government filing)."

SOURCES: dict[str, dict] = {
    "amzn-earnings-q1-2025": {
        "ticker": "AMZN",
        "company_name": "Amazon.com Inc",
        "fiscal_period": "Q1 2025",
        "calendar_quarter_end": "2025-03-31",
        "transcript_kind": "ceo_quote_article",
        "title": "Amazon earnings report: Q1 2025 highlights",
        "source_url": "https://www.aboutamazon.com/news/company-news/amazon-q1-2025-earnings",
        "filename": "page.html",
        "license": LICENSE_IR,
    },
    "amzn-earnings-q1-2026": {
        "ticker": "AMZN",
        "company_name": "Amazon.com Inc",
        "fiscal_period": "Q1 2026",
        "calendar_quarter_end": "2026-03-31",
        "transcript_kind": "ceo_quote_article",
        "title": "Amazon Q1 2026 earnings report: Read the release",
        "source_url": "https://www.aboutamazon.com/news/company-news/amazon-q1-2026-earnings",
        "filename": "page.html",
        "license": LICENSE_IR,
    },
    "amzn-earnings-q2-2025": {
        "ticker": "AMZN",
        "company_name": "Amazon.com Inc",
        "fiscal_period": "Q2 2025",
        "calendar_quarter_end": "2025-06-30",
        "transcript_kind": "ceo_quote_article",
        "title": "Amazon Q2 earnings report: Read the release",
        "source_url": "https://www.aboutamazon.com/news/company-news/amazon-q2-2025-earnings",
        "filename": "page.html",
        "license": LICENSE_IR,
    },
    "amzn-earnings-q3-2025": {
        "ticker": "AMZN",
        "company_name": "Amazon.com Inc",
        "fiscal_period": "Q3 2025",
        "calendar_quarter_end": "2025-09-30",
        "transcript_kind": "ceo_quote_article",
        "title": "Amazon Q3 earnings report: Read the release",
        "source_url": "https://www.aboutamazon.com/news/company-news/amazon-q3-2025-earnings",
        "filename": "page.html",
        "license": LICENSE_IR,
    },
    "amzn-earnings-q4-2025": {
        "ticker": "AMZN",
        "company_name": "Amazon.com Inc",
        "fiscal_period": "Q4 2025",
        "calendar_quarter_end": "2025-12-31",
        "transcript_kind": "ceo_quote_article",
        "title": "Amazon Q4 2025 earnings report: Read the release",
        "source_url": "https://www.aboutamazon.com/news/company-news/amazon-q4-2025-earnings",
        "filename": "page.html",
        "license": LICENSE_IR,
    },
    "amzn-jassy-ads-q1-2026": {
        "ticker": "AMZN",
        "company_name": "Amazon.com Inc",
        "fiscal_period": "Q1 2026",
        "calendar_quarter_end": "2026-03-31",
        "transcript_kind": "ceo_quote_article",
        "title": "Andy Jassy on Amazon Ads growth, AI tools in Q1 2026 earnings",
        "source_url": "https://www.aboutamazon.com/news/company-news/amazon-ceo-andy-jassy-advertising-q1-2026-earnings",
        "filename": "page.html",
        "license": LICENSE_IR,
    },
    "amzn-jassy-aws-ai-q1-2026": {
        "ticker": "AMZN",
        "company_name": "Amazon.com Inc",
        "fiscal_period": "Q1 2026",
        "calendar_quarter_end": "2026-03-31",
        "transcript_kind": "ceo_quote_article",
        "title": "Amazon CEO Andy Jassy on why customers are choosing AWS for AI",
        "source_url": "https://www.aboutamazon.com/news/company-news/amazon-ceo-andy-jassy-aws-ai-q1-2026-earnings",
        "filename": "page.html",
        "license": LICENSE_IR,
    },
    "amzn-jassy-chips-q1-2026": {
        "ticker": "AMZN",
        "company_name": "Amazon.com Inc",
        "fiscal_period": "Q1 2026",
        "calendar_quarter_end": "2026-03-31",
        "transcript_kind": "ceo_quote_article",
        "title": "Amazon CEO Andy Jassy on the growth of Amazon’s chips business",
        "source_url": "https://www.aboutamazon.com/news/company-news/amazon-ceo-andy-jassy-amazon-chips-business-q1-2026-earnings",
        "filename": "page.html",
        "license": LICENSE_IR,
    },
    "amzn-jassy-letter-2025": {
        "ticker": "AMZN",
        "company_name": "Amazon.com Inc",
        "fiscal_period": "FY2025 letter",
        "calendar_quarter_end": None,
        "transcript_kind": "ceo_quote_article",
        "title": "Amazon CEO Andy Jassy’s 2025 Letter to Shareholders",
        "source_url": "https://www.aboutamazon.com/news/company-news/amazon-ceo-andy-jassy-2025-shareholder-letter",
        "filename": "page.html",
        "license": LICENSE_IR,
    },
    "amzn-jassy-stores-q1-2026": {
        "ticker": "AMZN",
        "company_name": "Amazon.com Inc",
        "fiscal_period": "Q1 2026",
        "calendar_quarter_end": "2026-03-31",
        "transcript_kind": "ceo_quote_article",
        "title": "CEO Andy Jassy on Amazon Stores growth, delivery speed in Q1 2026",
        "source_url": "https://www.aboutamazon.com/news/company-news/amazon-ceo-andy-jassy-stores-q1-2026-earnings",
        "filename": "page.html",
        "license": LICENSE_IR,
    },
    "ibm-1q26": {
        "ticker": "IBM",
        "company_name": "International Business Machines Corp",
        "fiscal_period": "1Q26",
        "calendar_quarter_end": "2026-03-31",
        "transcript_kind": "prepared_remarks",
        "title": "IBM 1Q26 Earnings Call — Prepared Remarks",
        "source_url": "https://www.ibm.com/downloads/documents/us-en/15db805fff4249f1",
        "hub_url": "https://www.ibm.com/investor/earnings-1q26",
        "filename": "prepared_remarks.pdf",
        "license": LICENSE_IR,
    },
    "ibm-2q25": {
        "ticker": "IBM",
        "company_name": "International Business Machines Corp",
        "fiscal_period": "2Q25",
        "calendar_quarter_end": "2025-06-30",
        "transcript_kind": "prepared_remarks",
        "title": "IBM 2Q25 Earnings Call — Prepared Remarks",
        "source_url": "https://www.ibm.com/downloads/documents/us-en/131cf87ac1331e91",
        "hub_url": "https://www.ibm.com/investor/earnings-2q25",
        "filename": "prepared_remarks.pdf",
        "license": LICENSE_IR,
    },
    "ibm-3q25": {
        "ticker": "IBM",
        "company_name": "International Business Machines Corp",
        "fiscal_period": "3Q25",
        "calendar_quarter_end": "2025-09-30",
        "transcript_kind": "prepared_remarks",
        "title": "IBM 3Q25 Earnings Call — Prepared Remarks",
        "source_url": "https://www.ibm.com/downloads/documents/us-en/1443d5dda6cf4179",
        "hub_url": "https://www.ibm.com/investor/earnings-3q25",
        "filename": "prepared_remarks.pdf",
        "license": LICENSE_IR,
        "notes": (
            "IBM investor page links 3Q25 and 4Q25 prepared remarks to the same "
            "document ID. Verify PDF content if IBM changes the destination."
        ),
    },
    "msft-fy25q3": {
        "ticker": "MSFT",
        "company_name": "Microsoft Corp",
        "fiscal_period": "FY25 Q3",
        "calendar_quarter_end": "2025-03-31",
        "transcript_kind": "full_qanda",
        "title": "Microsoft FY25 Q3 Earnings Call Transcript (Full Q&A)",
        "source_url": "https://cdn-dynmedia-1.microsoft.com/is/content/microsoftcorp/TranscriptFY25Q3",
        "filename": "transcript.docx",
        "license": LICENSE_IR,
    },
    "msft-fy25q4": {
        "ticker": "MSFT",
        "company_name": "Microsoft Corp",
        "fiscal_period": "FY25 Q4",
        "calendar_quarter_end": "2025-06-30",
        "transcript_kind": "full_qanda",
        "title": "Microsoft FY25 Q4 Earnings Call Transcript (Full Q&A)",
        "source_url": "https://cdn-dynmedia-1.microsoft.com/is/content/microsoftcorp/TranscriptQandAFY25q4",
        "filename": "transcript.docx",
        "license": LICENSE_IR,
    },
    "msft-fy26q1": {
        "ticker": "MSFT",
        "company_name": "Microsoft Corp",
        "fiscal_period": "FY26 Q1",
        "calendar_quarter_end": "2025-09-30",
        "transcript_kind": "full_qanda",
        "title": "Microsoft FY26 Q1 Earnings Call Transcript (Full Q&A)",
        "source_url": "https://cdn-dynmedia-1.microsoft.com/is/content/microsoftcorp/TranscriptFY26Q1",
        "filename": "transcript.docx",
        "license": LICENSE_IR,
    },
    "msft-fy26q2": {
        "ticker": "MSFT",
        "company_name": "Microsoft Corp",
        "fiscal_period": "FY26 Q2",
        "calendar_quarter_end": "2025-12-31",
        "transcript_kind": "full_qanda",
        "title": "Microsoft FY26 Q2 Earnings Call Transcript (Full Q&A)",
        "source_url": "https://cdn-dynmedia-1.microsoft.com/is/content/microsoftcorp/TranscriptQandAFY26q2",
        "filename": "transcript.docx",
        "license": LICENSE_IR,
    },
    "nvda-fy26q1": {
        "ticker": "NVDA",
        "company_name": "NVIDIA Corp",
        "fiscal_period": "FY26 Q1",
        "calendar_quarter_end": "2025-04-27",
        "transcript_kind": "cfo_commentary",
        "title": "NVIDIA FY26 Q1 CFO Commentary (8-K Exhibit 99.2)",
        "source_url": "https://www.sec.gov/Archives/edgar/data/1045810/000104581025000115/q1fy26cfocommentary.htm",
        "accession": "0001045810-25-000115",
        "filing_date": "2025-05-28",
        "filename": "cfo_commentary.htm",
        "license": LICENSE_SEC,
    },
    "nvda-fy26q2": {
        "ticker": "NVDA",
        "company_name": "NVIDIA Corp",
        "fiscal_period": "FY26 Q2",
        "calendar_quarter_end": "2025-07-27",
        "transcript_kind": "cfo_commentary",
        "title": "NVIDIA FY26 Q2 CFO Commentary (8-K Exhibit 99.2)",
        "source_url": "https://www.sec.gov/Archives/edgar/data/1045810/000104581025000207/q2fy26cfocommentary.htm",
        "accession": "0001045810-25-000207",
        "filing_date": "2025-08-27",
        "filename": "cfo_commentary.htm",
        "license": LICENSE_SEC,
    },
    "nvda-fy26q3": {
        "ticker": "NVDA",
        "company_name": "NVIDIA Corp",
        "fiscal_period": "FY26 Q3",
        "calendar_quarter_end": "2025-10-26",
        "transcript_kind": "cfo_commentary",
        "title": "NVIDIA FY26 Q3 CFO Commentary (8-K Exhibit 99.2)",
        "source_url": "https://www.sec.gov/Archives/edgar/data/1045810/000104581025000228/q3fy26cfocommentary.htm",
        "accession": "0001045810-25-000228",
        "filing_date": "2025-11-19",
        "filename": "cfo_commentary.htm",
        "license": LICENSE_SEC,
    },
    "nvda-fy26q4": {
        "ticker": "NVDA",
        "company_name": "NVIDIA Corp",
        "fiscal_period": "FY26 Q4",
        "calendar_quarter_end": "2026-01-26",
        "transcript_kind": "cfo_commentary",
        "title": "NVIDIA FY26 Q4 CFO Commentary (8-K Exhibit 99.2)",
        "source_url": "https://www.sec.gov/Archives/edgar/data/1045810/000104581026000019/q4fy26cfocommentary.htm",
        "accession": "0001045810-26-000019",
        "filing_date": "2026-02-25",
        "filename": "cfo_commentary.htm",
        "license": LICENSE_SEC,
    },
}


def _fetch(url: str) -> bytes:
    host = url.split("/", 3)[2]
    if host.endswith("sec.gov"):
        cmd = [
            "curl",
            "-sL",
            "--compressed",
            "--max-time",
            "300",
            "--fail",
            "-A",
            SEC_UA,
            "-H",
            "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "-H",
            "Accept-Language: en-US,en;q=0.5",
            "-H",
            f"Host: {host}",
            url,
        ]
    else:
        referer = "/".join(url.split("/", 3)[:3]) + "/"
        cmd = [
            "curl",
            "-sL",
            "--compressed",
            "--max-time",
            "180",
            "--fail",
            "-A",
            CHROME_UA,
            "-H",
            "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf,*/*;q=0.8",
            "-H",
            "Accept-Language: en-US,en;q=0.5",
            "-H",
            "Upgrade-Insecure-Requests: 1",
            "-H",
            "Sec-Fetch-Dest: document",
            "-H",
            "Sec-Fetch-Mode: navigate",
            "-H",
            "Sec-Fetch-Site: none",
            "-H",
            "Sec-Fetch-User: ?1",
            "-H",
            f"Referer: {referer}",
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
    args = set(sys.argv[1:])
    failures: list[str] = []
    for slug, meta in SOURCES.items():
        if args and slug not in args:
            continue
        out_dir = RAW / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / meta["filename"]
        try:
            blob = _fetch(meta["source_url"])
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
            print(f"unchanged  {slug:<28} ({len(blob):>9,} B)")
        else:
            target.write_bytes(blob)
            print(f"wrote      {slug:<28} ({len(blob):>9,} B)")
        manifest = {
            "corpus": "earnings",
            "doc_id": slug,
            "ticker": meta["ticker"],
            "company_name": meta["company_name"],
            "fiscal_period": meta["fiscal_period"],
            "calendar_quarter_end": meta["calendar_quarter_end"],
            "transcript_kind": meta["transcript_kind"],
            "title": meta["title"],
            "source_url": meta["source_url"],
            "fetched_at": date.today().isoformat(),
            "license": meta["license"],
            "files": [
                {
                    "path": meta["filename"],
                    "sha256": sha,
                    "bytes": len(blob),
                }
            ],
        }
        for optional in ("hub_url", "accession", "filing_date", "notes"):
            if optional in meta:
                manifest[optional] = meta[optional]
        (out_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
        )
    if failures:
        print(f"\n{len(failures)} failed: {' '.join(failures)}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
