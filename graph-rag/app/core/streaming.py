"""SSE event builders + helpers. Every generator yields these via
sse-starlette.EventSourceResponse; all handle asyncio.CancelledError so
client disconnects exit cleanly.
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import AsyncIterator


def _event(event: str, data: dict) -> dict:
    return {"event": event, "data": json.dumps(data, default=str)}


def no_template_match_event(query: str, request_id: str) -> dict:
    return _event("no_template_match", {
        "query": query,
        "reason": "unsupported_intent",
        "request_id": request_id,
    })


def no_context_event(query: str, request_id: str) -> dict:
    return _event("no_context", {
        "query": query,
        "reason": "no_graph_rows",
        "request_id": request_id,
    })


def token_event(token: str, request_id: str) -> dict:
    return _event("token", {"token": token, "request_id": request_id})


def done_event(fir_ids: list[str], rows_used: int, latency_ms: int, request_id: str) -> dict:
    return _event("done", {
        "fir_ids": fir_ids,
        "rows_used": rows_used,
        "latency_ms": latency_ms,
        "request_id": request_id,
    })


def error_event(code: str, message: str, request_id: str) -> dict:
    return _event("error", {"error": message, "code": code, "request_id": request_id})


async def safe_relay(generator: AsyncIterator[dict]) -> AsyncIterator[dict]:
    try:
        async for ev in generator:
            yield ev
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001
        yield error_event("internal_error", str(exc), "")
        return


def now_ms() -> int:
    return int(time.monotonic() * 1000)
