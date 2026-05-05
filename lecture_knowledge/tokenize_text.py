"""Shared tokenizer for BM25 indexing and BM25 query encoding.

Lowercase + simple word split (a-z0-9, length >= 2). No stemming / no
stopword removal — the dense side compensates, and stopwords actually
help on short utility queries like "what is RAG".
"""

from __future__ import annotations

import re

_WORD = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return [t for t in _WORD.findall(text.lower()) if len(t) >= 2]
