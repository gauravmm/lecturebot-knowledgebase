"""Download the C2 (VC essays + lecturer reading list) and C3 (Stratechery
free Articles) essay corpus per spec/SOURCES.md.

Each essay lands at:
    data/raw/essays/<slug>/page.html
    data/raw/essays/<slug>/manifest.json

Same browser-headers approach as scripts/fetch/consulting.py — many of
these sites have WAFs that drop bare curl. HTTP/2 default; --compressed
handles gzip transparently.

Re-run is idempotent: if the on-disk page.html sha256 already matches
the just-downloaded bytes, we leave the file in place. The manifest is
always rewritten to reflect on-disk state.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

RAW = Path("data/raw/essays")

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    # Sec-Fetch-* + Upgrade-Insecure-Requests are required by some
    # WAFs (6startupstages.com returns 403 without them).
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

# Essay catalog. Fields per entry:
#   url             — canonical URL to fetch
#   title           — display title (best-effort; processor may override
#                     from <title>/h1 if missing)
#   author          — comma-separated author list
#   publisher       — the brand the bot will cite
#   category        — vc | stratechery | lecturer_reading_list
#   published_at    — yyyy-mm or yyyy-mm-dd if known
ESSAYS: dict[str, dict] = {
    # ---------------- Sequoia ----------------
    "sequoia-generative-ai-creative-new-world-2022": {
        "url": "https://www.sequoiacap.com/article/generative-ai-a-creative-new-world/",
        "title": "Generative AI: A Creative New World",
        "author": "Sonya Huang, Pat Grady",
        "publisher": "Sequoia Capital",
        "category": "vc",
        "published_at": "2022-09",
    },
    "sequoia-generative-ai-act-two-2023": {
        "url": "https://www.sequoiacap.com/article/generative-ai-act-two/",
        "title": "Generative AI's Act Two",
        "author": "Sonya Huang, Pat Grady",
        "publisher": "Sequoia Capital",
        "category": "vc",
        "published_at": "2023-09",
    },
    "sequoia-ais-600b-question-2024": {
        "url": "https://www.sequoiacap.com/article/ais-600b-question/",
        "title": "AI's $600B Question",
        "author": "David Cahn",
        "publisher": "Sequoia Capital",
        "category": "vc",
        "published_at": "2024-06",
    },
    "sequoia-ai-ascent-2025": {
        "url": "https://www.sequoiacap.com/article/ai-ascent-2025/",
        "title": "AI Ascent 2025",
        "author": "Sequoia Team",
        "publisher": "Sequoia Capital",
        "category": "vc",
        "published_at": "2025-05",
    },
    "sequoia-2026-this-is-agi": {
        "url": "https://www.sequoiacap.com/article/2026-this-is-agi/",
        "title": "2026: This Is AGI",
        "author": "Pat Grady, Sonya Huang",
        "publisher": "Sequoia Capital",
        "category": "vc",
        "published_at": "2026-01",
    },
    # ---------------- a16z ----------------
    "a16z-empty-promise-of-data-moats-2019": {
        "url": "https://a16z.com/the-empty-promise-of-data-moats/",
        "title": "The Empty Promise of Data Moats",
        "author": "Martin Casado, Peter Lauten",
        "publisher": "Andreessen Horowitz (a16z)",
        "category": "vc",
        "published_at": "2019-05",
    },
    "a16z-new-business-of-ai-2020": {
        "url": "https://a16z.com/the-new-business-of-ai-and-how-its-different-from-traditional-software/",
        "title": "The New Business of AI (and How It's Different From Traditional Software)",
        "author": "Martin Casado et al.",
        "publisher": "Andreessen Horowitz (a16z)",
        "category": "vc",
        "published_at": "2020-02",
    },
    "a16z-taming-the-tail-2020": {
        "url": "https://a16z.com/taming-the-tail-adventures-in-improving-ai-economics/",
        "title": "Taming the Tail: Adventures in Improving AI Economics",
        "author": "Martin Casado",
        "publisher": "Andreessen Horowitz (a16z)",
        "category": "vc",
        "published_at": "2020-08",
    },
    "a16z-who-owns-the-generative-ai-platform-2023": {
        "url": "https://a16z.com/who-owns-the-generative-ai-platform/",
        "title": "Who Owns the Generative AI Platform?",
        "author": "Matt Bornstein, Guido Appenzeller, Martin Casado",
        "publisher": "Andreessen Horowitz (a16z)",
        "category": "vc",
        "published_at": "2023-01",
    },
    "a16z-ai-will-save-the-world-2023": {
        "url": "https://a16z.com/ai-will-save-the-world/",
        "title": "Why AI Will Save the World",
        "author": "Marc Andreessen",
        "publisher": "Andreessen Horowitz (a16z)",
        "category": "vc",
        "published_at": "2023-06",
    },
    "a16z-economic-case-for-generative-ai-2023": {
        "url": "https://a16z.com/the-economic-case-for-generative-ai/",
        "title": "The Economic Case for Generative AI",
        "author": "Martin Casado",
        "publisher": "Andreessen Horowitz (a16z)",
        "category": "vc",
        "published_at": "2023-10",
    },
    "a16z-economic-case-genai-and-foundation-models": {
        "url": "https://a16z.com/the-economic-case-for-generative-ai-and-foundation-models/",
        "title": "The Economic Case for Generative AI and Foundation Models",
        "author": "a16z",
        "publisher": "Andreessen Horowitz (a16z)",
        "category": "vc",
        "published_at": None,
    },
    # ---------------- NFX ----------------
    "nfx-generative-tech-2022": {
        "url": "https://www.nfx.com/post/generative-tech",
        "title": "Generative AI Begins",
        "author": "James Currier",
        "publisher": "NFX",
        "category": "vc",
        "published_at": "2022-10",
    },
    "nfx-5-layer-generative-tech-stack": {
        "url": "https://www.nfx.com/post/generative-ai-tech-5-layers",
        "title": "The 5-Layer Generative Tech Stack",
        "author": "NFX",
        "publisher": "NFX",
        "category": "vc",
        "published_at": "2023",
    },
    "nfx-ai-workforce-is-here": {
        "url": "https://www.nfx.com/post/ai-workforce-is-here",
        "title": "The AI Workforce is Here",
        "author": "NFX",
        "publisher": "NFX",
        "category": "vc",
        "published_at": "2024",
    },
    # ---------------- Benedict Evans ----------------
    "benedict-evans-building-ai-products-2024": {
        "url": "https://www.ben-evans.com/benedictevans/2024/6/8/building-ai-products",
        "title": "Building AI products",
        "author": "Benedict Evans",
        "publisher": "Benedict Evans",
        "category": "vc",
        "published_at": "2024-06",
    },
    # ---------------- Bessemer ----------------
    "bessemer-state-of-ai-2025": {
        "url": "https://www.bvp.com/atlas/the-state-of-ai-2025",
        "title": "The State of AI 2025",
        "author": "Bessemer Venture Partners",
        "publisher": "Bessemer Venture Partners",
        "category": "vc",
        "published_at": "2025-08",
    },
    # ---------------- Lecturer external_links ----------------
    "lecturer-6-startup-stages": {
        "url": "https://6startupstages.com/",
        "title": "The Six Startup Stages",
        "author": None,
        "publisher": "6startupstages.com",
        "category": "lecturer_reading_list",
        "published_at": None,
    },
    "lecturer-fs-blog-chestertons-fence": {
        "url": "https://fs.blog/chestertons-fence/",
        "title": "Chesterton's Fence",
        "author": "Farnham Street",
        "publisher": "Farnham Street",
        "category": "lecturer_reading_list",
        "published_at": None,
    },
    # angellist.com renders post bodies client-side from a JSON API.
    # The user dropped a browser-saved archive into the repo root and
    # it was ingested manually — see data/raw/essays/lecturer-angellist-
    # power-law-vc/manifest.json (notes field documents the path). Not
    # re-enabled in this catalog because plain curl still won't work;
    # add a Playwright fetch path if you want hands-off re-pulls.
    # "lecturer-angellist-power-law-vc": {...},
    "lecturer-skalata-venture-returns": {
        "url": "https://www.skalata.vc/blog/how-venture-returns-really-work-power-law-patience-and-portfolio-construction",
        "title": "How Venture Returns Really Work: Power Law, Patience, and Portfolio Construction",
        "author": "Skalata Ventures",
        "publisher": "Skalata Ventures",
        "category": "lecturer_reading_list",
        "published_at": None,
    },
    "lecturer-ribbonfarm-gervais-principle": {
        "url": "https://www.ribbonfarm.com/2009/10/07/the-gervais-principle-or-the-office-according-to-the-office/",
        "title": "The Gervais Principle, Or The Office According to The Office",
        "author": "Venkatesh Rao",
        "publisher": "ribbonfarm",
        "category": "lecturer_reading_list",
        "published_at": "2009-10",
    },
    "lecturer-wheresyoured-men-who-killed-google": {
        "url": "https://www.wheresyoured.at/the-men-who-killed-google/",
        "title": "The Men Who Killed Google",
        "author": "Edward Zitron",
        "publisher": "Where's Your Ed At",
        "category": "lecturer_reading_list",
        "published_at": None,
    },
    # YC Library uses Inertia.js — article body is HTML-attribute-
    # escaped JSON inside <div data-page="...">. The user dropped
    # browser-saved archives into the repo root and they were ingested
    # manually (yc-stages-of-startups + yc-essential-startup-advice);
    # see those manifests' notes field. Not re-enabled in this catalog
    # because plain curl still won't reach them; add a Playwright path
    # if you want hands-off re-pulls.
    # "lecturer-yc-stages-of-startups": {...},
    # "lecturer-yc-essential-startup-advice": {...},
    "lecturer-prediction-machines": {
        "url": "https://www.predictionmachines.ai/",
        "title": "Prediction Machines (book site)",
        "author": "Ajay Agrawal, Joshua Gans, Avi Goldfarb",
        "publisher": "predictionmachines.ai",
        "category": "lecturer_reading_list",
        "published_at": None,
    },
    # ---------------- Stratechery ----------------
    "stratechery-ai-and-the-big-five-2023": {
        "url": "https://stratechery.com/2023/ai-and-the-big-five/",
        "title": "AI and the Big Five",
        "author": "Ben Thompson",
        "publisher": "Stratechery",
        "category": "stratechery",
        "published_at": "2023-02",
    },
    "stratechery-attenuating-innovation-ai-2023": {
        "url": "https://stratechery.com/2023/attenuating-innovation-ai/",
        "title": "Attenuating Innovation (AI)",
        "author": "Ben Thompson",
        "publisher": "Stratechery",
        "category": "stratechery",
        "published_at": "2023-02",
    },
    "stratechery-accidental-consumer-tech-company-2023": {
        "url": "https://stratechery.com/2023/the-accidental-consumer-tech-company-chatgpt-meta-and-product-market-fit-aggregation-and-apis/",
        "title": "The Accidental Consumer Tech Company; ChatGPT, Meta, and Product-Market Fit; Aggregation and APIs",
        "author": "Ben Thompson",
        "publisher": "Stratechery",
        "category": "stratechery",
        "published_at": "2023-02",
    },
    "stratechery-nvidia-on-the-mountaintop-2023": {
        "url": "https://stratechery.com/2023/nvidia-on-the-mountaintop/",
        "title": "Nvidia On the Mountaintop",
        "author": "Ben Thompson",
        "publisher": "Stratechery",
        "category": "stratechery",
        "published_at": "2023-05",
    },
    "stratechery-meta-open-sources-llama2-2023": {
        "url": "https://stratechery.com/2023/free-meta-open-sources-another-ai-model-moats-and-open-source-apple-and-meta/",
        "title": "Meta Open Sources Another AI Model, Moats and Open Source, Apple and Meta",
        "author": "Ben Thompson",
        "publisher": "Stratechery",
        "category": "stratechery",
        "published_at": "2023-07",
    },
    "stratechery-aggregators-ai-risk-2024": {
        "url": "https://stratechery.com/2024/aggregators-ai-risk/",
        "title": "Aggregator's AI Risk",
        "author": "Ben Thompson",
        "publisher": "Stratechery",
        "category": "stratechery",
        "published_at": "2024-04",
    },
    "stratechery-nvidia-waves-and-moats-2024": {
        "url": "https://stratechery.com/2024/nvidia-waves-and-moats/",
        "title": "Nvidia Waves and Moats",
        "author": "Ben Thompson",
        "publisher": "Stratechery",
        "category": "stratechery",
        "published_at": "2024-08",
    },
    "stratechery-deepseek-faq-2025": {
        "url": "https://stratechery.com/2025/deepseek-faq/",
        "title": "DeepSeek FAQ",
        "author": "Ben Thompson",
        "publisher": "Stratechery",
        "category": "stratechery",
        "published_at": "2025-01",
    },
    "stratechery-checking-in-on-ai-and-the-big-five-2025": {
        "url": "https://stratechery.com/2025/checking-in-on-ai-and-the-big-five/",
        "title": "Checking In on AI and the Big Five",
        "author": "Ben Thompson",
        "publisher": "Stratechery",
        "category": "stratechery",
        "published_at": "2025-02",
    },
    "stratechery-openais-windows-play-2025": {
        "url": "https://stratechery.com/2025/openais-windows-play/",
        "title": "OpenAI's Windows Play",
        "author": "Ben Thompson",
        "publisher": "Stratechery",
        "category": "stratechery",
        "published_at": "2025-10",
    },
    "stratechery-google-nvidia-and-openai-2025": {
        "url": "https://stratechery.com/2025/google-nvidia-and-openai/",
        "title": "Google, Nvidia, and OpenAI",
        "author": "Ben Thompson",
        "publisher": "Stratechery",
        "category": "stratechery",
        "published_at": "2025-12",
    },
    "stratechery-agents-over-bubbles-2026": {
        "url": "https://stratechery.com/2026/agents-over-bubbles/",
        "title": "Agents Over Bubbles",
        "author": "Ben Thompson",
        "publisher": "Stratechery",
        "category": "stratechery",
        "published_at": "2026-03",
    },
    # ---------------- Asianometry (Substack) ----------------
    # Jon Y's semiconductor / AI-chip beat. Picked the 8 directly
    # AI/GPU/data-center-relevant articles from the 23-post archive;
    # the broader semis-history catalog (Sony/Toshiba/Sharp, BOE,
    # STMicro) isn't pulled. Substack pages render server-side and
    # extract cleanly through the existing prose extractor.
    "asianometry-nvidia-history-culture-2024": {
        "url": "https://www.asianometry.com/p/nvidias-unique-history-and-culture",
        "title": "Nvidia's Unique History and Culture",
        "author": "Jon Y (interview with Tae Kim)",
        "publisher": "Asianometry",
        "category": "asianometry",
        "published_at": "2024-12",
    },
    "asianometry-600b-ai-chip-giant-2024": {
        "url": "https://www.asianometry.com/p/the-600-billion-ai-chip-giant",
        "title": "The $600 Billion AI Chip Giant",
        "author": "Jon Y",
        "publisher": "Asianometry",
        "category": "asianometry",
        "published_at": "2024-08",
    },
    "asianometry-data-center-water-problem-2024": {
        "url": "https://www.asianometry.com/p/the-big-data-center-water-problem",
        "title": "The Big Data Center Water Problem",
        "author": "Jon Y",
        "publisher": "Asianometry",
        "category": "asianometry",
        "published_at": "2024-11",
    },
    "asianometry-is-the-ai-boom-real-2024": {
        "url": "https://www.asianometry.com/p/is-the-ai-boom-real",
        "title": "Is the AI Boom Real?",
        "author": "Jon Y",
        "publisher": "Asianometry",
        "category": "asianometry",
        "published_at": "2024-03",
    },
    "asianometry-ais-hardware-problem-2023": {
        "url": "https://www.asianometry.com/p/ais-hardware-problem",
        "title": "AI's Hardware Problem",
        "author": "Jon Y",
        "publisher": "Asianometry",
        "category": "asianometry",
        "published_at": "2023-04",
    },
    "asianometry-fpgas-ultimate-flex-2023": {
        "url": "https://www.asianometry.com/p/fpgas-making-the-ultimate-flex",
        "title": "FPGAs: The Ultimate Flex",
        "author": "Jon Y",
        "publisher": "Asianometry",
        "category": "asianometry",
        "published_at": "2023-06",
    },
    "asianometry-analog-chip-design-ai-2024": {
        "url": "https://www.asianometry.com/p/analog-chip-design-is-an-art-can",
        "title": "Analog Chip Design is an Art. Can AI Help?",
        "author": "Jon Y",
        "publisher": "Asianometry",
        "category": "asianometry",
        "published_at": "2024-02",
    },
    "asianometry-nn-meshes-of-light-2023": {
        "url": "https://www.asianometry.com/p/running-neural-networks-on-meshes",
        "title": "Running Neural Networks on Meshes of Light",
        "author": "Jon Y",
        "publisher": "Asianometry",
        "category": "asianometry",
        "published_at": "2023-06",
    },
}


def _fetch(url: str) -> bytes:
    referer = "/".join(url.split("/", 3)[:3]) + "/"
    cmd = [
        "curl",
        "-sL",
        "--compressed",
        "--max-time",
        "120",
        "--fail",
        "-A",
        BROWSER_HEADERS["User-Agent"],
    ]
    for h, v in BROWSER_HEADERS.items():
        if h in ("User-Agent", "Accept-Encoding"):
            continue
        cmd += ["-H", f"{h}: {v}"]
    cmd += ["-H", f"Referer: {referer}", url]
    res = subprocess.run(cmd, capture_output=True, check=False)
    if res.returncode != 0:
        raise RuntimeError(
            f"curl failed (exit {res.returncode}): "
            f"{res.stderr.decode(errors='replace').strip() or '<no stderr>'}"
        )
    return res.stdout


def _write_manifest(slug: str, meta: dict, page_path: Path) -> None:
    blob = page_path.read_bytes()
    sha = hashlib.sha256(blob).hexdigest()
    license_text = (
        "Subscriber-archive (free Weekly Articles only); quote with "
        "attribution + link, do not redistribute the body text."
        if meta["category"] == "stratechery"
        else "Public web; quote with attribution + link."
    )
    manifest = {
        "corpus": "essays",
        "doc_id": slug,
        "title": meta["title"],
        "author": meta.get("author"),
        "publisher": meta["publisher"],
        "category": meta["category"],
        "source_url": meta["url"],
        "fetched_at": date.today().isoformat(),
        "published_at": meta.get("published_at"),
        "license": license_text,
        "files": [
            {"path": "page.html", "sha256": sha, "bytes": len(blob)},
        ],
    }
    (page_path.parent / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    args = set(sys.argv[1:])  # optional slug filter for retries
    failures: list[str] = []
    for slug, meta in ESSAYS.items():
        if args and slug not in args:
            continue
        out_dir = RAW / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        page_path = out_dir / "page.html"
        try:
            blob = _fetch(meta["url"])
        except Exception as e:
            print(f"FAIL {slug}: {e}", file=sys.stderr)
            failures.append(slug)
            continue
        sha = hashlib.sha256(blob).hexdigest()
        if page_path.exists() and hashlib.sha256(page_path.read_bytes()).hexdigest() == sha:
            print(f"unchanged  {slug}  ({len(blob):>9,} B)")
        else:
            page_path.write_bytes(blob)
            print(f"wrote      {slug}  ({len(blob):>9,} B)")
        _write_manifest(slug, meta, page_path)
    if failures:
        print(f"\n{len(failures)} failed: {' '.join(failures)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
