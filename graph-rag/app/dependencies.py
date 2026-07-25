"""FastAPI dependency providers — singletons for settings, clients, etc.
Lazily initialised once per process via lifespan in main.py.
"""
from __future__ import annotations

from .config import settings as _settings_singleton
from .graphstore.neo4j_client import Neo4jClient
from .embedding.embedder import Embedder
from .llm.client import LLMClient

_neo4j: Neo4jClient | None = None
_embedder: Embedder | None = None
_llm: LLMClient | None = None


def get_settings():
    """Return the module-level settings singleton."""
    return _settings_singleton


async def get_neo4j() -> Neo4jClient:
    global _neo4j
    if _neo4j is None:
        _neo4j = Neo4jClient()
        await _neo4j.connect()
    return _neo4j


async def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        _embedder = Embedder()
    return _embedder


async def get_llm_client() -> LLMClient:
    global _llm
    if _llm is None:
        _llm = LLMClient()
        await _llm.open()
    return _llm


async def shutdown() -> None:
    global _neo4j, _embedder, _llm
    if _neo4j:
        await _neo4j.close()
    if _embedder:
        await _embedder.close()
    if _llm:
        await _llm.close()
    _neo4j = _embedder = _llm = None