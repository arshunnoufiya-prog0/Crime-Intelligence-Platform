"""Intent classification + slot extraction (spec §12.1).

Constrained prompts, temperature 0, thinking OFF — a classifier that
deliberates for 400 tokens before emitting one label wastes the latency
budget (§11.5). On any unrecognized label the intent falls back to
FREEFORM_SEARCH rather than retrying (§12.1). Slots are validated against
the schema-report ground truth: stations checked against the real 40-station
list, fir_id checked against the derived id_regex — invented values are
silently discarded (§12.1).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ingest"))

import _schema_constants as SC  # noqa: E402
import normalize as N  # noqa: E402

from ..llm import client, prompts, sampling  # noqa: E402
from ..schemas import SlotPayload  # noqa: E402

INTENTS = (
    "FIR_LOOKUP", "PERSON_PROFILE", "PERSON_NETWORK", "PATTERN_SEARCH", "STATION_STATS",
    "CRIME_TREND", "REPEAT_OFFENDERS", "SHARED_IDENTIFIER", "GEO_CLUSTER",
    "MODUS_OPERANDI_MATCH", "EVIDENCE_TRAIL", "FREEFORM_SEARCH",
)
FALLBACK_INTENT = "FREEFORM_SEARCH"

VALID_STATION_CODES = {N.code_name(s) for s in SC.POLICE_STATIONS}
VALID_CRIME_CODES = {N.code_name(c) for c in SC.CRIME_HEADS}
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


async def classify(question: str) -> str:
    preset = sampling.sampling_for("intent")
    out = await client.chat(prompts.build_intent_prompt(question), preset, thinking=False)
    label = out.strip().strip(".").strip().upper()
    if label not in INTENTS:
        return FALLBACK_INTENT
    return label


def _parse_json_block(text: str) -> dict | None:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


def _validate_stations(raw: list | None) -> list[str]:
    out = []
    for s in raw or []:
        code = N.code_name(s)
        if code in VALID_STATION_CODES and code not in out:
            out.append(code)
    return out


def _validate_date(value: str | None) -> str | None:
    if not value:
        return None
    value = str(value).strip()
    return value if _DATE_RE.match(value) else None


def _validate_fir_id(value: str | None) -> str | None:
    if not value:
        return None
    value = str(value).strip()
    return value if re.match(SC.ID_REGEX, value) else None


def slots_from_payload(data: dict) -> SlotPayload:
    """Typed-slot validation against schema-report ground truth (§12.1)."""
    crime = N.code_name(data.get("crime_type")) if data.get("crime_type") else None
    if crime and crime not in VALID_CRIME_CODES:
        crime = None
    return SlotPayload(
        person_names=[N.normalize_text(p) for p in (data.get("person_names") or []) if p][:3],
        stations=_validate_stations(data.get("stations")),
        date_from=_validate_date(data.get("date_from")),
        date_to=_validate_date(data.get("date_to")),
        crime_type=crime,
        vehicle=N.normalize_token(data.get("vehicle")) or None,
        phone=N.normalize_token(data.get("phone")) or None,
        fir_id=_validate_fir_id(data.get("fir_id")),
        gang=N.normalize_text(data.get("gang")) or None,
        free_text=(data.get("free_text") or "").strip() or None,
    )


async def extract_slots(question: str) -> SlotPayload:
    preset = sampling.sampling_for("slots")
    messages = prompts.build_slot_prompt(SC.POLICE_STATIONS, SC.CRIME_HEADS, question)
    out = await client.chat(messages, preset, thinking=False)
    data = _parse_json_block(out)
    if data is None:
        return SlotPayload()
    return slots_from_payload(data)
