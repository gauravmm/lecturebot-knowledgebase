# Suggested Sources

Candidate corpora for the lecture bot's retrieval index. Grouped by category.
For each: what it is, why it's useful for a business-school audience, how to
ingest, and license/access notes.

Status: rough shortlist, not yet ingested. Final pick depends on lecture
focus and licensing review.

---

## A. Industry data & benchmarks

### A1. Stanford HAI — AI Index Report

- **What**: Annual ~400-page report with the canonical numbers on AI
  compute, funding, capability benchmarks, hiring, regulation, public
  opinion.
- **Why**: Most-cited single source in business-school AI lectures. Every
  "how big is AI" question lands here.
- **Format**: Public PDF + a public dataset of the underlying figures.
- **Ingest**: PDF → section-aware chunking. Pull figure captions as
  separate chunks for chart-grounding.
- **License**: CC BY-ND. Attribution required, no derivatives — fine for
  retrieval/quoting, do not modify text.

### A2. Epoch AI — model & compute database

- **What**: Curated dataset of frontier models with training compute,
  parameter count, dataset size, estimated cost.
- **Why**: Anchors any "how much does it cost to train X" question with
  real numbers.
- **Format**: CSV + accompanying blog posts.
- **Ingest**: CSV → one chunk per model row, joined with the relevant blog
  post explaining the methodology.
- **License**: CC BY.

### A3. Our World in Data — AI page

- **What**: Curated charts on AI compute, parameters, benchmark progress.
- **Why**: Clean, well-cited summary visualizations students recognize.
- **License**: CC BY.

---

## B. Company filings & investor communications

### B1. SEC EDGAR — 10-Ks and 10-Qs

- **Companies**: MSFT, GOOG/GOOGL, META, NVDA, AMZN, AAPL, CRM, ORCL,
  PLTR, SNOW, ADBE, IBM. Add TSLA if AV/robotics comes up.
- **Why**: Authoritative on revenue mix, capex, segment performance,
  risk factors. Earnings transcripts (below) cover narrative.
- **Format**: HTML + XBRL via EDGAR API.
- **Ingest**: Pull most recent 10-K + last 4 10-Qs per company. Section-
  aware chunking (Item 1, 1A, 7, 7A, 8). Tag with ticker + period.
- **License**: Public domain (US gov filings).

### B2. Earnings call transcripts

