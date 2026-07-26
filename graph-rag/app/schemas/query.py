"""Request/response schemas for the query endpoints."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Body for POST /api/v1/query/stream and POST /api/v1/query/sync."""
    query: str = Field(..., min_length=1, description="Natural-language query to classify and route")


class QuerySyncResponse(BaseModel):
    """Collected response from /query/sync."""
    answer: str | None = None
    fir_ids: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    reason: str | None = None
    rows_used: int = 0
    request_id: str | None = None
    error: str | None = None


class QueryStreamDone(BaseModel):
    """Terminal `done` event payload for /query/stream."""
    event: str = "done"
    fir_ids: list[str] = Field(default_factory=list)
    rows_used: int = 0
    latency_ms: int = 0
    request_id: str | None = None


class NoContextEvent(BaseModel):
    event: str = "no_context"
    query: str
    request_id: str | None = None


class NoTemplateMatchEvent(BaseModel):
    event: str = "no_template_match"
    query: str
    request_id: str | None = None


class TokenEvent(BaseModel):
    event: str = "token"
    token: str
    request_id: str | None = None


class ErrorEvent(BaseModel):
    event: str = "error"
    code: str
    message: str = ""
    request_id: str | None = None
