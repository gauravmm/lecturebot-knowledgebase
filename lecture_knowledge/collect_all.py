"""Fetch every scripted corpus used by the public-safe repo profile."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

STAGES: list[tuple[str, list[str]]] = [
    ("ai_index", ["scripts/fetch/ai_index.py"]),
    ("consulting", ["scripts/fetch/consulting.py"]),
    ("edgar", ["scripts/fetch/edgar.py"]),
    ("epoch_models", ["scripts/fetch/epoch_models.py"]),
    ("essays", ["scripts/fetch/essays.py"]),
    ("funding", ["scripts/fetch/funding.py"]),
    ("letters", ["scripts/fetch/letters.py"]),
    ("owid", ["scripts/fetch/owid.py"]),
    ("regulation", ["scripts/fetch/regulation.py"]),
    ("vendors", ["scripts/fetch/vendors.py"]),
    ("youtube", ["scripts/fetch/youtube.py"]),
]


def _selected(filters: set[str]) -> list[tuple[str, list[str]]]:
    if not filters:
        return STAGES
    selected = [stage for stage in STAGES if stage[0] in filters]
    unknown = sorted(filters - {name for name, _ in STAGES})
    if unknown:
        raise SystemExit(
            "Unknown fetch stages: "
            + ", ".join(unknown)
            + "\nAvailable: "
            + ", ".join(name for name, _ in STAGES)
        )
    return selected


def main() -> int:
    filters = set(sys.argv[1:])
    stages = _selected(filters)
    overall = time.time()
    for name, args in stages:
        print(f"\n==> fetch:{name}")
        t0 = time.time()
        result = subprocess.run([sys.executable, *args], cwd=REPO_ROOT)
        if result.returncode != 0:
            print(f"\n!! fetch:{name} failed (exit {result.returncode}). Stopping.")
            return result.returncode
        print(f"<== fetch:{name}: {time.time() - t0:.1f}s")
    print(f"\nDone in {time.time() - overall:.1f}s.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
