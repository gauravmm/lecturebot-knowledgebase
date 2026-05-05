"""Download the B1 SEC EDGAR filings: per spec/SOURCES.md §B1 we want
the most-recent 10-K and the last 4 10-Qs for each of 12 companies.

EDGAR API:
  - Submissions index per CIK: data.sec.gov/submissions/CIK<10digit>.json
    (lists `recent` filings with form/accession/primaryDocument/filingDate)
  - Primary document URL:
    sec.gov/Archives/edgar/data/<CIK>/<acc-no-stripped-of-dashes>/<primaryDocument>

SEC requires a User-Agent that identifies a real party (their fair-use
guidance — anonymous bots get 403'd). The HEAD endpoint sometimes 403s
even with a valid UA; GET works fine.

Outputs (per filing):
    data/raw/edgar/<TICKER>/<form>_<period>.htm    # raw iXBRL HTML
    data/raw/edgar/<TICKER>/<form>_<period>.json   # per-filing manifest

The .htm files are gitignored (60 filings × 5-10 MB each is heavy and
fully reproducible from the manifest's URL + accession number). Manifests
+ processed JSONL stay in git; re-fetch = `uv run python scripts/fetch/edgar.py`.

Re-run is idempotent on sha256: if the on-disk .htm matches the just-
downloaded body, the file is left as-is. The manifest is rewritten so
on-disk state always reflects truth.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

RAW = Path("data/raw/edgar")

# SEC's fair-use guidance: identify the requester. Pulled from CLAUDE.md
# user email (this is research / educational use).
SEC_UA = "lecture-knowledge research maneks@gmail.com"

# 12 companies per spec/SOURCES.md §B1, with 10-digit CIKs (zero-padded
# as the data.sec.gov endpoint expects).
COMPANIES: dict[str, dict] = {
    "MSFT":  {"cik": "0000789019", "name": "Microsoft Corp"},
    "GOOGL": {"cik": "0001652044", "name": "Alphabet Inc"},
    "META":  {"cik": "0001326801", "name": "Meta Platforms Inc"},
    "NVDA":  {"cik": "0001045810", "name": "NVIDIA Corp"},
    "AMZN":  {"cik": "0001018724", "name": "Amazon.com Inc"},
    "AAPL":  {"cik": "0000320193", "name": "Apple Inc"},
    "CRM":   {"cik": "0001108524", "name": "Salesforce Inc"},
    "ORCL":  {"cik": "0001341439", "name": "Oracle Corp"},
    "PLTR":  {"cik": "0001321655", "name": "Palantir Technologies Inc"},
    "SNOW":  {"cik": "0001640147", "name": "Snowflake Inc"},
    "ADBE":  {"cik": "0000796343", "name": "Adobe Inc"},
    "IBM":   {"cik": "0000051143", "name": "International Business Machines Corp"},
}

# 1 most-recent 10-K + 4 most-recent 10-Qs per company.
TARGET_FORMS = {
    "10-K": 1,
    "10-Q": 4,
}

LICENSE_TEXT = (
    "Public domain (US government filing). EDGAR fair-use applies; "
    "identify the requester via User-Agent on every request."
)


def _curl(url: str) -> bytes:
    cmd = [
        "curl",
        "-sL",
        "--compressed",
        "--max-time", "300",
        "--fail",
        "-A", SEC_UA,
        "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "-H", "Accept-Language: en-US,en;q=0.5",
        "-H", "Host: " + url.split("/", 3)[2],
        url,
    ]
    res = subprocess.run(cmd, capture_output=True, check=False)
    if res.returncode != 0:
        raise RuntimeError(
            f"curl failed (exit {res.returncode}) for {url}: "
            f"{res.stderr.decode(errors='replace').strip() or '<no stderr>'}"
        )
    return res.stdout


def _list_filings(cik: str) -> list[dict]:
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    payload = json.loads(_curl(url))
    recent = payload.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    out: list[dict] = []
    for i, form in enumerate(forms):
        if form not in TARGET_FORMS:
            continue
        out.append({
            "form": form,
            "accession": recent["accessionNumber"][i],
            "primary_document": recent["primaryDocument"][i],
            "filing_date": recent["filingDate"][i],
            "report_date": recent["reportDate"][i],
            "fiscal_year_end_month": payload.get("fiscalYearEnd", "")[:2] or None,
        })
    return out


def _select_target(filings: list[dict]) -> list[dict]:
    """Return up to TARGET_FORMS[form] most-recent filings per form, in
    filing-date-descending order."""
    out: list[dict] = []
    by_form: dict[str, list[dict]] = {}
    for f in filings:
        by_form.setdefault(f["form"], []).append(f)
    for form, n in TARGET_FORMS.items():
        items = sorted(by_form.get(form, []), key=lambda f: f["filing_date"], reverse=True)
        out.extend(items[:n])
    return out


def _doc_url(cik: str, accession: str, primary_document: str) -> str:
    cik_int = str(int(cik))  # strip leading zeros
    acc_clean = accession.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_clean}/{primary_document}"


def _filing_basename(form: str, report_date: str) -> str:
    # `10-K_2025-06-30` style
    return f"{form}_{report_date}"


def _fetch_filing(ticker: str, meta: dict, filing: dict) -> str:
    out_dir = RAW / ticker
    out_dir.mkdir(parents=True, exist_ok=True)
    base = _filing_basename(filing["form"], filing["report_date"])
    htm_path = out_dir / f"{base}.htm"
    manifest_path = out_dir / f"{base}.json"

    url = _doc_url(meta["cik"], filing["accession"], filing["primary_document"])
    blob = _curl(url)
    sha = hashlib.sha256(blob).hexdigest()

    status = "wrote"
    if htm_path.exists() and hashlib.sha256(htm_path.read_bytes()).hexdigest() == sha:
        status = "unchanged"
    else:
        htm_path.write_bytes(blob)

    manifest = {
        "corpus": "edgar",
        "doc_id": f"{ticker}-{base}",
        "ticker": ticker,
        "company_name": meta["name"],
        "cik": meta["cik"],
        "form": filing["form"],
        "filing_date": filing["filing_date"],
        "report_date": filing["report_date"],
        "accession": filing["accession"],
        "source_url": url,
        "filing_index_url": (
            f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
            f"&CIK={meta['cik']}&type={filing['form']}&dateb=&owner=include&count=40"
        ),
        "fetched_at": date.today().isoformat(),
        "license": LICENSE_TEXT,
        "files": [
            {"path": htm_path.name, "sha256": sha, "bytes": len(blob)},
        ],
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return status


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    args = set(sys.argv[1:])  # optional ticker filter
    failures: list[str] = []
    for ticker, meta in COMPANIES.items():
        if args and ticker not in args:
            continue
        try:
            all_filings = _list_filings(meta["cik"])
        except Exception as e:
            print(f"FAIL  {ticker} index: {e}", file=sys.stderr)
            failures.append(ticker)
            continue
        targets = _select_target(all_filings)
        print(f"[{ticker}] {meta['name']:<40} -> {len(targets)} filings to fetch")
        # SEC fair-use: ≤10 req/s. Sleep 100ms between fetches.
        for f in targets:
            try:
                status = _fetch_filing(ticker, meta, f)
                base = _filing_basename(f["form"], f["report_date"])
                print(f"  {status:<10}  {base:<25}  acc={f['accession']}")
            except Exception as e:
                print(f"  FAIL      {f['form']} {f['report_date']}: {e}", file=sys.stderr)
                failures.append(f"{ticker}:{f['form']}_{f['report_date']}")
            time.sleep(0.15)
        time.sleep(0.3)
    if failures:
        print(f"\n{len(failures)} failure(s): {' '.join(failures)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
