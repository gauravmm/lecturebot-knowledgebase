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

- `spec/` — authoritative rough spec for the data side.
  - `ROUGH.md` — scope, retrieval contract, chunking strategy, open
    questions, milestones (§2 and §3 are what matter here).
  - `SOURCES.md` — candidate corpora and ingest notes per category.
  - `LAYOUT.md` — on-disk layout. Conventions for manifests, chunk
    JSONL schema, embedding cache.
  - `PROGRESS.md` — what's been done vs. what's next. Read this to
    orient on a fresh context window.
- `data/raw/` — immutable originals. Top-level dirs are flat,
  descriptive corpus names (no letter prefix; LAYOUT.md was updated
  to drop that convention).
- `data/processed/` — normalized JSONL chunks, mirroring the raw
  corpus layout. One file per source doc for some corpora; one
  bundled file for others. Per-corpus rules in `spec/LAYOUT.md`.
- `data/cache/embeddings/` — sha256(model_id+text)-keyed `.npy` per
  chunk. Gitignored; reproducible from `data/processed/`.
- `data/index/` — built BM25 dump + FAISS flat-IP +
  `chunk_meta.parquet` (text folded in). Gitignored.
- `data/exports/` — `index_<date>.tar.zst` (~100 MB), the
  self-contained drop the chat layer loads. Gitignored.
- `scripts/fetch/` — one fetcher per source family. WAF /
  anti-bot pitfalls live in `scripts/fetch/CLAUDE.md`.
- `scripts/process/` — one processor per corpus, plus `rechunk.py`.
  Ingest pitfalls + subagent dispatch pattern live in
  `scripts/process/CLAUDE.md`.
- `scripts/index/` — `build_bm25.py`, `build_dense.py`,
  `build_meta.py`, `package.py`. Run via `uv run rebuild`; each
  stage is independently idempotent.
- `scripts/inspect/` — read-only helpers. `chunk_stats.py` for
  per-corpus token-size audits (flags > 800-token cap; uses real
  tiktoken cl100k_base; prefers `*.rechunked.jsonl` sidecars over
  the originals). `mcp_e2e.py` end-to-end MCP test.
- `lecture_knowledge/` — installable package: `search`, `fetch_doc`,
  the MCP server, and warmup. Details in
  `lecture_knowledge/CLAUDE.md`.
- `.claude/skills/` — `lecture-indexer` and `meme-indexer` codify
  the schemas and procedures used to ingest those two corpora.
  Reuse them when adding similar sources.

## Tooling

- **Python**: `uv` for everything. `uv add <pkg>` to add a dep,
  `uv run python ...` to execute. Project uses Python 3.14.
- **Deps in use**: `pymupdf` (PDF text extraction),
  `python-pptx` (slide deck text extraction), `beautifulsoup4` +
  `lxml` (HTML scraping for OWID and any future HTML corpora).
- **Pre-commit hook**: markdownlint-cli2 runs on every commit.
  Config at `.markdownlint.jsonc` (MD036 and MD013 disabled to
  allow our bold-as-sublabel and long-line writing style). MD040,
  MD060, MD031 are active — fence languages, table padding, blank
  lines around fences are all enforced.
- **Git**: clean history, root commit + ingest commit. Don't amend;
  make new commits. Don't push without being asked.

## Useful one-liners

- **Rebuild the retrieval index end-to-end: `uv run rebuild`.**
  Chains rechunk → bm25 → dense → meta → package in order. ~20 s
  when the embedding cache is warm; first cold rebuild is ~80 s
  (the bge-base-en-v1.5 embed pass is the bottleneck). Each stage
  is idempotent — if you only changed one corpus, re-running the
  whole chain still only re-embeds the cache misses.
- Re-process all corpora: run each `scripts/process/*.py` script,
  e.g. `for f in scripts/process/*.py; do uv run python "$f"; done`.
- Token-size + chunk-count audit across every processed JSONL:
  `uv run python scripts/inspect/chunk_stats.py`. Use this after
  any ingest to see corpus shape and which chunks blow past the
  800-token cap.
- Run the linter manually: `uv run pre-commit run --all-files`.
- Stage a re-fetch: edit the relevant raw manifest, then re-run the
  process script for that corpus, then `uv run rebuild`.

For retrieval / MCP-server commands, see
`lecture_knowledge/CLAUDE.md`.

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
- Don't add `audience`, `abstract`, or exact `date` fields to
  lecture manifests. Removed deliberately.
- The NTU BMES workshop lecture was dropped (duplicate content with
  the astar workshop). Don't re-ingest from
  `gauravmanek.com/lectures/2026/ntu-bmes-workshop/`.
- Don't include a title field on YouTube/Vimeo URL entries — agents
  guess wrong. URL only.

## See also

- `scripts/fetch/CLAUDE.md` — fetcher pitfalls (WAFs, anti-bot,
  yt-dlp, manual-sub allowlist).
- `scripts/process/CLAUDE.md` — ingest pitfalls (subagent JSON,
  embedded videos, OWID hubs, YouTube dedup, slide URLs) +
  subagent dispatch pattern.
- `lecture_knowledge/CLAUDE.md` — retrieval engine, MCP server
  transports, warmup timings, CPU pinning.