- **Why**: Where AI strategy is actually articulated by execs ("we will
  spend $80B on data centers this year"). Highly quotable.
- **License**: Restricted to **IR-site canonical** publications — what
  companies post themselves. Whisper-transcription of webcasts is off
  the table for v1 (compute cost + ToS grey area).
- **Picks for ingest** (~22 docs across 4 companies that publish
  actual transcript text):

  - **MSFT** — full Q&A transcripts as `.docx` from
    `cdn-dynmedia-1.microsoft.com`, last 4 quarters (FY25 Q3/Q4 +
    FY26 Q1/Q2).
  - **IBM** — prepared-remarks PDFs from the per-quarter hub pages
    `ibm.com/investor/earnings-NqYY`, last 3 quarters (1Q26, 3Q25,
    2Q25). Q&A is webcast-only and not included. (4Q25 was dropped
    because IBM's investor page links it to a stale 3Q25 PDF — see
    PROGRESS notes.)
  - **NVDA** — CFO Commentary HTML from each earnings 8-K's
    Exhibit 99.2 (FY26 Q1-Q4, May 2025 / Aug 2025 / Nov 2025 / Feb
    2026). Not a full transcript but the closest thing NVIDIA
    publishes — structured prepared-remarks with all quarterly
    metrics + segment commentary.
  - **AMZN** — 10 articles from `aboutamazon.com`: 4 per-topic
    "Andy Jassy on X — Q1 2026" excerpt pieces (AWS+AI, ads,
    chips, stores), 5 quarterly "Amazon QN YYYY Earnings
    Highlights" reports (Q1 2025 — Q1 2026), plus the 2025 annual
    shareholder letter. Per-topic excerpts only exist for Q1 2026;
    earlier quarters only have the consolidated press release.
- **Skipped from B2**: GOOGL, META, AAPL, CRM, ORCL, SNOW, PLTR,
  ADBE — all publish only the press release / webcast, no
  transcript text. No 8-K exhibit transcripts on EDGAR for any of
  the 12 either.

### B3. Shareholder letters

- **Why**: Bezos / Huang / Nadella letters are canonical strategy
  texts in MBA programs.
- **Picks for ingest** (16 letters):

  - **Bezos / AMZN — 10 letters**: 6 standalone HTML pages on
    aboutamazon.com (1997 "Day 1" + 2016, 2017, 2018, 2019, 2020)
    plus 4 annual-report PDFs on the Q4 CDN where the letter is on
    page 1 (2013, 2015, 2016, 2018). Bezos always appends a copy
    of the original 1997 letter at the end of each year's letter;
    the processor slices to the FIRST sign-off ("Sincerely / Jeff
    Bezos / Founder and Chief Executive Officer / Amazon.com, Inc.")
    so we don't double-ingest the 1997 letter inside other years'
    chunks.
  - **Nadella / MSFT — 6 letters**: annual-report HTML at
    `microsoft.com/investor/reports/arNN/index.html`, FY20-FY25.
    The letter section is anchored at `#shareholder-letter` inside
    the page; the processor slices that subtree.
  - **Huang / NVDA — skipped (no standalone)**: NVIDIA doesn't
    publish a separate annual letter; Huang's content is in the
    10-K (covered by B1).
- **Years not covered for Bezos**: 1998-2012 + 2014 + 2017 +
  2019-2020 PDFs aren't on Amazon-controlled URLs (Amazon's IR
  hub only links 1997 + 2016-2020 standalone HTML and a handful of
  AR PDFs). The standalone HTMLs cover 1997 + 2016-2020, and the
  Q4 CDN PDFs add 2013 + 2015. The remaining years would need a
  third-party mirror — out of scope for the clean-license rule.

---

## C. Strategy / consulting / VC writing

### C1. Big-3 consulting AI reports

- **Sources**: McKinsey "State of AI" annual, BCG AI at Scale, Bain
  Technology Report, Deloitte State of GenAI in the Enterprise.
- **Why**: Speak the language MBAs already know. Heavy on adoption stats,
  ROI claims, org-design recommendations.
- **Format**: Public PDFs (released as marketing).
- **License**: Generally permissive for non-commercial summarization with
  attribution. Don't redistribute the PDFs themselves.
- **Picks for ingest** (5 reports — covers all four firms with the
  flagship 2025/2026 surveys plus the seminal 2023 McKinsey number):
  1. McKinsey, **The State of AI 2025: Agents, innovation, and
     transformation** (Nov 2025).
     `https://www.mckinsey.com/~/media/mckinsey/business%20functions/quantumblack/our%20insights/the%20state%20of%20ai/november%202025/the-state-of-ai-2025-agents-innovation_cmyk-v1.pdf`
  2. McKinsey, **The Economic Potential of Generative AI: The Next
     Productivity Frontier** (Jun 2023, ~68pp).
     `https://www.mckinsey.com/~/media/mckinsey/business%20functions/mckinsey%20digital/our%20insights/the%20economic%20potential%20of%20generative%20ai%20the%20next%20productivity%20frontier/the-economic-potential-of-generative-ai-the-next-productivity-frontier.pdf`
  3. BCG, **Build for the Future 2025: The Widening AI Value Gap**
     (Oct 2025, 7.9 MB).
     `https://media-publications.bcg.com/The-Widening-AI-Value-Gap-October-2025.pdf`
  4. Bain, **Technology Report 2025** (Sep 2025, 7.4 MB).
     `https://www.bain.com/globalassets/noindex/2025/bain_report_technology_report_2025.pdf`
  5. Deloitte, **State of AI in the Enterprise 2026 — Global cut**
     (Jan 2026, 8.2 MB).
     `https://www.deloitte.com/content/dam/assets-shared/docs/about/2025/state-of-ai-2026-global.pdf`
- **Verified at pick time**: BCG, Bain, Deloitte URLs returned
  `Content-Type: application/pdf`. McKinsey URLs follow the canonical
  `mckinsey.com/~/media/...` CDN pattern but were not curl-verifiable
  from the curation sandbox — re-verify from the ingest host before
  committing to a manifest.

### C2. VC essays

- **Why**: Frame AI as an investable thesis — useful counterpoint to
  consulting reports.
- **Format**: Blog HTML.
- **License**: Public web; quote with attribution + link.
- **Picks for ingest** — 2026-relevant cross-section of canonical
  AI strategy essays plus the lecturer's own external_links.

  *Sequoia (5)*

  - Sonya Huang & Pat Grady, **Generative AI: A Creative New World**
    (Sep 2022). `https://www.sequoiacap.com/article/generative-ai-a-creative-new-world/`
  - Sonya Huang & Pat Grady, **Generative AI's Act Two**
    (Sep 2023). `https://www.sequoiacap.com/article/generative-ai-act-two/`
  - David Cahn, **AI's $600B Question** (Jun 2024).
    `https://www.sequoiacap.com/article/ais-600b-question/`
  - Sequoia Team, **AI Ascent 2025** (May 2025).
    `https://www.sequoiacap.com/article/ai-ascent-2025/`
  - Pat Grady & Sonya Huang, **2026: This Is AGI** (Jan 2026).
    `https://www.sequoiacap.com/article/2026-this-is-agi/`

  *a16z (7)*

  - Martin Casado & Peter Lauten, **The Empty Promise of Data
    Moats** (May 2019). `https://a16z.com/the-empty-promise-of-data-moats/`
  - Martin Casado et al., **The New Business of AI (and How It's
    Different From Traditional Software)** (Feb 2020).
    `https://a16z.com/the-new-business-of-ai-and-how-its-different-from-traditional-software/`
  - Martin Casado, **Taming the Tail: Adventures in Improving AI
    Economics** (Aug 2020).
    `https://a16z.com/taming-the-tail-adventures-in-improving-ai-economics/`
  - Martin Casado et al., **Who Owns the Generative AI Platform?**
    (Jan 2023). `https://a16z.com/who-owns-the-generative-ai-platform/`
  - Marc Andreessen, **Why AI Will Save the World** (Jun 2023).
    `https://a16z.com/ai-will-save-the-world/`
  - Martin Casado, **The Economic Case for Generative AI**
    (Oct 2023). `https://a16z.com/the-economic-case-for-generative-ai/`
  - **The Economic Case for Generative AI and Foundation Models**
    (companion to the above, explicit user request).
    `https://a16z.com/the-economic-case-for-generative-ai-and-foundation-models/`

  *NFX (3)*

  - James Currier, **Generative AI Begins** (Oct 2022).
    `https://www.nfx.com/post/generative-tech`
  - **The 5-Layer Generative Tech Stack** (2023).
    `https://www.nfx.com/post/generative-ai-tech-5-layers`
  - **The AI Workforce is Here** (2024).
    `https://www.nfx.com/post/ai-workforce-is-here`

  *Benedict Evans (1)*

  - **Building AI products** (Jun 2024).
    `https://www.ben-evans.com/benedictevans/2024/6/8/building-ai-products`
    The annual deck PDFs at `ben-evans.com/presentations` rotate;
    ingest those separately if/when wanted.

  *Bessemer (1)*

  - **The State of AI 2025** (Aug 2025).
    `https://www.bvp.com/atlas/the-state-of-ai-2025`

  *Asianometry / Jon Y — Substack (8)*. Semiconductor + AI-chip
  beat. AI/GPU/data-center-direct subset of the archive. Substack
  pages render server-side.

  - **Nvidia's Unique History and Culture** (Dec 2024, interview
    with Tae Kim). `https://www.asianometry.com/p/nvidias-unique-history-and-culture`
  - **The $600 Billion AI Chip Giant** (Aug 2024).
    `https://www.asianometry.com/p/the-600-billion-ai-chip-giant`
  - **The Big Data Center Water Problem** (Nov 2024).
    `https://www.asianometry.com/p/the-big-data-center-water-problem`
  - **Is the AI Boom Real?** (Mar 2024).
    `https://www.asianometry.com/p/is-the-ai-boom-real`
  - **AI's Hardware Problem** (Apr 2023).
    `https://www.asianometry.com/p/ais-hardware-problem`
  - **FPGAs: The Ultimate Flex** (Jun 2023).
    `https://www.asianometry.com/p/fpgas-making-the-ultimate-flex`
  - **Analog Chip Design is an Art. Can AI Help?** (Feb 2024).
    `https://www.asianometry.com/p/analog-chip-design-is-an-art-can`
  - **Running Neural Networks on Meshes of Light** (Jun 2023).
    `https://www.asianometry.com/p/running-neural-networks-on-meshes`

  *Lecturer external_links (essay-shaped only — drop Amazon book
  pages, GitHub repos, social profiles, vendor docs, lecturer
  self-references):*

  - `https://6startupstages.com/`
  - `https://fs.blog/chestertons-fence/`
  - `https://www.angellist.com/blog/what-angellist-data-says-about-power-law-returns-in-venture-capital`
  - `https://www.skalata.vc/blog/how-venture-returns-really-work-power-law-patience-and-portfolio-construction`
  - `https://www.ribbonfarm.com/2009/10/07/the-gervais-principle-or-the-office-according-to-the-office/`
  - `https://www.wheresyoured.at/the-men-who-killed-google/`
  - `https://www.ycombinator.com/library/Ek-stages-of-startups`
  - `https://www.ycombinator.com/library/carousel/Early%20Stage%20Advice`
  - `https://www.predictionmachines.ai/`

  Excluded from the lecturer reading list (not single-essay HTML):
  `promptingguide.ai` (multi-page tutorial),
  `developers.openai.com/...` and `platform.claude.com/docs/...`
  (vendor docs — D1/D2 territory),
  `thevcfactory.com/...Sequoia-Capital-YouTube-Investor-Memo-1.pdf`
  (PDF; defer or fold in later as a single-PDF entry).

