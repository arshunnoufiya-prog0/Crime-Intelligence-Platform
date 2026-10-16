"""Async Neo4j client for the domain crime graph (spec §10.1, §12.3).

The ONLY path from the RAG service to Neo4j. Templates come from
cypher_templates.TEMPLATES — the client never builds Cypher strings.
A CypherTimeout degrades the request to the narrative source and is reported
in metadata; it never fails the request (§12.3).
"""
from __future__ import annotations

import asyncio
from typing import Any

from neo4j import AsyncGraphDatabase

from ..config import get_settings
from .cypher_templates import TEMPLATES


class CypherTimeout(Exception):
    code = "cypher_timeout"


class UnknownTemplateId(KeyError):
    code = "unknown_template"


_driver = None


def _get_driver():
    global _driver
    if _driver is None:
        settings = get_settings()
        _driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
    return _driver


async def close() -> None:
    global _driver
    if _driver is not None:
        await _driver.close()
        _driver = None


async def run_template(template_id: str, params: dict) -> list[dict]:
    if template_id not in TEMPLATES:
        raise UnknownTemplateId(template_id)
    return await run_cypher(TEMPLATES[template_id], params)


async def run_cypher(cypher: str, params: dict | None = None) -> list[dict]:
    settings = get_settings()
    driver = _get_driver()
    try:
        async with driver.session(database=settings.neo4j_database) as session:
            result = await asyncio.wait_for(
                session.run(cypher, params or {}).data(),
                timeout=settings.cypher_timeout_s,
            )
            return result
    except asyncio.TimeoutError as exc:
        raise CypherTimeout(f"cypher exceeded {settings.cypher_timeout_s}s (§12.3)") from exc


async def explain(template_id: str, params: dict) -> Any:
    """EXPLAIN plan for a template with the given params (§13 test gate).
    Planning happens without executing."""
    if template_id not in TEMPLATES:
        raise UnknownTemplateId(template_id)
    driver = _get_driver()
    settings = get_settings()
    async with driver.session(database=settings.neo4j_database) as session:
        result = await session.run("EXPLAIN " + TEMPLATES[template_id], params)
        await result.consume()
        return result.plan() if callable(getattr(result, "plan", None)) else None
