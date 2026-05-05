"""Marshal the D1 vendor / pricing corpus into JSONL chunks.

Three sources, three chunking strategies (per spec/SOURCES.md §D1):

  - openrouter-models: one chunk per model row from catalog.json.
    Renders the JSON record as a readable line block (id, provider,
    context window, modalities, prompt/completion/cache $/Mtok, etc.).
    Drops noisy fields (created timestamps, internal links, default
    parameter scaffolding).

  - anthropic-pricing: chunk by H2 in the source markdown. Each chunk
    keeps the H2 heading plus all H3 subsections under it (so e.g.
    "Feature-specific pricing" stays together with its prompt-caching,
    batch, tool-use sub-tables).

  - google-gemini-pricing: chunk by H2 in the rendered HTML. Each H2
    is a per-model section (Gemini 2.5 Pro, Imagen 4, Veo 3, etc.)
    plus a few feature/tool/notes sections at the end.

Output: data/processed/vendors/<slug>.chunks.jsonl
"""

from __future__ import annotations

import json
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

from bs4 import BeautifulSoup, Tag

RAW = Path("data/raw/vendors")
OUT = Path("data/processed/vendors")


def _slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "section"


# --- OpenRouter ----------------------------------------------------------- #


# Convert per-token USD price (as shipped by OpenRouter) into $/Mtok with up
# to four significant digits, dropping trailing zeros. e.g. "0.0000025" ->
# "$2.50 / Mtok"; "0.00000125" -> "$1.25 / Mtok"; "0" -> "$0 / Mtok".
def _per_mtok(raw: str | None) -> str | None:
    if raw is None or raw == "":
        return None
    try:
        d = Decimal(raw) * Decimal(1_000_000)
    except Exception:
        return None
    # Trim to 6 places then strip trailing zeros / lone dot.
    s = f"{d:.6f}".rstrip("0").rstrip(".")
    if s == "" or s == "-":
        s = "0"
    return f"${s} / Mtok"


def _per_unit(raw: str | None, unit: str) -> str | None:
    if raw is None or raw == "":
        return None
    try:
        d = Decimal(raw)
    except Exception:
        return None
    s = f"{d:.6f}".rstrip("0").rstrip(".")
    if s == "" or s == "-":
        s = "0"
    return f"${s} / {unit}"


def _render_openrouter_model(m: dict) -> str:
    pricing = m.get("pricing") or {}
    arch = m.get("architecture") or {}
    top = m.get("top_provider") or {}

    lines: list[str] = []
    name = m.get("name") or m.get("id") or "(unknown)"
    lines.append(f"{name}")
    lines.append(f"OpenRouter id: {m.get('id')}")
    if m.get("canonical_slug") and m["canonical_slug"] != m.get("id"):
        lines.append(f"Canonical slug: {m['canonical_slug']}")
    if m.get("hugging_face_id"):
        lines.append(f"Hugging Face: {m['hugging_face_id']}")

    ctx = top.get("context_length") or m.get("context_length")
    if ctx:
        lines.append(f"Context window: {ctx:,} tokens")
    if top.get("max_completion_tokens"):
        lines.append(f"Max completion tokens: {top['max_completion_tokens']:,}")

    modality = arch.get("modality")
    if modality:
        lines.append(f"Modality: {modality}")
    in_mods = arch.get("input_modalities") or []
    out_mods = arch.get("output_modalities") or []
    if in_mods or out_mods:
        lines.append(
            "Modalities: input=["
            + ", ".join(in_mods)
            + "], output=["
            + ", ".join(out_mods)
            + "]"
        )
    if arch.get("tokenizer"):
        lines.append(f"Tokenizer: {arch['tokenizer']}")
    if arch.get("instruct_type"):
        lines.append(f"Instruct format: {arch['instruct_type']}")

    if m.get("knowledge_cutoff"):
        lines.append(f"Knowledge cutoff: {m['knowledge_cutoff']}")

    price_lines: list[str] = []
    for label, key, unit in (
        ("prompt", "prompt", "mtok"),
        ("completion", "completion", "mtok"),
        ("cache read (input)", "input_cache_read", "mtok"),
        ("cache write (input)", "input_cache_write", "mtok"),
        ("internal reasoning", "internal_reasoning", "mtok"),
    ):
        if key in pricing:
            v = _per_mtok(pricing[key])
            if v is not None:
                price_lines.append(f"  {label}: {v}")
    # Per-unit (image, audio, request, web_search) — render in native unit.
    for label, key, unit in (
        ("image", "image", "image"),
        ("audio", "audio", "audio-min"),
        ("per request", "request", "request"),
        ("web search", "web_search", "search"),
    ):
        if key in pricing:
            v = _per_unit(pricing[key], unit)
            if v is not None:
                price_lines.append(f"  {label}: {v}")
    if price_lines:
        lines.append("Pricing (USD):")
        lines.extend(price_lines)

    if top.get("is_moderated"):
        lines.append("Provider moderation: enabled")

    sp = m.get("supported_parameters") or []
    if sp:
        lines.append("Supported parameters: " + ", ".join(sorted(sp)))

    desc = (m.get("description") or "").strip()
    if desc:
        lines.append("")
        lines.append(desc)

    return "\n".join(lines).strip()


