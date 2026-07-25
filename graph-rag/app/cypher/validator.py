"""Validator: builds the whitelisted, type-checked params dict per intent.
Extra entity fields are dropped — never interpolated. Re-checks formats.
"""
from __future__ import annotations

import re

from ..core.exceptions import GraphRagError
from ..intent.schema import ClassifiedIntent, IntentType, INTENT_FIELDS
from ..graphstore.neo4j_client import neo4j_client

_FIR_ID_RE = re.compile(r"^\d+/\d{4}$")
_PHONE_RE = re.compile(r"^\+?\d{7,15}$")


def build_params_sync(intent: IntentType, entities) -> dict:
    allowed = INTENT_FIELDS.get(intent, set())
    params: dict = {}
    e = entities
    for field in allowed:
        val = getattr(e, field, None)
        if val is None or val == "":
            params[field] = None
            continue
        val = val.strip() if isinstance(val, str) else val
        if field == "fir_id":
            if not _FIR_ID_RE.match(val):
                raise GraphRagError("invalid_params", f"fir_id does not match format: {val}")
        elif field == "phone_number":
            if not _PHONE_RE.match(val):
                raise GraphRagError("invalid_params", f"phone_number invalid: {val}")
        elif field == "vehicle_number":
            if not re.match(r"^KA-[A-Z0-9]{2}-[A-Z0-9]{2}-\d{4}$", val, re.IGNORECASE):
                raise GraphRagError("invalid_params", f"vehicle_number invalid: {val}")
        params[field] = val

    if intent == IntentType.FIND_BY_PHONE_OR_VEHICLE:
        if not params.get("phone_number") and not params.get("vehicle_number"):
            raise GraphRagError("invalid_params", "phone_number or vehicle_number required")
    if intent == IntentType.FIND_SUSPECT_NETWORK and not params.get("gang_name"):
        raise GraphRagError("invalid_params", "gang_name required")
    if intent == IntentType.FIND_FIRS_BY_CRIME_TYPE and not params.get("crime_head"):
        raise GraphRagError("invalid_params", "crime_head required")
    if intent in (IntentType.FIND_FIR_BY_ID, IntentType.FIND_LINKED_FIRS) and not params.get("fir_id"):
        raise GraphRagError("invalid_params", "fir_id required")
    return params


async def resolve_fir_key(fir_id: str) -> str:
    cypher = (
        "MATCH (f:FIR {fir_id: $fir_id}) "
        "RETURN f.fir_key AS fir_key, f.police_station_name AS ps LIMIT 10"
    )
    rows = await neo4j_client.run_template(cypher, {"fir_id": fir_id})
    if not rows:
        raise GraphRagError("not_found", f"no FIR with fir_id={fir_id}")
    if len(rows) > 1:
        stations = ", ".join(r.get("ps", "") for r in rows)
        raise GraphRagError(
            "ambiguous_fir_id",
            f"fir_id={fir_id} exists at multiple stations: {stations}. "
            "Supply police_station to disambiguate.",
        )
    return rows[0]["fir_key"]


async def build_params(classified) -> dict[str, object]:
    base = build_params_sync(classified.intent, classified.entities)
    if classified.intent in (IntentType.FIND_FIR_BY_ID, IntentType.FIND_LINKED_FIRS):
        fir_id = base.pop("fir_id")
        fk = await resolve_fir_key(fir_id)
        base["fir_key"] = fk
    return base