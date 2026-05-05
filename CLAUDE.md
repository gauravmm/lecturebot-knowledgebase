# CLAUDE.md

Project-local memory for the lecture-knowledge corpus. Read this and
`spec/PROGRESS.md` first when picking up a fresh session.

## What this is

A retrieval corpus for a guest lecture on AI in business school. The
chat layer (Telegram bot, model, orchestrator, persistence, Mermaid
rendering, etc.) is owned by a separate workstream and **out of scope
here**. This repo only owns the **data side**: ingest, chunking,
indexing, and the `search` / `fetch_doc` tool surface.

## Where things live

- `spec/ROUGH.md` — authoritative rough spec for the data side
  (scope, retrieval contract, chunking strategy, open questions,
  milestones). Sections §2 and §3 are what matters here.
- `spec/SOURCES.md` — candidate corpora and ingest notes per category.
- `spec/LAYOUT.md` — on-disk layout (`raw/`, `processed/`, `index/`,
  `cache/`, `exports/`). Conventions for manifests, chunk JSONL schema,
  embedding cache.
- `spec/PROGRESS.md` — what's been done vs. what's next. Read this
  to orient on a fresh context window.
- `data/raw/` — immutable originals. Top-level dirs are flat,
  descriptive corpus names (no letter prefix; LAYOUT.md was updated to
  drop that convention). Current corpora: `lecturer/`, `memes/`,
  `ai_index/`, `epoch_models/`, `owid/`.
- `data/processed/` — normalized JSONL chunks, mirroring the raw
  corpus layout. One file per source doc for lectures and AI Index;
  one bundled file each for memes / Epoch / OWID.
- `scripts/process/` — one script per corpus. Currently:
  `lectures.py`, `memes.py`, `ai_index.py`, `epoch_models.py`,
  `owid.py`. Each reads its corpus's `manifest.json` and emits
  per-doc JSONL.
- `scripts/inspect/` — read-only helpers over the processed JSONL.
  `chunk_stats.py` reports per-corpus counts and the token-size
  distribution (flags chunks over the 800-token cap; uses real
  tiktoken cl100k_base; prefers `*.rechunked.jsonl` sidecars over
  the originals when both are present).
- `scripts/index/` — `build_bm25.py`, `build_dense.py`,
  `build_meta.py`, `package.py`. Run via `uv run rebuild` (see
  below); each is independently idempotent if you want to rerun
  one stage.
- `lecture_knowledge/` — installable Python package exposing
  `search(query, corpus, k)` and `fetch_doc(id)` over the built
  index. Loaded lazily; cold first call ~6s (model load), warm
  queries 10–25 ms. Two consumption surfaces:
  - In-process Python: `from lecture_knowledge.retrieve import
    search, fetch_doc`. Cheapest path; the chat-layer workstream
    can use this if it wants tight coupling.
  - HTTP MCP server: `uv run knowledge-mcp` exposes the same two
    tools over Streamable HTTP at `http://127.0.0.1:8765/mcp`.
    Decoupled from any specific chat backend; any MCP-aware client
    (custom backends via the official `mcp` SDK, IDE plugins, etc.)
    can hit it. See `lecture_knowledge/mcp_server.py`.
- `data/cache/embeddings/` — sha256(model_id+text)-keyed `.npy`
  per chunk. Gitignored; reproducible from `data/processed/`.
- `data/index/` — built BM25 dump + FAISS flat-IP +
  `chunk_meta.parquet` (text folded in). Gitignored.
- `data/exports/` — `index_<date>.tar.zst` (~100 MB), the
  self-contained drop the chat layer loads. Gitignored.
- `.claude/skills/` — `lecture-indexer` and `meme-indexer` codify
  the schemas and procedures used to ingest those two corpora. Reuse
  them when adding similar sources.

## Tooling

- **Python**: `uv` for everything. `uv add <pkg>` to add a dep,
  `uv run python ...` to execute. Project uses Python 3.14.
- **Deps in use**: `pymupdf` (PDF text extraction),
  `python-pptx` (slide deck text extraction), `beautifulsoup4` + `lxml`
  (HTML scraping for OWID and any future HTML corpora — vendor pricing
  pages, OWID grapher pages, etc.).
- **Pre-commit hook**: markdownlint-cli2 runs on every commit. Config
  at `.markdownlint.jsonc` (MD036 and MD013 disabled to allow our
  bold-as-sublabel and long-line writing style). MD040, MD060, MD031
  are active — fence languages, table padding, blank lines around
  fences are all enforced.
- **Git**: clean history, root commit + ingest commit. Don't amend;
  make new commits. Don't push without being asked.

## Useful one-liners

- Re-process all corpora: run each `scripts/process/*.py` script,
  e.g. `for f in scripts/process/*.py; do uv run python "$f"; done`.
- Token-size + chunk-count audit across every processed JSONL:
  `uv run python scripts/inspect/chunk_stats.py`. Use this after any
  ingest to see corpus shape and which chunks blow past the 800-token
  cap.
