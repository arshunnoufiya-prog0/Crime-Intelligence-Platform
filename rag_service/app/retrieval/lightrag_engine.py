"""LightRAG engine wiring (spec §2.2, §9).

Binding decision (§2.2): the KG is built deterministically from the structured
JSON and injected via insert_custom_kg — ZERO LLM calls at index time. The
module-level INDEXING_IN_PROGRESS flag makes llm_model_func RAISE while
indexing, so the guarantee is enforced rather than merely intended (§9).

VERIFY PENDING (§3.2): the real signatures of LightRAG.__init__,
ainsert_custom_kg/insert_custom_kg, aquery/query, initialize_storages and
QueryParam must be dumped from the installed lightrag-hku into
artifacts/verification.md and gate this wiring. Until then this module:
  * resolves the insert entrypoint at runtime (ainsert_custom_kg preferred,
    else insert_custom_kg; if BOTH absent → BLOCKED, never falls back to
    insert() — §3.2);
  * awaits initialize_storages()/finalize_storages() only when they exist.

Storage split (§2.3): NetworkX in-process for the LightRAG KG, Qdrant for
vectors, Neo4j NEVER touched by LightRAG.
"""
from __future__ import annotations

import asyncio
from typing import Any

import httpx

from ..config import get_settings

INDEXING_IN_PROGRESS = False
llm_calls_during_indexing = 0


class LlmCalledDuringIndexing(RuntimeError):
    """Raised when the zero-LLM-indexing contract is violated (§2.2/§9)."""


async def llm_model_func(prompt: str, system_prompt: str | None = None,
                         history_messages: list | None = None, **kwargs) -> str:
    """Query-path-only LLM callable hitting llama-gen :8080 (§9).

    OpenAI-compatible chat completions; used ONLY on the query path.
    Raises LlmCalledDuringIndexing while INDEXING_IN_PROGRESS is set.
    """
    global llm_calls_during_indexing
    if INDEXING_IN_PROGRESS:
        llm_calls_during_indexing += 1
        raise LlmCalledDuringIndexing(
            "llm_model_func invoked during indexing — zero-LLM-indexing "
            "contract violated (§2.2/§9)"
        )
    settings = get_settings()
    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    for m in history_messages or []:
        messages.append({"role": m.get("role", "user"), "content": m.get("content", "")})
    messages.append({"role": "user", "content": prompt})
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
        r = await client.post(settings.llm_chat_url, json={
            "model": "qwen35-4b",
            "messages": messages,
            "stream": False,
            "cache_prompt": True,
        })
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


async def embedding_func(texts: list[str]) -> list[list[float]]:
    """Wraps llama-embed :8081 (§7). Batch ≤16 (§10.2); asserts every vector
    is EMBED_DIM (1024) long — a silent mismatch presents as 'retrieval
    returns nothing', so it fails loud instead."""
    settings = get_settings()
    out: list[list[float]] = []
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
        for i in range(0, len(texts), 16):
            batch = texts[i:i + 16]
            r = await client.post(settings.embed_url, json={"input": batch, "model": "bge-m3"})
            r.raise_for_status()
            data = r.json()["data"]
            if len(data) != len(batch):
                raise RuntimeError(
                    f"embedding count mismatch: sent {len(batch)}, got {len(data)} (§10.2)"
                )
            for item in data:
                vec = item["embedding"]
                if len(vec) != settings.embed_dim:
                    raise RuntimeError(
                        f"embedding dim {len(vec)} != {settings.embed_dim} (§7) — "
                        "silent dim mismatch against the Qdrant collection is the "
                        "classic 'retrieval returns nothing' failure"
                    )
                out.append(vec)
    return out


def create_engine() -> Any:
    """LightRAG instance per §9 config. Instantiate ONCE in the FastAPI
    lifespan and store on app.state — constructing per request leaks file
    descriptors (§9)."""
    settings = get_settings()
    from lightrag import LightRAG
    from lightrag.utils import EmbeddingFunc

    return LightRAG(
        working_dir=settings.lightrag_working_dir,
        kv_storage=settings.lightrag_kv_storage,
        vector_storage=settings.lightrag_vector_storage,
        graph_storage=settings.lightrag_graph_storage,
        doc_status_storage=settings.lightrag_doc_status_storage,
        llm_model_func=llm_model_func,
        embedding_func=EmbeddingFunc(
            embedding_dim=settings.embed_dim,
            max_token_size=settings.embed_max_tokens,
            func=embedding_func,
        ),
        chunk_token_size=settings.chunk_token_size,
        chunk_overlap_token_size=settings.chunk_overlap_token_size,
    )


async def open_engine() -> Any:
    """Create + initialize a standalone engine (ingest path, no FastAPI app)."""
    rag = create_engine()
    init = getattr(rag, "initialize_storages", None)
    if init is not None:
        result = init()
        if asyncio.iscoroutine(result):
            await result
    return rag


async def close_engine(rag: Any) -> None:
    if rag is None:
        return
    fin = getattr(rag, "finalize_storages", None)
    if fin is not None:
        result = fin()
        if asyncio.iscoroutine(result):
            await result


async def initialize(app: Any) -> None:
    """Lifespan startup hook (§9): build engine once, init storages if the
    installed version requires it (confirmed from §3.2's dump)."""
    app.state.rag = await open_engine()


async def finalize(app: Any) -> None:
    await close_engine(getattr(app.state, "rag", None))
    app.state.rag = None


async def insert_custom_kg(engine: Any, payload: dict) -> Any:
    """§3.2: prefer ainsert_custom_kg, else insert_custom_kg; both absent →
    BLOCKED — never fall back to insert()."""
    fn = getattr(engine, "ainsert_custom_kg", None)
    if fn is None:
        fn = getattr(engine, "insert_custom_kg", None)
    if fn is None:
        raise RuntimeError(
            "BLOCKED: Step 8 — neither ainsert_custom_kg nor insert_custom_kg "
            "exists on the installed LightRAG (§3.2). Record the signature "
            "dump in artifacts/verification.md and adapt; do not fall back to insert()."
        )
    result = fn(payload)
    if asyncio.iscoroutine(result):
        result = await result
    return result


async def query(engine: Any, mode: str, query_text: str, **param_kwargs: Any) -> Any:
    """§9 query modes: local/global/hybrid/mix/naive — picked by the intent
    router, never exposed to the end user."""
    from lightrag import QueryParam

    param = QueryParam(mode=mode, **param_kwargs)
    fn = getattr(engine, "aquery", None)
    if fn is None:
        fn = getattr(engine, "query", None)
    if fn is None:
        raise RuntimeError("BLOCKED: neither aquery nor query on installed LightRAG (§3.2)")
    result = fn(query_text, param=param)
    if asyncio.iscoroutine(result):
        result = await result
    return result
