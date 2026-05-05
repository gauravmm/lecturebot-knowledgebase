"""End-to-end test of the MCP server, over both stdio and HTTP.

For each transport, drives `knowledge-mcp` via the official MCP client
and asserts that:

  - tools/list returns exactly {search, fetch_doc}
  - search("EU AI Act high-risk systems", k=3) returns 3 hits, each
    with the documented schema, and at least one is from regulation
  - fetch_doc(<top hit id>) returns non-empty full_text and matching
    source URL
  - search(corpus="letters") respects the corpus filter

stdio path: launches `uv run knowledge-mcp` (default transport) as a
subprocess and speaks JSON-RPC over its stdin/stdout via the official
`stdio_client`.

HTTP path: spawns `uv run knowledge-mcp --transport http --port <P>`
on an ephemeral port and connects with `streamablehttp_client`.

Exit 0 on pass, 1 on fail. Run with `uv run python
scripts/inspect/mcp_e2e.py`.
"""

from __future__ import annotations

import asyncio
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client

REQUIRED_HIT_FIELDS = {
    "id",
    "corpus",
    "title",
    "source",
    "section_path",
    "citation_url",
    "citation_text",
    "citation_html",
    "snippet",
    "score",
}
REQUIRED_DOC_FIELDS = {
    "id",
    "title",
    "source",
    "citation_url",
    "citation_text",
    "citation_html",
    "full_text",
}
READY_TIMEOUT_S = 30.0


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_until_ready(url: str, deadline: float) -> None:
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)  # noqa: S310 - localhost only
            return
        except urllib.error.HTTPError:
            # Any HTTP response means the server is up; MCP /mcp without
            # an MCP handshake will 4xx, that's fine.
            return
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            time.sleep(0.2)
    raise TimeoutError(f"Server at {url} did not come up within {READY_TIMEOUT_S}s")


async def _exercise(session: ClientSession) -> None:
    await session.initialize()

    tools = await session.list_tools()
    names = {t.name for t in tools.tools}
    assert names == {"search", "fetch_doc"}, f"unexpected tools: {names}"
    print(f"  [ok] tools/list = {sorted(names)}")

    r = await session.call_tool(
        "search", {"query": "EU AI Act high-risk systems", "k": 3}
    )
    assert r.structuredContent is not None, "search returned no structuredContent"
    hits = r.structuredContent["result"]
    assert isinstance(hits, list), f"hits not a list: {type(hits)}"
    assert len(hits) == 3, f"expected k=3 hits, got {len(hits)}"
    for h in hits:
        missing = REQUIRED_HIT_FIELDS - set(h)
        assert not missing, f"hit missing fields {missing}: {h}"
        if h["citation_url"] is not None:
            assert h["citation_text"], f"citation text missing for hit: {h}"
            assert h["citation_html"], f"citation html missing for hit: {h}"
    assert any(h["corpus"] == "regulation" for h in hits), (
        f"expected at least one regulation hit, got corpora="
        f"{[h['corpus'] for h in hits]}"
    )
    print(f"  [ok] search returned {len(hits)} hits, "
          f"corpora={sorted({h['corpus'] for h in hits})}")

    top_id = hits[0]["id"]
    r2 = await session.call_tool("fetch_doc", {"id": top_id})
    assert r2.structuredContent is not None, "fetch_doc returned no structuredContent"
    doc = r2.structuredContent
    missing = REQUIRED_DOC_FIELDS - set(doc)
    assert not missing, f"doc missing fields {missing}: {doc.keys()}"
    assert doc["id"] == top_id, f"id mismatch: {doc['id']} != {top_id}"
    assert doc["source"] == hits[0]["source"], "source URL mismatch"
    assert doc["citation_url"] == hits[0]["citation_url"], "citation URL mismatch"
    assert doc["citation_text"] == hits[0]["citation_text"], "citation text mismatch"
    assert doc["citation_html"] == hits[0]["citation_html"], "citation HTML mismatch"
    assert doc["full_text"], "fetch_doc returned empty full_text"
    print(f"  [ok] fetch_doc({top_id}) → {len(doc['full_text'])} chars")

    r3 = await session.call_tool(
        "search",
        {"query": "shareholder letter", "corpus": "letters", "k": 2},
    )
    scoped = r3.structuredContent["result"]
    assert all(h["corpus"] == "letters" for h in scoped), (
        f"corpus filter ignored: {[h['corpus'] for h in scoped]}"
    )
    print(f"  [ok] search(corpus='letters') returned {len(scoped)} hits, all letters")


async def _drive_http(url: str) -> None:
    async with streamablehttp_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await _exercise(session)


async def _drive_stdio() -> None:
    params = StdioServerParameters(command="uv", args=["run", "knowledge-mcp"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await _exercise(session)


def _run_stdio() -> None:
    print("Driving knowledge-mcp over stdio")
    asyncio.run(_drive_stdio())


def _run_http() -> None:
    port = _free_port()
    url = f"http://127.0.0.1:{port}/mcp"
    print(f"Spawning knowledge-mcp --transport http on :{port}")
    proc = subprocess.Popen(
        ["uv", "run", "knowledge-mcp", "--transport", "http", "--port", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_until_ready(url, time.time() + READY_TIMEOUT_S)
        print(f"Server ready at {url}")
        asyncio.run(_drive_http(url))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def main() -> int:
    try:
        print("=== stdio transport ===")
        _run_stdio()
        print("\n=== http transport ===")
        _run_http()
        print("\nALL CHECKS PASSED")
        return 0
    except AssertionError as e:
        print(f"\nFAIL: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\nERROR: {type(e).__name__}: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
