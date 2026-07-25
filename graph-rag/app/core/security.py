from fastapi import Header, HTTPException

from ..config import settings


async def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """If settings.api_key is empty, no auth is required. Otherwise the caller
    must send X-API-Key matching. Returns None (FastAPI dependency side-effect)."""
    if not settings.api_key:
        return None
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail={"error": "invalid api key", "code": "unauthorized"})
    return None
