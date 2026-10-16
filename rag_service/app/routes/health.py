"""GET /v1/health — stack liveness for compose healthchecks (§16)."""
from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from ..config import get_settings
from ..deps import require_api_key

router = APIRouter(prefix="/v1", tags=["health"])


@router.get("/health", dependencies=[Depends(require_api_key)])
async def health():
    settings = get_settings()
    checks: dict[str, str] = {}

    async def probe(name: str, url: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                r = await client.get(url)
                checks[name] = "up" if r.status_code < 500 else f"http_{r.status_code}"
        except Exception as exc:  # noqa: BLE001 — health probe must never raise
            checks[name] = f"down ({exc.__class__.__name__})"

    await probe("llama-gen", f"{settings.llm_base_url.rstrip('/')}/health")
    await probe("llama-embed", f"{settings.embed_base_url.rstrip('/')}/health")
    if settings.enable_rerank:
        await probe("llama-rerank", f"{settings.rerank_base_url.rstrip('/')}/health")

    try:
        from ..graph import neo4j_client

        await neo4j_client.run_cypher("RETURN 1 AS ok")
        checks["neo4j"] = "up"
    except Exception as exc:  # noqa: BLE001
        checks["neo4j"] = f"down ({exc.__class__.__name__})"

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{settings.qdrant_url.rstrip('/')}/healthz")
            checks["qdrant"] = "up" if r.status_code == 200 else f"http_{r.status_code}"
    except Exception as exc:  # noqa: BLE001
        checks["qdrant"] = f"down ({exc.__class__.__name__})"

    code = 200 if all(v == "up" for v in checks.values()) else 503
    return JSONResponse(status_code=code, content={"ok": code == 200, "checks": checks})
