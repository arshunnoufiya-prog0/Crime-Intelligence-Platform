"""Admin ingest trigger endpoint — guarded by API key."""
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from ....config import get_settings
from ....ingest.pipeline import run_ingest
from ....core.exceptions import GraphRagError

router = APIRouter(tags=["ingest"])


class IngestRequest(BaseModel):
    json_path: str = "../data/bengaluru_40ps_1000_firs.json"


async def _auth(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    settings = get_settings()
    if not settings.api_key:
        return  # no auth if not configured
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail={"error": "invalid api key", "code": "unauthorized"})


@router.post("/ingest")
async def trigger_ingest(
    req: IngestRequest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    _auth=Depends(_auth),
):
    try:
        result = await run_ingest(req.json_path)
        return {"status": "ok", **result}
    except GraphRagError as exc:
        raise HTTPException(status_code=500, detail={"error": exc.code, "message": exc.message})
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail={"error": "internal_error", "message": str(exc)})