- **Rebuild the retrieval index end-to-end: `uv run rebuild`.**
  Chains rechunk → bm25 → dense → meta → package in order. ~20 s
  when the embedding cache is warm; first cold rebuild is ~80 s
  (the bge-base-en-v1.5 embed pass is the bottleneck). Each stage
  is idempotent — if you only changed one corpus, re-running the
  whole chain still only re-embeds the cache misses.
- Ad-hoc query (in-process): `uv run python -c 'from
  lecture_knowledge.retrieve import search; print(search("EU AI
  Act high-risk", k=3))'`.
- Serve as MCP over HTTP: `uv run knowledge-mcp` (default
  `127.0.0.1:8765`, override with `--host`/`--port`). Endpoint is
  `/mcp`; tools are `search` and `fetch_doc`.
- End-to-end MCP server test: `uv run python
  scripts/inspect/mcp_e2e.py`. Spawns the server on an ephemeral
  port, drives it via the official `mcp` SDK client, asserts the
  tool surface + result schemas + corpus filter, tears the server
  down. Exit 0 = pass.
- Run the linter manually: `uv run pre-commit run --all-files`
- Stage a re-fetch: edit the relevant raw manifest, then re-run the
  process script for that corpus, then `uv run rebuild`.

## Things not to redo

- Don't re-ingest the lecturer corpus, memes, AI Index 2026, Epoch
  notable models, OWID AI topic page, the 5 C1 consulting reports
  (McKinsey ×2, BCG, Bain, Deloitte), the 35 C2+C3+lecturer-
  reading-list essays, the 3 D1 vendor pricing pages
  (OpenRouter + Anthropic + Google Gemini), the 44-video F3
  YouTube whitelist, the 60 B1 EDGAR filings, the 21 B2 earnings
  docs, the 16 B3 shareholder letters, the F2 regulation corpus
  (NIST AI RMF + GenAI Profile, EU AI Act articles + annexes,
  US AI EOs + AI Action Plan, ISO/IEC 42001 abstract), or the
  12 E3 Crunchbase News funding articles — all done. See
  `spec/PROGRESS.md` for what was processed and where the
  manifests live.
- Don't add a `recommended_books` field to lecture manifests. We
  removed it deliberately — the `external_links` array carries the
  same content with URLs.
- Don't add `audience`, `abstract`, or exact `date` fields to lecture
  manifests. Removed deliberately.
- The NTU BMES workshop lecture was dropped (duplicate content with
  the astar workshop). Don't re-ingest from
  `gauravmanek.com/lectures/2026/ntu-bmes-workshop/`.
- Don't include a title field on YouTube/Vimeo URL entries — agents
  guess wrong. URL only.

## Common pitfalls (lessons from prior runs)

- **Subagent JSON output**: agents sometimes emit unescaped quotes
  inside `ocr_text` or other free-text fields. Validate with
  `python3 -c "import json,sys; [json.load(open(p)) for p in sys.argv[1:]]" data/raw/memes/*.json`
  before trusting a batch.
- **Embedded videos** on lecture pages are usually `<iframe>` tags
  that WebFetch's HTML→markdown pass strips. Always `curl` the raw
  HTML and grep for `youtube.com/embed`, `youtu.be/`, `<iframe`,
  `data-src` to catch them. The `lecture-indexer` skill covers this.
- **Allegorical memes** need Sonnet-or-better. Haiku misreads
  composition (counts figures wrong, mis-attributes speech bubbles).
  Stick with Sonnet for the meme-indexer batch.
- **Slide URLs may be relative or point at GitHub release tags**
  (not direct downloads). Resolve to the actual binary URL before
  curl. Ask the user if a slide repo is unclear — they may have a
  release URL in mind.
- **OWID topic pages are hub pages, not articles.** The H3 elements
  on `ourworldindata.org/<topic>` are *cards linking to other OWID
  articles*, not section headings of the page itself. Splitting by H3
  produces tiny noise chunks. Treat OWID topic pages as: lead prose
  chunk + linked-articles index chunk. Section anchor IDs are
  JS-rendered and not in static HTML, so cite the page URL only.
- **Cloudflare bot walls.** OpenAI's `platform.openai.com` returns
  403 to plain curl. Anything that curl-403s probably needs a
  Playwright headless-browser fetch path. OpenRouter is curl-fine
  (and ships a clean public JSON catalog at `/api/v1/models` —
  use that, not the `/models` SPA shell). Mistral, Cohere, Together,
  Fireworks, DeepSeek, Groq, xAI, Perplexity also curl-fine.
- **Mintlify-hosted docs are JS-hydrated.** `docs.anthropic.com`
  pages return ~25KB of HTML where the entire body is "Loading…"
  ×17 — the pricing tables only appear after client-side hydration.
  Workaround: every page exposes its source markdown at the same
  URL with a `.md` suffix
  (`https://docs.anthropic.com/en/docs/about-claude/pricing.md`),
  served gzip-only, so you must pass `--compressed` or curl
  silent-truncates to 0 bytes. Codified in `scripts/fetch/vendors.py`.
