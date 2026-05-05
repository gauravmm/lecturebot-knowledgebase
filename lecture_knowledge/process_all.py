"""Run every corpus normalizer before `uv run rebuild`."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

STAGES: list[tuple[str, list[str]]] = [
    ("ai_index", ["scripts/process/ai_index.py"]),
    ("consulting", ["scripts/process/consulting.py"]),
    ("earnings", ["scripts/process/earnings.py"]),
    ("edgar", ["scripts/process/edgar.py"]),
    ("epoch_models", ["scripts/process/epoch_models.py"]),
    ("essays", ["scripts/process/essays.py"]),
    ("funding", ["scripts/process/funding.py"]),
    ("lectures", ["scripts/process/lectures.py"]),
    ("letters", ["scripts/process/letters.py"]),
    ("memes", ["scripts/process/memes.py"]),
    ("owid", ["scripts/process/owid.py"]),
    ("regulation", ["scripts/process/regulation.py"]),
    ("vendors", ["scripts/process/vendors.py"]),
    ("youtube", ["scripts/process/youtube.py"]),
]


def _selected(filters: set[str]) -> list[tuple[str, list[str]]]:
    if not filters:
        return STAGES
    selected = [stage for stage in STAGES if stage[0] in filters]
    unknown = sorted(filters - {name for name, _ in STAGES})
    if unknown:
        raise SystemExit(
            "Unknown process stages: "
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
        print(f"\n==> process:{name}")
        t0 = time.time()
        result = subprocess.run([sys.executable, *args], cwd=REPO_ROOT)
        if result.returncode != 0:
            print(f"\n!! process:{name} failed (exit {result.returncode}). Stopping.")
            return result.returncode
        print(f"<== process:{name}: {time.time() - t0:.1f}s")
    print(f"\nDone in {time.time() - overall:.1f}s.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
