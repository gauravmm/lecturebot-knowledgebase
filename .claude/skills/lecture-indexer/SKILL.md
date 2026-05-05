---
name: lecture-indexer
description: Extract structured metadata, prose, slides, and embedded videos from a lecture page on the web (originally written for gauravmanek.com/lectures/<year>/<slug>/) into a manifest.json plus alongside binary assets. Use when ingesting one or more lecture pages into the data corpus.
---

# Lecture indexer

Extract one lecture page into `data/raw/lecturer/lectures/<year>/<slug>/`.
Designed for `gauravmanek.com/lectures/<year>/<slug>/` but the schema and
heuristics generalize to similar lecturer/instructor sites.

## Output

For each lecture, produce one directory containing:

- `manifest.json` (schema below)
- `slides.pptx` / `slides.pdf` if the page links to a downloadable deck
  (binary blob, not extracted)
- nothing else for now — slide text extraction, transcript pulls, and
  external link archiving are downstream pipelines

## Manifest schema

```json
{
  "slug": "...",
  "title": "...",
  "venue": "...",
  "course": "...",
  "semester": null,
  "format": "...",
  "url": "...",
  "speaker": "...",
  "fetched_at": "<ISO 8601 date>",
  "license": "CC BY-SA 4.0",
  "page_text": "<verbatim cleaned prose from the page>",
  "slides": [
    {"url": "...", "format": "pptx|pdf|google-slides|speakerdeck|...",
     "license": "...", "downloaded_to": "slides.pptx|null"}
  ],
  "lecture_recordings": [{"url": "...", "platform": "youtube|vimeo|..."}],
  "referenced_videos":  [{"url": "...", "platform": "youtube|vimeo|..."}],
  "external_links": [{"url": "...", "label": "..."}],
  "social_links":   [{"platform": "...", "url": "...", "label": "..."}],
  "notes": "anything weird, missing, or worth flagging"
}
```

## Field rules (read these — they are the lessons from past mistakes)

- **`page_text` is verbatim.** Strip nav/footer chrome but copy the
  lecturer's actual sentences. Never paraphrase. If you find yourself
  writing "the lecture covers..." or "the speaker discusses...", stop
  and copy the real text instead.
- **No `audience`, no `abstract` field.** Don't infer them.
- **`semester`** is non-null only if the page explicitly states a
  semester ("Fall 2025", "AY 2025/26 Sem 1", etc.). Otherwise `null`.
- **No date or time field.** The exact lecture date/time is intentionally
  omitted.
- **`course` holds the course code only** (e.g., `NUS BSN4811`). No
  semester guesses or free-text expansions.
- **YouTube/Vimeo entries: URL only.** Do not include a title field —
  past runs guessed titles from URLs and got them wrong.
- **`lecture_recordings` vs `referenced_videos`**:
  - *Lecture recordings* = the lecture itself, usually an embedded
    `<iframe src="youtube.com/embed/...">` on the page.
  - *Referenced videos* = videos cited in a reading list / further
    reading section.
  - These are different concepts. Don't conflate.
- **No `recommended_books` field.** The reading-list items are already
  captured in `external_links` with their URLs; a parallel array of
  bare titles is redundant.
- **Don't fabricate annotations.** Labels in `external_links` should
  be the link text the lecturer wrote, not your gloss on what the
  link is about.

## Procedure

1. **Fetch the page** with `WebFetch` for prose and link extraction.

2. **Find embedded videos in raw HTML.** WebFetch converts to markdown
   and may strip `<iframe>` tags. To catch embedded recordings, also
   `curl` the page and grep for `youtube.com/embed`, `youtu.be/`,
   `<iframe`, `data-src`. Embedded videos go in `lecture_recordings`.

3. **Download slide binaries.** If the page links to a `.pptx` or `.pdf`,
   `curl` it to `slides.pptx` / `slides.pdf` in the manifest's directory.
   Don't try to extract text — that's a separate pipeline. Set
   `downloaded_to` to the relative filename. For Google Slides /
   SpeakerDeck links, leave `downloaded_to: null` — those need a
   different pipeline.

4. **Write the manifest** as pretty-printed JSON (2-space indent).
   Create the parent directory with `mkdir -p` if needed.

5. **Report back briefly** (under 200 words):
   - manifest path and downloaded slide filename(s)
   - whether an embedded lecture recording was found, and where in HTML
   - anything you couldn't do or anything surprising
   - don't restate the schema or repeat instructions

## Output path convention

```text
data/raw/lecturer/lectures/<year>-<slug>/manifest.json
data/raw/lecturer/lectures/<year>-<slug>/slides.pptx   (if downloaded)
```

`year` and `slug` come from the source URL pattern
`/lectures/<year>/<slug>/`. The directory name flattens them with a
hyphen (e.g. `2025-nus-bsn4811-ai-startups/`) so all lectures sit in a
single sortable folder.

## Common gotchas

- Slide URLs may be relative (`./BSN4811 AI Startups.pptx`). Resolve
  against the page URL before downloading. Store the resolved absolute
  URL in `slides[].url`.
- License text near a slide link ("released under CC BY-SA 4.0") goes
  in `slides[].license`. The lecture-level `license` field defaults to
  `"CC BY-SA 4.0"` (every gauravmanek.com lecture page declares this in
  prose); override only if a specific page says otherwise.
- The same lecture title may appear at multiple venues (e.g., "Early
  Stage AI Startups" at NUS BSN4811 and NUS BSE3713). The slug
  disambiguates — don't dedup across pages.
- Some pages have no prose, just a title + slide link. That's fine —
  `page_text` becomes a short string or empty.
- If a link is a relative URL (`/lectures/2025/...`), keep it relative
  in `external_links` — downstream pipelines resolve against `url`.
