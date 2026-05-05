# scripts/fetch — fetcher pitfalls

One script per source family. Each reads a manifest (typically the
matching `data/raw/<corpus>/manifest.json`) and downloads the raw
payloads referenced from it. Re-running a fetcher is idempotent: it
skips files that are already on disk and the right size.

The repo's history of WAFs, anti-bot challenges, and JS-hydrated
shells is the main thing worth preserving here — it's what makes
the existing fetchers work and tells you what *not* to retry blindly
on a new source.

## HTTP / WAF gotchas

- **Mintlify-hosted docs are JS-hydrated.** `docs.anthropic.com`
  pages return ~25KB of HTML where the entire body is "Loading…"
  ×17 — the pricing tables only appear after client-side hydration.
  Workaround: every page exposes its source markdown at the same
  URL with a `.md` suffix
  (`https://docs.anthropic.com/en/docs/about-claude/pricing.md`),
  served gzip-only, so you must pass `--compressed` or curl
  silent-truncates to 0 bytes. Codified in `vendors.py`.
- **Google AI docs OAuth loop.** `ai.google.dev/...` redirects
  normal browser UAs into an endless `oauth2authorize → accounts.
  google.com → oauth2callback?error=interaction_required → /<page>`
  loop that curl can't break (the `signin=autosignin` cookie keeps
  re-arming). `Googlebot/2.1 (+http://www.google.com/bot.html)` UA
  bypasses the auto-signin and returns the fully-rendered page.
  Codified in `vendors.py`.
- **McKinsey WAF.** `www.mckinsey.com/~/media/...` PDFs require the
  full browser-style header set or curl gets `code=000` /
  `exit 92`. Send User-Agent (Chrome desktop), Accept,
  Accept-Language, Accept-Encoding, and a Referer; default HTTP/2
  is fine. **Don't use `--http1.1`** — McKinsey serves it byte-by-
  byte and curl times out at 5 min. **Don't use `urllib`** — body
  read stalls even when HEAD shows 200. The fetcher at
  `consulting.py` codifies this.
- **Sec-Fetch-* + Upgrade-Insecure-Requests** are required by some
  smaller-site WAFs (`6startupstages.com` returns 403 without
  them). The richer header set in `essays.py` (UA + Accept +
  Accept-Language + Accept-Encoding + Upgrade-Insecure-Requests +
  Sec-Fetch-Dest/Mode/Site/User) is the safe default for HTML
  pages going forward.
- **JS-rendered SPAs.** YC Library (`ycombinator.com/library/...`)
  and AngelList blog (`angellist.com/blog/...`) hydrate the article
  body client-side; static HTML is just a navigation shell. Any
  page that returns 0–100 chars of prose after our bs4 extraction
  is probably one of these — needs Playwright. Same family:
  `claude.com/pricing` (vendor side, see D1 notes).
- **NIST nvlpubs HEAD lies.** `nvlpubs.nist.gov/nistpubs/ai/...`
  returns `HTTP/2 404` to HEAD and to GET-without-Referer, but the
  same GET with `Referer: https://www.nist.gov/itl/ai-risk-management-
  framework` returns `200 application/pdf` with the actual document.
  Always GET, never HEAD-probe; always send the Referer for NIST
  PDFs. Codified in `regulation.py`.
- **EUR-Lex AWS-WAF.** `eur-lex.europa.eu/legal-content/...` returns
  `HTTP/1.1 202 Accepted` with `x-amzn-waf-action: challenge` to
  plain curl — would need Playwright. The Future of Life Institute
  mirror at `artificialintelligenceact.eu/article/<N>/` (and
  `/annex/<N>/`) is server-rendered Divi-WordPress and curl-fine,
  one page per article/annex (113 articles + 13 annexes). Body
  selector is `div.et_pb_post_content`.
- **Revoked US executive orders.** `whitehouse.gov` permanently
  scrubs revoked / superseded EOs from the site (e.g., Trump 2025
  removed Biden's EO 14110 on AI). The legal-of-record copy is on
  `govinfo.gov`'s Federal Register PDF feed
  (`govinfo.gov/content/pkg/FR-YYYY-MM-DD/pdf/<doc-id>.pdf`).
  Use that as the canonical archive URL for any EO that may be
  revoked; current EOs can stay on whitehouse.gov.
- **Cloudflare / anti-bot dead ends.** Tried and dropped at fetch
  time: OpenAI's `platform.openai.com` (403 to plain curl),
  `dealroom.co` (HubSpot lead-capture form gates on report PDFs),
  `files.pitchbook.com` (Cloudflare challenge `cf-mitigated:
  challenge`, 403), `cbinsights.com` (CloudFront WAF, 202
  challenge). All would need Playwright. OpenRouter, Mistral,
  Cohere, Together, Fireworks, DeepSeek, Groq, xAI, Perplexity are
  all curl-fine. For OpenRouter use the public JSON catalog at
  `/api/v1/models`, not the `/models` SPA shell.

## yt-dlp

- **snap-confined yt-dlp can't write to /tmp.** The Ubuntu snap
  build refuses writes outside `$HOME` with `Permission denied` on
  `*.part` files. Always run yt-dlp with cwd inside the project
  tree (the F3 fetcher does this via `subprocess.run(..., cwd=...)`)
  or install yt-dlp via `uv add yt-dlp` to bypass snap entirely.
- **Manual-sub coverage on "trusted-author" channels is patchy.**
  Karpathy's entire channel is auto-only (every video, including
  "Intro to LLMs"). 3B1B is consistently manual-sub. Dwarkesh's
  long-form episodes are manual-sub but his short-clip uploads
  are auto-only. Lex Fridman's manual-sub language code varies
  (`en` vs `en-ehkg1hFWq8A` per-track ID); accept any `^en` prefix.
  No Priors is fully auto-only and was dropped at curation. The
  fetcher's `TRUSTED_AUTOSUB_CHANNELS` allowlist (Karpathy / 3B1B /
  Dwarkesh) is what makes the corpus viable.
