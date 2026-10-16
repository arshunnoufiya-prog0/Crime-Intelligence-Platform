"""Plan builder (spec §12.2): (intent, slots, scope) → execution Plan.

Maps to a Cypher template id + typed params (RBAC scope on every template —
§13), a LightRAG mode + query text (§9 mode table), whether centrality runs,
and the response shape. Only typed slots ever reach the parameter dict; the
question text itself is never interpolated into Cypher.
"""
from __future__ import annotations

from typing import cast

from ..schemas import IntentId, Plan, SlotPayload


def _base_params(scope) -> dict:
    return {
        "districts": list(scope.districts) if scope.districts else None,
        "stations": list(scope.stations) if scope.stations else None,
    }


def _person_or_gang(slots: SlotPayload) -> tuple[str | None, str | None]:
    person = slots.person_names[0] if slots.person_names else None
    if not person and slots.gang:
        person = slots.gang
    return person, slots.gang


def build_plan(intent: str, slots: SlotPayload, scope) -> Plan:
    params = _base_params(scope)
    lightrag_mode: str | None = None
    lightrag_query: str | None = None
    needs_centrality = False
    response_shape = "answer"
    template_id: str | None = intent

    person, gang = _person_or_gang(slots)

    if intent == "FIR_LOOKUP":
        params["fir_id"] = slots.fir_id
        params["station"] = slots.stations[0] if slots.stations else None
        lightrag_mode, lightrag_query = "local", f"FIR {slots.fir_id}"
    elif intent == "PERSON_PROFILE":
        params["person_name"] = person or ""
        lightrag_mode, lightrag_query = "local", person or ""
    elif intent == "PERSON_NETWORK":
        params["person_name"] = person or ""
        lightrag_mode, lightrag_query = "local", f"associates of {person or gang or ''}"
        needs_centrality, response_shape = True, "graph"
    elif intent == "PATTERN_SEARCH":
        params.update({
            "crime_code": slots.crime_type,
            "date_from": slots.date_from,
            "date_to": slots.date_to,
            "locality": slots.stations[0].replace("_PS", "").replace("_", " ") if slots.stations else None,
        })
        lightrag_mode, lightrag_query = "global", slots.free_text or slots.crime_type or "crime pattern"
    elif intent == "STATION_STATS":
        params.update({"date_from": slots.date_from, "date_to": slots.date_to})
        lightrag_mode, lightrag_query = "global", "station caseload overview"
    elif intent == "CRIME_TREND":
        params.update({
            "crime_code": slots.crime_type,
            "date_from": slots.date_from,
            "date_to": slots.date_to,
        })
        lightrag_mode, lightrag_query = "global", f"trend of {slots.crime_type or 'crimes'}"
    elif intent == "REPEAT_OFFENDERS":
        params["min_firs"] = 2
        lightrag_mode, lightrag_query = "global", "repeat offenders multiple FIRs"
    elif intent == "SHARED_IDENTIFIER":
        params["value"] = slots.phone or slots.vehicle
        if slots.vehicle:
            params["kind"] = "VEHICLE"
        elif slots.phone:
            params["kind"] = "PHONE"
        lightrag_mode, lightrag_query = "local", f"identifier {slots.phone or slots.vehicle}"
    elif intent == "GEO_CLUSTER":
        locality = (slots.free_text or "").upper() if slots.free_text else None
        params.update({"locality": locality, "lat": None, "lon": None, "radius_m": None})
        lightrag_mode, lightrag_query = "hybrid", slots.free_text or "crime clusters by area"
    elif intent == "MODUS_OPERANDI_MATCH":
        params.update({
            "crime_code": slots.crime_type,
            "stolen_item": None,
            "weapon": None,
        })
        lightrag_mode, lightrag_query = "mix", "similar modus operandi stolen property"
    elif intent == "EVIDENCE_TRAIL":
        params.update({
            "fir_id": slots.fir_id,
            "person_name": person,
        })
        lightrag_mode, lightrag_query = "mix", f"evidence of {person or slots.fir_id or ''}"
    elif intent == "FREEFORM_SEARCH":
        template_id = "FREEFORM_SEARCH"
        params["query_text"] = slots.free_text or ""
        lightrag_mode, lightrag_query = "hybrid", slots.free_text or ""

    return Plan(
        intent=cast(IntentId, intent),
        slots=slots,
        cypher_template_id=template_id,
        cypher_params=params,
        lightrag_mode=lightrag_mode,
        lightrag_query=lightrag_query,
        needs_centrality=needs_centrality,
        response_shape=response_shape,
    )
