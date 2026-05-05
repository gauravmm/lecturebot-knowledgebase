# lecture-knowledge

A curated reference library that the in-class AI bot uses to answer
your questions during the AI-in-business lecture. This repo only owns
the **library** — the chat layer (Telegram bot, model, conversation
state) is a separate workstream and not documented here.

If the bot tells you "according to *Bain Technology Report 2025, p.34*",
this is where that PDF lives. If the bot can't answer something, it's
probably because the source isn't in here yet — the gaps are listed at
the bottom of this page.

---

## What's in the library

About **9,600 searchable passages** drawn from ten source families.
Roughly grouped by what kind of question they're best at answering:

### "How big is AI?" — industry data and benchmarks

- **Stanford HAI AI Index 2026** — the canonical 425-page annual
  report on AI compute, funding, capability benchmarks, hiring,
  regulation, and public opinion. The most-cited single source in
  business-school AI lectures.
- **Epoch notable AI models database** — 1,011 models with
  training compute, parameter counts, dataset sizes, and estimated
  training cost. Use this when a question needs a number on a
  specific model.
- **Our World in Data — AI topic page** — clean chart-grounded
  summaries with curated visualizations.

### "What does the C-suite actually say?" — company filings + letters

- **SEC filings (EDGAR)** — most-recent 10-K and last four 10-Qs
  for 12 companies: Microsoft, Alphabet, Meta, NVIDIA, Amazon,
  Apple, Salesforce, Oracle, Palantir, Snowflake, Adobe, IBM. The
  bot prioritizes Items 1, 1A (Risk Factors), 7 (Management's
  Discussion), 7A, and 8 (Financial Statements) — the sections
  investors actually read.
- **Earnings call transcripts and CEO commentary** — IR-published
  transcripts where companies make them available. Microsoft (full
  Q&A), IBM (prepared remarks), NVIDIA (CFO commentary, the
  closest thing they publish to a transcript), Amazon (CEO quote
  excerpts). Other companies don't publish transcripts, so they
  aren't covered here.
- **Shareholder letters** — Jeff Bezos's annual letters
  (1997, 2013, 2015–2020) and Satya Nadella's annual letters
  (FY20–FY25). Jensen Huang doesn't publish a separate letter; his
  content is in NVIDIA's 10-K.

### "How do strategists frame this?" — consulting and VC

- **Big-3 consulting AI reports** — McKinsey *State of AI 2025*,
  McKinsey *Economic Potential of Generative AI* (2023), BCG
  *Widening AI Value Gap* (2025), Bain *Technology Report 2025*,
  Deloitte *State of AI in the Enterprise 2026*.
- **VC and tech-strategy essays** — 46 essays from Sequoia
  (Generative AI, $600B Question, AI Ascent, This Is AGI), a16z
  (Empty Promise of Data Moats, New Business of AI, Will Save the
  World), NFX, Benedict Evans, Bessemer, Stratechery (Ben
  Thompson's free Weekly Articles applying aggregation theory to
  AI), Asianometry (Jon Y on the semiconductor / GPU economics
  backstory), plus the lecturer's own reading list (Chesterton's
  Fence, Gervais Principle, Where's Your Ed At, etc.).

### "What does it cost? What model should I use?" — vendor reference

- **OpenRouter models catalog** — 371 models with normalized
  prompt and completion pricing per million tokens, context
  windows, modalities, and providers — one consistent schema
  across the industry.
- **Anthropic and Google Gemini pricing pages** — the two narrative
  vendor pages that cover discount mechanics (prompt caching, batch,
  long-context) the API catalog doesn't show.

### "Can I see how this actually works?" — deep technical explainers

- **YouTube transcripts** — 88 curated talks with timestamped
  citations (the bot can deep-link you to the exact moment in the
  video). Channels: 3Blue1Brown's neural-network series, Andrej
  Karpathy's *Intro to LLMs* / *Let's build GPT* / *Reproduce
  GPT-2*, Dwarkesh Patel's interviews (Sutskever, Amodei,
  Karpathy, Sutton, Nadella, Zuckerberg, Musk, Huang), Lex Fridman
  (Altman, Hassabis, Amodei, LeCun, Pichai, Huang, Bezos), No
  Priors, a16z, Sequoia (AI Ascent keynotes), Y Combinator (How To
  Build The Future, Karpathy "Software Is Changing Again"), and
  selected Stanford GSB / eCorner talks (Andrew Ng "AI is the new
  electricity", Ethan Mollick "Co-Intelligence", Susan Athey on AI
  economics).

