"""BAAI/bge-m3 embedding model, thread-pooled.
1024-dim. Lazy-loaded so service can start without torch installed when
embedder is unused (e.g., intent-classifier-only tests).
"""
from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Iterable

from ..config import settings

logger = logging.getLogger("graph-rag.embedder")


class Embedder:
    def __init__(self) -> None:
        self._model = None
        self._lock = asyncio.Lock()
        self._pool: ThreadPoolExecutor | None = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            logger.info("loading embedding model %s on %s", settings.embed_model, settings.embed_device)
            self._model = SentenceTransformer(settings.embed_model, device=settings.embed_device)
        return self._model

    async def _ensure_pool(self) -> ThreadPoolExecutor:
        async with self._lock:
            if self._pool is None:
                self._pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="embed")
        return self._pool

    async def embed_documents(self, texts: Iterable[str]) -> list[list[float]]:
        texts = list(texts)
        pool = await self._ensure_pool()
        loop = asyncio.get_running_loop()
        def _work():
            model = self._load()
            vecs = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
            return [v.tolist() for v in vecs]
        return await loop.run_in_executor(pool, _work)

    async def embed_query(self, text: str) -> list[float]:
        pool = await self._ensure_pool()
        loop = asyncio.get_running_loop()
        def _work():
            model = self._load()
            vec = model.encode([text], convert_to_numpy=True, normalize_embeddings=True)
            return vec[0].tolist()
        return await loop.run_in_executor(pool, _work)

    async def close(self) -> None:
        if self._pool is not None:
            self._pool.shutdown(wait=False)
            self._pool = None


embedder = Embedder()