- **Google AI docs OAuth loop.** `ai.google.dev/...` redirects
  normal browser UAs into an endless `oauth2authorize → accounts.
  google.com → oauth2callback?error=interaction_required → /<page>`
  loop that curl can't break (the `signin=autosignin` cookie keeps
  re-arming). `Googlebot/2.1 (+http://www.google.com/bot.html)` UA
  bypasses the auto-signin and returns the fully-rendered page.
  Codified in `scripts/fetch/vendors.py`.
- **McKinsey WAF.** `www.mckinsey.com/~/media/...` PDFs require the
  full browser-style header set or curl gets `code=000` /
  `exit 92`. Send User-Agent (Chrome desktop), Accept,
  Accept-Language, Accept-Encoding, and a Referer; default HTTP/2
  is fine. **Don't use `--http1.1`** — McKinsey serves it byte-by-
  byte and curl times out at 5 min. **Don't use `urllib`** — body
  read stalls even when HEAD shows 200. The fetcher at
  `scripts/fetch/consulting.py` codifies this.
- **Sec-Fetch-* + Upgrade-Insecure-Requests** are required by
  some smaller-site WAFs (`6startupstages.com` returns 403 without
  them). The richer header set in `scripts/fetch/essays.py`
  (UA + Accept + Accept-Language + Accept-Encoding +
  Upgrade-Insecure-Requests + Sec-Fetch-Dest/Mode/Site/User) is
  the safe default for HTML pages going forward.
- **JS-rendered SPAs.** YC Library (`ycombinator.com/library/...`)
  and AngelList blog (`angellist.com/blog/...`) hydrate the article
  body client-side; static HTML is just a navigation shell. Any
  page that returns 0–100 chars of prose after our bs4 extraction
  is probably one of these — needs Playwright. Same family:
  `claude.com/pricing` (vendor side, see D1 notes).
- **YouTube auto-captions are rolling-window.** Each cue re-emits
  the previous cue's tail before adding new tokens (one phrase
  shows up 2–3× across consecutive cues). Naive concatenation
  triples chunk word counts. The processor's `_dedup_overlap`
  in `scripts/process/youtube.py` strips the longest token-suffix
  of cue N-1 that prefixes cue N. Don't disable it — chunks become
  unreadable ("30-minute talk on large language models 30-minute
  talk on large language models 30-minute talk").
- **Manual-sub coverage on "trusted-author" channels is patchy.**
  Karpathy's entire channel is auto-only (every video, including
  "Intro to LLMs"). 3B1B is consistently manual-sub. Dwarkesh's
  long-form episodes are manual-sub but his short-clip uploads
  are auto-only. Lex Fridman's manual-sub language code varies
  (`en` vs `en-ehkg1hFWq8A` per-track ID); accept any `^en` prefix.
  No Priors is fully auto-only and was dropped at curation. The
  fetcher's `TRUSTED_AUTOSUB_CHANNELS` allowlist (Karpathy / 3B1B
  / Dwarkesh) is what makes the corpus viable.
- **snap-confined yt-dlp can't write to /tmp.** The Ubuntu snap
  build refuses writes outside `$HOME` with `Permission denied`
  on `*.part` files. Always run yt-dlp with cwd inside the project
  tree (the F3 fetcher does this via `subprocess.run(..., cwd=...)`)
  or install yt-dlp via `uv add yt-dlp` to bypass snap entirely.
- **NIST nvlpubs HEAD lies.** `nvlpubs.nist.gov/nistpubs/ai/...`
  returns `HTTP/2 404` to HEAD and to GET-without-Referer, but the
  same GET with `Referer: https://www.nist.gov/itl/ai-risk-management-
  framework` returns `200 application/pdf` with the actual document.
  Always GET, never HEAD-probe; always send the Referer for NIST
  PDFs. Codified in `scripts/fetch/regulation.py`.
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
- **Cloudflare bot walls (E1/E2 funding sources).** Tried and
  dropped at fetch time: `dealroom.co` (HubSpot lead-capture form
  gates on the report PDFs), `files.pitchbook.com` (Cloudflare
  challenge `cf-mitigated: challenge`, returns 403), `cbinsights.
  com` (CloudFront WAF, returns 202 challenge). All would need
  Playwright. The Stanford AI Index Report (already in corpus)
  covers funding numbers in its Investment chapter, so we just
  index Crunchbase News articles for narrative coverage of E3.

## Subagent dispatch pattern

When batching ingest:

- Each subagent prompt must be **self-contained** — they don't
  inherit context. Include the schema, hard rules, and gotchas inline,
  not a reference to a file they can't see.
- Run them with `run_in_background: true` so notifications stream
  back. The runtime fires a system notification per completion — do
  NOT treat those as user input.
- Pick the right model per task: lecture indexing is Haiku-fine;
  meme captioning needs Sonnet for allegorical content. Don't
  reach for Opus unless quality is publication-grade-critical
  (5× Sonnet cost, marginal gain on this corpus).
