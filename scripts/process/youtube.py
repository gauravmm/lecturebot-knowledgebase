"""Marshal the F3 YouTube corpus into JSONL chunks.

Each video lives at:
    data/raw/youtube/<video_id>/info.json
    data/raw/youtube/<video_id>/subs.<lang>.vtt   # one of these
    data/raw/youtube/<video_id>/manifest.json

This processor:
  - Parses the VTT cues into (start_seconds, text) segments,
    de-duplicating consecutive identical lines (YouTube's auto-caption
    rolling-window output repeats each line up to 3x).
  - Joins consecutive segments into chunks targeting ~75 seconds of
    speech (≈190 words). Chunk break also triggered if accumulated
    word count exceeds 280 words even mid-window.
  - Stamps each chunk with `t_start_seconds` (start of first segment)
    and `t_end_seconds` (end of last segment) so the orchestrator can
    deep-link via `https://youtu.be/<id>?t=<seconds>`.
  - Reads `subs_kind` from the manifest (manual | auto) and propagates
    it into each chunk so retrieval can soften direct-quote claims
    against auto-captions.

Output: data/processed/youtube/<video_id>.chunks.jsonl
"""

from __future__ import annotations

import json
import re
from pathlib import Path

RAW = Path("data/raw/youtube")
OUT = Path("data/processed/youtube")

# ~75s window with a hard 280-word ceiling. ~190 words/min is the typical
# spoken-English rate (Karpathy lecture pace ~140 wpm, Dwarkesh interview
# pace ~210 wpm), so 75s × 190 wpm ≈ 240 words, comfortably under cap.
WINDOW_SECONDS = 75.0
MAX_WORDS = 280

VTT_TS = re.compile(r"^(\d{1,2}):(\d{2}):(\d{2})\.(\d{3})\s+-->\s+(\d{1,2}):(\d{2}):(\d{2})\.(\d{3})")