### C3. Stratechery / Ben Thompson — free posts only

- **Why**: The strategy framing students will encounter elsewhere
  (aggregation theory, etc.) applied to AI.
- **License**: ⚠️ Paid newsletter — index only the free Weekly
  Articles at `stratechery.com/<year>/<slug>/`. Never the Daily
  Updates (paid), Sharp Tech / Sharp China / Stratechery Plus.
- **Picks for ingest** — Aggregation-Theory-applied-to-AI arc,
  2023–2026.

  - **AI and the Big Five** (Feb 2023).
    `https://stratechery.com/2023/ai-and-the-big-five/`
  - **Attenuating Innovation (AI)** (Feb 2023).
    `https://stratechery.com/2023/attenuating-innovation-ai/`
  - **The Accidental Consumer Tech Company; ChatGPT, Meta, and
    Product-Market Fit; Aggregation and APIs** (Feb 2023).
    `https://stratechery.com/2023/the-accidental-consumer-tech-company-chatgpt-meta-and-product-market-fit-aggregation-and-apis/`
  - **Nvidia On the Mountaintop** (May 2023).
    `https://stratechery.com/2023/nvidia-on-the-mountaintop/`
  - **Meta Open Sources Another AI Model, Moats and Open Source,
    Apple and Meta** (Jul 2023).
    `https://stratechery.com/2023/free-meta-open-sources-another-ai-model-moats-and-open-source-apple-and-meta/`
  - **Aggregator's AI Risk** (Apr 2024).
    `https://stratechery.com/2024/aggregators-ai-risk/`
  - **Nvidia Waves and Moats** (Aug 2024).
    `https://stratechery.com/2024/nvidia-waves-and-moats/`
  - **DeepSeek FAQ** (Jan 2025).
    `https://stratechery.com/2025/deepseek-faq/`
  - **Checking In on AI and the Big Five** (Feb 2025).
    `https://stratechery.com/2025/checking-in-on-ai-and-the-big-five/`
  - **OpenAI's Windows Play** (Oct 2025).
    `https://stratechery.com/2025/openais-windows-play/`
  - **Google, Nvidia, and OpenAI** (Dec 2025).
    `https://stratechery.com/2025/google-nvidia-and-openai/`
  - **Agents Over Bubbles** (Mar 2026).
    `https://stratechery.com/2026/agents-over-bubbles/`

  Verification at curation time: each URL returned full-body HTML
  (8K-11K word count, 100+ `<p>` tags) with no
  `subscribe to read` / `members-only` markers. Stratechery's
  gated posts return ~30-50 KB shells with those phrases — re-check
  before any future re-pull.

