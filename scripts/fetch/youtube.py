"""Download manual (and trusted-author auto) subtitles for the F3
YouTube whitelist per spec/SOURCES.md.

For each video in WHITELIST:
  1. Try `yt-dlp --write-sub --skip-download --sub-format vtt
     --sub-langs 'en.*'` to grab any uploader-provided English subs.
  2. If no manual subs and the channel is on TRUSTED_AUTOSUB_CHANNELS,
     fall back to `--write-auto-sub`.
  3. Skip videos that yield neither.
  4. Always write `info.json` (--write-info-json) for downstream
     processing and reproducibility.

Outputs (per video):
    data/raw/youtube/<video_id>/info.json
    data/raw/youtube/<video_id>/subs.<lang>.vtt
    data/raw/youtube/<video_id>/manifest.json

Re-run is idempotent: a video is skipped if its manifest already
records the .vtt file with a non-zero size.

CLI usage:
    uv run python scripts/fetch/youtube.py            # fetch all
    uv run python scripts/fetch/youtube.py <video_id> # fetch one
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

RAW = Path("data/raw/youtube")

# Channels for which we accept auto-captions when manual subs aren't
# published. Identified by the YouTube channel handle (without the @);
# matched case-insensitively against the info.json `channel` and
# `uploader_id` fields. See SOURCES.md F3 point 2.
#
# The first three are the original "trusted-author" allowlist (deep
# technical content, on-screen-verifiable). The Tier-1 expansion (No
# Priors, a16z, Sequoia, YC, Stanford eCorner / GSB / Online) was added
# at the user's direction to recover canonical AI talks that we'd
# otherwise miss — these channels ship auto-only at scale.
TRUSTED_AUTOSUB_CHANNELS = {
    # Tier 0 — original trusted-author allowlist
    "andrej karpathy",
    "3blue1brown",
    "dwarkesh patel",
    # Tier 1 — expansion (canonical AI talks/interviews)
    "no priors",
    "no priors podcast",
    "a16z",
    "andreessen horowitz",
    "sequoia capital",
    "sequoia",
    "y combinator",
    "ycombinator",
    "stanford ecorner",
    "stanford graduate school of business",
    "stanford gsb",
    "stanford online",
}

LICENSE_TEXT = (
    "YouTube ToS — educational use; transcript indexed for search and "
    "deep-link citation only."
)

# Whitelist of video IDs to ingest. Populated by the F3 curation agent;
# see /tmp/youtube_whitelist.py and the F3 section of spec/SOURCES.md.
WHITELIST: dict[str, dict] = {
    "aircAruvnKk": {
        "title": "But what is a neural network? | Deep learning chapter 1",
        "channel": "3Blue1Brown",
        "channel_id": "UCYO_jab_esuFRV4b17AJtAw",
        "published_at": "2017-10-05",
        "duration_seconds": 1120,
        "topic_tag": "explainer",
    },
    "IHZwWFHWa-w": {
        "title": "Gradient descent, how neural networks learn | Deep Learning Chapter 2",
        "channel": "3Blue1Brown",
        "channel_id": "UCYO_jab_esuFRV4b17AJtAw",
        "published_at": "2017-10-16",
        "duration_seconds": 1233,
        "topic_tag": "llm-mechanics",
    },
    "Ilg3gGewQ5U": {
        "title": "Backpropagation, intuitively | Deep Learning Chapter 3",
        "channel": "3Blue1Brown",
        "channel_id": "UCYO_jab_esuFRV4b17AJtAw",
        "published_at": "2017-11-03",
        "duration_seconds": 767,
        "topic_tag": "llm-mechanics",
    },
    "tIeHLnjs5U8": {
        "title": "Backpropagation calculus | Deep Learning Chapter 4",
        "channel": "3Blue1Brown",
        "channel_id": "UCYO_jab_esuFRV4b17AJtAw",
        "published_at": "2017-11-03",
        "duration_seconds": 617,
        "topic_tag": "llm-mechanics",
    },
    "wjZofJX0v4M": {
        "title": "Transformers, the tech behind LLMs | Deep Learning Chapter 5",
        "channel": "3Blue1Brown",
        "channel_id": "UCYO_jab_esuFRV4b17AJtAw",
        "published_at": "2024-04-01",
        "duration_seconds": 1634,
        "topic_tag": "llm-mechanics",
    },
    "eMlx5fFNoYc": {
        "title": "Attention in transformers, step-by-step | Deep Learning Chapter 6",
        "channel": "3Blue1Brown",
        "channel_id": "UCYO_jab_esuFRV4b17AJtAw",
        "published_at": "2024-04-07",
        "duration_seconds": 1569,
        "topic_tag": "llm-mechanics",
    },
    "9-Jl0dxWQs8": {
        "title": "How might LLMs store facts | Deep Learning Chapter 7",
        "channel": "3Blue1Brown",
        "channel_id": "UCYO_jab_esuFRV4b17AJtAw",
        "published_at": "2024-08-31",
        "duration_seconds": 1362,
        "topic_tag": "llm-mechanics",
    },
    "LPZh9BOjkQs": {
        "title": "Large Language Models explained briefly",
        "channel": "3Blue1Brown",
        "channel_id": "UCYO_jab_esuFRV4b17AJtAw",
        "published_at": "2024-11-20",
        "duration_seconds": 478,
        "topic_tag": "explainer",
    },
    "xmkSf5IS-zw": {
        "title": "How GPT-5, Claude, and Gemini are actually trained and served – Reiner Pope",
        "channel": "Dwarkesh Patel",
        "channel_id": "UCXl4i9dYBrFOabk0xGmbkRA",
        "published_at": "2026-04-29",
        "duration_seconds": 8020,
        "topic_tag": "llm-mechanics",
    },
    "Hrbq66XqtCo": {
        "title": "Jensen Huang – Will Nvidia’s moat persist?",
        "channel": "Dwarkesh Patel",
        "channel_id": "UCXl4i9dYBrFOabk0xGmbkRA",
        "published_at": "2026-04-15",
        "duration_seconds": 6192,
        "topic_tag": "frontier-lab-interview",
    },
    "mDG_Hx3BSUE": {
        "title": "Dylan Patel — The single biggest bottleneck to scaling AI compute",
        "channel": "Dwarkesh Patel",
        "channel_id": "UCXl4i9dYBrFOabk0xGmbkRA",
        "published_at": "2026-03-13",
        "duration_seconds": 9044,
        "topic_tag": "economics",
    },
    "n1E9IZfvGMA": {
        "title": "Dario Amodei — “We are near the end of the exponential”",
        "channel": "Dwarkesh Patel",
        "channel_id": "UCXl4i9dYBrFOabk0xGmbkRA",
        "published_at": "2026-02-13",
        "duration_seconds": 8540,
        "topic_tag": "frontier-lab-interview",
    },
    "BYXbuik3dgA": {
        "title": "Elon Musk – \"In 36 months, the cheapest place to put AI will be space”",
        "channel": "Dwarkesh Patel",
        "channel_id": "UCXl4i9dYBrFOabk0xGmbkRA",
        "published_at": "2026-02-05",
        "duration_seconds": 10185,
        "topic_tag": "frontier-lab-interview",
    },
    "aR20FWCCjAs": {
        "title": "Ilya Sutskever – We're moving from the age of scaling to the age of research",
        "channel": "Dwarkesh Patel",
        "channel_id": "UCXl4i9dYBrFOabk0xGmbkRA",
        "published_at": "2025-11-25",
        "duration_seconds": 5763,
        "topic_tag": "frontier-lab-interview",
    },
    "8-boBsWcr5A": {
        "title": "Satya Nadella – How Microsoft thinks about AGI",
        "channel": "Dwarkesh Patel",
        "channel_id": "UCXl4i9dYBrFOabk0xGmbkRA",
        "published_at": "2025-11-12",
        "duration_seconds": 5321,
        "topic_tag": "frontier-lab-interview",
    },
    "lXUZvyajciY": {
        "title": "Andrej Karpathy — “We’re summoning ghosts, not building animals”",
        "channel": "Dwarkesh Patel",
        "channel_id": "UCXl4i9dYBrFOabk0xGmbkRA",
        "published_at": "2025-10-17",
        "duration_seconds": 8768,
        "topic_tag": "frontier-lab-interview",
    },
    "21EYKqUsPfg": {
        "title": "Richard Sutton – Father of RL thinks LLMs are a dead end",
        "channel": "Dwarkesh Patel",
        "channel_id": "UCXl4i9dYBrFOabk0xGmbkRA",
        "published_at": "2025-09-26",
        "duration_seconds": 4029,
        "topic_tag": "ai-strategy",
    },
    "64lXQP6cs5M": {
        "title": "Is RL + LLMs enough for AGI? — Sholto Douglas & Trenton Bricken",
        "channel": "Dwarkesh Patel",
        "channel_id": "UCXl4i9dYBrFOabk0xGmbkRA",
        "published_at": "2025-05-22",
        "duration_seconds": 8641,
        "topic_tag": "ai-strategy",
    },
    "rYXeQbTuVl0": {
        "title": "Mark Zuckerberg — AI will write most Meta code in 18 months",
        "channel": "Dwarkesh Patel",
        "channel_id": "UCXl4i9dYBrFOabk0xGmbkRA",
        "published_at": "2025-04-29",
        "duration_seconds": 4549,
        "topic_tag": "frontier-lab-interview",
    },
    "WLBsUarvWTw": {
        "title": "AGI is still 30 years away — Ege Erdil & Tamay Besiroglu",
        "channel": "Dwarkesh Patel",
        "channel_id": "UCXl4i9dYBrFOabk0xGmbkRA",
        "published_at": "2025-04-17",
        "duration_seconds": 11343,
        "topic_tag": "ai-strategy",
    },
    "htOvH12T7mU": {
        "title": "AI 2027: month-by-month model of intelligence explosion — Scott Alexander & Daniel Kokotajlo",
        "channel": "Dwarkesh Patel",
        "channel_id": "UCXl4i9dYBrFOabk0xGmbkRA",
        "published_at": "2025-04-03",
        "duration_seconds": 11116,
        "topic_tag": "ai-strategy",
    },
    "3cDHx2_QbPE": {
        "title": "China is killing the US on energy. Does that mean they’ll win AGI? — Casey Handmer",
        "channel": "Dwarkesh Patel",
        "channel_id": "UCXl4i9dYBrFOabk0xGmbkRA",
        "published_at": "2025-08-15",
        "duration_seconds": 4102,
        "topic_tag": "economics",
    },
    "nyvmYnz6EAg": {
        "title": "Why I don’t think AGI is right around the corner",
        "channel": "Dwarkesh Patel",
        "channel_id": "UCXl4i9dYBrFOabk0xGmbkRA",
        "published_at": "2025-08-01",
        "duration_seconds": 1034,
        "topic_tag": "ai-strategy",
    },
    "vif8NQcjVf0": {
        "title": "Jensen Huang: NVIDIA - The $4 Trillion Company & the AI Revolution | Lex Fridman Podcast #494",
        "channel": "Lex Fridman",
        "channel_id": "UCSHZKyawb77ixDdsGog4iWA",
        "published_at": "2026-03-23",
        "duration_seconds": 8758,
        "topic_tag": "frontier-lab-interview",
    },
    "EV7WhVT270Q": {
        "title": "State of AI in 2026: LLMs, Coding, Scaling Laws, China, Agents, GPUs, AGI | Lex Fridman Podcast #490",
        "channel": "Lex Fridman",
        "channel_id": "UCSHZKyawb77ixDdsGog4iWA",
        "published_at": "2026-01-31",
        "duration_seconds": 15913,
        "topic_tag": "ai-strategy",
    },
    "-HzgcbRXUK8": {
        "title": "Demis Hassabis: Future of AI, Simulating Reality, Physics and Video Games | Lex Fridman Podcast #475",
        "channel": "Lex Fridman",
        "channel_id": "UCSHZKyawb77ixDdsGog4iWA",
        "published_at": "2025-07-23",
        "duration_seconds": 8894,
        "topic_tag": "frontier-lab-interview",
    },
    "9V6tWC4CdFQ": {
        "title": "Sundar Pichai: CEO of Google and Alphabet | Lex Fridman Podcast #471",
        "channel": "Lex Fridman",
        "channel_id": "UCSHZKyawb77ixDdsGog4iWA",
        "published_at": "2025-06-05",
        "duration_seconds": 7924,
        "topic_tag": "frontier-lab-interview",
    },
    "HUkBz-cdB-k": {
        "title": "Terence Tao: Hardest Problems in Mathematics, Physics & the Future of AI | Lex Fridman Podcast #472",
        "channel": "Lex Fridman",
        "channel_id": "UCSHZKyawb77ixDdsGog4iWA",
        "published_at": "2025-06-14",
        "duration_seconds": 11674,
        "topic_tag": "explainer",
    },
    "e-gwvmhyU7A": {
        "title": "Aravind Srinivas: Perplexity CEO on Future of AI, Search & the Internet | Lex Fridman Podcast #434",
        "channel": "Lex Fridman",
        "channel_id": "UCSHZKyawb77ixDdsGog4iWA",
        "published_at": "2024-06-19",
        "duration_seconds": 10936,
        "topic_tag": "frontier-lab-interview",
    },
    "_1f-o0nqpEI": {
        "title": "DeepSeek, China, OpenAI, NVIDIA, xAI, TSMC, Stargate, and AI Megaclusters | Lex Fridman Podcast #459",
        "channel": "Lex Fridman",
        "channel_id": "UCSHZKyawb77ixDdsGog4iWA",
        "published_at": "2025-02-03",
        "duration_seconds": 18378,
        "topic_tag": "ai-strategy",
    },
    "ugvHCXCOmm4": {
        "title": "Dario Amodei: Anthropic CEO on Claude, AGI & the Future of AI & Humanity | Lex Fridman Podcast #452",
        "channel": "Lex Fridman",
        "channel_id": "UCSHZKyawb77ixDdsGog4iWA",
        "published_at": "2024-11-11",
        "duration_seconds": 18900,
        "topic_tag": "frontier-lab-interview",
    },
    "oFfVt3S51T4": {
        "title": "Cursor Team: Future of Programming with AI | Lex Fridman Podcast #447",
        "channel": "Lex Fridman",
        "channel_id": "UCSHZKyawb77ixDdsGog4iWA",
        "published_at": "2024-10-06",
        "duration_seconds": 8944,
        "topic_tag": "frontier-lab-interview",
    },
    "Kbk9BiPhm7o": {
        "title": "Elon Musk: Neuralink and the Future of Humanity | Lex Fridman Podcast #438",
        "channel": "Lex Fridman",
        "channel_id": "UCSHZKyawb77ixDdsGog4iWA",
        "published_at": "2024-08-02",
        "duration_seconds": 31054,
        "topic_tag": "frontier-lab-interview",
    },
    "jvqFAi7vkBc": {
        "title": "Sam Altman: OpenAI, GPT-5, Sora, Board Saga, Elon Musk, Ilya, Power & AGI | Lex Fridman Podcast #419",
        "channel": "Lex Fridman",
        "channel_id": "UCSHZKyawb77ixDdsGog4iWA",
        "published_at": "2024-03-18",
        "duration_seconds": 6910,
        "topic_tag": "frontier-lab-interview",
    },
    "5t1vTLU7s40": {
        "title": "Yann Lecun: Meta AI, Open Source, Limits of LLMs, AGI & the Future of AI | Lex Fridman Podcast #416",
        "channel": "Lex Fridman",
        "channel_id": "UCSHZKyawb77ixDdsGog4iWA",
        "published_at": "2024-03-07",
        "duration_seconds": 10037,
        "topic_tag": "frontier-lab-interview",
    },
    "JN3KPFbWCy8": {
        "title": "Elon Musk: War, AI, Aliens, Politics, Physics, Video Games, and Humanity | Lex Fridman Podcast #400",
        "channel": "Lex Fridman",
        "channel_id": "UCSHZKyawb77ixDdsGog4iWA",
        "published_at": "2023-11-09",
        "duration_seconds": 8206,
        "topic_tag": "frontier-lab-interview",
    },
    "DcWqzZ3I2cY": {
        "title": "Jeff Bezos: Amazon and Blue Origin | Lex Fridman Podcast #405",
        "channel": "Lex Fridman",
        "channel_id": "UCSHZKyawb77ixDdsGog4iWA",
        "published_at": "2023-12-14",
        "duration_seconds": 7892,
        "topic_tag": "frontier-lab-interview",
    },
    # ---------------- Andrej Karpathy (auto-sub allowlist) ----------------
    # Karpathy's channel ships auto-captions only; included via the
    # trusted-author allowlist (per SOURCES.md F3 point 2). makemore
    # series + stable-diffusion experiments intentionally skipped.
    "zjkBMFhNj_g": {
        "title": "[1hr Talk] Intro to Large Language Models",
        "channel": "Andrej Karpathy",
        "channel_id": "UCXUPKJO5MZQN11PqgIvyuvQ",
        "published_at": "2023-11-22",
        "duration_seconds": 3588,
        "topic_tag": "explainer",
    },
    "EWvNQjAaOHw": {
        "title": "How I use LLMs",
        "channel": "Andrej Karpathy",
        "channel_id": "UCXUPKJO5MZQN11PqgIvyuvQ",
        "published_at": "2025-02-27",
        "duration_seconds": 7872,
        "topic_tag": "explainer",
    },
    "7xTGNNLPyMI": {
        "title": "Deep Dive into LLMs like ChatGPT",
        "channel": "Andrej Karpathy",
        "channel_id": "UCXUPKJO5MZQN11PqgIvyuvQ",
        "published_at": "2025-02-05",
        "duration_seconds": 12684,
        "topic_tag": "llm-mechanics",
    },
    "kCc8FmEb1nY": {
        "title": "Let's build GPT: from scratch, in code, spelled out.",
        "channel": "Andrej Karpathy",
        "channel_id": "UCXUPKJO5MZQN11PqgIvyuvQ",
        "published_at": "2023-01-17",
        "duration_seconds": 6980,
        "topic_tag": "llm-mechanics",
    },
    "l8pRSuU81PU": {
        "title": "Let's reproduce GPT-2 (124M)",
        "channel": "Andrej Karpathy",
        "channel_id": "UCXUPKJO5MZQN11PqgIvyuvQ",
        "published_at": "2024-06-09",
        "duration_seconds": 14486,
        "topic_tag": "llm-mechanics",
    },
    "zduSFxRajkE": {
        "title": "Let's build the GPT Tokenizer",
        "channel": "Andrej Karpathy",
        "channel_id": "UCXUPKJO5MZQN11PqgIvyuvQ",
        "published_at": "2024-02-20",
        "duration_seconds": 8015,
        "topic_tag": "llm-mechanics",
    },
    "VMj-3S1tku0": {
        "title": "The spelled-out intro to neural networks and backpropagation: building micrograd",
        "channel": "Andrej Karpathy",
        "channel_id": "UCXUPKJO5MZQN11PqgIvyuvQ",
        "published_at": "2022-08-16",
        "duration_seconds": 8752,
        "topic_tag": "llm-mechanics",
    },
    # ============= TIER 1 EXPANSION (auto-sub allowlist widened) =============
    # No Priors / a16z / Sequoia / YC / Stanford eCorner+GSB+Online — added
    # at user direction with manual-sub requirement relaxed for these channels.
    # ---------------- No Priors ----------------
        "hM_h0UA7upI": {
            "title": "No Priors Ep. 80 | With Andrej Karpathy from OpenAI and Tesla",
            "channel": "No Priors",
            "channel_id": "UCSI7h9hydQ40K5MJHnCrQvw",
            "published_at": "2024-09-05",
            "duration_seconds": 2656,
            "topic_tag": "frontier-lab-interview",
        },
        "kwSVtQ7dziU": {
            "title": "Skill Issue: Andrej Karpathy on Code Agents, AutoResearch, and the Loopy Era of AI",
            "channel": "No Priors",
            "channel_id": "UCSI7h9hydQ40K5MJHnCrQvw",
            "published_at": "2026-03-20",
            "duration_seconds": 3991,
            "topic_tag": "frontier-lab-interview",
        },
        "k-xtmISBCNE": {
            "title": "NVIDIA’s Jensen Huang on Reasoning Models, Robotics, and Refuting the “AI Bubble” Narrative",
            "channel": "No Priors",
            "channel_id": "UCSI7h9hydQ40K5MJHnCrQvw",
            "published_at": "2026-01-08",
            "duration_seconds": 4581,
            "topic_tag": "frontier-lab-interview",
        },
        "hw7EnjC68Fw": {
            "title": "No Priors Ep. 89 | With NVIDIA CEO Jensen Huang",
            "channel": "No Priors",
            "channel_id": "UCSI7h9hydQ40K5MJHnCrQvw",
            "published_at": "2024-11-07",
            "duration_seconds": 2209,
            "topic_tag": "frontier-lab-interview",
        },
        "SYisFbhR7xs": {
            "title": "No Priors Ep. 128 | With Andrew Ng, Managing General Partner at AI Fund",
            "channel": "No Priors",
            "channel_id": "UCSI7h9hydQ40K5MJHnCrQvw",
            "published_at": "2025-08-21",
            "duration_seconds": 2532,
            "topic_tag": "ai-strategy",
        },
        "vGhlJqnECd0": {
            "title": "No Priors Ep. 127 | With SemiAnalysis Founder and CEO Dylan Patel",
            "channel": "No Priors",
            "channel_id": "UCSI7h9hydQ40K5MJHnCrQvw",
            "published_at": "2025-08-14",
            "duration_seconds": 2838,
            "topic_tag": "economics",
        },
        "C6Zm5S7JHMw": {
            "title": "No Priors Ep. 117 | With Co-Director of Stanford's HAI & Founder of World Labs Dr. Fei-Fei Li",
            "channel": "No Priors",
            "channel_id": "UCSI7h9hydQ40K5MJHnCrQvw",
            "published_at": "2025-06-05",
            "duration_seconds": 2147,
            "topic_tag": "frontier-lab-interview",
        },
        "aStf54Vxy24": {
            "title": "No Priors Ep. 118 | With Anthropic Co-Founder Ben Mann",
            "channel": "No Priors",
            "channel_id": "UCSI7h9hydQ40K5MJHnCrQvw",
            "published_at": "2025-06-12",
            "duration_seconds": 2485,
            "topic_tag": "frontier-lab-interview",
        },
        "2XRpTZpHjfc": {
            "title": "No Priors Ep. 91 | With Cohere Co-Founder and CEO Aidan Gomez",
            "channel": "No Priors",
            "channel_id": "UCSI7h9hydQ40K5MJHnCrQvw",
            "published_at": "2024-11-21",
            "duration_seconds": 2656,
            "topic_tag": "frontier-lab-interview",
        },
        "uX6ceY1vcUg": {
            "title": "No Priors Ep. 90 | With Google's DeepMind's AlphaProof Team",
            "channel": "No Priors",
            "channel_id": "UCSI7h9hydQ40K5MJHnCrQvw",
            "published_at": "2024-11-14",
            "duration_seconds": 2362,
            "topic_tag": "frontier-lab-interview",
        },
        "riWB5nPNZEM": {
            "title": "No Priors Ep. 82 | With CEO of Sierra Bret Taylor",
            "channel": "No Priors",
            "channel_id": "UCSI7h9hydQ40K5MJHnCrQvw",
            "published_at": "2024-09-19",
            "duration_seconds": 2911,
            "topic_tag": "ai-strategy",
        },
        # ---------------- a16z ----------------
        "xRh2sVcNXQ8": {
            "title": "Marc Andreessen's 2026 Outlook: AI Timelines, US vs. China, and The Price of AI",
            "channel": "a16z",
            "channel_id": "UC9cn0TuPq4dnbTY-CBsm8XA",
            "published_at": "2026-01-07",
            "duration_seconds": 4878,
            "topic_tag": "ai-strategy",
        },
        "JfE1Wun9xkk": {
            "title": "Sam Altman on Sora, Energy, and Building an AI Empire",
            "channel": "a16z",
            "channel_id": "UC9cn0TuPq4dnbTY-CBsm8XA",
            "published_at": "2025-10-08",
            "duration_seconds": 2966,
            "topic_tag": "frontier-lab-interview",
        },
        "g-WeCOUYBrk": {
            "title": "Marc Andreessen & Amjad Masad on “Good Enough” AI, AGI, and the End of Coding",
            "channel": "a16z",
            "channel_id": "UC9cn0TuPq4dnbTY-CBsm8XA",
            "published_at": "2025-10-23",
            "duration_seconds": 4316,
            "topic_tag": "ai-strategy",
        },
        "brjL6iyoEhI": {
            "title": "Reid Hoffman on AI, Consciousness, and the Future of Labor",
            "channel": "a16z",
            "channel_id": "UC9cn0TuPq4dnbTY-CBsm8XA",
            "published_at": "2025-10-20",
            "duration_seconds": 3182,
            "topic_tag": "ai-strategy",
        },
        "r8_2CSpcmls": {
            "title": "Ben Horowitz on Investing in AI: AI Bubbles, Economic Impact, and VC Acceleration",
            "channel": "a16z",
            "channel_id": "UC9cn0TuPq4dnbTY-CBsm8XA",
            "published_at": "2026-01-13",
            "duration_seconds": 2049,
            "topic_tag": "economics",
        },
        "vvlE8-MzxyA": {
            "title": "Dylan Patel on the AI Chip Race - NVIDIA, Intel & the US Government vs. China",
            "channel": "a16z",
            "channel_id": "UC9cn0TuPq4dnbTY-CBsm8XA",
            "published_at": "2025-09-22",
            "duration_seconds": 5938,
            "topic_tag": "economics",
        },
        "Uho2GupZSgU": {
            "title": "Sacks, Andreessen & Horowitz: How America Wins the AI Race Against China",
            "channel": "a16z",
            "channel_id": "UC9cn0TuPq4dnbTY-CBsm8XA",
            "published_at": "2025-11-03",
            "duration_seconds": 4649,
            "topic_tag": "ai-strategy",
        },
        # ---------------- Sequoia Capital ----------------
        "96jN2OCOfLs": {
            "title": "Andrej Karpathy: From Vibe Coding to Agentic Engineering",
            "channel": "Sequoia Capital",
            "channel_id": "UCWrF0oN6unbXrWsTN7RctTw",
            "published_at": "2026-04-29",
            "duration_seconds": 1789,
            "topic_tag": "frontier-lab-interview",
        },
        "AFpeWo1GTeg": {
            "title": "Demis Hassabis: We're Three Quarters of the Way to AGI",
            "channel": "Sequoia Capital",
            "channel_id": "UCWrF0oN6unbXrWsTN7RctTw",
            "published_at": "2026-04-29",
            "duration_seconds": 1611,
            "topic_tag": "frontier-lab-interview",
        },
        "bBS93A0BeNI": {
            "title": "OpenAI's Greg Brockman: Why Human Attention Is the New BottleneckOpenAI's",
            "channel": "Sequoia Capital",
            "channel_id": "UCWrF0oN6unbXrWsTN7RctTw",
            "published_at": "2026-04-30",
            "duration_seconds": 1706,
            "topic_tag": "frontier-lab-interview",
        },
        "LRo33rnv6rQ": {
            "title": "This is AGI: Sequoia AI Ascent 2026 Keynote",
            "channel": "Sequoia Capital",
            "channel_id": "UCWrF0oN6unbXrWsTN7RctTw",
            "published_at": "2026-04-30",
            "duration_seconds": 1947,
            "topic_tag": "ai-strategy",
        },
        "v9JBMnxuPX8": {
            "title": "AI's Trillion-Dollar Opportunity: Sequoia AI Ascent 2025 Keynote",
            "channel": "Sequoia Capital",
            "channel_id": "UCWrF0oN6unbXrWsTN7RctTw",
            "published_at": "2025-05-07",
            "duration_seconds": 1715,
            "topic_tag": "ai-strategy",
        },
        "ctcMA6chfDY": {
            "title": "OpenAI’s Sam Altman on Building the ‘Core AI Subscription’ for Your Life",
            "channel": "Sequoia Capital",
            "channel_id": "UCWrF0oN6unbXrWsTN7RctTw",
            "published_at": "2025-05-12",
            "duration_seconds": 1919,
            "topic_tag": "frontier-lab-interview",
        },
        "dq8MhTFCs80": {
            "title": "Google's Jeff Dean on the Coming Transformations in AI",
            "channel": "Sequoia Capital",
            "channel_id": "UCWrF0oN6unbXrWsTN7RctTw",
            "published_at": "2025-05-12",
            "duration_seconds": 1831,
            "topic_tag": "frontier-lab-interview",
        },
        "Js1gU6L1Zi8": {
            "title": "Anthropic CPO Mike Krieger: Building AI Products From the Bottom Up",
            "channel": "Sequoia Capital",
            "channel_id": "UCWrF0oN6unbXrWsTN7RctTw",
            "published_at": "2025-05-09",
            "duration_seconds": 1438,
            "topic_tag": "frontier-lab-interview",
        },
        "z_-nLK4Ps1Q": {
            "title": "The Breakthroughs Needed for AGI Have Already Been Made: OpenAI Former Research Head Bob McGrew",
            "channel": "Sequoia Capital",
            "channel_id": "UCWrF0oN6unbXrWsTN7RctTw",
            "published_at": "2025-06-17",
            "duration_seconds": 2931,
            "topic_tag": "ai-strategy",
        },
        # ---------------- Y Combinator ----------------
        "xXCBz_8hM9w": {
            "title": "How To Build The Future: Sam Altman",
            "channel": "Y Combinator",
            "channel_id": "UCcefcZRL2oaA_uBNeo5UOWg",
            "published_at": "2024-11-08",
            "duration_seconds": 2812,
            "topic_tag": "frontier-lab-interview",
        },
        "LCEmiRjPEtQ": {
            "title": "Andrej Karpathy: Software Is Changing (Again)",
            "channel": "Y Combinator",
            "channel_id": "UCcefcZRL2oaA_uBNeo5UOWg",
            "published_at": "2025-06-19",
            "duration_seconds": 2371,
            "topic_tag": "ai-strategy",
        },
        "AUUZuzVHKdo": {
            "title": "Satya Nadella: Microsoft's AI Bets, Hyperscaling, Quantum Computing Breakthroughs",
            "channel": "Y Combinator",
            "channel_id": "UCcefcZRL2oaA_uBNeo5UOWg",
            "published_at": "2025-06-25",
            "duration_seconds": 2430,
            "topic_tag": "frontier-lab-interview",
        },
        "cFIlta1GkiE": {
            "title": "Elon Musk: Digital Superintelligence, Multiplanetary Life, How to Be Useful",
            "channel": "Y Combinator",
            "channel_id": "UCcefcZRL2oaA_uBNeo5UOWg",
            "published_at": "2025-06-19",
            "duration_seconds": 2981,
            "topic_tag": "frontier-lab-interview",
        },
        "SP7Ua8FKZN4": {
            "title": "How To Build The Future: Aravind Srinivas",
            "channel": "Y Combinator",
            "channel_id": "UCcefcZRL2oaA_uBNeo5UOWg",
            "published_at": "2025-02-21",
            "duration_seconds": 2079,
            "topic_tag": "frontier-lab-interview",
        },
        "JNyuX1zoOgU": {
            "title": "Demis Hassabis: Agents, AGI & The Next Big Scientific Breakthrough",
            "channel": "Y Combinator",
            "channel_id": "UCcefcZRL2oaA_uBNeo5UOWg",
            "published_at": "2026-04-29",
            "duration_seconds": 2457,
            "topic_tag": "frontier-lab-interview",
        },
        "p8Jx4qvDoSo": {
            "title": "Scaling and the Road to Human-Level AI | Anthropic Co-founder Jared Kaplan",
            "channel": "Y Combinator",
            "channel_id": "UCcefcZRL2oaA_uBNeo5UOWg",
            "published_at": "2025-07-29",
            "duration_seconds": 2448,
            "topic_tag": "frontier-lab-interview",
        },
        # ---------------- Stanford eCorner ----------------
        "GLKoDkbS1Cg": {
            "title": "The Possibilities of AI [Entire Talk] - Sam Altman (OpenAI)",
            "channel": "Stanford eCorner",
            "channel_id": "UCctkeBNtFIOn7Yl_9TTj_4w",
            "published_at": "2024-05-01",
            "duration_seconds": 2748,
            "topic_tag": "frontier-lab-interview",
        },
        "NUNyK6P6q8s": {
            "title": "Brendan Foody (Mercor) - Agentic Data and the Future of AI [Entire Talk]",
            "channel": "Stanford eCorner",
            "channel_id": "UCctkeBNtFIOn7Yl_9TTj_4w",
            "published_at": "2026-04-15",
            "duration_seconds": 2830,
            "topic_tag": "ai-strategy",
        },
        # ---------------- Stanford Graduate School of Business ----------------
        "21EiKfQYZXc": {
            "title": "Andrew Ng: Artificial Intelligence is the New Electricity",
            "channel": "Stanford Graduate School of Business",
            "channel_id": "UCGwuxdEeCf0TIA2RbPOj-8g",
            "published_at": "2017-02-02",
            "duration_seconds": 5264,
            "topic_tag": "ai-strategy",
        },
        "tofBqR5N1RI": {
            "title": "U.S. Leadership in AI with Jensen Huang, Founder and CEO of NVIDIA, and Congressman Ro Khanna",
            "channel": "Stanford Graduate School of Business",
            "channel_id": "UCGwuxdEeCf0TIA2RbPOj-8g",
            "published_at": "2026-04-16",
            "duration_seconds": 3518,
            "topic_tag": "ai-strategy",
        },
        "3sYBe7yEJ3U": {
            "title": "AI in the Enterprise: What Works, What Doesn’t, and What’s Next",
            "channel": "Stanford Graduate School of Business",
            "channel_id": "UCGwuxdEeCf0TIA2RbPOj-8g",
            "published_at": "2025-02-21",
            "duration_seconds": 3302,
            "topic_tag": "ai-strategy",
        },
        "CcQAj5spD1A": {
            "title": "“Artificial Intelligence for Social Good,” with Professor Susan Athey",
            "channel": "Stanford Graduate School of Business",
            "channel_id": "UCGwuxdEeCf0TIA2RbPOj-8g",
            "published_at": "2021-10-21",
            "duration_seconds": 3481,
            "topic_tag": "ai-strategy",
        },
        "sOeNWib_nvo": {
            "title": "S4E3 Grit & Growth | Co-Intelligence; An AI Masterclass with Ethan Mollick",
            "channel": "Stanford Graduate School of Business",
            "channel_id": "UCGwuxdEeCf0TIA2RbPOj-8g",
            "published_at": "2024-06-21",
            "duration_seconds": 1987,
            "topic_tag": "ai-strategy",
        },
        "lNsl76AD1kE": {
            "title": "“Economics & AI” Fireside Chat: Professor Susan Athey and Dean Jon Levin",
            "channel": "Stanford Graduate School of Business",
            "channel_id": "UCGwuxdEeCf0TIA2RbPOj-8g",
            "published_at": "2024-05-16",
            "duration_seconds": 3078,
            "topic_tag": "economics",
        },
        "SyFAcDx8Hi8": {
            "title": "AI@GSB: A conversation with Derek Thompson, Journalist, The Atlantic",
            "channel": "Stanford Graduate School of Business",
            "channel_id": "UCGwuxdEeCf0TIA2RbPOj-8g",
            "published_at": "2026-03-26",
            "duration_seconds": 3589,
            "topic_tag": "ai-strategy",
        },
        # ---------------- Stanford Online ----------------
        "5UJ0uWqO1Ho": {
            "title": "Stanford Webinar - Human-Centered AI: Designing Systems People Trust",
            "channel": "Stanford Online",
            "channel_id": "UCBa5G_ESCn8Yd4vw5U-gIcg",
            "published_at": "2026-02-02",
            "duration_seconds": 3354,
        "topic_tag": "ai-strategy",
    },
}


def _yt_dlp(args: list[str], cwd: Path) -> tuple[int, str, str]:
    # Use the project-managed module so `uv run collect-all` works from a
    # clean checkout without requiring a separate global `yt-dlp` install.
    cmd = [sys.executable, "-m", "yt_dlp", *args]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return res.returncode, res.stdout, res.stderr


def _existing_vtt(out_dir: Path) -> Path | None:
    vtts = sorted(out_dir.glob("*.vtt"))
    return vtts[0] if vtts else None


def _existing_info(out_dir: Path) -> Path | None:
    # Match both yt-dlp's raw `<id>.info.json` and the post-rename `info.json`.
    candidates = [out_dir / "info.json", *sorted(out_dir.glob("*.info.json"))]
    for p in candidates:
        if p.exists():
            return p
    return None


def _fetch_one(video_id: str, meta: dict) -> tuple[str, dict]:
    """Returns (status, sidecar_metadata) where status is one of:
        'wrote'      — fetched fresh
        'unchanged'  — already on disk
        'no-subs'    — neither manual nor allowlisted auto subs available
        'fail'       — yt-dlp errored

    sidecar_metadata is whatever we should record in the manifest.
    """
    out_dir = RAW / video_id
    out_dir.mkdir(parents=True, exist_ok=True)
    url = f"https://www.youtube.com/watch?v={video_id}"

    # Idempotency: manifest.json is the canonical "fully ingested" signal.
    # info.json is gitignored (~600 KB of ephemeral signed URLs) so it may
    # be missing on a fresh checkout — manifest carries the durable fields.
    if (out_dir / "manifest.json").exists() and _existing_vtt(out_dir):
        return "unchanged", {}

    common = [
        "--skip-download",
        "--write-info-json",
        "--no-warnings",
        "--no-progress",
        "--sub-format", "vtt",
        "--sub-langs", "en.*,en",
        "-o", "%(id)s.%(ext)s",
        url,
    ]

    # First attempt: manual subs only.
    rc, _, err = _yt_dlp(["--write-sub", *common], out_dir)
    subs_kind = "manual"
    vtt = _existing_vtt(out_dir)

    if vtt is None:
        # Allowlist check: only retry with auto-captions for trusted channels.
        info_path = _existing_info(out_dir)
        info = json.loads(info_path.read_text()) if info_path else {}
        chan = (info.get("channel") or "").strip().lower()
        uploader = (info.get("uploader_id") or "").strip().lower().lstrip("@")
        meta_chan = (meta.get("channel") or "").strip().lower()
        is_trusted = (
            chan in TRUSTED_AUTOSUB_CHANNELS
            or uploader in TRUSTED_AUTOSUB_CHANNELS
            or meta_chan in TRUSTED_AUTOSUB_CHANNELS
        )
        if is_trusted:
            rc2, _, err2 = _yt_dlp(["--write-auto-sub", *common], out_dir)
            vtt = _existing_vtt(out_dir)
            subs_kind = "auto"
            if vtt is None:
                return "no-subs", {}
        else:
            return "no-subs", {}
    if vtt is None:
        return "fail", {"error": err.strip()[:500]}

    # Rename to a stable filename: subs.<lang>.vtt. yt-dlp writes
    # <id>.<lang>.vtt; pick whichever fresh download we got. If
    # _existing_vtt returned an already-renamed `subs.<lang>.vtt`
    # (because a previous run left one), there's nothing to rename
    # but we still want to scrub any leftover unrenamed siblings.
    if vtt.name.startswith("subs."):
        # Keep the existing renamed file; just record its lang.
        lang = vtt.name.split(".")[1] if "." in vtt.name else "en"
        target = vtt
    else:
        parts = vtt.name.split(".")
        lang = parts[-2] if len(parts) >= 3 else "en"
        target = out_dir / f"subs.{lang}.vtt"
        if vtt.name != target.name:
            if target.exists():
                target.unlink()
            shutil.move(str(vtt), str(target))
    # Clean up any other unrenamed <id>.*.vtt files that older
    # broken runs left behind, plus stale subs.*.vtt for other langs.
    for stale in out_dir.glob("*.vtt"):
        if stale != target and not stale.name.startswith("subs."):
            stale.unlink()

    # Pull info.json into a stable name too.
    info_path = _existing_info(out_dir)
    if info_path is None:
        return "fail", {"error": "no info.json after fetch"}
    info = json.loads(info_path.read_text())
    if info_path.name != "info.json":
        target_info = out_dir / "info.json"
        if target_info.exists():
            target_info.unlink()
        shutil.move(str(info_path), str(target_info))
    for stale_info in out_dir.glob("*.info.json"):
        stale_info.unlink()

    return "wrote", {
        "subs_kind": subs_kind,
        "subs_lang": lang,
        "info": info,
        "vtt_path": target,
    }


def _write_manifest(video_id: str, meta: dict, sidecar: dict) -> None:
    out_dir = RAW / video_id
    info = sidecar["info"]
    vtt_path: Path = sidecar["vtt_path"]
    blob = vtt_path.read_bytes()
    info_blob = (out_dir / "info.json").read_bytes()
    files = [
        {
            "path": vtt_path.name,
            "sha256": hashlib.sha256(blob).hexdigest(),
            "bytes": len(blob),
        },
        {
            "path": "info.json",
            "sha256": hashlib.sha256(info_blob).hexdigest(),
            "bytes": len(info_blob),
        },
    ]
    upload_date = info.get("upload_date") or ""  # YYYYMMDD
    if len(upload_date) == 8:
        published_at = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
    else:
        published_at = meta.get("published_at")
    manifest = {
        "corpus": "youtube",
        "doc_id": video_id,
        "title": info.get("title") or meta.get("title"),
        "channel": info.get("channel") or meta.get("channel"),
        "channel_id": info.get("channel_id") or meta.get("channel_id"),
        "source_url": f"https://youtu.be/{video_id}",
        "fetched_at": date.today().isoformat(),
        "published_at": published_at,
        "duration_seconds": info.get("duration") or meta.get("duration_seconds"),
        "subs_kind": sidecar["subs_kind"],
        "subs_lang": sidecar["subs_lang"],
        "topic_tag": meta.get("topic_tag"),
        "license": LICENSE_TEXT,
        "files": files,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )


def main() -> None:
    if not WHITELIST:
        print(
            "WHITELIST is empty. Populate the dict at the top of this file "
            "from the F3 curation agent's output (/tmp/youtube_whitelist.py).",
            file=sys.stderr,
        )
        sys.exit(2)
    RAW.mkdir(parents=True, exist_ok=True)
    args = set(sys.argv[1:])
    no_subs: list[str] = []
    failures: list[tuple[str, str]] = []
    for video_id, meta in WHITELIST.items():
        if args and video_id not in args:
            continue
        status, sidecar = _fetch_one(video_id, meta)
        title = (meta.get("title") or "")[:60]
        if status == "unchanged":
            print(f"unchanged  {video_id}  {title}")
            continue
        if status == "no-subs":
            print(f"NO-SUBS    {video_id}  {title}")
            no_subs.append(video_id)
            continue
        if status == "fail":
            print(f"FAIL       {video_id}  {sidecar.get('error', '')}", file=sys.stderr)
            failures.append((video_id, sidecar.get("error", "")))
            continue
        _write_manifest(video_id, meta, sidecar)
        kind = sidecar["subs_kind"]
        lang = sidecar["subs_lang"]
        print(f"wrote      {video_id}  [{kind}/{lang}]  {title}")
    if no_subs:
        print(
            f"\n{len(no_subs)} video(s) had no usable subs: {' '.join(no_subs)}",
            file=sys.stderr,
        )
    if failures:
        print(f"\n{len(failures)} fetch failure(s):", file=sys.stderr)
        for vid, err in failures:
            print(f"  {vid}: {err[:200]}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
