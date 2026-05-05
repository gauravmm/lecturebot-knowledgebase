# Telegram Bot — Rough Spec

A retrieval-augmented chat bot for a guest lecture on AI in business school.
Backed by `gemma-4-e4b-it` with tool access to a curated corpus
(SEC filings, AI Index, consulting reports, course slides, etc.).

Status: rough draft, pre-implementation. Open questions called out inline.

---

## 0. Scope of this document

**In scope here**: corpus contents, ingest pipelines, chunking strategy,
index build (BM25 + dense + metadata), the `search` / `fetch_doc` tool
surface the chat layer calls, citation IDs and labels.

**Out of scope** (owned by a separate workstream): the Telegram
interaction layer, slash commands, message rendering, image input
handling, Mermaid diagram rendering, personalities and system prompts,
conversation state and persistence, rate limiting, user-facing
observability, hosting and auth, and any open-web fallback tools.

---

## 1. Goals & non-goals

Goals

- Live demo during lecture: the prof asks a question, students follow along on phones.
- Each student can ask their own follow-ups privately.
- Transparent retrieval: students can see *which* document a claim came from.
- Show off prompt sensitivity (personalities) and corpus scoping as teaching moments.

Non-goals

- Voice, video, or file upload from students.
- Persistent user accounts beyond a single lecture session.
- Group chats. The bot is private-chat only for v1.

---

## 2. Retrieval

### 2.1 Tool surface exposed to the model

One primary tool, one escape hatch. Small models get confused by larger menus.

```text
search(query: str, corpus: str | null = null, k: int = 6)
  -> list[{id, title, source, snippet, score}]

fetch_doc(id: str)
  -> {title, source, full_text}
```

`corpus` is null by default (search everything) or set by `/scope`.

### 2.2 Index

- Hybrid BM25 + dense vectors, reciprocal rank fusion. (Open: which embedding
  model — leaning `bge-small-en-v1.5` for CPU-friendliness.)
- Chunking is **per-corpus**, not one-size-fits-all. Default is ~800 tokens
  with 100-token overlap, respecting section boundaries. Overrides:
  - **Filings (B)**: chunk on Item boundaries (1, 1A, 7, 8) before applying
    the token cap.
  - **YouTube (F3)**: chunk by ~60–90 seconds of speech (≈150–250 words),
    preserving the timestamp of the first segment in each chunk so
    citations can deep-link to `youtu.be/<id>?t=<seconds>`.
  - **Slides (G1, G3)**: one chunk per slide. Speaker notes stored as a
    separate boosted field. Slide PNG retained for attachment on cite.
  - **Earnings transcripts (B2)**: chunk on speaker-turn boundaries; tag
    chunks with `speaker_role` (CEO / CFO / analyst).
  - **Wikipedia (H)**: chunk by section, capped at the default token size.
- Metadata per chunk (superset; not all fields populated for every corpus):
  `corpus`, `doc_title`, `source_url`, `published_at`, `fetched_at`,
  `section_path`, `slide_number`, `t_start_seconds`, `speaker_role`.
- Per-corpus retrieval boosts at query time: course materials (G) >
  filings (B) > consulting/VC (C) > everything else.

### 2.3 Citations

Citations reference chunk IDs returned by `search`. The bot renders them as
short labels (e.g. `[NVDA 10-K FY24, p.42]`) rather than raw IDs. The
"Show sources" inline button posts a follow-up message with the actual
snippets so students can audit the answer.

---

## 3. Open questions

1. **Hosting** — self-host Gemma on a single L4 vs. a hosted inference
   provider that already serves the gemma-4 family?
2. **Auth** — open bot link, or require an invite code distributed in class
   to keep load predictable?
3. **Corpus freshness** — do we want a cron to pull latest 10-Qs / earnings
   transcripts, or freeze the corpus a week before the lecture?
4. **Multi-language** — any non-English-speaking students? Affects both
   `setMyCommands` localization and the embedding model.
5. **Persistence** — survive restarts (Redis) or accept that a crash resets
   everyone? Lecture is 90 min; probably fine to lose state.

---

## 4. Milestones

1. Skeleton bot: `/start`, `/help`, echoes text. Webhook deployed.
2. Gemma wired up, no retrieval. Personalities working.
3. Retriever + `search` tool. Citations rendered.
4. `/scope`, `/sources`, `/cite`, inline keyboards.
5. Image input.
6. Observability + `/stats` + admin commands.
7. Dry run with 5–10 colleagues, tune prompts and chunk size.
8. Lecture.