## D. Vendor / product reference

### D1. Frontier-lab product & pricing pages

- **Why**: Lets the bot answer "what does Claude cost vs GPT-5", "what's
  the context window of …", "which models are multimodal".
- **License**: Public web; no redistribution issue for short quotes.
- **Picks for ingest** (OpenRouter as the spine + two vendor
  narrative pages for pricing-mechanic depth — 3 URLs total):
  1. **OpenRouter models catalog** (primary).
     `https://openrouter.ai/models` — per-model prompt + completion
     $/Mtok, context window, modalities, provider for ~300 models in
     one consistent schema. Covers OpenAI without hitting their
     Cloudflare bot wall.
  2. **Anthropic API pricing**.
     `https://docs.anthropic.com/en/docs/about-claude/pricing` —
     server-rendered, includes batch + prompt-caching discount
     mechanics that OpenRouter strips.
  3. **Google Gemini API pricing**.
     `https://ai.google.dev/gemini-api/docs/pricing` —
     server-rendered; batch + cached-input tiers.
- **OpenAI deliberately omitted.** Their pricing page is Cloudflare-
  walled to plain curl and would need a Playwright headless-browser
  fetch path to capture. OpenRouter's catalog already exposes OpenAI
  per-token pricing, so the marginal value of also scraping
  `platform.openai.com/docs/pricing` (vendor-narrative copy + cache
  discount mechanics) doesn't justify the fetcher complexity.
