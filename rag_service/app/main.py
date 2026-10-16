"""FastAPI RAG service — app factory + lifespan (spec §9).

The LightRAG engine is instantiated EXACTLY ONCE in the lifespan and stored
on app.state (§9): constructing per request opens storage handles and leaks
file descriptors until the service dies.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .config import get_settings
from .llm import client as llm_client
from .retrieval import lightrag_engine
from .routes import graph, health, profile, query

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ksp-iis-rag")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("starting ksp-iis rag service (working_dir=%s)", settings.lightrag_working_dir)
    await lightrag_engine.initialize(app)
    yield
    await lightrag_engine.finalize(app)
    await llm_client.close()
    from .graph import neo4j_client

    await neo4j_client.close()
    logger.info("shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(title="ksp-iis-rag", version="1.0.0", lifespan=lifespan)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        logger.exception("unhandled error on %s", request.url.path)
        return JSONResponse(
            status_code=503,
            content={"ok": False, "error": {"code": "internal_error", "message": "internal server error"}},
        )

    app.include_router(health.router)
    app.include_router(query.router)
    app.include_router(graph.router)
    app.include_router(profile.router)
    return app


app = create_app()
