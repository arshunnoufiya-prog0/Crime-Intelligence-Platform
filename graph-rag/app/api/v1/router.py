"""V1 router aggregation."""
from fastapi import APIRouter

from .health import router as health_router
from .query import router as query_router
from .subgraph import router as subgraph_router
from .ingest import router as ingest_router

router = APIRouter(prefix="/api/v1")

router.include_router(health_router)
router.include_router(query_router)
router.include_router(subgraph_router)
router.include_router(ingest_router)