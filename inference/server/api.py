import time
import uuid

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from .config import settings
from .sampling import validate_sampling

LLAMA_BASE = f"http://{settings.host}:{settings.port}"
CREATIVE_LIMIT = 0.5

app = FastAPI(title="inference-proxy", version="1.0.0")
client: httpx.AsyncClient | None = None


@app.on_event("startup")
async def _startup() -> None:
    global client
    client = httpx.AsyncClient(http2=True, timeout=httpx.Timeout(120.0, connect=10.0))


@app.on_event("shutdown")
async def _shutdown() -> None:
    global client
    if client is not None:
        await client.aclose()
        client = None


def _structured_error(code: str, message: str, status: int, request_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": message, "code": code, "request_id": request_id},
    )


def _new_request_id() -> str:
    return uuid.uuid4().hex


@app.get("/health")
async def health() -> JSONResponse:
    rid = _new_request_id()
    if client is None:
        return _structured_error("not_ready", "client not initialized", 503, rid)
    try:
        r = await client.get(f"{LLAMA_BASE}/health", timeout=5.0)
        return JSONResponse({"status": "ok", "upstream": r.status_code, "request_id": rid})
    except Exception as exc:  # noqa: BLE001
        return _structured_error("upstream_down", str(exc), 503, rid)


def _apply_sampling(body: dict, allow_creative: bool | None) -> dict:
    sampling = {}
    for k in ("temperature", "top_k", "top_p", "repeat_penalty", "min_p"):
        if k in body:
            sampling[k] = body[k]
    try:
        return validate_sampling(sampling, bool(allow_creative))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def _inject_sampling(body: dict, normalized: dict) -> dict:
    body = dict(body)
    body.update(normalized)
    return body


@app.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    x_allow_creative: str | None = Header(default=None, alias="X-Allow-Creative"),
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
):
    rid = x_request_id or _new_request_id()
    body = await request.json()
    stream = bool(body.get("stream", False))
    allow_creative = (x_allow_creative is not None) and (x_allow_creative.lower() in ("1", "true", "yes"))
    try:
        normalized = _apply_sampling(body, allow_creative)
    except HTTPException as exc:
        return _structured_error("bad_sampling", exc.detail, exc.status_code, rid)
    payload = _inject_sampling(body, normalized)

    if settings.api_key:
        body.setdefault("api_key", settings.api_key)

    start = time.monotonic()
    headers = {"X-Request-ID": rid}

    if stream:
        if client is None:
            return _structured_error("not_ready", "client not initialized", 503, rid)

        async def gen() -> bytes:
            try:
                async with client.stream("POST", f"{LLAMA_BASE}/v1/chat/completions", json=payload, headers=headers) as r:
                    if r.status_code != 200:
                        raw = await r.aread()
                        yield _error_bytes(rid, "upstream_error", f"upstream {r.status_code}: {raw.decode('utf-8','replace')[:200]}")
                        return
                    async for chunk in r.aiter_raw():
                        if chunk:
                            yield chunk
            except httpx.HTTPError as exc:
                yield _error_bytes(rid, "upstream_error", str(exc))

        return StreamingResponse(
            gen(),
            media_type="text/event-stream",
            headers={"X-Request-ID": rid, "Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    if client is None:
        return _structured_error("not_ready", "client not initialized", 503, rid)
    try:
        r = await client.post(f"{LLAMA_BASE}/v1/chat/completions", json=payload, headers=headers)
        latency = int((time.monotonic() - start) * 1000)
        resp_headers = {"X-Request-ID": rid, "X-Latency-Ms": str(latency)}
        if r.status_code != 200:
            return JSONResponse(
                status_code=r.status_code,
                content={"error": f"upstream error: {r.text[:300]}", "code": "upstream_error", "request_id": rid},
                headers=resp_headers,
            )
        return JSONResponse(content=r.json(), headers=resp_headers)
    except httpx.HTTPError as exc:
        return _structured_error("upstream_error", str(exc), 502, rid)


def _error_bytes(rid: str, code: str, message: str) -> bytes:
    payload = f'{{"error": "{message}", "code": "{code}", "request_id": "{rid}"}}'.encode("utf-8")
    return b"event: error\ndata: " + payload + b"\n\n"


@app.get("/metrics")
async def metrics(x_request_id: str | None = Header(default=None, alias="X-Request-ID")) -> JSONResponse:
    rid = x_request_id or _new_request_id()
    return JSONResponse({"service": "inference-proxy", "alive": True, "request_id": rid})
