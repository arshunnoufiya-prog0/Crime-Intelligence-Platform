"""GET /v1/profile/person/{name} — grounded offender profile (§11.5).

Structured rows come from the PERSON_PROFILE template (authoritative), the
summary is generated at the 'profile' preset and forbidden from computing
counts the rows do not state (§10.1).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..answer import synthesize
from ..deps import require_api_key
from ..graph import neo4j_client

router = APIRouter(prefix="/v1/profile", tags=["profile"])


@router.get("/person/{person_name}", dependencies=[Depends(require_api_key)])
async def person_profile(
    person_name: str,
    districts: str | None = Query(default=None),
    stations: str | None = Query(default=None),
):
    params = {
        "districts": [d.strip().upper() for d in districts.split(",") if d.strip()] if districts else None,
        "stations": [s.strip().upper() for s in stations.split(",") if s.strip()] if stations else None,
        "person_name": person_name.strip().upper(),
    }
    rows = await neo4j_client.run_template("PERSON_PROFILE", params)
    if not rows:
        return {"ok": True, "data": {"person_name": person_name, "rows": [], "summary": None}}

    summary = await synthesize.offender_profile(person_name, rows)
    return {
        "ok": True,
        "data": {
            "person_name": person_name,
            "rows": rows,
            "summary": summary,
        },
        "meta": {"row_count": len(rows)},
    }
