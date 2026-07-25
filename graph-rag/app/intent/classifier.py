"""LangChain intent classifier.

Chain: ChatPromptTemplate | ChatOpenAI(OpenAI-compatible) | PydanticOutputParser.

The LLM output is parsed into ClassifiedIntent and validated. If parsing or
intent validation fails, intent=UNSUPPORTED is returned (never free-form).
The LLM NEVER sees or generates Cypher here; it only emits structured JSON.
"""
from __future__ import annotations

import logging
import re
from typing import Awaitable

from langchain_core.output_parsers import PydanticOutputParser
from langchain_openai import ChatOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from ..core.exceptions import IntentClassificationError, new_request_id
from ..config import settings
from .prompts import build_prompt_template
from .schema import ClassifiedIntent, IntentType

logger = logging.getLogger("graph-rag.intent.classifier")

_FIR_ID_RE = re.compile(r"^\d+/\d{4}$")
_DIGITS_RE = re.compile(r"^\+?\d+$")
_VEHICLE_RE = re.compile(r"^KA-[A-Z0-9]{2}-[A-Z0-9]{2}-\d{4}$", re.IGNORECASE)


def _strip_invalid_entities(ci: ClassifiedIntent) -> ClassifiedIntent:
    e = ci.entities
    if e.fir_id and not _FIR_ID_RE.match(e.fir_id):
        e.fir_id = None
    if e.phone_number and not _DIGITS_RE.match(e.phone_number):
        e.phone_number = None
    if e.vehicle_number and not _VEHICLE_RE.match(e.vehicle_number):
        e.vehicle_number = None
    if ci.intent == IntentType.SEMANTIC_SEARCH and not (e.free_text or "").strip():
        ci.intent = IntentType.UNSUPPORTED
    return ci


def _build_llm() -> ChatOpenAI:
    base = settings.llm_base_url.rstrip("/")
    return ChatOpenAI(
        model="Qwen2.5-4B-Instruct",
        base_url=f"{base}/v1",
        api_key=settings.api_key or "not-used",
        temperature=0.0,
        top_p=1.0,
        max_tokens=512,
        timeout=settings.llm_timeout_s,
    )


class IntentClassifier:
    def __init__(self) -> None:
        self._chain = None
        self._parser = PydanticOutputParser(pydantic_object=ClassifiedIntent)

    def _get_chain(self):
        if self._chain is None:
            prompt = build_prompt_template()
            llm = _build_llm()
            self._chain = {"query": lambda x: x["query"]} | prompt | llm | self._parser
        return self._chain

    async def classify(self, query: str) -> ClassifiedIntent:
        rid = new_request_id()
        chain = self._get_chain()

        @retry(
            reraise=True,
            stop=stop_after_attempt(2),
            wait=wait_exponential(multiplier=1, min=1, max=4),
        )
        async def _call() -> ClassifiedIntent:
            try:
                result = await chain.ainvoke({"query": query})
                if isinstance(result, ClassifiedIntent):
                    return result
                # Some parsers return dict-like
                return ClassifiedIntent.model_validate(result)
            except Exception as exc:  # noqa: BLE001
                logger.warning("intent parse failed (rid=%s): %s", rid, exc)
                raise

        try:
            ci = await _call()
        except Exception:
            return ClassifiedIntent(intent=IntentType.UNSUPPORTED, confidence=0.0)

        if ci.intent == IntentType.UNSUPPORTED or ci.confidence < 0.5:
            return ClassifiedIntent(intent=IntentType.UNSUPPORTED, confidence=ci.confidence)

        return _strip_invalid_entities(ci)


intent_classifier = IntentClassifier()


def classify(query: str) -> Awaitable[ClassifiedIntent]:
    """Top-level awaitable for callers that want `await classify(q)`."""
    return intent_classifier.classify(query)
