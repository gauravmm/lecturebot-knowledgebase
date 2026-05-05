"""Write a flat inventory of expected corpus files for local rebuilds.

The inventory is intentionally local-only and excludes `*.rechunked.jsonl`
sidecars. It focuses on the corpus artifacts a user should expect after
running the fetch + process pipeline:

  - tracked source-of-truth manifests / sidecars
  - raw payload files restored by `uv run collect-all`
  - primary `*.chunks.jsonl` outputs restored by `uv run process-all`

The output lives under `data/cache/`, which is already gitignored.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_ROOT = REPO_ROOT / "data" / "raw"
DEFAULT_OUT = REPO_ROOT / "data" / "cache" / "expected-files.txt"


def _rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _add_paths(bucket: set[str], *paths: Path) -> None:
    for path in paths:
        bucket.add(_rel(path))


def _processed_path_for_manifest(manifest_path: Path, manifest: dict) -> Path | None:
    raw_dir = manifest_path.parent
    corpus = manifest.get("corpus")

    if raw_dir.parts[-3:-1] == ("lecturer", "lectures"):
        slug = manifest["slug"]
        return REPO_ROOT / "data" / "processed" / "lecturer" / "lectures" / f"{slug}.chunks.jsonl"

    if raw_dir.parts[-2] == "edgar":
        ticker = manifest["ticker"]
        form = manifest["form"]
        period = manifest["report_date"]
        return REPO_ROOT / "data" / "processed" / "edgar" / ticker / f"{form}_{period}.chunks.jsonl"

    if raw_dir.parts[-2] == "memes":
        return REPO_ROOT / "data" / "processed" / "memes" / "memes.chunks.jsonl"

    if corpus == "epoch_models":
        return REPO_ROOT / "data" / "processed" / "epoch_models" / "notable.chunks.jsonl"

    if corpus == "owid":
        return REPO_ROOT / "data" / "processed" / "owid" / f"{manifest['doc_id']}.chunks.jsonl"

    if corpus:
        return REPO_ROOT / "data" / "processed" / corpus / f"{manifest['doc_id']}.chunks.jsonl"

    return None


def _collect_standard_manifest(
    manifest_path: Path,
    manifests: set[str],
    raw_payloads: set[str],
    processed: set[str],
) -> None:
    manifest = _read_json(manifest_path)
    _add_paths(manifests, manifest_path)

    raw_dir = manifest_path.parent
    for file_meta in manifest.get("files", []):
        file_path = raw_dir / file_meta["path"]
        _add_paths(raw_payloads, file_path)

    out_path = _processed_path_for_manifest(manifest_path, manifest)
    if out_path is not None:
        _add_paths(processed, out_path)


def _collect_lecture_manifest(
    manifest_path: Path,
    manifests: set[str],
    raw_payloads: set[str],
    processed: set[str],
) -> None:
    manifest = _read_json(manifest_path)
    _add_paths(manifests, manifest_path)

    raw_dir = manifest_path.parent
    for slide in manifest.get("slides", []):
        downloaded_to = slide.get("downloaded_to")
        if downloaded_to:
            _add_paths(raw_payloads, raw_dir / downloaded_to)

    out_path = REPO_ROOT / "data" / "processed" / "lecturer" / "lectures" / f"{manifest['slug']}.chunks.jsonl"
    _add_paths(processed, out_path)


def _collect_meme_sidecar(
    sidecar_path: Path,
    manifests: set[str],
    raw_payloads: set[str],
    processed: set[str],
) -> None:
    sidecar = _read_json(sidecar_path)
    _add_paths(manifests, sidecar_path)
    _add_paths(raw_payloads, sidecar_path.parent / sidecar["original_filename"])
    _add_paths(processed, REPO_ROOT / "data" / "processed" / "memes" / "memes.chunks.jsonl")


def build_inventory() -> tuple[list[str], list[str], list[str]]:
    manifests: set[str] = set()
    raw_payloads: set[str] = set()
    processed: set[str] = set()
    lecturer_root = RAW_ROOT / "lecturer" / "lectures"

    for manifest_path in sorted(RAW_ROOT.rglob("manifest.json")):
        if lecturer_root in manifest_path.parents:
            _collect_lecture_manifest(manifest_path, manifests, raw_payloads, processed)
        else:
            _collect_standard_manifest(manifest_path, manifests, raw_payloads, processed)

    for manifest_path in sorted((RAW_ROOT / "edgar").glob("*/*.json")):
        _collect_standard_manifest(manifest_path, manifests, raw_payloads, processed)

    for sidecar_path in sorted((RAW_ROOT / "memes").glob("*.json")):
        _collect_meme_sidecar(sidecar_path, manifests, raw_payloads, processed)

    return sorted(manifests), sorted(raw_payloads), sorted(processed)


def _write_section(lines: list[str], title: str, paths: list[str]) -> None:
    lines.append(f"# {title} ({len(paths)})")
    lines.extend(paths)
    lines.append("")


def main() -> int:
    parser = argparse.ArgumentParser(description="Write the local expected-files inventory.")
    parser.add_argument(
        "--out",
        default=str(DEFAULT_OUT),
        help=f"Output path (default: {DEFAULT_OUT.relative_to(REPO_ROOT)})",
    )
    args = parser.parse_args()

    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = REPO_ROOT / out_path

    manifests, raw_payloads, processed = build_inventory()
    lines = [
        f"# Generated by `uv run expected-files` on {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
        "#",
        "# Includes tracked manifests / sidecars, local raw payloads, and primary",
        "# `*.chunks.jsonl` outputs. Excludes `*.rechunked.jsonl`, `data/index/`,",
        "# `data/cache/` artifacts other than this file, and packaged exports.",
        "",
    ]
    _write_section(lines, "Tracked Manifests And Sidecars", manifests)
    _write_section(lines, "Local Raw Payloads", raw_payloads)
    _write_section(lines, "Primary Processed Outputs", processed)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines))
    total = len(manifests) + len(raw_payloads) + len(processed)
    print(f"Wrote {out_path.relative_to(REPO_ROOT)} ({total} paths)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