def process_openrouter(slug: str, base: dict) -> tuple[Path, int]:
    out_path = OUT / f"{slug}.chunks.jsonl"
    catalog = json.loads((RAW / slug / "catalog.json").read_text())
    models = catalog.get("data", [])
    chunks: list[dict] = []
    for m in models:
        mid = m.get("id") or "?"
        text = _render_openrouter_model(m)
        if not text:
            continue
        # Cite via the SPA's per-model anchor (best-effort — OpenRouter
        # routes per-model pages at /models/<author>/<slug>).
        per_model_url = f"https://openrouter.ai/models/{mid}"
        chunks.append({
            **base,
            "id": f"vendors::openrouter::{_slugify(mid)}",
            "section_path": mid,
            "doc_subtitle": m.get("name"),
            "model_id": mid,
            "source_url": per_model_url,
            "text": text,
        })
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    return out_path, len(chunks)


# --- Anthropic markdown --------------------------------------------------- #


def _split_md_by_h2(text: str) -> list[tuple[str, str]]:
    """Return [(heading, body_with_heading)] split on top-level H2."""
    lines = text.splitlines()
    sections: list[tuple[str, list[str]]] = []
    preamble: list[str] = []
    current: tuple[str, list[str]] | None = None
    for line in lines:
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m and not line.startswith("###"):
            if current is not None:
                sections.append(current)
            current = (m.group(1).strip(), [line])
        else:
            if current is None:
                preamble.append(line)
            else:
                current[1].append(line)
    if current is not None:
        sections.append(current)
    out: list[tuple[str, str]] = []
    if preamble and any(line.strip() for line in preamble):
        out.append(("Overview", "\n".join(preamble).strip()))
    for h, body in sections:
        out.append((h, "\n".join(body).strip()))
    return out


def process_anthropic(slug: str, base: dict) -> tuple[Path, int]:
    out_path = OUT / f"{slug}.chunks.jsonl"
    md = (RAW / slug / "page.md").read_text()
    sections = _split_md_by_h2(md)
    chunks: list[dict] = []
    for heading, body in sections:
        if not body.strip():
            continue
        anchor = _slugify(heading)
        chunks.append({
            **base,
            "id": f"vendors::anthropic-pricing::{anchor}",
            "section_path": heading,
            "source_url": f"{base['source_url']}#{anchor}",
            "text": body,
        })
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    return out_path, len(chunks)


# --- Google Gemini HTML --------------------------------------------------- #


# Tags we always strip before extracting prose.
DROP_TAGS = (
    "nav",
    "header",
    "footer",
    "aside",
    "script",
    "style",
    "form",
    "iframe",
    "svg",
    "button",
    "noscript",
)


