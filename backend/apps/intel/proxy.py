"""RAG proxy (spec §14.3 change 1, §17).

Django's only AI-adjacent jobs: authenticate, authorize, stamp the audit log,
attach RBAC scope, and proxy the stream — it NEVER builds a prompt, NEVER
talks to Qdrant or llama.cpp (§2.1).

SSE is relayed with httpx.Client.stream inside a generator passed to
StreamingHttpResponse (§17). The client-facing bytes pass through
UNMODIFIED — all §12.5 event types including unknown ones (§14.3-1). A
side-copy of the stream is parsed ONCE at end-of-stream for the audit
record: the ANSWER text is stored; the reasoning text is NEVER stored
(§14.3-2) — only its token count from the meta event.
"""
from __future__ import annotations

import json
import time

import httpx
from django.conf import settings
from django.http import StreamingHttpResponse

from apps.accounts.scope import build_scope


class RagUpstreamError(RuntimeError):
    code = "rag_upstream_unavailable"


def _headers() -> dict:
    return {"X-API-Key": settings.RAG_API_KEY} if settings.RAG_API_KEY else {}


def _rag_url(path: str) -> str:
    return f"{settings.RAG_URL.rstrip('/')}{path}"


def _parse_stream_for_audit(raw: bytes, started: float) -> dict:
    """End-of-stream parse of the side-copy. Answer text is captured; the
    reasoning channel is deliberately ignored (§1.3 rule 2, §14.3-2)."""
    answer: list[str] = []
    warnings: list[dict] = []
    citations: list[dict] = []
    meta: dict = {}
    event: str | None = None
    for line in raw.decode("utf-8", "replace").split("\n"):
        line = line.strip()
        if line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:") and event:
            try:
                parsed = json.loads(line[5:].strip())
            except json.JSONDecodeError:
                continue
            if event == "token":
                answer.append(parsed.get("t", ""))
            elif event == "warning":
                warnings.append(parsed)
            elif event == "citations":
                citations.extend(parsed.get("citations", []))
            elif event == "meta":
                meta = parsed
    return {
        "answer": "".join(answer),
        "intent": meta.get("intent", ""),
        "cypher_template_id": meta.get("cypher_template_id", ""),
        "fir_ids_returned": sorted({str(c["fir_id"]) for c in citations if c.get("fir_id")}),
        "prompt_token_count": meta.get("prompt_tokens", 0),
        "reasoning_token_count": meta.get("reasoning_tokens", 0),
        "warnings": warnings,
        "ttft_ms": meta.get("ttft_ms"),
        "latency_ms": meta.get("latency_ms") or int((time.monotonic() - started) * 1000),
    }


def _error_event(code: str, message: str) -> bytes:
    return (
        "event: error\ndata: "
        + json.dumps({"ok": False, "error": {"code": code, "message": message}})
        + "\n\n"
    ).encode()


def stream_query(user, question: str, conversation_id: str | None, history: list,
                 audit_sink=None) -> StreamingHttpResponse:
    payload = {
        "question": question,
        "scope": build_scope(user),
        "conversation_id": conversation_id,
        "history": history or [],
    }
    started = time.monotonic()

    def event_stream():
        side_copy = bytearray()
        try:
            with httpx.Client(timeout=httpx.Timeout(settings.GRAPH_RAG_TIMEOUT, connect=10.0)) as client:
                with client.stream(
                    "POST", _rag_url("/v1/query"), json=payload, headers=_headers()
                ) as resp:
                    if resp.status_code != 200:
                        yield _error_event(RagUpstreamError.code, f"upstream returned {resp.status_code}")
                        return
                    for chunk in resp.iter_raw():
                        side_copy.extend(chunk)
                        yield chunk
        except httpx.HTTPError as exc:
            yield _error_event(RagUpstreamError.code, str(exc))
            return
        if audit_sink is not None:
            try:
                audit_sink(**_parse_stream_for_audit(bytes(side_copy), started))
            except Exception:  # noqa: BLE001 — audit failure must never break the delivered answer
                pass

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    response["Connection"] = "keep-alive"
    return response


def get_json(user, path: str, params: dict | None = None) -> dict:
    """Blocking GET relay for graph/profile routes (scope attached as query
    params — §12 scope injection, never browser-supplied)."""
    scope = build_scope(user)
    params = dict(params or {})
    if scope["districts"]:
        params["districts"] = ",".join(scope["districts"])
    if scope["stations"]:
        params["stations"] = ",".join(scope["stations"])
    try:
        with httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
            resp = client.get(_rag_url(path), params=params, headers=_headers())
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as exc:
        raise RagUpstreamError(str(exc)) from exc
