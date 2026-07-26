"""Response schemas for the subgraph endpoint."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    """Force-graph-ready node (react-force-graph-2d shape)."""
    id: str
    label: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
    degree: float = 0.0
    betweenness: float = 0.0
    eigenvector: float = 0.0
    community: int = -1


class GraphLink(BaseModel):
    source: str
    target: str
    type: str = "RELATED"


class SubgraphResponse(BaseModel):
    """Body of GET /api/v1/subgraph/{fir_id}."""
    nodes: list[GraphNode] = Field(default_factory=list)
    links: list[GraphLink] = Field(default_factory=list)
    error: str | None = None
    request_id: str | None = None
