"""Reranker (spec §8) — llama-rerank :8082 with bge-reranker-v2-m3.

Behavior when ENABLE_RERANK=true: rerank the top-30 hybrid candidates down to
top-8 by relevance before context assembly. When off (or on any upstream
failure): take top-8 by hybrid score. BOTH paths must work (§8) — an upstream
failure degrades with a warning, never raises, and reranking is never
emulated with a generation prompt.

The endpoint path is the one recorded from `llama-server --help | grep -i
rerank` (§8 VERIFY, pending on the b9222 build — default /v1/rerank per
settings).
"""
from __future__ import annotations

import httpx

from ..config import get_settings
from ..schemas import Citation  # noqa: F401  (shared chunk shape re-exported below)


async def top_k_by_score(candidates: list[dict], k: int = 8) -> list[dict]:
    ordered = sorted(candidates, key=lambda c: c.get("score", 0.0), reverse=True)
    return ordered[:k]


async def rerank(query_text: str, candidates: list[dict], top_k: int = 8, pool: int = 30) -> tuple[list[dict], str | None]:
    """Returns (top_k chunks, warning). `candidates` are dicts with at least
    `content` and `score`. Degrades to the hybrid-score path on any upstream
    problem, with a warning string for the SSE metadata (§8)."""
    settings = get_settings()
    if not settings.enable_rerank:
        return await top_k_by_score(candidates, top_k), None

    pool_items = sorted(candidates, key=lambda c: c.get("score", 0.0), reverse=True)[:pool]
    if not pool_items:
        return [], None
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0)) as client:
            r = await client.post(settings.rerank_url, json={
                "model": "bge-reranker",
                "query": query_text,
                "documents": [c["content"] for c in pool_items],
                "top_n": top_k,
            })
            r.raise_for_status()
            results = r.json()["results"]
            picked: list[dict] = []
            for item in results[:top_k]:
                idx = item["index"]
                if 0 <= idx < len(pool_items):
                    chunk = dict(pool_items[idx])
                    chunk["score"] = item.get("relevance_score", chunk.get("score", 0.0))
                    picked.append(chunk)
            return picked, None
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        degraded = await top_k_by_score(candidates, top_k)
        return degraded, f"rerank unavailable ({exc.__class__.__name__}) — degraded to hybrid score order (§8)"
