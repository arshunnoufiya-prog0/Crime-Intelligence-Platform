"""Structured graph-rag exceptions. Every error exposes `to_dict()` returning
`{error, code, request_id}` — raw tracebacks are never leaked to clients.
"""
from __future__ import annotations

import uuid


class GraphRagError(RuntimeError):
    def __init__(self, code: str, message: str, request_id: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.request_id = request_id

    def to_dict(self) -> dict[str, str]:
        return {
            "error": self.message,
            "code": self.code,
            "request_id": self.request_id or "",
        }


class GraphStoreError(GraphRagError):
    pass


class IntentClassificationError(GraphRagError):
    pass


class LLMError(GraphRagError):
    pass


class SummarizerError(GraphRagError):
    pass


class IngestError(GraphRagError):
    pass


class ValidationError(GraphRagError):
    pass


class NoTemplateMatch(GraphRagError):
    """Sentinel — not a 5xx. Pipeline yields a structured SSE event, not an error page."""

    pass


class NoContext(GraphRagError):
    """Sentinel — empty Cypher/vector result. Pipeline yields no_context_event, stops."""

    pass


def new_request_id() -> str:
    return uuid.uuid4().hex
