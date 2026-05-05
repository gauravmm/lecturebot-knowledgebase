# Progress

Snapshot of where the lecture-knowledge data side stands. Read this
plus `CLAUDE.md` first when resuming on a fresh context window.

Last updated: 2026-05-04 (retrieval-side build: rechunker + BM25 +
dense FAISS + chunk_meta.parquet + `lecture_knowledge.retrieve` +
packaged tarball).

---

## Summary

- **Specs written** for the data-side scope (retrieval, layout,
  sources). Chat-layer concerns are owned by a separate workstream
  and not covered here. `SOURCES.md` records the actual picks for
  every ingested category.
- **Tooling**: uv project, pre-commit + markdownlint-cli2.
  Deps: `pymupdf`, `python-pptx`, `beautifulsoup4`, `lxml`.
- **Fourteen corpora ingested end-to-end**:
  - **Lecturer corpus** — 10 lectures from gauravmanek.com, page text
    plus per-slide content plus speaker notes.
  - **Meme corpus** — 40 memes captioned, OCR'd, joke-summarized,
    tagged via Sonnet subagents into per-image sidecars.
  - **AI Index 2026** — full 425-page Stanford HAI PDF, per-page
    chunks (citation deep-link via `<source_url>#page=<n>`).
  - **Epoch notable AI models** — 1,011 model rows from the
    `notable_ai_models.csv` plus the documentation overview.
  - **OWID — Artificial Intelligence (topic page)** — page prose
    chunk + linked-articles index chunk.
  - **Consulting (C1)** — five canonical reports from McKinsey
    (×2), BCG, Bain, Deloitte. Per-page chunking, deep-linked.
  - **Essays (C2 + C3 + lecturer reading list)** — 43 essays from
    Sequoia, a16z, NFX, Benedict Evans, Bessemer, Stratechery,
    Asianometry, plus the lecturer's external_links. One chunk per
    essay (most exceed the 800-token cap and will be split in the
    re-chunking pass).
  - **Vendors (D1)** — 3 frontier-lab pricing/catalog pages:
    OpenRouter `/api/v1/models` JSON (one chunk per model), Anthropic
    pricing markdown (chunked by H2 section), Google Gemini pricing
    HTML (chunked by H2 / per-model). 409 chunks total.
  - **YouTube (F3)** — 88-video curated whitelist of AI explainers,
    frontier-lab interviews, and canonical AI talks. Round 1
    (manual-subs default): 3B1B, Karpathy via auto-sub allowlist,
    Dwarkesh, Lex. Round 2 (channel-level auto-sub allowlist
    expansion at user direction): No Priors, a16z, Sequoia, YC,
    Stanford eCorner / GSB / Online. Chunked by ~75s of speech with
    `t_start_seconds` deep-link metadata. 6267 chunks total.
  - **EDGAR filings (B1)** — 60 filings (1 most-recent 10-K + 4 most-
    recent 10-Qs) for 12 companies: MSFT, GOOGL, META, NVDA, AMZN,
    AAPL, CRM, ORCL, PLTR, SNOW, ADBE, IBM. Item-aware chunking;
    priority sections (1, 1A, 7, 7A, 8 for 10-K; part1/part2 items
    for 10-Q) tagged for retrieval boost. 524 chunks total — many
    over the 800-token cap (per `ROUGH.md §2.2`, chunk on Item
    boundary first, sub-chunk by 800 tokens in the future
    re-chunking pass).
  - **Earnings transcripts (B2)** — 21 docs across the 4 companies
    that publish actual transcript text on their IR sites: MSFT
    (4 quarters, full Q&A docx), IBM (3 quarters, prepared-remarks
    PDF), NVDA (4 quarters, CFO Commentary HTML from 8-K Ex 99.2),
    AMZN (10 articles: per-topic Andy Jassy excerpts + quarterly
    earnings highlights + 2025 letter). 353 chunks. MSFT chunked on
    speaker-turn boundaries (CEO / CFO / IR / analyst).
  - **Shareholder letters (B3)** — 16 letters: Bezos × 10 (1997 +
    2016-2020 standalone HTML + 2013/2015/2016/2018 annual-report
    PDFs sliced to sign-off) + Nadella × 6 (FY20-FY25 annual-report
    HTML, sliced at #shareholder-letter anchor). Huang skipped —
    no separate letter, content is in the 10-K (B1).
  - **Regulation (F2)** — 135 docs / 306 chunks. NIST AI RMF +
    NIST 600-1 GenAI Profile (PDF, per-page chunks), EU AI Act
    113 articles + 13 annexes (HTML via FoLI mirror, one chunk
    per article/annex), 4 Trump 2025 AI EOs (HTML) + Biden EO
    14110 (govinfo PDF) + America's AI Action Plan (WH PDF),
    ISO/IEC 42001 abstract page.
  - **Funding (E3)** — 12 Crunchbase News articles spanning AI
    funding 2023–2026: 3 annual recaps, 6 quarterly recaps, 3
    theme pieces. E1 (Dealroom/PitchBook) and E2 (CB Insights)
    dropped at fetch time — all WAF-walled.
- **Three skills written**: `.claude/skills/lecture-indexer/`,
  `.claude/skills/meme-indexer/`, plus implicit conventions encoded
  in the per-corpus processing scripts under `scripts/process/`.
- **One inspection helper**: `scripts/inspect/chunk_stats.py` reports
  chunk counts and token-size distributions across all processed
  JSONL — flags chunks above the 800-token cap.

Total chunks in `data/processed/`: **10301**
(649 lecturer + 40 memes + 425 AI Index + 1012 Epoch + 2 OWID +
240 consulting + 46 essays + 409 vendors + 6267 youtube + 524 edgar +
353 earnings + 16 letters + 306 regulation + 12 funding). 410 chunks
currently exceed the 800-token cap (27 AI Index, 43 Epoch, 8
consulting, 1 OWID, 44 essays, 1 vendors, 195 edgar, 8 earnings,
16 letters, 55 regulation, 12 funding — most are natural-unit
Item / letter / essay / article sections that need sub-chunking;
see "Not done" §3 below).

---

## Done

### Specs

- `spec/ROUGH.md` — data-side rough spec. Scope (§0), goals (§1),
  retrieval contract + per-corpus chunking strategy (§2), open
  questions (§3), milestones (§4).
- `spec/SOURCES.md` — categorized candidate corpora (A–H plus the
  YouTube and slide-pipeline subsections). Now also records concrete
  picks for C1 (5 consulting PDFs), D1 (OpenRouter as spine + 3 vendor
  narrative pages), and F3 (manual-subs-only constraint).
- `spec/LAYOUT.md` — by-stage on-disk layout. **Letter-prefix
  convention dropped** in favor of flat, descriptive corpus dir names
  (`ai_index/`, `lecturer/`, `memes/`, `epoch_models/`, `owid/`).

### Tooling

- `uv init --bare` project at the repo root. Python 3.14 selected.
- Deps: `pre-commit`, `python-pptx`, `pymupdf`,
  `beautifulsoup4`, `lxml` (HTML scraping for OWID and any future
  HTML-shaped corpora).
- `.pre-commit-config.yaml` pinned to markdownlint-cli2 v0.22.1.
- `.markdownlint.jsonc` disables MD036, MD013; leaves MD040, MD060,
  MD031 active.

### Lecturer corpus (`data/raw/lecturer/lectures/`)

10 lectures, naming convention `<year>-<slug>/`:

| Slug | Slides | Embedded recording |
| --- | --- | --- |
| 2023-how-to-talk-to-your-cat | pptx (13 MB) | yes |
| 2025-nus-bmp5203-decision-making-early-stage-startups | pptx (4 MB) | yes |
| 2025-nus-bse3713-ai-platforms | pptx (14 MB) | yes |
| 2025-nus-bse3713-ai-startups | pptx (5.7 MB) | yes |
| 2025-nus-bsn4811-ai-innovation | pptx (12 MB) | yes |
| 2025-nus-bsn4811-ai-startups | pptx (5.7 MB) | yes |
| 2026-abc-infrastructure | pdf (4.2 MB) | no |
| 2026-ai-acjc | pdf (9.3 MB) | no |
| 2026-astar-workshop | 2 pdfs (1.4 MB + 307 KB) | no |
| 2026-roast-my-tech-stack | pdf (5.2 MB) | no |

Each lecture dir has `manifest.json` and the slide binary alongside.
NTU BMES workshop was dropped (duplicate with astar workshop).

### Meme corpus (`data/raw/memes/`)

40 images plus 40 sidecar JSONs. Sidecars filename'd by short hash;
the original image filenames are preserved on disk (the rename to
`<hash>--<slug>.<ext>` is still deferred).

### AI Index 2026 (`data/raw/ai_index/2026/`)

- `report.pdf` — Stanford HAI AI Index Report 2026 (24.9 MB,
  425 pages, sha256 captured in manifest).
- Source: `hai.stanford.edu/assets/files/ai_index_report_2026.pdf`.
  Published 2026-04-28 (S3 `Last-Modified`).
- License: CC BY-ND 4.0.
- Per-page chunking — 425 chunks, one per PDF page. Bot deep-links
  citations via `<source_url>#page=<slide_number>`.
- Section-aware chunking and figure-caption extraction are
  intentionally deferred (see "Not done" §3).

### Epoch notable AI models (`data/raw/epoch_models/`)

- `notable_ai_models.csv` (1011 rows × 47 columns) +
  `documentation.html` (Next.js Overview tab; other tabs are
  JS-rendered and not captured).
- Source: `epoch.ai/data/notable_ai_models.csv`. License: CC BY 4.0.
- Output: 1012 chunks (1 documentation overview + 1011 model rows).
  Each model chunk surfaces a populated subset of the 47 columns,
  folding `*_notes` annotations into their parent fields.

### Consulting reports (`data/raw/consulting/`)

5 reports, one subdir each, naming convention `<firm>-<slug>-<year>`:

| Slug | Title | Pages | Source |
| --- | --- | --- | --- |
| mckinsey-state-of-ai-2025 | The State of AI 2025: Agents, innovation, and transformation | 32 | mckinsey.com |
| mckinsey-economic-potential-genai-2023 | The Economic Potential of Generative AI | 68 | mckinsey.com |
| bcg-widening-ai-value-gap-2025 | Build for the Future 2025: The Widening AI Value Gap | 24 | media-publications.bcg.com |
| bain-technology-report-2025 | Bain Technology Report 2025 | 77 | bain.com |
| deloitte-state-of-ai-enterprise-2026 | State of AI in the Enterprise 2026 (Global cut) | 41 | deloitte.com |

Per-page chunking → 240 chunks total. Same deep-link convention as
AI Index: bot renders `<source_url>#page=<slide_number>`. License
recorded uniformly as marketing-publication / permissive non-
commercial summarization with attribution. Re-fetcher at
`scripts/fetch/consulting.py` (see fetcher quirks in
"Common pitfalls" in CLAUDE.md).

### Vendors / pricing (D1) (`data/raw/vendors/`)

3 sources, one subdir each:

| Slug | Source | Format | Chunks |
| --- | --- | --- | --- |
| openrouter-models | openrouter.ai/api/v1/models | JSON | 371 |
| anthropic-pricing | docs.anthropic.com/en/docs/about-claude/pricing.md | markdown | 8 |
| google-gemini-pricing | ai.google.dev/gemini-api/docs/pricing | HTML | 30 |

OpenRouter ships a clean public JSON catalog at `/api/v1/models`
(no SPA scrape needed); each model row becomes one chunk with the
prompt, completion, and cache $/Mtok rates normalized, modalities
listed, and the description folded in. Anthropic's docs page is
fully JS-hydrated
(static HTML returns "Loading..." × 17), but the `.md` source
endpoint at the same URL returns clean markdown — chunked by H2.
Google Gemini's pricing page redirects normal browser UAs into an
endless OAuth `prompt=none&auto_signin=True` loop; `Googlebot/2.1`
UA bypasses it and returns fully-rendered HTML — chunked by H2
(per-model sections). Re-fetcher at `scripts/fetch/vendors.py`.

### YouTube (F3) (`data/raw/youtube/`)

88 videos curated across two rounds, 6267 chunks total at ~75s of
speech each (median 301 tokens, max 390 — comfortably under cap).

**Round 1 (44 videos, manual-subs default)** — 3Blue1Brown × 8,
Karpathy × 7 via auto-sub allowlist, Dwarkesh Patel × 14, Lex
Fridman × 15. The Karpathy / 3B1B / Dwarkesh channels were on the
"trusted-author" auto-caption allowlist; in practice only
Karpathy's 7 videos triggered it.

**Round 2 (44 videos, channel-level auto-sub allowlist widened)** —
No Priors × 11, a16z × 7, Sequoia Capital × 9, Y Combinator × 7,
Stanford eCorner × 2, Stanford GSB × 7, Stanford Online × 1.
Captures Sam Altman talks at YC + a16z + Sequoia + Stanford,
Karpathy "Software Is Changing Again", Hassabis at Sequoia/YC,
AI Ascent 2025 + 2026 keynotes, Andrew Ng "AI is the new
electricity", Ethan Mollick "Co-Intelligence", Susan Athey on AI
economics, Marc Andreessen 2026 outlook. Stanford CS25 Transformers
United explicitly excluded.

Auto-sub VTTs ship with rolling-window prefix overlap — each cue
re-emits the previous cue's tail before adding new tokens. The
processor strips that overlap word-by-word (`_dedup_overlap` in
`scripts/process/youtube.py`); without it, totals nearly double
and chunks read like "30-minute talk on large language models
30-minute talk on large language models 30-minute talk".

Citation deep-link via `https://youtu.be/<id>?t=<seconds>`. Each
chunk carries `subs_kind: manual | auto`. Note: yt-dlp labels
YouTube's `en-orig` (original-audio language track) inconsistently
between runs — sometimes manual, sometimes auto — even though the
underlying transcript is auto-generated. Don't treat the
manual/auto label as ground truth at the per-track level; treat
it as a soft signal at best.

### EDGAR filings (B1) (`data/raw/edgar/`)

60 filings — 1 most-recent 10-K + 4 most-recent 10-Qs for each of
12 companies: MSFT, GOOGL, META, NVDA, AMZN, AAPL, CRM, ORCL,
PLTR, SNOW, ADBE, IBM. 524 chunks, sliced on Item boundaries.

Per-company directory structure:

```text
data/raw/edgar/<TICKER>/
  10-K_<period>.htm     # raw inline-XBRL HTML (gitignored)
  10-K_<period>.json    # manifest with URL, accession, sha256
  10-Q_<period>.htm
  10-Q_<period>.json
  ...
```

Raw `.htm` files are gitignored — 60 filings × ~7 MB each =
~420 MB, fully reproducible from each manifest's `source_url`
(SEC accession URLs are immutable). Re-fetch with
`uv run python scripts/fetch/edgar.py`. Each fetch obeys SEC's
fair-use guidance: identifying User-Agent header (`lecture-
knowledge research <email>`), 100 ms throttle between requests.

Item-aware chunking (`scripts/process/edgar.py`): a loose
`^Item N. ...` regex finds all body-header occurrences, taking
the second occurrence (first is the TOC entry). Sections run
from one body-header to the next. Priority sections per
`ROUGH.md §2.2` — Items 1, 1A, 7, 7A, 8 for 10-K and the
Part I/II items for 10-Q — get tagged `is_priority_section: true`
for retrieval boost. 195 chunks exceed the 800-token cap;
they're the natural-unit Item 1A (Risk Factors), Item 7 (MD&A),
and Item 15 (Exhibits) sections, all targets of the future
re-chunking pass.

Note that modern 10-K filings often place the actual financial
statements under Item 15 (Exhibits + Financial Statement
Schedules) rather than Item 8 — Item 8 becomes a one-line
pointer. The processor handles this transparently; both Items
appear as separate chunks where present, and the priority flag
catches the canonical Item 8 even when stub-sized.

### Earnings transcripts (B2) (`data/raw/earnings/`)

21 docs, 353 chunks. Restricted to IR-site canonical content —
no Whisper-transcription of webcasts, no third-party paywalled
sources.

| Source | Format | Slugs | Chunking |
| --- | --- | --- | --- |
| MSFT (4 quarters) | `.docx` (full Q&A) | `msft-fy25q3 .. msft-fy26q2` | speaker-turn boundaries via `python-docx`; tags speaker_role: ceo / cfo / investor-relations / analyst / operator |
| IBM (3 quarters) | PDF (prepared remarks only) | `ibm-1q26 / 3q25 / 2q25` | ~220-word windows via PyMuPDF |
| NVDA (4 quarters) | HTML (CFO Commentary, 8-K Ex 99.2) | `nvda-fy26q1 .. fy26q4` | NVDA's HTML is heavily-tabled with no `<h1>/<h2>/<p>`; processor splits on heading-shaped substring matches (`Q4 Fiscal 2026 Summary`, `Outlook`, `Quarterly Cash Flow`, etc.) |
| AMZN (10 articles) | HTML | `amzn-earnings-q1-2025 .. q1-2026` + `amzn-jassy-{aws-ai,ads,chips,stores}-q1-2026` + `amzn-jassy-letter-2025` | one chunk per article (CEO-quote articles are short and topic-focused) |

Skipped per probe results: GOOGL, META, AAPL, CRM, ORCL, SNOW,
PLTR, ADBE — all publish only the press release / webcast, no
transcript text. No 8-K exhibit transcripts on EDGAR for any of
these.

IBM 4Q25 was dropped: IBM's investor page links it to the same
PDF as 3Q25 (stale link on their site). Verified by reading the
PDF body — content is the 3Q25 prepared remarks. Will re-add when
IBM publishes a real 4Q25 doc.

NVDA's "CFO Commentary" exhibit is the closest thing they publish
to a transcript text — structured prepared remarks with quarterly
metrics + segment commentary. Not a verbatim call transcript, but
much more structured than a press release.

### Shareholder letters (B3) (`data/raw/letters/`)

16 letters, 16 chunks (all single-chunk-per-letter; long
letters exceed the 800-token cap and queue for the future
re-chunking pass).

| Author | Slugs | Source |
| --- | --- | --- |
| Bezos × 6 (HTML) | `bezos-1997-day-1`, `bezos-2016 .. 2020` | aboutamazon.com standalone pages |
| Bezos × 4 (PDF) | `bezos-2013-ar`, `bezos-2015-ar`, `bezos-2016-ar`, `bezos-2018-ar` | Q4 CDN annual-report PDFs; processor slices to first sign-off (Bezos appends a copy of the 1997 letter at the end of each year, so we deliberately stop at the FIRST sign-off) |
| Nadella × 6 (HTML) | `nadella-fy20 .. fy25` | microsoft.com/investor/reports/arNN/ — letter section anchored at #shareholder-letter |

Huang (NVDA) doesn't publish a separate letter; his content is
in the 10-K (B1).

### Regulation (F2) (`data/raw/regulation/`)

135 docs, 306 chunks across 4 source families:

| Family | Docs | Format | Chunking |
| --- | --- | --- | --- |
| NIST | 2 | PDF | per-page (RMF: 48, GenAI Profile: 64) |
| EU AI Act | 126 | HTML (FoLI mirror) | one chunk per article (1–113) / annex (1–13) |
| US AI EOs + Action Plan | 6 | HTML × 4 + PDF × 2 | one chunk per EO; per-page for the 2 PDFs |
| ISO/IEC 42001 | 1 | HTML | one chunk (abstract / scope summary only) |

EU AI Act fetched via `artificialintelligenceact.eu/article/<N>/`
and `/annex/<N>/` (FoLI Divi-WordPress mirror, body in
`div.et_pb_post_content`); EUR-Lex itself is AWS-WAF-walled to
plain curl. Biden EO 14110 was scrubbed from `whitehouse.gov` on
2025-01-20, so the canonical archive URL is the Federal Register
PDF on `govinfo.gov`. NIST nvlpubs HEAD-probe lies — always GET
with `Referer: nist.gov/itl/ai-risk-management-framework`.
55 chunks exceed the 800-token cap (NIST PDF pages, AI Action
Plan PDF pages, longest EU AI Act articles); they go into the
future re-chunking pass.

### Funding (E3) (`data/raw/funding/`)

12 Crunchbase News articles, 12 chunks (one chunk per article;
all over the 800-token cap and queue for the re-chunking pass).

Picks span 2023–2026: 3 annual recaps (Global EOY 2023 / 2024 /
2025), 6 quarterly recaps (Global Q1–Q3 2025, NA Q1 2026, Europe
Q1 2026, Capital concentrated in AI Q1 2026), 3 theme pieces
(big-dollar AI investors of 2025, week's biggest AI/autonomy/
biotech rounds, average seed amounts in 2025). All on
`news.crunchbase.com`, server-rendered WordPress, `<article>`
extraction.

E1 (Dealroom / PitchBook) and E2 (CB Insights) dropped at fetch
time: Dealroom gates the actual report PDFs behind HubSpot lead-
capture forms; PitchBook returns Cloudflare's `cf-mitigated:
challenge` (HTTP 403); CB Insights returns CloudFront's WAF
challenge (HTTP 202). All would need a Playwright path. The
Stanford AI Index Report (already in corpus, A1) covers funding
numbers in its Investment chapter, so the marginal value of
backfilling these later isn't high.

### Essays (C2 + C3 + lecturer reading list + Asianometry) (`data/raw/essays/`)

43 single-page essays, one subdir each (`<slug>/page.html` +
`manifest.json`). Per-essay categories:

- **vc** (Sequoia, a16z, NFX, Benedict Evans, Bessemer): 17 essays
- **stratechery** (Ben Thompson Weekly Articles, free): 12 essays
- **asianometry** (Jon Y, Substack — semiconductor / AI-chip
  beat): 8 essays. Picked the AI/GPU/data-center-direct subset;
  semis-history catalog (Sony / Toshiba / Sharp / STMicro / BOE)
  skipped.
- **lecturer_reading_list** (essays cited from
  `data/raw/lecturer/lectures/*` external_links — fs.blog,
  ribbonfarm, wheresyoured.at, Skalata, predictionmachines.ai,
  6startupstages.com): 6 essays

Picks recorded in `spec/SOURCES.md §C2` and `§C3`. One chunk per
essay (single-prose-blob).

**Dropped at fetch time** — JS-rendered SPAs whose article body
isn't in static HTML and would need a Playwright fetch path:

- `ycombinator.com/library/Ek-stages-of-startups`
- `ycombinator.com/library/carousel/Early%20Stage%20Advice`
- `angellist.com/blog/...power-law-returns-in-venture-capital`

**Sites with non-default WAF requirements** (codified in
`scripts/fetch/essays.py`): `6startupstages.com` returns 403
without `Sec-Fetch-*` + `Upgrade-Insecure-Requests` headers.

### OWID — Artificial Intelligence (`data/raw/owid/`)

- `artificial-intelligence.html` (single topic-page snapshot,
  178 KB). Source: `ourworldindata.org/artificial-intelligence`.
  License: CC BY 4.0.
- Output: 2 chunks — `prose` (15.6 KB lead + chart-grid prose with
  55 OWID Grapher slugs inlined) and `linked-articles` (a 1 KB index
  of the 6 sub-articles the topic page links to).
- OWID topic pages are *hub pages*, not articles — the H3 elements
  on the page are cards linking to other OWID articles, not section
  headings. Captured in CLAUDE.md gotchas.

### Processing scripts

- `scripts/process/lectures.py` — page_text + per-slide body + per-
  slide notes for PPTX, per-page for PDF. 649 chunks.
- `scripts/process/memes.py` — one chunk per meme. 40 chunks.
- `scripts/process/ai_index.py` — one chunk per PDF page. 425 chunks.
- `scripts/process/epoch_models.py` — one chunk per model row plus
  a documentation overview. 1012 chunks.
- `scripts/process/owid.py` — prose + linked-articles split for OWID
  hub pages. 2 chunks.
- `scripts/process/consulting.py` — per-page chunking for the 5
  consulting reports. 240 chunks.
- `scripts/process/essays.py` — bs4-based prose extraction over
  HTML essays (drops nav/header/footer/aside/script/etc., picks
  the most specific main-content node available). One chunk per
  essay. 35 chunks.
- `scripts/process/vendors.py` — three-strategy chunker: per-model
  rendering for OpenRouter JSON (with $/Mtok normalization), H2
  splitting for the Anthropic markdown, and a recursive-walk H2
  splitter for Gemini HTML (whose H2s are nested inside
  `<div class="heading-group">` containers, so a `find_next_siblings`
  pass would miss the pricing tables). 409 chunks.
- `scripts/process/youtube.py` — VTT parser with rolling-window
  overlap stripping (`_dedup_overlap`) needed for auto-captions,
  then chunked into ~75s windows with a 280-word ceiling. Stamps
  `t_start_seconds` on each chunk and propagates `subs_kind` from
  the manifest. 6267 chunks.
- `scripts/process/edgar.py` — Item-aware HTML→prose chunking for
  10-K and 10-Q filings. Loose `^Item N.` regex finds body headers
  (skipping the TOC duplicate), then slices sections. 10-Q
  disambiguates Item numbers by Part I vs Part II. 524 chunks.
- `scripts/process/letters.py` — three input shapes: HTML
  (Bezos standalone), HTML-AR (Nadella, slice on
  `#shareholder-letter`), PDF-AR (Bezos AR via PyMuPDF, slice on
  Bezos sign-off regex). One chunk per letter. 16 chunks.
- `scripts/process/earnings.py` — four input shapes: docx (MSFT
  speaker-turn boundaries via python-docx), PDF (IBM ~220-word
  windows), HTML-cfo (NVDA section-heading-substring split since
  the doc has no `<h*>` tags), HTML-article (AMZN one-chunk-per-
  article). 353 chunks.
- `scripts/process/regulation.py` — six input shapes: pdf-nist /
  pdf-eo / pdf-action-plan all do per-page chunking via PyMuPDF;
  html-eo (Trump EOs, `<main>` body), html-eu (EU AI Act articles
  and annexes, `div.et_pb_post_content` Divi container), html-iso
  (ISO 42001 abstract page, `<main>` body) all do
  single-chunk-per-doc. 306 chunks.
- `scripts/process/funding.py` — bs4-based prose extraction over
  Crunchbase News HTML (`<article>` body). One chunk per article.
  12 chunks.

### Fetcher scripts

- `scripts/fetch/consulting.py` — downloads the 5 C1 PDFs and
  emits each report's `manifest.json` (sha256, bytes, page count).
  McKinsey-WAF-aware: full browser-style headers, HTTP/2 default,
  `--compressed`. Idempotent on re-run via sha256 compare.
- `scripts/fetch/essays.py` — downloads the C2/C3 essays + lecturer
  reading list (35 URLs). Same browser-headers approach as
  consulting plus `Sec-Fetch-*` + `Upgrade-Insecure-Requests` for
  WAFs like 6startupstages.com. Pass slug args on the command line
  to retry just specific entries. Catalog comments record dropped
  JS-rendered URLs.
- `scripts/fetch/vendors.py` — downloads the 3 D1 sources. Each has
  a different fetch profile (OpenRouter API JSON, Anthropic `.md`
  raw source, Google Gemini under `Googlebot/2.1` UA to dodge
  the OAuth auto-signin loop). All three quirks documented inline
  and in CLAUDE.md "Common pitfalls". Pass slug args to retry one.
- `scripts/fetch/youtube.py` — downloads subs via yt-dlp for the
  88-video F3 whitelist. Manual subs by default; falls back to
  `--write-auto-sub` for channels in `TRUSTED_AUTOSUB_CHANNELS`
  (Karpathy, 3B1B, Dwarkesh + the Tier-1 expansion: No Priors,
  a16z, Sequoia, YC, Stanford eCorner/GSB/Online). Records
  `subs_kind` in each per-video manifest. Whitelist enumerated
  inline in the script.
- `scripts/fetch/edgar.py` — pulls the most-recent 10-K + last 4
  10-Qs per company via EDGAR's per-CIK submissions JSON
  (`data.sec.gov/submissions/CIK<10digit>.json`). SEC requires an
  identifying User-Agent header on every request; the fetcher
  sends `lecture-knowledge research <email>` and throttles at
  ~7 req/s to stay under SEC's 10 req/s ceiling. Idempotent on
  sha256. Pass ticker args to retry one company.
- `scripts/fetch/letters.py` — 16 shareholder-letter URLs (Bezos
  standalone HTML + Bezos AR PDFs + Nadella AR HTML). Standard
  browser-headers curl + sha256 idempotency.
- `scripts/fetch/earnings.py` — *not yet written as a unified
  script.* The B2 ingest was done by 4 parallel one-off Sonnet
  subagents (one per company), each writing directly into
  `data/raw/earnings/<slug>/`. Manifests + on-disk files are the
  durable record; if you need to re-fetch, you can re-dispatch
  the agents or write a unified fetcher from the manifest URLs.
- `scripts/fetch/regulation.py` — F2 fetcher: 9 explicit entries
  (NIST RMF + GenAI Profile, Biden EO 14110 govinfo PDF, 4 Trump
  2025 AI EOs, AI Action Plan PDF, ISO/IEC 42001 abstract) plus
  range-generated entries for EU AI Act articles 1–113 and
  annexes 1–13 (artificialintelligenceact.eu, throttled 0.3s).
  Sends a NIST-specific `Referer: nist.gov/itl/ai-risk-management-
  framework` header so nvlpubs.nist.gov's lying HEAD-probe doesn't
  bite. 135 entries total. Pass slug args to retry one.
- `scripts/fetch/funding.py` — E3 fetcher: 12 Crunchbase News
  articles. Standard browser-headers curl + sha256 idempotency.
  Pass slug args to retry one.

### Inspection helpers

- `scripts/inspect/chunk_stats.py` — token-size + chunk-count audit
  across every `*.chunks.jsonl`. Run after each ingest.

### Skills

- `.claude/skills/lecture-indexer/SKILL.md` — lecturer-page schema,
  field rules, procedure.
- `.claude/skills/meme-indexer/SKILL.md` — meme-sidecar schema,
  field rules, procedure.

---

### Index build (this session)

- **Rechunker** (`scripts/process/rechunk.py`): tiktoken cl100k_base
  splitter, 800-token windows + 100-token overlap, sidecar
  `*.rechunked.jsonl` next to the original `*.chunks.jsonl`. 617
  parents split into 5,568 parts (true tiktoken count was higher
  than the old word-heuristic estimate of 410). Indexer prefers the
  sidecar when present. `chunk_stats.py` switched to real tiktoken
  cl100k_base; post-rechunk audit shows 15,252 chunks, 0 over cap.
- **Embedding cache** (`data/cache/embeddings/<sha[:2]>/<sha>.npy`)
  keyed by `sha256(model_id + "\0" + text)`. Two-char shard so a
  single dir doesn't end up with 15k files.
- **Dense index** (`data/index/dense/`): `BAAI/bge-base-en-v1.5`
  (768-dim) via sentence-transformers, IndexFlatIP over L2-normalized
  vectors. Cold full embed ≈ 62s on CPU; cache hits make subsequent
  rebuilds near-instant.
- **BM25 index** (`data/index/bm25/`): `bm25s` native dump, shared
  tokenizer in `lecture_knowledge/tokenize_text.py` (lowercase a-z0-9,
  len ≥ 2). Build ≈ 1s.
- **`chunk_meta.parquet`** — row-aligned with FAISS / BM25, 33 cols
  (the spec's metadata superset, per-corpus extras, the chunk
  `text` itself, and a `source_path` audit pointer). 8.3 MB
  compressed; folding text in keeps the export tarball
  self-contained (`fetch_doc` reads from parquet, never from
  `processed/`).
- **`lecture_knowledge.retrieve`**: `search(query, corpus, k)` and
  `fetch_doc(id)`. Hybrid BM25 + dense → RRF (k=60) → per-corpus
  boost (lecturer/lectures 1.40; edgar/earnings/letters 1.20;
  consulting/essays/vendors/ai_index 1.05; rest 1.00). Lazy
  module-level load; cold first call ≈ 6s (model load), warm
  queries ≈ 10–25 ms. Returns `{id, corpus, title, source,
  section_path, snippet, score}`.
- **Packaged tarball**: `data/exports/index_2026-05-04.tar.zst` (100
  MB). Bundles `bm25/`, `dense/`, `chunk_meta.parquet` (with text
  folded in), `manifest.json` (git sha, build time, corpora +
  counts, embedding model id). Self-contained — chat layer loads
  this and never touches `processed/` or `index/` directly.

Smoke test results (warm queries):

- "what does GPT-4 cost" → Lex Fridman GPT-4 transcript, OpenRouter
  GPT-Audio-Mini pricing, Epoch GPT-4 model row.
- "EU AI Act high-risk systems" → Articles 42 / 26 / 27 (the
  high-risk-AI articles).
- "how should startups think about AI moats" → lecturer "Early
  Stage AI Startups" (×2), a16z "Who Owns the Generative AI
  Platform?".
- "item 1A risk factors AI" → 3 EDGAR 10-Q risk-factors chunks.

## Not done (next session pickup)

Roughly in order of bang-for-buck:

1. **JS-rendered backfills** (would need a Playwright fetch path):
   the 3 essays we dropped (YC Library × 2, AngelList × 1), the
   OpenAI pricing page (Cloudflare-walled to plain curl;
   intentionally omitted from D1 in favor of OpenRouter coverage),
   and any future similar SPAs.
2. **Per-slide PNG rendering** for the lecturer slide decks so
   citations can attach the actual slide image. LibreOffice headless:
   `soffice --convert-to png`. Mentioned in `spec/SOURCES.md §G3a`.
3. **Rename the meme files** to `<hash>--<slug>.<ext>` per each
   sidecar's `proposed_filename`. Trivial batch script.
4. **Eval harness** (`data/eval/`) — held-out questions + expected
   sources, used to regression-test the index after rebuilds. Use
   it to tune the per-corpus boost weights (currently picked by
   gut feel) and validate RRF k=60.
5. **Open questions in `spec/ROUGH.md §3`**: corpus freshness cron,
   multi-language scope.

---

## Repo state

Commits on `master`:

- `82368a4` — Initial spec drafts and tooling.
- `683bd33` — Ingest lecturer corpus and meme corpus.
- `5936992` — Process lecturer + meme corpora into chunked JSONL
  (slide re-downloads, NTU BMES deletion, processing scripts, etc.).
- `d0b9c09` — Ingest category A (AI Index 2026, Epoch models, OWID),
  drop the letter-prefix convention from LAYOUT.md, record C1/D1/F3
  picks in SOURCES.md, add `scripts/inspect/chunk_stats.py`, add
  `beautifulsoup4`+`lxml` deps.
- `36197bf` — Ingest C1 consulting reports (McKinsey x2, BCG, Bain,
  Deloitte). +240 chunks.
- `03d512c` — Ingest C2 + C3 + lecturer reading list as a single
  `essays/` corpus. Drop C4 from SOURCES, drop OpenAI from D1
  picks, add `scripts/fetch/essays.py` and `scripts/process/essays.py`,
  +35 chunks.
- next commit (this session): ingest D1 (OpenRouter + Anthropic +
  Google Gemini pricing) and F3 round 1 (44-video YouTube whitelist
  with rolling-window auto-sub dedup). +409 vendor chunks +4565
  youtube chunks. Address SOURCES.md TODOs (drop F1 arXiv → fold
  into F3 with auto-sub allowlist for trusted authors; expand F2
  to include ISO/IEC 42001 governance; propose backstop website
  whitelist in H2). Update CLAUDE.md "Common pitfalls" with the
  three new fetch quirks.
- `4313f08` — F3 round 2 (channel-level auto-sub allowlist widened
  to No Priors / a16z / Sequoia / YC / Stanford eCorner+GSB+Online),
  +44 videos (+1702 chunks). Plus 8 Asianometry Substack articles
  ingested into the essays/ corpus (+8 essay chunks). Idempotency
  bug in `_existing_info` glob fixed (was missing the post-rename
  `info.json` filename, causing re-runs to re-fetch).
- `0b3d8f3` — B1 EDGAR ingest — 60 filings (1 10-K + 4 10-Qs each)
  for 12 companies. +524 chunks via Item-aware HTML chunking. Raw
  .htm gitignored (~420 MB across 60 filings, fully reproducible
  from manifests). SOURCES.md cleaned up: drop D2 (model cards),
  G2 (case studies, license-blocked), H entirely (Wikipedia +
  backstop whitelist — runtime Wikipedia/Brave is owned by the
  chat layer, not this corpus), C4 stub. spec/HANDOFF.md deleted.
- `454a164` — Ingest B2 earnings (21 docs / 353 chunks) + B3
  letters (16 docs / 16 chunks) + student-facing README.
- next commit (this session): F2 regulation + E3 funding ingest.
  F2: 135 docs / 306 chunks (NIST RMF + GenAI Profile, EU AI Act
  113 articles and 13 annexes via FoLI mirror, 4 Trump 2025 AI EOs,
  Biden EO 14110 govinfo PDF, WH AI Action Plan PDF, ISO/IEC
  42001 abstract). E3: 12 Crunchbase News articles / 12 chunks
  spanning AI funding 2023–2026. E1 (Dealroom/PitchBook) and E2
  (CB Insights) dropped at fetch time — all WAF-walled. Total:
  10,301 chunks across 14 corpora. New CLAUDE.md "Common
  pitfalls" entries for nvlpubs HEAD-lies, EUR-Lex AWS-WAF,
  revoked-EO archival via govinfo, and the E1/E2 funding-source
  dropouts.
