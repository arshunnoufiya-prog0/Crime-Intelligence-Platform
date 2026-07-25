"""llm views — proxy SSE and subgraph endpoints to graph-rag:9000.

POST /api/llm/graph/query/      — SSE relay via StreamingHttpResponse
GET  /api/llm/graph/subgraph/{fir_id}/
GET  /api/llm/graph/history/
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import time

from django.http import JsonResponse, StreamingHttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from apps.accounts.decorators import is_authenticated
from .models import GraphQuery
from .services import graph_rag_client

logger = logging.getLogger("backend.llm.views")


def _drive_async_sse(query: str) -> str:
    """
    Drive the async graph_rag_client.stream_query generator inside a new event
    loop on django's worker thread and collect the complete SSE text payload.

    The async generator yields parsed dicts; we serialize each as `data: {...}\n`
    and return the full string.
    """
    loop = asyncio.new_event_loop()

    try:
        async def collector():
            bufs = []
            async for ev in graph_rag_client.stream_query(query):
                bufs.append(f"data: {json.dumps(ev, default=str)}\n")
            return "".join(bufs)

        return loop.run_until_complete(collector())
    finally:
        loop.close()


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(is_authenticated, name="dispatch")
class GraphQueryView(View):
    def post(self, request):
        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({"error": "invalid json", "code": "bad_request"}, status=400)
        query = (body.get("query") or "").strip()
        if not query:
            return JsonResponse({"error": "query required", "code": "bad_request"}, status=400)

        start = time.monotonic()
        gq = GraphQuery.objects.create(user=request.user, query=query)

        def event_stream():
            try:
                sse_payload = _drive_async_sse(query)
                yield sse_payload
            finally:
                latency = int((time.monotonic() - start) * 1000)
                gq.latency_ms = latency
                gq.save()

        response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        response["Connection"] = "keep-alive"
        return response


@method_decorator(is_authenticated, name="dispatch")
class SubgraphView(View):
    def get(self, request, fir_id: str):
        try:
            data = asyncio.run(graph_rag_client.get_subgraph(fir_id))
        except Exception as exc:
            logger.exception("subgraph error: %s", exc)
            return JsonResponse({"error": str(exc), "code": "internal_error"}, status=500)
        if "error" in data:
            return JsonResponse(data, status=502)
        return JsonResponse(data)


@method_decorator(is_authenticated, name="dispatch")
class GraphQueryHistoryView(View):
    def get(self, request):
        qs = GraphQuery.objects.filter(user=request.user).order_by("-created_at")[:100]
        return JsonResponse([
            {
                "id": str(g.id),
                "query": g.query,
                "intent": g.intent,
                "fir_ids": g.fir_ids,
                "latency_ms": g.latency_ms,
                "confidence": g.confidence,
                "created_at": g.created_at.isoformat(),
            }
            for g in qs
        ], safe=False)