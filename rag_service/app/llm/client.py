"""LLM client for llama-gen :8080 (spec §6, §11.4, §1.3).

Reasoning is routed away from the answer channel on both paths:
  1. server-side separation — when a VERIFIED --reasoning-format is active the
     SSE delta carries `reasoning_content`, which is yielded as ('reasoning', …);
  2. the mandatory fallback — the ReasoningSplitter state machine (§1.3)
     applied to `delta.content` regardless, so the client stays correct even
     if the server is swapped.

`cache_prompt: true` on EVERY generation request (§11.4). Thinking is disabled
for deterministic sub-tasks via `chat_template_kwargs: {"enable_thinking":
false}` — the mechanism documented on the Qwen3.5 model card (§1.3/§1.6).

Upstream failures raise LLMUpstreamError so routes can surface a typed 503
with a machine-readable code (§0.4) — never a silent fallback.
"""
from __future__ import annotations

import json
from typing import AsyncGenerator

import httpx

from .reasoning import ReasoningSplitter
from .tokens import count_tokens
from ..config import Settings, get_settings


class LLMUpstreamError(RuntimeError):
    code = "llm_upstream_unavailable"


_client: httpx.AsyncClient | None = None


def _client_for(settings: Settings) -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(180.0, connect=10.0),
            headers={"Accept": "text/event-stream"},
        )
    return _client


async def close() -> None:
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


def _payload(messages: list[dict], sampling: dict, *, stream: bool, thinking: bool) -> dict:
    payload: dict = {
        "model": "qwen35-4b",
        "messages": messages,
        "stream": stream,
        "cache_prompt": True,
        "temperature": sampling.get("temperature", 0.7),
        "top_p": sampling.get("top_p", 0.9),
        "top_k": sampling.get("top_k", 20),
        "presence_penalty": sampling.get("presence_penalty", 0.0),
        "repeat_penalty": sampling.get("repeat_penalty", 1.0),
    }
    if "min_p" in sampling:
        payload["min_p"] = sampling["min_p"]
    if "n_predict" in sampling:
        payload["n_predict"] = sampling["n_predict"]
    if not thinking:
        payload["chat_template_kwargs"] = {"enable_thinking": False}
    return payload


async def chat(messages: list[dict], sampling: dict, *, thinking: bool) -> str:
    settings = get_settings()
    client = _client_for(settings)
    try:
        r = await client.post(
            settings.llm_chat_url,
            json=_payload(messages, sampling, stream=False, thinking=thinking),
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except httpx.HTTPError as exc:
        raise LLMUpstreamError(f"llama-gen upstream error: {exc}") from exc
    except (KeyError, IndexError, ValueError) as exc:
        raise LLMUpstreamError(f"malformed upstream completion payload: {exc}") from exc


async def stream(messages: list[dict], sampling: dict, *, thinking: bool) -> AsyncGenerator[tuple[str, str], None]:
    """Yield ('reasoning'|'token', text) events until the stream ends."""
    settings = get_settings()
    client = _client_for(settings)
    splitter = ReasoningSplitter()
    try:
        async with client.stream(
            "POST",
            settings.llm_chat_url,
            json=_payload(messages, sampling, stream=True, thinking=thinking),
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if not data or data == "[DONE]":
                    if data == "[DONE]":
                        break
                    continue
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                reasoning = delta.get("reasoning_content")
                if reasoning:
                    yield ("reasoning", reasoning)
                content = delta.get("content")
                if content:
                    for event in splitter.feed(content):
                        yield event
    except httpx.HTTPError as exc:
        raise LLMUpstreamError(f"llama-gen stream error: {exc}") from exc
    finally:
        for event in splitter.close():
            yield event


async def count_tokens_for(text: str) -> int:
    """Exact count via the serving tokenizer (§11.1), against the embed
    instance (:8081) which runs the same llama-server binary."""
    settings = get_settings()
    client = _client_for(settings)
    return await count_tokens(client, settings.embed_tokenize_url, text)