- **Tradeoff vs. per-vendor scrape**: OpenRouter alone misses
  vendor-specific discount mechanics (caching, batch, fine-tune
  pricing) and strategic positioning copy. The two narrative pages
  recover most of the 80% case without the weekly maintenance load
  of scraping eight vendor sites.
- **Ingest cadence**: re-pull all three a week before lecture, then
  again 24h before. Date-stamp filenames (`pricing_2026-MM-DD.html`)
  so we keep a short trail.

---

## E. Funding & market data

### ~~E1. Dealroom / PitchBook free annual AI reports~~ (dropped)

Tried at fetch time and dropped. Dealroom gates the actual PDF
behind a HubSpot lead-capture form; `files.pitchbook.com` returns
Cloudflare's `cf-mitigated: challenge` (HTTP 403). Both would need
a Playwright path. The Stanford AI Index Report (already in
corpus, A1) covers funding numbers in its Investment chapter, so
the marginal value of these doesn't justify the fetcher complexity.

### ~~E2. CB Insights State of AI / State of Venture~~ (dropped)

Tried and dropped. `cbinsights.com` returns CloudFront's WAF
challenge (HTTP 202 with `x-amzn-waf-action: challenge`). Same
Stanford AI Index argument as E1.

### E3. Crunchbase News articles

- **Why**: Searchable narrative around the numbers — quarterly /
  annual recaps, regional breakouts, theme pieces.
- **License**: Public web; quote with attribution + link.
- **Picks for ingest** (12 articles spanning 2023–2026):

  *Annual recaps (3)*

  - Global EOY 2023 — AI bucks the trend
    (`/venture/global-funding-data-analysis-ai-eoy-2023/`)
  - Global EOY 2024 — AI's outsized share
    (`/venture/global-funding-data-analysis-ai-eoy-2024/`)
  - Global 2025 — third-largest year on record
    (`/venture/funding-data-third-largest-year-2025/`)

  *Quarterly recaps (6)*

  - Global Q1 2025 (AI-led)
  - Global Q2 2025 (AI + M&A)
  - Global Q3 2025 (AI + M&A)
  - North America Q1 2026 (AI-led, all stages surge)
  - Europe Q1 2026 (AI-led pickup)
  - Capital concentrated in AI — Global Q1 2026

  *Theme pieces (3)*

  - Big-dollar AI investors of 2025 (SoftBank et al.)
  - Week's 10 biggest funding rounds — AI/autonomy/biotech
  - Average seed funding amounts and deals grew in 2025

  All hosted on `news.crunchbase.com` (server-rendered WordPress;
  plain curl works with standard browser headers). Slugs and full
  URLs codified in `scripts/fetch/funding.py`.

---

## F. Academic & technical (lightly indexed)

### ~~F1. arXiv — selected commercially-relevant papers~~ (dropped)

The original plan was a curated arXiv whitelist (Attention Is All You
Need, GPT-3, Chinchilla, Llama, etc.). Dropped: in a business-school
lecture, students who want the *paper* are a tiny minority. The same
content explained well lives on YouTube (Karpathy's "Intro to LLMs",
3Blue1Brown's NN series) and in blog form (a16z, Sequoia — already in
C2). Folded into F3 with a relaxation: trusted-author videos (Karpathy,
3B1B) bypass the manual-subs requirement and may use auto-captions,
since their on-screen content is consistently transcribable.

### F2. AI regulation & governance

- **Why**: Regulation is half the AI-in-business conversation now.
- **License**: Public domain (NIST, US gov) / OJEU re-use (EU AI Act).
  ISO standard text is copyrighted; abstract + scope only.
