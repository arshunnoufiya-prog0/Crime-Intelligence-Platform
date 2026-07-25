"""Query endpoints — SSE streaming + sync.

POST /api/v1/query/stream  — SSE, implements the exact pseudo-code from spec [2J]
POST /api/v1/query/sync    — collects full JSON response
"""
from __future__ import annotations

import logging
import time
from typing import AsyncIterator

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sse_starlette import EventSourceResponse

from ...config import settings
from ...core.exceptions import GraphRagError, NoContext, NoTemplateMatch, new_request_id
from ...core.streaming import (
    done_event,
    error_event,
    no_context_event,
    no_template_match_event,
    safe_relay,
    token_event,
    now_ms,
)
from ...intent.classifier import classify
from ...cypher.router import route
from ...embedding.embedder import embedder
from ...graphstore.neo4j_client import neo4j_client
from ...llm.summarizer import extract_fir_ids_from_rows, summarize_stream

router = APIRouter(tags=["query"])

logger = logging.getLogger("graph-rag.api.query")


async def _auth(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail={"error": "invalid api key", "code": "unauthorized"})


@router.post("/query/stream")
async def query_stream(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    _auth=Depends(_auth),
):
    body = await request.json()
    query = body.get("query", "").strip()
    if not query:
        raise HTTPException(status_code=400, detail={"error": "query is required", "code": "bad_request"})

    rid = new_request_id()
    start_ms = now_ms()
    logger.info("query stream start rid=%s q=%s", rid, query[:100])

    async def generator() -> AsyncIterator[dict]:
        try:
            classified = await classify(query)
            if classified.intent.value == "unsupported" or classified.confidence < 0.5:
                yield no_template_match_event(query, rid)
                return

            if classified.intent.value == "semantic_search":
                vec = await embedder.embed_query(classified.entities.free_text or query)
                rows = await neo4j_client.vector_search(
                    vec,
                    top_k=10,
                    score_threshold=settings.similarity_threshold,
                )
            else:
                routed = await route(classified)
                if routed is None:
                    yield no_template_match_event(query, rid)
                    return
                template, params = routed
                rows = await neo4j_client.run_template(template, params)

            if not rows:
                yield no_context_event(query, rid)
                return

            fir_ids = extract_fir_ids_from_rows(rows)
            async for token in summarize_stream(query, rows):
                yield token_event(token, rid)

            elapsed = now_ms() - start_ms
            yield done_event(fir_ids=fir_ids, rows_used=len(rows), latency_ms=elapsed, request_id=rid)

        except GraphRagError:
            yield error_event("graph_error", "internal error", rid)
            return
        except Exception:
            logger.exception("query stream error rid=%s", rid)
            yield error_event("internal_error", "internal server error", rid)
            return

    return EventSourceResponse(safe_relay(generator()))


@router.post("/query/sync")
async def query_sync(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    _auth=Depends(_auth),
):
    body = await request.json()
    query = body.get("query", "").strip()
    if not query:
        raise HTTPException(status_code=400, detail={"error": "query is required", "code": "bad_request"})

    rid = new_request_id()
    logger.info("query sync start rid=%s q=%s", rid, query[:100])

    try:
        classified = await classify(query)
        if classified.intent.value == "unsupported" or classified.confidence < 0.5:
            return {"error": "no_template_match", "query": query, "request_id": rid}

        if classified.intent.value == "semantic_search":
            vec = await embedder.embed_query(classified.entities.free_text or query)
            rows = await neo4j_client.vector_search(
                vec,
                top_k=10,
                score_threshold=settings.similarity_threshold,
            )
        else:
            routed = await route(classified)
            if routed is None:
                return {"error": "no_template_match", "query": query, "request_id": rid}
            template, params = routed
            rows = await neo4j_client.run_template(template, params)

        if not rows:
            return {"error": "no_context", "query": query, "request_id": rid}

        from ...llm.summarizer import summarize_sync
        result = await summarize_sync(query, rows)

        return {
            "answer": result.answer,
            "fir_ids": result.fir_ids,
            "confidence": result.confidence,
            "reason": result.reason,
            "rows_used": len(rows),
            "request_id": rid,
        }

    except GraphRagError as exc:
        return {"error": exc.code, "message": exc.message, "request_id": rid}
    except Exception:
        logger.exception("query sync error rid=%s", rid)
        return {"error": "internal_error", "message": "internal server error", "request_id": rid}