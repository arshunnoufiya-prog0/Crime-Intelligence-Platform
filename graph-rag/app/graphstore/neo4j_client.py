"""Async Neo4j client — the ONLY module that talks to Neo4j.

Wraps the official async neo4j driver. All graph + vector operations live
here. Driver exceptions are normalised into GraphStoreError so raw
tracebacks never reach the client.
"""
from __future__ import annotations

import logging
from typing import Any

from neo4j import AsyncGraphDatabase
from neo4j.exceptions import Neo4jError, AuthError, ServiceUnavailable, ClientError

from ..config import settings
from .schema import CONSTRAINT_CYPHER, INDEX_CYPHER, VECTOR_INDEX_CYPHER

logger = logging.getLogger("graph-rag.neo4j_client")


class GraphStoreError(RuntimeError):
    """Structured graph-store error. `to_dict()` yields a client-safe payload."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def to_dict(self) -> dict[str, str]:
        return {"error": self.message, "code": self.code}


def _wrap(exc: Exception) -> GraphStoreError:
    if isinstance(exc, (ServiceUnavailable,)):
        return GraphStoreError("neo4j_unavailable", f"Neo4j unavailable: {exc}")
    if isinstance(exc, AuthError):
        return GraphStoreError("neo4j_auth", "Neo4j authentication failed")
    if isinstance(exc, ClientError):
        return GraphStoreError("neo4j_client", f"Neo4j client error: {exc}")
    if isinstance(exc, Neo4jError):
        return GraphStoreError("neo4j_error", f"Neo4j error: {exc}")
    return GraphStoreError("neo4j_unknown", f"Unexpected Neo4j error: {exc}")


def _node_to_dict(node: Any) -> dict[str, Any]:
    """Serialize a neo4j Node to a plain dict (incl. label + properties)."""
    if node is None:
        return {}
    try:
        labels = list(node.labels)
    except AttributeError:
        labels = []
    props = dict(node) if hasattr(node, "items") else {}
    return {"label": labels[0] if labels else None, "properties": props}


def _row_to_dict(record: Any) -> Any:
    """Recursively convert neo4j record values to JSON-friendly dicts."""
    if record is None:
        return None
    if hasattr(record, "labels") and callable(getattr(record, "labels", None)):
        return _node_to_dict(record)
    if hasattr(record, "items") and callable(getattr(record, "items", None)):
        out: dict[str, Any] = {}
        for k, v in record.items():
            out[k] = _row_to_dict(v)
        return out
    if isinstance(record, (list, tuple)):
        return [_row_to_dict(x) for x in record]
    return record


class Neo4jClient:
    def __init__(self) -> None:
        self._driver = None
        self._database = settings.neo4j_database

    async def connect(self) -> None:
        self._driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        try:
            await self._driver.verify_connectivity()
        except Exception as exc:  # noqa: BLE001
            await self.close()
            raise _wrap(exc) from exc
        logger.info("Neo4j driver connected to %s", settings.neo4j_uri)

    async def close(self) -> None:
        if self._driver is not None:
            try:
                await self._driver.close()
            except Exception:
                pass
            self._driver = None

    @property
    def driver(self):
        if self._driver is None:
            raise GraphStoreError("neo4j_not_connected", "Neo4j driver not initialised")
        return self._driver

    async def _run(self, cypher: str, params: dict[str, Any] | None = None) -> list[Any]:
        try:
            result = await self._driver.execute_query(
                cypher,
                parameters_=params or {},
                database_=self._database,
                routing_="r",
            )
            records = result.records if hasattr(result, "records") else list(result)
            return [_row_to_dict(r) for r in records]
        except Exception as exc:  # noqa: BLE001
            raise _wrap(exc) from exc

    async def run_template(self, cypher: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        return await self._run(cypher, params)

    async def vector_search(
        self, query_embedding: list[float], top_k: int = 10, score_threshold: float | None = None
    ) -> list[dict[str, Any]]:
        threshold = settings.similarity_threshold if score_threshold is None else score_threshold
        cypher = (
            "CALL db.index.vector.queryNodes($index_name, $top_k, $vec) "
            "YIELD node, score "
            "WHERE score >= $threshold "
            "RETURN node, score ORDER BY score DESC"
        )
        params = {
            "index_name": settings.vector_index_name,
            "top_k": int(top_k),
            "vec": list(query_embedding),
            "threshold": float(threshold),
        }
        try:
            return await self._run(cypher, params)
        except GraphStoreError as exc:
            # Vector index may not be populated; surface empty result on no-context rather than
            # a hard error, but propagate genuine infra failures.
            if exc.code == "neo4j_client":
                return []
            raise

    async def get_subgraph(self, fir_key: str, max_hops: int | None = None) -> list[dict[str, Any]]:
        hops = int(settings.subgraph_max_hops if max_hops is None else max_hops)
        limit = int(settings.subgraph_max_nodes)
        cypher = (
            "MATCH (root:FIR {fir_key: $fir_key}) "
            "CALL { "
            "  WITH root "
            "  MATCH path = (root)-[*1.." + str(hops) + "]-(connected) "
            "  RETURN nodes(path) AS ns, relationships(path) AS rs "
            "} "
            "UNWIND ns AS n "
            "WITH collect(DISTINCT n) AS nodes, collect(DISTINCT rs) AS rs_lists "
            "UNWIND rs_lists AS rs "
            "UNWIND rs AS r "
            "WITH nodes, collect(DISTINCT r) AS rels "
            "RETURN nodes, rels LIMIT $limit"
        )
        params = {"fir_key": fir_key, "limit": limit}
        return await self._run(cypher, params)

    async def get_subgraph_rows(self, fir_key: str, max_hops: int | None = None) -> dict[str, Any]:
        rows = await self.get_subgraph(fir_key, max_hops)
        nodes: list[dict[str, Any]] = []
        rels: list[dict[str, Any]] = []
        for row in rows:
            ns = row.get("nodes") or []
            for n in ns:
                d = _row_to_dict(n)
                if d:
                    nodes.append(d)
            for r in row.get("rels") or []:
                try:
                    rels.append({
                        "source": r.start_node["fir_key"] if r.start_node and "fir_key" in dict(r.start_node) else None,
                        "target": r.end_node["fir_key"] if r.end_node and "fir_key" in dict(r.end_node) else None,
                        "type": r.type,
                    })
                except Exception:  # noqa: BLE001
                    continue
        # Deduplicate by node label+properties (keyed on natural key if present)
        seen: set[str] = set()
        uniq_nodes: list[dict[str, Any]] = []
        for n in nodes:
            props = n.get("properties", {}) or {}
            key = props.get("fir_key") or props.get("name") or props.get("number") or props.get("plate") or props.get("account_id") or props.get("person_key") or id(n)
            if key in seen:
                continue
            seen.add(key)
            uniq_nodes.append(n)
        return {"nodes": uniq_nodes, "edges": rels}

    async def write_batch(self, cypher: str, rows: list[dict[str, Any]]) -> None:
        try:
            await self._driver.execute_query(
                cypher,
                parameters_={"rows": rows},
                database_=self._database,
                routing_="w",
            )
        except Exception as exc:  # noqa: BLE001
            raise _wrap(exc) from exc

    async def setup_schema(self) -> dict[str, int]:
        counts = {"constraints": 0, "indexes": 0, "vector_indexes": 0}
        for c in CONSTRAINT_CYPHER:
            await self._run(c)
            counts["constraints"] += 1
        for c in INDEX_CYPHER:
            await self._run(c)
            counts["indexes"] += 1
        await self._run(VECTOR_INDEX_CYPHER)
        counts["vector_indexes"] += 1
        return counts


neo4j_client = Neo4jClient()
