"""MCP server exposing the corpus retriever.

Wraps `lecture_knowledge.retrieve.search` and `fetch_doc` as two MCP
tools. Two transports are supported:

  - stdio (default) — the standard MCP transport. The chat layer (or
    any MCP-aware client like Claude Desktop / Claude Code) launches
    `uv run knowledge-mcp` as a child process and speaks JSON-RPC over
    its stdin/stdout. No port, no host, no network exposure.
  - http (Streamable HTTP) — for clients that can't spawn child
    processes or want to share one server across consumers. Run with
    `uv run knowledge-mcp --transport http` (default 127.0.0.1:8765,
    endpoint `/mcp`).

Decoupled from the chat layer on purpose — the same server can back
the lecture Telegram bot, an experimental agent, an MCP-aware IDE,
or anything else without each consumer having to import the package
in-process.
"""

from __future__ import annotations

import argparse
import sys
import time
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
    parser.add_argument(
        "--transport",
        choices=("stdio", "http"),
        default="stdio",
        help="MCP transport to use (default: stdio).",
    )
    parser.add_argument("--host", default="127.0.0.1", help="HTTP transport only.")
    parser.add_argument("--port", type=int, default=8765, help="HTTP transport only.")
    args = parser.parse_args()

    # Stdio transport owns stdout for JSON-RPC; route logs to stderr.
    log = sys.stderr if args.transport == "stdio" else sys.stdout
    print("lecture-knowledge: warming up retrieval engine…", file=log, flush=True)
    t0 = time.monotonic()
    retrieve.warmup()
    print(
        f"lecture-knowledge: warm in {time.monotonic() - t0:.1f}s",
        file=log,
        flush=True,
    )

    if args.transport == "stdio":
        print("lecture-knowledge MCP server → stdio", file=sys.stderr, flush=True)
        mcp.run(transport="stdio")
    else:
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        print(f"lecture-knowledge MCP server → http://{args.host}:{args.port}/mcp")
        mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