- **Picks for ingest** (135 docs across 4 source families):

  *NIST (2 PDFs)*

  - **NIST AI RMF 1.0** (`NIST.AI.100-1.pdf`, Jan 2023) — the
    canonical risk-management framework. Per-page chunked.
  - **NIST AI 600-1 — Generative AI Profile** (`NIST.AI.600-1.pdf`,
    Jul 2024) — companion profile applying the RMF to GenAI.

  *EU AI Act — Regulation (EU) 2024/1689 (113 articles + 13 annexes)*

  - Source: `artificialintelligenceact.eu/article/<N>/` and
    `/annex/<N>/` (Future of Life Institute mirror, server-
    rendered). EUR-Lex itself is AWS-WAF-walled to plain curl.
  - One chunk per article / annex.

  *US AI Executive Orders + AI Action Plan (6 docs)*

  - **Biden EO 14110** — Safe, Secure, and Trustworthy AI
    (Oct 2023; revoked Jan 2025). Whitehouse.gov scrubbed it; we
    use the Federal Register PDF on `govinfo.gov` as the
    canonical archive URL.
  - **Trump 2025 AI EOs** (4 standalone HTML pages on
    `whitehouse.gov/presidential-actions/2025/...`):
    Removing Barriers to American Leadership in AI (Jan),
    Advancing AI Education for American Youth (Apr),
    Unlocking Cures for Pediatric Cancer with AI (Sep),
    Eliminating State Law Obstruction of National AI Policy (Dec).
  - **America's AI Action Plan** (Jul 2025 White House PDF).

  *ISO/IEC 42001 (1 page, abstract only)*

  - `iso.org/standard/42001` — public abstract / scope summary
    only. The standard text is copyrighted and not redistributed.

  Slugs and full URLs codified in `scripts/fetch/regulation.py`.

### F3. YouTube — curated lecture & talk whitelist

- **What**: ~30–60 videos covering deep technical explainers, founder/
  exec interviews, and frontier-lab leadership. Source channels:
  Karpathy, 3Blue1Brown, Dwarkesh Patel, No Priors, Lex Fridman.
- **Why**: A lot of canonical AI explanation lives on YouTube and
  nowhere else. Time-coded citations make for a memorable demo.
