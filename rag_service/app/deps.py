from __future__ import annotations

from fastapi import Header, HTTPException, Request


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """Optional internal shared secret between Django and the RAG service.
    If unset, no auth is enforced (service is compose-internal, §2.4)."""
    from .config import get_settings

    expected = get_settings().rag_api_key
    if expected and x_api_key != expected:
        raise HTTPException(status_code=401, detail={"code": "unauthorized", "message": "invalid API key"})


def get_engine(request: Request):
    """LightRAG engine instantiated ONCE in the FastAPI lifespan (§9)."""
    engine = getattr(request.app.state, "rag", None)
    if engine is None:
        raise HTTPException(status_code=503, detail={"code": "lightrag_not_ready", "message": "engine not initialized"})
    return engine


def get_settings_dep():
    from .config import get_settings

    return get_settings()
