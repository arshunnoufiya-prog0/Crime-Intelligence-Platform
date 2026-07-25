"""Graph-RAG client — httpx AsyncClient to graph-rag:9000.

Mirrors /query/stream, /subgraph/{id}, /query/sync.
"""
from __future__ import annotations

import json
import logging
import time
from typing import AsyncGenerator

import httpx
from django.conf import settings

logger = logging.getLogger("backend.llm.graph_rag_client")

_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            base_url=settings.GRAPH_RAG_URL.rstrip("/"),
            timeout=httpx.Timeout(settings.GRAPH_RAG_TIMEOUT, connect=10.0),
            http2=True,
            headers={"Accept": "text/event-stream"},
        )
    return _client


async def close_client() -> None:
    global _client
    if _client is not None:
        try:
            await _client.aclose()
        except Exception:
            pass
        _client = None


async def stream_query(query: str) -> AsyncGenerator[dict, None]:
    """Yield parsed SSE events from graph-rag /api/v1/query/stream."""
    client = get_client()
    async with client.stream("POST", "/api/v1/query/stream", json={"query": query}) as resp:
        if resp.status_code != 200:
            yield {"error": "upstream_error", "status": resp.status_code}
            return
        event_type = None
        async for line in resp.aiter_lines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("event:"):
                event_type = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                try:
                    data = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue
                if event_type:
                    data = {**data, "event": event_type}
                yield data


async def query_sync(query: str) -> dict:
    client = get_client()
    start = time.monotonic()
    resp = await client.post("/api/v1/query/sync", json={"query": query})
    latency = int((time.monotonic() - start) * 1000)
    if resp.status_code != 200:
        return {"error": "upstream_error", "status": resp.status_code, "latency_ms": latency}
    data = resp.json()
    data.setdefault("latency_ms", latency)
    return data


async def get_subgraph(fir_id: str, max_hops: int = 2) -> dict:
    client = get_client()
    start = time.monotonic()
    resp = await client.get(f"/api/v1/subgraph/{fir_id}", params={"max_hops": max_hops})
    latency = int((time.monotonic() - start) * 1000)
    if resp.status_code != 200:
        return {"error": "upstream_error", "status": resp.status_code, "latency_ms": latency}
    data = resp.json()
    data.setdefault("latency_ms", latency)
    return data