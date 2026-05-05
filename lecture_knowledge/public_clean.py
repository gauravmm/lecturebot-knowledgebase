"""Remove rebuildable bulk payloads before pushing the repo public."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Rule:
    name: str
    reason: str
    rebuild_note: str
    patterns: tuple[str, ...]


RULES: tuple[Rule, ...] = (
    Rule(
        name="consulting",
        reason="Marketing PDFs are quote/summarization sources, not public repo assets.",
        rebuild_note="uv run collect-all consulting && uv run process-all consulting",
        patterns=(
            "data/raw/consulting/*/report.pdf",
            "data/processed/consulting/*.jsonl",
        ),
    ),
    Rule(
        name="earnings",
        reason="Issuer-copyright IR press releases / prepared remarks / transcripts; quote/attribution norm is not a redistribution grant.",
        rebuild_note="uv run collect-all earnings && uv run process-all earnings",
        patterns=(
            "data/raw/earnings/*/page.html",
            "data/raw/earnings/*/prepared_remarks.pdf",
            "data/raw/earnings/*/cfo_commentary.htm",
            "data/raw/earnings/*/transcript.docx",
            "data/processed/earnings/*.jsonl",
        ),
    ),
    Rule(
        name="essays",
        reason="Most essay pages are public-web quote sources; bulk copies stay local.",
        rebuild_note=(
            "uv run collect-all essays && uv run process-all essays "
            "(public-safe profile intentionally excludes the manual YC/AngelList captures)."
        ),
        patterns=(
            "data/raw/essays/*/page.html",
            "data/processed/essays/*.jsonl",
        ),
    ),
    Rule(
        name="funding",
        reason="Crunchbase News pages are quote-only sources and should not live in git.",
        rebuild_note="uv run collect-all funding && uv run process-all funding",
        patterns=(
            "data/raw/funding/*/page.html",
            "data/processed/funding/*.jsonl",
        ),
    ),
    Rule(
        name="letters",
        reason="Canonical IR letters can be re-fetched; keep manifests, not full page payloads.",
        rebuild_note="uv run collect-all letters && uv run process-all letters",
        patterns=(
            "data/raw/letters/*/page.html",
            "data/raw/letters/*/report.pdf",
            "data/processed/letters/*.jsonl",
        ),
    ),
    Rule(
        name="vendors",
        reason="Vendor pricing pages are reference material; local rebuild is safer than public mirroring.",
        rebuild_note="uv run collect-all vendors && uv run process-all vendors",
        patterns=(
            "data/raw/vendors/*/catalog.json",
            "data/raw/vendors/*/page.md",
            "data/raw/vendors/*/page.html",
            "data/processed/vendors/*.jsonl",
        ),
    ),
    Rule(
        name="youtube",
        reason="Subtitle payloads and derived chunks should be regenerated locally, not committed.",
        rebuild_note="uv run collect-all youtube && uv run process-all youtube",
        patterns=(
            "data/raw/youtube/*/subs*.vtt",
            "data/processed/youtube/*.jsonl",
        ),
    ),
)


def _fmt_bytes(n: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    size = float(n)
    unit = units[0]
    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            break
        size /= 1024.0
    return f"{size:.1f} {unit}"


def _matches(pattern: str) -> list[Path]:
    return sorted(
        path for path in REPO_ROOT.glob(pattern) if path.is_file()
    )


def _prune_empty_dirs(root: Path) -> None:
    for parent in sorted(root.parents, reverse=True):
        if parent == REPO_ROOT:
            break
        try:
            parent.rmdir()
        except OSError:
            break


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Dry-run by default. Use --apply to remove rebuildable bulk payloads "
            "before pushing the repo publicly."
        )
    )
    parser.add_argument("--apply", action="store_true", help="Delete the matched files.")
    args = parser.parse_args()

    total_files = 0
    total_bytes = 0
    for rule in RULES:
        files: list[Path] = []
        for pattern in rule.patterns:
            files.extend(_matches(pattern))
        uniq_files = sorted(set(files))
        if not uniq_files:
            continue
        rule_bytes = sum(path.stat().st_size for path in uniq_files)
        total_files += len(uniq_files)
        total_bytes += rule_bytes
        print(f"\n[{rule.name}] {len(uniq_files)} files, {_fmt_bytes(rule_bytes)}")
        print(f"  Why: {rule.reason}")
        for path in uniq_files:
            print(f"  - {path.relative_to(REPO_ROOT)}")
        if args.apply:
            for path in uniq_files:
                path.unlink()
                _prune_empty_dirs(path.parent)
            print("  Applied.")
        else:
            print("  Dry run only.")
        print(f"  Rebuild: {rule.rebuild_note}")

    print(f"\nTotal: {total_files} files, {_fmt_bytes(total_bytes)}")
    if not args.apply:
        print("Next step: uv run public-clean --apply")
    else:
        print("Next steps:")
        print("  1. uv run collect-all")
        print("  2. uv run process-all")
        print("  3. uv run rebuild")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
