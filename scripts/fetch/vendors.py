"""Download the D1 vendor / pricing pages from spec/SOURCES.md.

Three sources, each with its own fetch quirk — see CLAUDE.md "Common
pitfalls" section for the gotcha catalog this fetcher codifies:

  1. OpenRouter — public JSON catalog at /api/v1/models. Plain curl,
     no special headers needed. Returns ~370 models in one stable
     schema (per-model prompt + completion $/Mtok, context window,
     modalities, provider).

  2. Anthropic pricing — the Mintlify docsite is fully JS-hydrated;
     a normal HTML fetch returns "Loading... Loading..." 17x. The
     `.md` extension is the canonical source markdown that hydrates
     the rendered page; ~23 KB of clean tables + prose. Requires
     --compressed (Anthropic serves .md gzip-only and silent-truncates
     to 0 bytes without it).

  3. Google Gemini pricing — `ai.google.dev` redirects normal browser
     UAs into an OAuth `prompt=none&auto_signin=True` loop that curl
     can't break (each /oauth2authorize → /accounts.google.com →
     /oauth2callback?error=interaction_required → back to /pricing,
     forever). `Googlebot/2.1` UA bypasses the auto-signin entirely
     and returns 200 KB of fully-rendered HTML with all 30+ pricing
     sections and 60+ tables intact.

Outputs:
    data/raw/vendors/openrouter-models/catalog.json
    data/raw/vendors/anthropic-pricing/page.md
    data/raw/vendors/google-gemini-pricing/page.html
    data/raw/vendors/<slug>/manifest.json

Re-run is idempotent on sha256: unchanged files left in place; manifest
always rewritten so on-disk state matches.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

RAW = Path("data/raw/vendors")

CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)
GOOGLEBOT_UA = "Googlebot/2.1 (+http://www.google.com/bot.html)"

LICENSE_TEXT = (
    "Public web; vendor-published reference. Quote with attribution; "
    "do not redistribute the page in bulk."
)

VENDORS: dict[str, dict] = {
    "openrouter-models": {
        # The /models page itself is a Next.js SPA — the API endpoint
        # backing it returns the same catalog as flat JSON.
        "fetch_url": "https://openrouter.ai/api/v1/models",
        "display_url": "https://openrouter.ai/models",
        "filename": "catalog.json",
        "ua": CHROME_UA,
        "compressed": True,
        "title": "OpenRouter — Models Catalog",
        "publisher": "OpenRouter",
        "notes": (
            "Per-model JSON: id, name, pricing (prompt/completion/image/request "
            "$/unit), context_length, architecture (modalities, tokenizer), "
            "top_provider, supported_parameters."
        ),
    },
    "anthropic-pricing": {
        # Mintlify-rendered docs page; the .md endpoint is the source.
        "fetch_url": (
            "https://docs.anthropic.com/en/docs/about-claude/pricing.md"
        ),
        "display_url": (
            "https://docs.anthropic.com/en/docs/about-claude/pricing"
        ),
        "filename": "page.md",
        "ua": CHROME_UA,
        "compressed": True,
        "title": "Claude API — Pricing",
        "publisher": "Anthropic",
        "notes": (
            "Markdown source for the docsite pricing page. Includes per-"
            "model base/cache/output rates, batch + prompt-caching discount "
            "mechanics, third-party platform pricing pointers."
        ),
    },
    "google-gemini-pricing": {
        # Googlebot UA dodges the auto-signin OAuth loop.
        "fetch_url": "https://ai.google.dev/gemini-api/docs/pricing",
        "display_url": "https://ai.google.dev/gemini-api/docs/pricing",
        "filename": "page.html",
        "ua": GOOGLEBOT_UA,
        "compressed": True,
        "title": "Gemini API — Developer Pricing",
        "publisher": "Google",
        "notes": (
            "Server-rendered HTML. Per-model free / paid tier pricing, "
            "context-cache + batch discount tiers, Live API pricing."
        ),
    },
}


def _fetch(url: str, ua: str, compressed: bool) -> bytes:
    cmd = [
        "curl",
        "-sL",
        "--max-time",
        "120",
        "--fail",
        "-A",
        ua,
        "-H",
        "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,"
        "application/json,*/*;q=0.8",
        "-H",
        "Accept-Language: en-US,en;q=0.5",
    ]
    if compressed:
        cmd.append("--compressed")
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
        "corpus": "vendors",
        "doc_id": slug,
        "title": meta["title"],
        "publisher": meta["publisher"],
        "source_url": meta["display_url"],
        "fetch_url": meta["fetch_url"],
        "fetched_at": date.today().isoformat(),
        "license": LICENSE_TEXT,
        "notes": meta["notes"],
        "files": [
            {"path": meta["filename"], "sha256": sha, "bytes": len(blob)},
        ],
    }
    (file_path.parent / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    args = set(sys.argv[1:])  # optional slug filter for retries
    failures: list[str] = []
    for slug, meta in VENDORS.items():
        if args and slug not in args:
            continue
        out_dir = RAW / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / meta["filename"]
        try:
            blob = _fetch(meta["fetch_url"], meta["ua"], meta["compressed"])
        except Exception as e:
            print(f"FAIL {slug}: {e}", file=sys.stderr)
            failures.append(slug)
            continue
        if not blob:
            print(f"FAIL {slug}: empty body", file=sys.stderr)
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