def _ts_to_seconds(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def _strip_vtt_tags(line: str) -> str:
    # Drop inline timing tags `<00:00:01.000>` and styling like `<c>`.
    line = re.sub(r"<[^>]+>", "", line)
    # Drop YouTube's positioning attrs that sometimes appear inline.
    line = re.sub(r"\bposition:\d+%", "", line)
    line = re.sub(r"\balign:\w+", "", line)
    return line.strip()


def _parse_vtt(text: str) -> list[tuple[float, float, str]]:
    """Return [(start_s, end_s, text)] from a VTT file. Consecutive cues
    with identical text are collapsed: the merged span runs from the
    first cue's start to the last cue's end. Rolling-window prefix
    overlap (auto-caption artifact) is stripped via _dedup_overlap on
    the way in."""
    cues: list[tuple[float, float, str]] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        m = VTT_TS.match(lines[i].strip())
        if not m:
            i += 1
            continue
        start = _ts_to_seconds(*m.group(1, 2, 3, 4))
        end = _ts_to_seconds(*m.group(5, 6, 7, 8))
        i += 1
        cue_lines: list[str] = []
        while i < len(lines) and lines[i].strip() and not VTT_TS.match(lines[i].strip()):
            cleaned = _strip_vtt_tags(lines[i])
            if cleaned:
                cue_lines.append(cleaned)
            i += 1
        cue_text = " ".join(cue_lines).strip()
        if not cue_text:
            continue
        if cues and cues[-1][2] == cue_text:
            # Identical-cue rolling window — extend the previous span.
            cues[-1] = (cues[-1][0], end, cue_text)
        else:
            cues.append((start, end, cue_text))
    return _dedup_overlap(cues)


def _dedup_overlap(
    cues: list[tuple[float, float, str]],
) -> list[tuple[float, float, str]]:
    """Strip rolling-window prefix overlap from each cue.

    YouTube auto-captions emit cumulative cues:
        cue 1: "hi everyone so I gave"
        cue 2: "hi everyone so I gave a 30-minute talk"
        cue 3: "I gave a 30-minute talk on large language models"
    Naive concatenation triples each phrase. We strip the longest
    leading-word overlap between cue N and the tail of cue N-1's
    accumulated text, leaving only the *new* tokens in cue N. The
    timestamps are kept (cue N's start), since the new tokens land
    at that moment.
    """
    if not cues:
        return cues
    out: list[tuple[float, float, str]] = []
    prev_tokens: list[str] = []
    # Track tokens accumulated across all kept cues (bounded window of
    # the most recent ~30 tokens — enough to catch any auto-caption
    # rolling overlap, cheap to scan).
    WINDOW = 30
    for start, end, cue_text in cues:
        cue_tokens = cue_text.split()
        if not cue_tokens:
            continue
        # Find the longest k such that prev_tokens[-k:] == cue_tokens[:k].
        max_k = min(len(prev_tokens), len(cue_tokens), WINDOW)
        overlap = 0
        for k in range(max_k, 0, -1):
            if prev_tokens[-k:] == cue_tokens[:k]:
                overlap = k
                break
        new_tokens = cue_tokens[overlap:]
        if not new_tokens:
            # Cue was fully contained in the rolling window — extend the
            # previous span's end timestamp without emitting new text.
            if out:
                ps, _, pt = out[-1]
                out[-1] = (ps, end, pt)
            continue
        out.append((start, end, " ".join(new_tokens)))
        prev_tokens = (prev_tokens + new_tokens)[-WINDOW:]
    return out


def _chunk_cues(
    cues: list[tuple[float, float, str]],
) -> list[tuple[float, float, str]]:
    """Group cues into ~WINDOW_SECONDS / MAX_WORDS chunks.

    Returns [(chunk_start_s, chunk_end_s, joined_text)].
    """
    chunks: list[tuple[float, float, str]] = []
    cur_start: float | None = None
    cur_end: float = 0.0
    cur_words: list[str] = []
    for start, end, txt in cues:
        if cur_start is None:
            cur_start = start
        cur_end = end
        cur_words.extend(txt.split())
        if (cur_end - cur_start) >= WINDOW_SECONDS or len(cur_words) >= MAX_WORDS:
            chunks.append((cur_start, cur_end, " ".join(cur_words)))
            cur_start = None
            cur_end = 0.0
            cur_words = []
    if cur_words:
        assert cur_start is not None
        chunks.append((cur_start, cur_end, " ".join(cur_words)))
    return chunks


def _format_timestamp_label(seconds: float) -> str:
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def process_video(manifest_path: Path) -> tuple[Path, int]:
    manifest = json.loads(manifest_path.read_text())
    video_id = manifest["doc_id"]
    out_path = OUT / f"{video_id}.chunks.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # The manifest's files list points at the .vtt; first vtt wins.
    video_dir = manifest_path.parent
    vtt_path: Path | None = None
    for f in manifest.get("files", []):
        p = video_dir / f["path"]
        if p.suffix == ".vtt" and p.exists():
            vtt_path = p
            break
    if vtt_path is None:
        # Fall back to scanning the dir.
        vtts = sorted(video_dir.glob("*.vtt"))
        if not vtts:
            if out_path.exists():
                out_path.unlink()
            return out_path, 0
        vtt_path = vtts[0]

    cues = _parse_vtt(vtt_path.read_text(errors="replace"))
    if not cues:
        if out_path.exists():
            out_path.unlink()
        return out_path, 0

    chunks_data = _chunk_cues(cues)

    base = {
        "corpus": "youtube",
        "doc_title": manifest["title"],
        "channel": manifest.get("channel"),
        "channel_id": manifest.get("channel_id"),
        "video_id": video_id,
        "source_url": f"https://youtu.be/{video_id}",
        "fetched_at": manifest["fetched_at"],
        "published_at": manifest.get("published_at"),
        "duration_seconds": manifest.get("duration_seconds"),
        "subs_kind": manifest.get("subs_kind", "manual"),
        "subs_lang": manifest.get("subs_lang"),
        "topic_tag": manifest.get("topic_tag"),
        "license": manifest.get("license"),
    }

    written = 0
    with out_path.open("w") as f:
        for i, (start_s, end_s, text) in enumerate(chunks_data):
            t = int(start_s)
            chunk = {
                **base,
                "id": f"youtube::{video_id}::{t:06d}",
                "section_path": _format_timestamp_label(start_s),
                "t_start_seconds": t,
                "t_end_seconds": int(end_s),
                "source_url": f"https://youtu.be/{video_id}?t={t}",
                "text": text,
            }
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")
            written += 1
    return out_path, written


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    total_chunks = 0
    total_videos = 0
    skipped = 0
    for m in sorted(RAW.glob("*/manifest.json")):
        out_path, n = process_video(m)
        total_videos += 1
        total_chunks += n
        if n == 0:
            skipped += 1
            print(f"skip (no cues)  {m.parent.name}")
            continue
        print(f"{out_path}: {n} chunks")
    print(
        f"\nTotal: {total_chunks} chunks across {total_videos - skipped} videos "
        f"({skipped} skipped)"
    )


if __name__ == "__main__":
    main()
