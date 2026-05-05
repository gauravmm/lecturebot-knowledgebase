---
name: meme-indexer
description: Caption, OCR, tag, and propose a renaming for one meme image into a sidecar JSON. Use when ingesting meme files into the data corpus so the bot can search for memes by topic, caption, or text overlay.
---

# Meme indexer

Process one meme image into a sidecar JSON containing a vision-model
caption, transcribed text overlay, topic tags, format classification,
and a proposed human-readable filename.

## Output

For each meme image at `data/raw/memes/<original_filename>`, write a
sidecar at `data/raw/memes/<short_hash>.json` (do NOT rename the image
file in the pilot — the rename is applied later in batch).

`short_hash` = first 8 hex chars of the file's sha256.

## Sidecar schema

```json
{
  "id": "f3a9b1c0",
  "sha256": "<full 64-char sha256>",
  "original_filename": "Screenshot_20250814_084934_Instagram.jpg",
  "proposed_filename": "f3a9b1c0--ai-hallucinates-citations.jpg",
  "width": 1080,
  "height": 1350,
  "format": "two-panel|reaction|screenshot|comic|chart|single-panel|gif|...",
  "caption": "<1-2 sentence description of the visual composition>",
  "ocr_text": "<verbatim text overlay, line breaks preserved>",
  "joke_summary": "<1 sentence on what the meme is actually saying>",
  "topics": ["..."],
  "added_at": "<today, ISO 8601 date>"
}
```

## Procedure

1. **Hash + dimensions**: compute sha256 with `sha256sum`, dimensions
   with `identify` (ImageMagick) or `python -c "from PIL import Image..."`.

2. **Vision pass**: Read the image with the Read tool (Claude is
   multimodal — pass the image path directly). Then derive ALL of the
   following yourself, in this order:

   - **caption**: 1–2 sentences on the *visual composition* — what
     elements are in the frame, how they relate spatially. Note when
     the same element appears twice (e.g. "the same bird appears on
     both sides of the chasm") because that's often the punchline.
     Description, not interpretation, not snark.
   - **ocr_text**: verbatim transcription, preserving case and line
     breaks. Speech bubbles get `[speech bubble: "..."]` framing so
     attribution is preserved. Use literal `<no-text>` if there's none.
   - **joke_summary**: ONE sentence stating what the meme is actually
     saying. This is the conceptual punchline, not the visual content.
     If you can't articulate the joke in one sentence, you probably
     misread the image — go back and re-examine.
   - **topics**: 3–5 short kebab-case tags. Prefer **concept tags** that
     describe what the meme is *about* (`hallucination`,
     `prompt-engineering`, `regression-is-ml`, `agi-doomerism`) over
     **visual-element tags** (`torch-passing`, `whiteboard`) or
     **joke-specific tags** (`that-time-gpt-said-2024-was-three-years
     -ago`). A good test: would this tag plausibly apply to other memes
     in the corpus? If no, drop it.
   - **format**: one of `two-panel`, `reaction`, `screenshot`, `comic`,
     `chart`, `single-panel`, `gif`.

3. **Slug generation**: from the caption, derive a 3-6 word kebab-case
   slug. Lowercase, ASCII only, no stopwords like "a/the/of" unless they
   carry meaning. Examples:
   - "A scientist looks horrified at an AI-generated paper full of fake
     citations" → `scientist-horrified-fake-citations`
   - "Distracted-boyfriend meme: developer ignoring documentation in
     favor of ChatGPT" → `distracted-boyfriend-chatgpt-vs-docs`

4. **Compose `proposed_filename`**: `<short_hash>--<slug>.<original_ext>`.
   Preserve the original extension exactly (`.jpg`, `.png`, `.webp`,
   `.gif`).

5. **Write the sidecar JSON** (2-space indent) to
   `data/raw/memes/<short_hash>.json`. Do NOT rename the original image
   in pilot mode.

## Field rules (lessons baked in)

- **`caption` describes visual composition, not interpretation.** "Two
  scientists at a whiteboard" not "Two scientists who clearly don't
  understand transformers". When elements repeat or relate visually
  (same figure twice, speech bubble pointing at something specific,
  one image labeled and another unlabeled), call that out — it's
  usually load-bearing for the joke.
- **`joke_summary` is the conceptual content in one sentence.** This is
  what the retriever needs to match a student's question to a relevant
  meme. The caption tells you what's in the frame; the joke summary
  tells you *why anyone would post this*. If you can't write it,
  re-examine the image — you probably misread the structure.
- **`ocr_text` is verbatim.** Preserve case (memes are usually ALL CAPS),
  preserve line breaks. Speech bubbles get `[speech bubble: "..."]`
  framing so the attribution doesn't get lost. Use `<no-text>` literal
  if there's nothing written.
- **`topics` are concept tags, not visual elements.** Tags should be
  about what the meme is *about*, not what's in the picture. Test:
  "would this tag plausibly apply to a different meme?" If no, drop
  it. `regression-is-ml` good, `torch-passing` bad. `hallucination`
  good, `whiteboard` bad.
- **Don't include speculation about source/origin.** The image may be
  from Reddit, Twitter, Substack — we don't know and shouldn't guess.
- **`format`** captures the structural pattern, not the joke. A
  "distracted boyfriend" meme is `reaction`; a chart of GPU prices is
  `chart`; an Instagram screenshot of a tweet is `screenshot`.

## Common gotchas

- **JSON-escape every double quote in `ocr_text`.** Memes frequently
  contain dialogue ("DO IT!", "I'm sorry, I cannot complete that
  request") and tweets in quotes. Inside a JSON string these MUST be
  written as `\"`. A real example that broke downstream processing:
  `"ocr_text": "...says \"DO IT!\" and refuses..."`. Same applies to
  literal backslashes (`\\`) and any control characters. Validate by
  parsing your output before writing it (e.g., `python3 -c "import
  json,sys; json.load(open(sys.argv[1]))"`).
- **Allegorical memes are hard.** When the image uses a metaphor (Greek
  vase paintings, religious iconography, video-game tropes) to make a
  point about AI/ML, weaker vision models tend to enumerate visible
  elements without parsing the metaphor. The `joke_summary` field is
  the forcing function — if you can't write a coherent one-sentence
  punchline, slow down and look again.
- **Speech bubbles attribute statements to specific characters.** "X
  exclaims Y" is different from "Y is a label on X". Get this wrong
  and the meme's meaning inverts.
- Vision models sometimes refuse to transcribe text on memes that
  include real names or look like screenshots of private messages. If
  the model refuses OCR, set `ocr_text` to `<refused>` and add a note.
- Some memes have *no* text — that's fine, set `ocr_text: "<no-text>"`.
- File extensions: respect the original. A `.png` meme stays `.png`;
  don't normalize to `.jpg`.
- WebP and GIF: handle the same way; for animated GIFs, caption the
  first frame and note `format: "gif"`.
- Filenames may contain spaces, parens, or unicode. Quote paths.

## What this skill does NOT do

- Does not rename the image file (rename is a separate batch step
  after schemas are validated).
- Does not deduplicate by sha256 (downstream concern; sidecars carry
  the hash so dedup is trivial later).
- Does not compute CLIP embeddings (separate pipeline if/when added).
- Does not constrain `topics` to a fixed vocabulary in pilot mode —
  that vocab gets defined after seeing what tags the batch produces.
