"""POST /v1/query — the §12 execution path, streamed as §12.5 SSE events.

Pipeline: classify → slots → plan → parallel retrieval (Cypher + LightRAG,
independent timeouts, degrade-don't-fail §12.3) → rerank (§8) → context
budget (§11) → streaming synthesis with the reasoning split (§1.3) →
citation validation on the ANSWER ONLY (§12.6) → citations / graph /
warning / meta / done events.

The scope is injected by Django from the validated JWT and is REQUIRED at the
schema layer — the RAG service never accepts a browser-supplied scope (§12).
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
import time
from pathlib import Path
from typing import AsyncGenerator

import networkx as nx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ingest"))

import _schema_constants as SC  # noqa: E402

from ..answer import citations as citation_mod  # noqa: E402
from ..answer import synthesize  # noqa: E402
from ..config import get_settings  # noqa: E402
from ..deps import get_engine, get_settings_dep, require_api_key  # noqa: E402
from ..graph import centrality, neo4j_client, serializers  # noqa: E402
from ..llm import client as llm_client  # noqa: E402
from ..llm import prompts  # noqa: E402
from ..retrieval import rerank as rerank_mod  # noqa: E402
from ..retrieval import context_budget  # noqa: E402
from ..retrieval.lightrag_engine import query as lightrag_query  # noqa: E402
from ..router import intent as intent_router  # noqa: E402
from ..router import plan as plan_mod  # noqa: E402
from ..schemas import QueryRequest  # noqa: E402

router = APIRouter(prefix="/v1", tags=["query"])

_FIR_ID_RE = re.compile(SC.ID_REGEX)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _row_ids(rows: list[dict]) -> set[str]:
    ids: set[str] = set()
    for row in rows:
        for value in row.values():
            if isinstance(value, str) and _FIR_ID_RE.match(value):
                ids.add(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str) and _FIR_ID_RE.match(item):
                        ids.add(item)
    return ids


def _parse_lightrag(result) -> tuple[list[dict], list[dict]]:
    """Tolerant parser for the documented aquery return shape. The exact
    structure is confirmed by the §3.2 signature dump at install time —
    unknown shapes degrade to empty, never raise mid-request."""
    if not result:
        return [], []
    chunks: list[dict] = []
    entity_facts: list[dict] = []
    if isinstance(result, dict):
        for chunk in result.get("chunks") or []:
            if isinstance(chunk, dict) and chunk.get("content"):
                source = chunk.get("source_id") or chunk.get("source") or ""
                if isinstance(source, list):
                    source = source[0] if source else ""
                chunks.append({"content": chunk["content"], "score": chunk.get("score", 0.5),
                               "source_id": str(source)})
        for ent in result.get("entities") or []:
            if isinstance(ent, dict):
                text = ent.get("description") or ent.get("content") or ""
                if text:
                    entity_facts.append({"text": f"{ent.get('entity_name', 'entity')}: {text}",
                                         "score": ent.get("score", 0.4)})
    elif isinstance(result, str):
        chunks = [{"content": result, "score": 0.5, "source_id": ""}]
    return chunks, entity_facts


@router.post("/query", dependencies=[Depends(require_api_key)])
async def query(
    body: QueryRequest,
    request: Request,
    engine=Depends(get_engine),
    settings=Depends(get_settings_dep),
):
    started = time.monotonic()

    try:
        intent_label, slots = await asyncio.gather(
            intent_router.classify(body.question),
            intent_router.extract_slots(body.question),
        )
    except llm_client.LLMUpstreamError as exc:
        return JSONResponse(status_code=503, content={
            "ok": False, "error": {"code": exc.code, "message": str(exc)},
        })

    plan = plan_mod.build_plan(intent_label, slots, body.scope)
    degradation_warnings: list[dict] = []

    async def cypher_task() -> list[dict]:
        template_id = plan.cypher_template_id or "FREEFORM_SEARCH"
        try:
            return await neo4j_client.run_template(template_id, plan.cypher_params)
        except neo4j_client.CypherTimeout:
            degradation_warnings.append({
                "code": "CYPHER_TIMEOUT",
                "detail": f"structured retrieval exceeded {settings.cypher_timeout_s}s — degraded to narrative source (§12.3)",
            })
            return []

    async def lightrag_task() -> list:
        try:
            return await asyncio.wait_for(
                lightrag_query(engine, plan.lightrag_mode or "hybrid", plan.lightrag_query or body.question),
                timeout=settings.lightrag_timeout_s,
            )
        except asyncio.TimeoutError:
            degradation_warnings.append({
                "code": "LIGHTRAG_TIMEOUT",
                "detail": f"narrative retrieval exceeded {settings.lightrag_timeout_s}s — degraded to structured source (§12.3)",
            })
            return []

    cypher_rows, lightrag_result = await asyncio.gather(cypher_task(), lightrag_task())
    chunks, entity_facts = _parse_lightrag(lightrag_result)

    picked, rerank_warning = await rerank_mod.rerank(body.question, chunks)
    if rerank_warning:
        degradation_warnings.append({"code": "RERANK_DEGRADED", "detail": rerank_warning})

    try:
        context_block, kept_history, budget_meta = await context_budget.assemble(
            llm_client.count_tokens_for,
            system=f"{prompts.SYNTHESIS_SYSTEM}\n\n{prompts.FORMAT_INSTRUCTIONS}",
            scope=prompts.scope_preamble(body.scope),
            question=body.question,
            history=[m.model_dump() for m in body.history],
            history_summarizer=synthesize.history_summarizer,
            cypher=context_budget.CypherResult(
                template_id=plan.cypher_template_id or "none",
                rows=cypher_rows,
                header={"rows": len(cypher_rows)},
            ),
            chunks=[context_budget.Chunk(**c) for c in picked],
            entity_facts=[context_budget.EntityFact(**e) for e in entity_facts],
            thinking_enabled=llm_client_sampling_thinking(),
        )
    except context_budget.ContextOverflowError as exc:
        return JSONResponse(status_code=422, content={
            "ok": False,
            "error": {"code": exc.code, "message": str(exc), "details": {"suggestion": exc.suggestion}},
        })

    retrieval_ids = _row_ids(cypher_rows) | {c["source_id"] for c in picked if c.get("source_id")}

    async def event_stream() -> AsyncGenerator[str, None]:
        answer_parts: list[str] = []
        reasoning_parts: list[str] = []
        ttft_ms: int | None = None
        first_token_at = None
        try:
            async for channel, token in synthesize.stream_answer(
                body.scope, context_block, kept_history, body.question
            ):
                if channel == "reasoning":
                    reasoning_parts.append(token)
                    yield _sse("reasoning", {"t": token})
                else:
                    if first_token_at is None:
                        first_token_at = time.monotonic()
                        ttft_ms = int((first_token_at - started) * 1000)
                    answer_parts.append(token)
                    yield _sse("token", {"t": token})
        except llm_client.LLMUpstreamError as exc:
            yield _sse("warning", {"code": exc.code, "detail": "generation upstream failed mid-stream"})
            yield _sse("done", {})
            return

        answer_text = "".join(answer_parts)
        reasoning_text = "".join(reasoning_parts)

        clean_answer, validation_warnings = citation_mod.validate_answer(
            answer_text, retrieval_ids, len(cypher_rows)
        )
        if clean_answer != answer_text:
            yield _sse("warning", {
                "code": "ANSWER_EDITED",
                "detail": "unverifiable references were struck from the answer (§12.6)",
            })

        cited = citation_mod.extract_cited_ids(clean_answer)
        yield _sse("citations", {"citations": [
            {"fir_id": c, "station": None, "chunk_id": None, "score": None} for c in cited
        ]})

        if plan.needs_centrality and cypher_rows:
            graph = serializers.rows_to_force_graph(
                cypher_rows, src_key="src", dst_key="dst",
                src_label_key="src_name", dst_label_key="dst_name",
                type_key="rel_type", weight_key="weight",
            )
            G = nx.Graph()
            G.add_nodes_from(n["id"] for n in graph["nodes"])
            G.add_edges_from((l["source"], l["target"]) for l in graph["links"])
            metrics, approximate = await asyncio.to_thread(centrality.compute_metrics, G)
            graph = serializers.apply_metrics(graph, metrics, approximate)
            yield _sse("graph", graph)

        for warning in degradation_warnings + validation_warnings:
            yield _sse("warning", warning)

        reasoning_tokens = await llm_client.count_tokens_for(reasoning_text) if reasoning_text else 0
        completion_tokens = await llm_client.count_tokens_for(answer_text) if answer_text else 0
        yield _sse("meta", {
            "prompt_tokens": budget_meta.prompt_tokens,
            "reasoning_tokens": reasoning_tokens,
            "completion_tokens": completion_tokens,
            "ttft_ms": ttft_ms,
            "latency_ms": int((time.monotonic() - started) * 1000),
            "mode": plan.lightrag_mode,
            "intent": plan.intent,
            "cypher_template_id": plan.cypher_template_id,
            "segments": budget_meta.segment_tokens,
        })
        yield _sse("done", {})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def llm_client_sampling_thinking() -> bool:
    from ..llm import sampling

    return sampling.sampling_for("synthesis")["thinking"]
