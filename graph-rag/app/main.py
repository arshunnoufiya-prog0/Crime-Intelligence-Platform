"""FastAPI app factory + lifespan."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .config import settings
from .api.v1.router import router as v1_router
from .dependencies import shutdown, get_settings

# structlog setup
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)
logger = structlog.get_logger("graph-rag")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("starting graph-rag service", port=settings.port)
    yield
    logger.info("shutting down...")
    await shutdown()
    logger.info("shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(title="crime-graph-rag", version="1.0.0", lifespan=lifespan)

    @app.exception_handler(Exception)
    async def global_exc_handler(request: Request, exc: Exception):
        logger.exception("unhandled error", path=request.url.path)
        return JSONResponse(
            status_code=500,
            content={"error": "internal server error", "code": "internal_error", "request_id": ""},
        )

    app.include_router(v1_router)
    return app


app = create_app()