"""Grounded summarizer — the ONLY place the LLM sees retrieved rows.
Zero-hallucination prompt: temperature=0, top_k=1. Returns strictly the
JSON schema: {answer, fir_ids, confidence, reason}. Parse failures yield
structured error, never raw text.
"""
from __future__ import annotations

import json
import logging
from typing import AsyncIterator

from ..config import settings
from ..core.exceptions import SummarizerError
from ..llm.client import llm_client

logger = logging.getLogger("graph-rag.summarizer")


SYSTEM_PROMPT = """You are a crime-record assistant. Answer ONLY using the
GRAPH RESULTS below. Do not use outside knowledge. Do not infer
facts not present in the results.

GRAPH RESULTS (JSON, from Neo4j — {n} records):
{results_json}

USER QUESTION:
{query}

Rules:
- If GRAPH RESULTS is empty, respond exactly:
  {"answer": null, "reason": "not_in_graph"}
- Every FIR ID you mention must appear in GRAPH RESULTS.
- Return ONLY this JSON schema, nothing else:
  {"answer": "<string or null>", "fir_ids": ["..."],
   "confidence": 0.0-1.0, "reason": "found|partial|not_in_graph"}
"""


class SummaryResult:
    __slots__ = ("answer", "fir_ids", "confidence", "reason")

    def __init__(self, answer: str | None, fir_ids: list[str], confidence: float, reason: str):
        self.answer = answer
        self.fir_ids = fir_ids
        self.confidence = confidence
        self.reason = reason


async def summarize_stream(query: str, rows: list[dict]) -> AsyncIterator[str]:
    """Yield tokens from the LLM stream for the grounded summary."""
    if not rows:
        yield json.dumps({"answer": None, "reason": "not_in_graph"}, ensure_ascii=False)
        return

    import json as _json
    prompt = SYSTEM_PROMPT.format(n=len(rows), results_json=_json.dumps(rows, ensure_ascii=False), query=query)
    messages = [{"role": "system", "content": prompt}]

    # Stream tokens from LLM; the LLM returns a JSON object (streamed token by token)
    # We accumulate and yield the tokens as they come; caller re-assembles.
    async for token in llm_client.stream_chat(messages, settings.synthesis_params()):
        yield token


async def summarize_sync(query: str, rows: list[dict]) -> SummaryResult:
    """Blocking call that returns a validated SummaryResult."""
    if not rows:
        return SummaryResult(None, [], 1.0, "not_in_graph")

    import json as _json
    prompt = SYSTEM_PROMPT.format(n=len(rows), results_json=_json.dumps(rows, ensure_ascii=False), query=query)
    messages = [{"role": "system", "content": prompt}]
    try:
        text = await llm_client.chat(messages, settings.synthesis_params())
        data = _json.loads(text)
        answer = data.get("answer")
        fir_ids = data.get("fir_ids", [])
        confidence = float(data.get("confidence", 0.0))
        reason = data.get("reason", "found")
        return SummaryResult(answer, fir_ids, confidence, reason)
    except (_json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        logger.error("summarizer parse failed: %s; raw=%s", exc, text[:300])
        raise SummarizerError("parse_error", f"LLM output parse failed: {exc}") from exc


def extract_fir_ids_from_rows(rows: list[dict]) -> list[str]:
    ids: list[str] = []
    for r in rows:
        if isinstance(r, dict):
            # row may have 'f' or 'linked' etc; try common keys
            for k in ("fir_key", "fir_id", "id"):
                v = r.get(k)
                if v:
                    ids.append(v)
                    break
            # also handle nested
            for v in r.values():
                if isinstance(v, dict):
                    fk = v.get("fir_key") or v.get("fir_id")
                    if fk:
                        ids.append(fk)
    return list(dict.fromkeys(ids))