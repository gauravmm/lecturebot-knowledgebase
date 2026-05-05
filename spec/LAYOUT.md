# Data Layout — Rough Spec

On-disk layout for the corpus, indexes, and supporting scripts.

By-stage at the top level (so it's always obvious which step you're
debugging), per-corpus underneath following the letter scheme from
`SOURCES.md`.

Status: rough draft, pre-implementation.

---

## Tree

```text
data/
  raw/                              # immutable originals, never edited
    ai_index/
      2026/
        report.pdf
        manifest.json               # url, fetched_at, sha256, license
    epoch_models/
      models.csv
      blog_posts/
      manifest.json
    edgar/
      msft/10-K_FY25.htm
      nvda/10-K_FY25.htm
      ...
    earnings_transcripts/
      nvda_FY26Q1.txt
    consulting/
      mckinsey/ bcg/ bain/ deloitte/
    vc/
      a16z/ sequoia/ benedict_evans/
    vendors/
      pricing_2026-04-28.html       # date in filename — these change weekly
      model_cards/
    funding/
    arxiv/
      1706.03762_attention.pdf
    youtube/
      <video_id>/
        info.json                   # title, channel, published_at
        subs.en.vtt                 # manual subs only (see SOURCES F3)
    regulation/
    lecturer/                       # the lecturer's own slides + page text
      lectures/<year>-<slug>/
        manifest.json
        slides.pdf|slides.pptx
    memes/
      <hash>.json                   # sidecar; image alongside
    wikipedia/
      <page_slug>.json

  processed/                        # normalized JSONL, one chunk per line
    ai_index/2026.chunks.jsonl
    edgar/msft.chunks.jsonl
    youtube/<video_id>.chunks.jsonl
    lecturer/lectures/<slug>.chunks.jsonl
    memes/memes.chunks.jsonl
    ...

  index/
    bm25/                           # bm25.pkl + vocab.json
    dense/                          # faiss.index + embeddings.npy
    chunk_meta.parquet              # row-aligned with FAISS (no dup metadata)
    manifest.json                   # corpora present, build time, git sha

  cache/
    embeddings/                     # keyed by chunk content-hash
    whisper/                        # keyed by video_id

  exports/
    index_<date>.tar.zst            # the bundle downstream consumers load
    manifest.json

scripts/
  fetch/    fetch_edgar.py  fetch_youtube.py  fetch_arxiv.py  ...
  process/  chunk_pdf.py    chunk_pptx.py     chunk_vtt.py    ...
  index/    build_bm25.py   build_dense.py    package.py

spec/
  ROUGH.md
  SOURCES.md
  LAYOUT.md
```

---

## Conventions

- **`raw/` is immutable.** Re-fetches overwrite the file *and* update the
  per-doc `manifest.json` (new `fetched_at` + hash). If history matters,
  use a `raw_archive/<date>/` sibling rather than versioning in place.
- **One JSONL per source doc** in `processed/`, schema-stable:

  ```text
  {id, corpus, doc_title, source_url, fetched_at, published_at,
   section_path, slide_number, t_start_seconds, speaker_role, text}
  ```

  Not all fields populated for every corpus. Keeps re-processing one doc
  cheap and isolates schema drift.
- **`chunk_meta.parquet` row-aligned with FAISS** so the vector store
  stays metadata-free and rebuilds are fast. Consumers join by row
  index, not by chunk ID lookup.
- **Embedding cache keyed by `sha256(text + model_id)`** so corpus
  re-runs only embed *changed* chunks. The difference between a 5-minute
  rebuild and a 3-hour one.
- **Flat, descriptive corpus dirs** (`ai_index/`, `edgar/`, `lecturer/`,
  `memes/`, …). The spec category letters in `SOURCES.md` are an
  organizational aid for the spec, not a path convention — corpus dirs
  are named for what they hold.
- **Manifests at multiple levels**: per-doc (in `raw/.../manifest.json`)
  and at the index level (`data/index/manifest.json` records which
  corpora and which doc revisions went into the build).
- **`exports/` is what downstream consumers load.** Consumers never
  read `processed/` or `index/` directly — they load a packaged
  tarball. Lets us iterate on the indexer without restarting them.

---

## Per-corpus manifest schema (rough)

```json
{
  "corpus": "youtube",
  "doc_id": "dQw4w9WgXcQ",
  "source_url": "https://youtu.be/dQw4w9WgXcQ",
  "fetched_at": "2026-04-28T14:02:11Z",
  "published_at": "2024-09-12T00:00:00Z",
  "license": "youtube-tos",
  "files": [
    {"path": "subs.en.vtt", "sha256": "…", "bytes": 48211},
    {"path": "info.json",   "sha256": "…", "bytes": 1834}
  ],
  "notes": "manual subs only; auto-captions skipped per SOURCES.md F3"
}
```

---

## Tradeoff considered

**By-stage-at-top** (chosen) vs. **by-corpus-at-top**
(`data/edgar/{raw,processed,index}/...`).

By-stage wins when the *pipelines* differ more than the *corpora* — one
BM25/FAISS index spans everything, and you debug fetch/process/index
issues stage by stage.

By-corpus would win if we wanted to ship per-corpus indexes independently
or hand off one corpus to another team. Not the case here: single index,
one bot, one lecture.

---

## Open questions

1. Do we want a `data/eval/` for a small held-out set of student-style
   questions + expected sources, used to regression-test the index after
   re-builds?
2. Where do scraped HTML pages with embedded images live — keep the
   page as a single HTML file with `<img src="data:...">`, or split into
   `page.html` + `assets/`?
3. Per-doc manifest as `manifest.json` in each doc dir vs. one
   `corpus_manifest.jsonl` per corpus. The latter is faster to scan; the
   former is more git-friendly.
