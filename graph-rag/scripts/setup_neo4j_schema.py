#!/usr/bin/env python3
"""Neo4j schema setup: run constraints, indexes, and the vector index.

Idempotent (IF NOT EXISTS). Run once after Neo4j is up.
"""
import asyncio
import logging

from app.graphstore.schema import (
    CONSTRAINT_CYPHER,
    INDEX_CYPHER,
    VECTOR_INDEX_CYPHER,
)
from app.graphstore.neo4j_client import neo4j_client
from app.config import settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("setup_neo4j_schema")


async def main() -> None:
    logger.info("Connecting to Neo4j at %s", settings.neo4j_uri)
    await neo4j_client.connect()

    logger.info("Applying constraints...")
    for c in CONSTRAINT_CYPHER:
        await neo4j_client._run(c)
    logger.info("Applied %d constraints", len(CONSTRAINT_CYPHER))

    logger.info("Applying indexes...")
    for i in INDEX_CYPHER:
        await neo4j_client._run(i)
    logger.info("Applied %d indexes", len(INDEX_CYPHER))

    logger.info("Applying vector index...")
    await neo4j_client._run(VECTOR_INDEX_CYPHER)
    logger.info("Vector index ready")

    await neo4j_client.close()
    logger.info("Schema setup complete")


if __name__ == "__main__":
    asyncio.run(main())