"""Health endpoint."""
from fastapi import APIRouter, Depends

from ..dependencies import get_neo4j
from ..config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": get_settings().app_name}


@router.get("/ready")
async def readiness(neo4j=Depends(get_neo4j)) -> dict:
    try:
        await neo4j.driver.verify_connectivity()
        return {"ready": True}
    except Exception:
        return {"ready": False}