# lecture_knowledge — retrieval engine + MCP server

The installable Python package that exposes the built index. Two
public functions: `search(query, corpus, k)` and `fetch_doc(id)`.
Hybrid BM25 + dense → reciprocal rank fusion → per-corpus boost.

## Consumption surfaces

- **In-process Python**: `from lecture_knowledge.retrieve import
  search, fetch_doc`. Cheapest path; loaded lazily on first call,
  warm queries 10–25 ms. The chat-layer workstream can use this if
  it wants tight coupling.
- **MCP server**: `uv run knowledge-mcp` exposes the same two tools
  over **stdio by default** — the chat layer (or any MCP-aware
  client like Claude Desktop / Claude Code) launches it as a child
  process and speaks JSON-RPC over its stdin/stdout. Add
  `--transport http` to serve over Streamable HTTP at
  `http://127.0.0.1:8765/mcp` instead, for clients that can't
  spawn subprocesses or want to share one server across consumers.
  See `mcp_server.py`.

## Warmup behavior

The MCP server pays the cold-start cost up front via
`retrieve.warmup()` so the first user query is already warm.
Per-stage timings are printed on startup (stderr for stdio,
stdout for http). Typical numbers (warm HF cache, CPU-only):

```text
chunk_meta_parquet       ~180 ms
bm25_index                ~15 ms
faiss_index               ~15 ms
embedding_model         ~5000 ms   ← dominates
first_query               ~40 ms
TOTAL                   ~5300 ms
```

The embedding model is pinned to `device="cpu"` in
`retrieve._load`. faiss is CPU-only here, the small bge-base model
runs fine on CPU, and pinning avoids contention with co-located
GPU jobs (e.g., a vLLM server on the same box).

## Tests

`scripts/inspect/mcp_e2e.py` is the end-to-end MCP server test.
Drives both stdio and HTTP transports via the official `mcp` SDK
client; asserts the tool surface + result schemas + corpus filter
on each, tears the server down. Exit 0 = pass.

## Ad-hoc query

In-process: `uv run python -c 'from lecture_knowledge.retrieve
import search; print(search("EU AI Act high-risk", k=3))'`.
