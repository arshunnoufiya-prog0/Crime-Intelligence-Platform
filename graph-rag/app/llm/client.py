"""HTTP/2 client to the inference /v1/chat/completions endpoint (OpenAI-compatible).
Used by the intent classifier's underlying LangChain binding AND directly by the
summarizer for the final grounded answer (next module).
"""
from __future__ import annotations

import json
import logging
from typing import AsyncIterator

import httpx

from ..config import settings

logger = logging.getLogger("graph-rag.llm.client")

LLM_BASE = settings.llm_base_url.rstrip("/")
CHAT_URL = f"{LLM_BASE}/v1/chat/completions"


class LLMClient:
    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def open(self) -> None:
        self._client = httpx.AsyncClient(
            http2=True,
            timeout=httpx.Timeout(settings.llm_timeout_s, connect=10.0),
        )

    async def close(self) -> None:
        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception:
                pass
        self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("LLMClient not opened; call .open() first")
        return self._client

    async def chat(self, messages: list[dict], sampling: dict | None = None) -> str:
        payload = {
            "model": "Qwen2.5-4B-Instruct",
            "messages": messages,
            "temperature": 0.0,
            "top_k": 1,
            "top_p": 1.0,
            "stream": False,
        }
        if sampling:
            payload.update(sampling)
        try:
            r = await self.client.post(CHAT_URL, json=payload)
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"]
        except httpx.HTTPError as exc:
            logger.error("LLM chat error: %s", exc)
            raise

    async def stream_chat(self, messages: list[dict], sampling: dict | None = None) -> AsyncIterator[str]:
        payload = {
            "model": "Qwen2.5-4B-Instruct",
            "messages": messages,
            "temperature": 0.0,
            "top_k": 1,
            "top_p": 1.0,
            "stream": True,
        }
        if sampling:
            payload.update(sampling)
        try:
            async with self.client.stream("POST", CHAT_URL, json=payload) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        return
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    choices = chunk.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {}).get("content") or ""
                    if delta:
                        yield delta
        except httpx.HTTPError as exc:
            logger.error("LLM stream error: %s", exc)
            raise


llm_client = LLMClient()