### Course materials

- **The lecturer's slide decks** — 10 lectures from
  gauravmanek.com, including page text, per-slide content, and
  speaker notes. Tagged so the bot can boost them when answering
  course-specific questions.
- **Memes** — 40 lecture-relevant captioned images, OCR'd and
  tagged so the bot can return one when the joke fits.

---

## How to read citations

The bot renders sources as short labels — for example:

- `[NVDA 10-K FY26 / Item 7]` — the MD&A section of NVIDIA's most
  recent 10-K
- `[McKinsey State of AI 2025, p.14]` — page 14 of that PDF
- `[Karpathy "Intro to LLMs", 12:45]` — that video at 12 min 45 sec
- `[Sequoia: AI Ascent 2026 Keynote]` — the linked talk
- `[Bezos 1997 letter]` — the original Day-1 letter

Tapping or clicking the source label opens the original document.
Quotes are short and attributed; we don't redistribute body text in
bulk. If the bot makes a strong claim, it should always cite a source
— if it doesn't, that's a sign you should push back ("show me where
that comes from").

## What dates apply

Most of the library was last refreshed on **2026-05-04**. The
underlying documents have their own publication dates (e.g., the
NVIDIA 10-K was filed in early 2026 and reflects FY ending January
2026). When recency matters, ask the bot to tell you when the source
was published — it tracks that.

The bot doesn't know about events after the refresh date. If you're
asking about something that broke this morning, it can't help.

## Public Repo Workflow

If this repo is pushed to a public Git host, the intended workflow is:

1. Run `uv run public-clean --apply` to remove rebuildable bulk payloads
   from quote-only corpora while keeping the manifests and fetch scripts.
2. Commit that cleaned state.
3. Any user who wants the full local corpus can then run:
   `uv run collect-all`, `uv run process-all`, `uv run rebuild`.

If you want a flat checklist of the corpus files that should exist
locally after fetch + process, run `uv run expected-files`. It writes
an ignored inventory to `data/cache/expected-files.txt` and
intentionally leaves out `*.rechunked.jsonl` sidecars.

This public-safe profile strips the raw payloads and derived JSONL for
the consulting reports, essays, Crunchbase funding pages, shareholder
letters, vendor pricing pages, and YouTube subtitle corpus. Those
sources are all rebuildable from the scripted fetchers already in the
repo, but they should not live in git in bulk.

One small exception: a few manual essay captures that were originally
browser-saved (notably the YC and AngelList pages called out in
`scripts/fetch/essays.py`) are intentionally excluded from the
public-safe rebuild because they do not yet have a hands-off fetch path.
Another current exception is `earnings`: some Amazon-hosted source URLs
have already started returning `404`, so that corpus stays in git until
we add a reliable archival or fallback fetch path.

## License

The repository's original software and repo-authored documentation are
licensed under [MIT](LICENSE).

Corpus content is not uniformly MIT-licensed. Material under `data/raw/`
and `data/processed/` keeps its own licensing and usage rules, recorded
in the relevant manifests. See [LICENSES.md](LICENSES.md) for the split
between original code/docs and mixed-license source material.

## What's *not* in here

The bot is restricted to this curated library — it doesn't browse the
open web by default. So it generally can't answer:

- Real-time numbers (stock prices, today's funding rounds, breaking
  news).
- Detailed technical questions outside the AI / business space
  (biotech specifics, low-level systems engineering, etc.).
- Questions about specific people unless they appear in one of the
  source documents (founder bios, exec career arcs).
- Anything paywalled — Harvard Business Review, full Stratechery
  paid posts, premium consulting bundles, etc.

For lookups that the library can't answer, the bot may fall back to
an external search tool. Treat those answers with extra skepticism;
they're not curated and may include errors.

## A note on the AI-generated content here

The bot uses a language model on top of this library. It will
sometimes summarize incorrectly, miss nuance, or sound more confident
than it should. This is a known limitation of the technology — the
whole point of the lecture is to discuss it openly.

When in doubt:

1. Ask the bot to **show its sources**.
2. Click through to the original document.
3. Form your own view from the source text, not the summary.

You're MBAs — you already know to read the footnotes.
