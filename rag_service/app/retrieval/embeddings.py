"""Embedding client (spec §10.2) — llama-embed :8081 with hard guarantees.

* batch ≤ 16 texts per call;
* every vector must be EMBED_DIM (1024) long — assert on every response;
* retry with tenacity: 3 attempts, exponential backoff, on transport errors
  and 5xx ONLY — a 4xx is never retried (§10.2).
"""
from __future__ import annotations

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from ..config import get_settings


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code >= 500


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception(_retryable),
)
async def embed_texts(texts: list[str]) -> list[list[float]]:
    settings = get_settings()
    out: list[list[float]] = []
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
        for i in range(0, len(texts), 16):
            batch = texts[i:i + 16]
            r = await client.post(settings.embed_url, json={"input": batch, "model": "bge-m3"})
            r.raise_for_status()
            data = r.json()["data"]
            if len(data) != len(batch):
                raise RuntimeError(f"embedding count mismatch: sent {len(batch)}, got {len(data)} (§10.2)")
            for item in data:
                vec = item["embedding"]
                if len(vec) != settings.embed_dim:
                    raise RuntimeError(
                        f"embedding dim {len(vec)} != {settings.embed_dim} — silent dim mismatch "
                        "presents as 'retrieval returns nothing' (§7/§10.2)"
                    )
                out.append(vec)
    return out


async def embed_query(text: str) -> list[float]:
    vecs = await embed_texts([text])
    return vecs[0]
