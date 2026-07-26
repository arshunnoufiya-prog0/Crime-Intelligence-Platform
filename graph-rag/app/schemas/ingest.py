"""Request/response schemas for the ingest endpoint."""
from __future__ import annotations

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    """Body for POST /api/v1/ingest."""
    json_path: str = "../data/bengaluru_40ps_1000_firs.json"


class IngestResponse(BaseModel):
    """Result of an ingest run."""
    status: str = "ok"
    total: int = 0
    inserted: int = 0
    skipped: int = 0
    errors: int = 0
    elapsed_ms: int = 0
    json_path: str | None = None