- **Ingest pipeline**:
  1. `yt-dlp --write-sub --sub-format vtt --skip-download` — by
     default, **manual subs only**. Auto-captions are skipped to
     avoid mis-transcriptions on technical terms (transformer,
     attention, model names) without spending compute on Whisper.
  2. **Trusted-author auto-sub allowlist** (per F1's drop): for
     channels with consistently-clean speech and a strong on-screen-
     content signal — Karpathy, 3Blue1Brown, Dwarkesh Patel —
     accept auto-captions when manual subs aren't published. Tag
     those chunks with `subs_kind: auto`.
  3. Parse VTT → segments with start timestamps.
  4. Chunk by ~60–90 seconds of speech (≈150–250 words), preserving
     the start timestamp of the first segment in the chunk.
- **Metadata per chunk**:

  ```text
  {video_id, channel, title, published_at, t_start_seconds, duration}
  ```

- **Citation magic**: render citations as deep links —
  `https://youtu.be/<id>?t=<seconds>`. Tapping the source opens the
  video at the exact moment.
- **Risks**:
  - Even on the trusted-author channels, sub coverage is patchy.
    every channel on the auto-sub allowlist (point 2 above) ships
    auto-only at curation time, so without that allowlist most of
    these picks would be unreachable.
  - YouTube ToS is grey on transcript scraping — fine for an
    educational one-off, would not productionize.
  - Visuals are not indexed, so "what's the diagram at 4:32" won't
    work. Acceptable for v1.

- **Picks for ingest** (88 videos across 9 channels):

  *Round 1 (44 videos, manual-subs default):*

  - *3Blue1Brown — 8* (Deep Learning chapters 1-7 + the 8-min
    "LLMs explained briefly" overview). All have manual subs.
  - *Andrej Karpathy — 7 (auto-sub allowlist)*: Intro to LLMs,
    How I use LLMs, Deep Dive into LLMs, Let's build GPT, Let's
    reproduce GPT-2, Let's build the GPT Tokenizer, building
    micrograd. Skipped: makemore series and the stable-diffusion
    experiment shorts.
  - *Dwarkesh Patel — 14*: Sutskever, Sholto/Trenton, Amodei,
    Karpathy guest, Sutton, Nadella, Zuckerberg, Musk, Huang,
    Reiner Pope, Dylan Patel, Ege/Tamay (AGI 30y), Kokotajlo
    (AI 2027), Casey Handmer (China energy), plus Dwarkesh's own
    "Why AGI not around the corner."
  - *Lex Fridman — 15*: Altman, Hassabis, Amodei, LeCun, Pichai,
    Huang, Musk × 2, Bezos, DeepSeek roundtable, Cursor team,
    Aravind Srinivas (Perplexity), Terence Tao, plus the
    State-of-AI-2026 episode.

  *Round 2 — Tier 1 expansion (44 videos, auto-sub allowlist
  widened to channel-level):* No Priors had been dropped from
  Round 1 because the channel publishes auto-only; Round 2 added
  it (and a16z, Sequoia, YC, Stanford eCorner / GSB / Online) to
  the trusted-author allowlist on the user's call. Also captured:
  Sam Altman talks at YC + a16z + Sequoia + Stanford, the
  Karpathy "Software Is Changing Again" YC talk, Hassabis at
  Sequoia/YC, AI Ascent 2025 + 2026 keynotes, Andrew Ng "AI is
  the new electricity" at GSB, Ethan Mollick "Co-Intelligence" at
  GSB, Susan Athey on AI economics. CS25 Transformers United was
  explicitly excluded from the GSB pull (the user wants the talk
  channels, not the technical-course catalog).

  - No Priors — 11
  - a16z — 7
  - Sequoia Capital — 9
  - Y Combinator — 7
  - Stanford eCorner — 2
  - Stanford GSB — 7
  - Stanford Online — 1

  Final whitelist enumerated in `scripts/fetch/youtube.py`. The
  fetcher records `subs_kind: manual | auto` per video.

---

## G. Course-specific (highest priority)

### G1. The professor's slides and assigned readings

- **Why**: This is what students will ask about first. If the bot can't
  answer "what did slide 14 mean", the demo falls flat.
- **Ingest**: Get from the prof. PPTX → text + per-slide images. Tag
  every chunk with `course=true` so we can boost it in retrieval.
- **License**: Internal to the course.

### G2. Slide ingest pipeline

Two cases, handled differently. Applies to G1 and to any deck-shaped
content elsewhere in the corpus (e.g. consulting decks in C1).

**G2a. PPTX / Keynote (the prof's own decks)**

- `python-pptx` to extract per slide: title, body text, **speaker notes**,
  rendered slide image.
- Speaker notes are the highest-value field — that's what the prof was
  planning to *say*. Index in a separate field with a retrieval boost.
- One chunk per slide with `slide_number`, `deck_title`, `section`.
- Render each slide to PNG (LibreOffice headless:
  `soffice --convert-to png`). When a student asks about "slide 14", the
  bot can attach the image alongside the answer.
- Keynote: export to PPTX or PDF first; no clean Python library for `.key`.

**G2b. PDF slide decks (consulting reports, conference decks, exported PDFs)**

- `PyMuPDF` for text extraction and per-page rendering.
- One chunk per page. For decks where one "slide" spans multiple PDF
  pages (animation frames exported separately), de-dup near-identical
  neighbors by text similarity.
- For text-sparse / chart-heavy slides, run the rendered page image
  through Gemma's vision in a one-time pre-processing pass and store the
  description as an additional searchable field. Catches "what's the
  McKinsey 2x2 about generative AI use cases" type questions.

**Citation format**: `[CourseDeck L3 / slide 14]`, with the slide PNG
attached as a Telegram photo when cited — far more memorable than a
text quote.

**Common gotchas**

- PowerPoint text in grouped shapes / SmartArt sometimes doesn't
  extract — verify on a sample deck before trusting the pipeline.
- Slides often rely on the *spoken word* for meaning. Without speaker
  notes, retrieval will surface decks but the answers will be thin.

---

## Cross-cutting notes

- **Recency**: Most categories should be re-pulled in the week before the
  lecture. Tag every chunk with `fetched_at`.
- **Deduplication**: Earnings transcripts often appear in multiple
  sources; prefer the IR-site canonical version.
- **Image content**: Charts in PDFs — extract figure captions as searchable
  text. Optionally OCR axis labels for the AI Index figures, since students
  will ask about specific charts shown in lecture.
- **Open-web fallback**: live general-knowledge lookups (Wikipedia,
  Britannica-class reference) and free-text web search are owned by
  the chat layer, not this corpus. The retrieval index covers only
  the curated A-G categories above.
