# scripts/process — processor pitfalls

One script per corpus. Each reads the corpus's `manifest.json`
(plus any sidecar JSON or downloaded payload from `data/raw/`) and
emits the normalized JSONL in `data/processed/<corpus>/`. Re-running
a processor is idempotent on the chunk-id schema; the `rebuild`
chain only re-embeds chunks whose text or id changed.

`rechunk.py` is the post-processor that splits oversized chunks down
to the 800-token cap; it runs as the first stage of `uv run rebuild`.

## Ingest gotchas

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
  articles*, not section headings of the page itself. Splitting by
  H3 produces tiny noise chunks. Treat OWID topic pages as: lead
  prose chunk + linked-articles index chunk. Section anchor IDs
  are JS-rendered and not in static HTML, so cite the page URL only.
- **YouTube auto-captions are rolling-window.** Each cue re-emits
  the previous cue's tail before adding new tokens (one phrase
  shows up 2–3× across consecutive cues). Naive concatenation
  triples chunk word counts. The processor's `_dedup_overlap` in
  `youtube.py` strips the longest token-suffix of cue N-1 that
  prefixes cue N. Don't disable it — chunks become unreadable
  ("30-minute talk on large language models 30-minute talk on
  large language models 30-minute talk").

## Subagent dispatch pattern

When batching ingest:

- Each subagent prompt must be **self-contained** — they don't
  inherit context. Include the schema, hard rules, and gotchas
  inline, not a reference to a file they can't see.
- Run them with `run_in_background: true` so notifications stream
  back. The runtime fires a system notification per completion — do
  NOT treat those as user input.
- Pick the right model per task: lecture indexing is Haiku-fine;
  meme captioning needs Sonnet for allegorical content. Don't
  reach for Opus unless quality is publication-grade-critical
  (5× Sonnet cost, marginal gain on this corpus).