def _normalize_text(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _render_table(tbl: Tag) -> str:
    rows: list[str] = []
    for row in tbl.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in row.find_all(["th", "td"])]
        if any(c for c in cells):
            rows.append(" | ".join(cells))
    return "\n".join(rows)


def _walk_sections(root: Tag) -> list[tuple[str, str | None, list[str]]]:
    """Walk root in document order, splitting into sections at every H2.

    The Gemini page wraps each H2 in a <div class="heading-group"> so the
    pricing content lives in *later siblings of the wrapping div*, not as
    siblings of the H2 itself. We need a recursive walk that splits at
    H2s but still picks up content from sibling subtrees.

    Returns: [(heading, anchor_id_or_None, [rendered_block, ...])]
    """
    sections: list[tuple[str, str | None, list[str]]] = []
    current: tuple[str, str | None, list[str]] | None = ("__preamble__", None, [])

    LEAF_TAGS = {
        "p", "ul", "ol", "table", "pre", "blockquote",
        "h3", "h4", "h5", "h6",
    }

    def emit(text: str) -> None:
        nonlocal current
        if current is None:
            return
        text = text.strip()
        if text:
            current[2].append(text)

    def visit(node: Tag) -> None:
        nonlocal current
        for child in node.children:
            if not isinstance(child, Tag):
                continue
            if child.name == "h2":
                # flush current and open new
                if current is not None:
                    sections.append(current)
                heading = child.get_text(" ", strip=True)
                anchor = child.get("id")
                # The heading group's surrounding div sometimes carries an
                # id attribute that the page anchors-to instead of the h2.
                if not anchor and child.parent and child.parent.get("id"):
                    anchor = child.parent.get("id")
                current = (heading, anchor, [])
                continue
            if child.name in LEAF_TAGS:
                if child.name == "table":
                    rendered = _render_table(child)
                    if rendered:
                        emit(rendered)
                elif child.name in ("h3", "h4", "h5", "h6"):
                    emit(f"### {child.get_text(' ', strip=True)}")
                else:
                    emit(child.get_text(" ", strip=True))
                continue
            # container — recurse to find nested H2s / leaves
            visit(child)

    visit(root)
    if current is not None:
        sections.append(current)
    return sections


def process_gemini(slug: str, base: dict) -> tuple[Path, int]:
    out_path = OUT / f"{slug}.chunks.jsonl"
    soup = BeautifulSoup((RAW / slug / "page.html").read_text(), "lxml")
    root = soup.find("main") or soup.body
    for tag in root.find_all(DROP_TAGS):
        tag.decompose()

    chunks: list[dict] = []
    for heading, anchor, blocks in _walk_sections(root):
        if heading == "__preamble__":
            continue
        body = _normalize_text(f"## {heading}\n" + "\n\n".join(blocks))
        if len(body) < 60:  # skip empty / decorative sections
            continue
        anchor_slug = anchor or _slugify(heading)
        chunks.append({
            **base,
            "id": f"vendors::google-gemini-pricing::{_slugify(heading)}",
            "section_path": heading,
            "source_url": f"{base['source_url']}#{anchor_slug}",
            "text": body,
        })
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    return out_path, len(chunks)


# --- Driver --------------------------------------------------------------- #


PROCESSORS = {
    "openrouter-models": process_openrouter,
    "anthropic-pricing": process_anthropic,
    "google-gemini-pricing": process_gemini,
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    total = 0
    for manifest_path in sorted(RAW.glob("*/manifest.json")):
        slug = manifest_path.parent.name
        manifest = json.loads(manifest_path.read_text())
        base = {
            "corpus": "vendors",
            "doc_title": manifest["title"],
            "publisher": manifest["publisher"],
            "source_url": manifest["source_url"],
            "fetched_at": manifest["fetched_at"],
            "license": manifest.get("license"),
        }
        proc = PROCESSORS.get(slug)
        if proc is None:
            print(f"skip (no processor)  {slug}")
            continue
        out_path, n = proc(slug, base)
        total += n
        print(f"{out_path}: {n} chunks")
    print(f"\nTotal: {total} vendor chunks")


if __name__ == "__main__":
    main()
