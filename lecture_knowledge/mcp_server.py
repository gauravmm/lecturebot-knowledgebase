"""MCP server exposing the corpus retriever over HTTP.

Wraps `lecture_knowledge.retrieve.search` and `fetch_doc` as two MCP
tools and serves them on the Streamable HTTP transport — that's the
modern HTTP transport for MCP, supported by any non-stdio MCP client
(Claude Desktop via http-bridge, custom backends via the official
SDK, IDE plugins, etc.).

Run via `uv run knowledge-mcp` (default: 127.0.0.1:8765). Override
host/port with --host / --port. Endpoint is `http://host:port/mcp`.

Decoupled from the chat layer on purpose — the same server can back
the lecture Telegram bot, an experimental agent, an MCP-aware IDE,
or anything else without each consumer having to import the package
in-process.
"""

from __future__ import annotations

import argparse
from typing import Any

from mcp.server.fastmcp import FastMCP

from lecture_knowledge import retrieve

mcp = FastMCP("lecture-knowledge")


@mcp.tool()
def search(
    query: str,
    corpus: str | list[str] | None = None,
    k: int = 6,
) -> list[dict[str, Any]]:
    """Hybrid BM25 + dense retrieval over the lecture corpus.

    Args:
        query: Natural-language query.
        corpus: Optional corpus name or list of names to scope to.
            Available: lecturer/lectures, edgar, earnings, letters,
            consulting, essays, vendors, ai_index, youtube, regulation,
            funding, epoch_models, owid, memes.
        k: Number of results to return (default 6).

    Returns: List of hits, each with id, corpus, title, source URL,
        section_path, citation_url, citation_text, citation_html,
        snippet, score. Use `fetch_doc(id)` to get the full chunk
        text for any hit.
    """
    return retrieve.search(query, corpus=corpus, k=k)


@mcp.tool()
def fetch_doc(id: str) -> dict[str, Any]:
    """Fetch the full text of one chunk by its id.

    Args:
        id: A chunk id, as returned by `search`.

    Returns: {id, title, source, citation_url, citation_text,
        citation_html, full_text}.
    """
    return retrieve.fetch_doc(id)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    mcp.settings.host = args.host
    mcp.settings.port = args.port
    print(f"lecture-knowledge MCP server → http://{args.host}:{args.port}/mcp")
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
