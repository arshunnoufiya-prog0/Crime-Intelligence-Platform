from __future__ import annotations

import enum
from pydantic import BaseModel, Field


class IntentType(str, enum.Enum):
    FIND_FIR_BY_ID = "find_fir_by_id"
    FIND_FIRS_BY_CRIME_TYPE = "find_firs_by_crime_type"
    FIND_FIRS_BY_LOCATION = "find_firs_by_location"
    FIND_LINKED_FIRS = "find_linked_firs"           # ai_metadata.linked_firs
    FIND_SUSPECT_NETWORK = "find_suspect_network"   # gang / associates
    FIND_BY_PHONE_OR_VEHICLE = "find_by_digital_evidence"
    SEMANTIC_SEARCH = "semantic_search"             # falls back to vector index
    UNSUPPORTED = "unsupported"


class ExtractedEntities(BaseModel):
    fir_id: str | None = None
    crime_head: str | None = None
    district: str | None = None
    police_station: str | None = None
    phone_number: str | None = None
    vehicle_number: str | None = None
    gang_name: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    free_text: str | None = None   # only populated for SEMANTIC_SEARCH


class ClassifiedIntent(BaseModel):
    intent: IntentType
    entities: ExtractedEntities = Field(default_factory=ExtractedEntities)
    confidence: float = 0.0


# Whitelist of which entity fields each intent may consume.
# Keys not listed here are stripped by validator.build_params.
INTENT_FIELDS: dict[IntentType, set[str]] = {
    IntentType.FIND_FIR_BY_ID: {"fir_id"},
    IntentType.FIND_FIRS_BY_CRIME_TYPE: {"crime_head", "district", "date_from", "date_to"},
    IntentType.FIND_FIRS_BY_LOCATION: {"district", "police_station"},
    IntentType.FIND_LINKED_FIRS: {"fir_id"},
    IntentType.FIND_SUSPECT_NETWORK: {"gang_name"},
    IntentType.FIND_BY_PHONE_OR_VEHICLE: {"phone_number", "vehicle_number"},
    IntentType.SEMANTIC_SEARCH: {"free_text"},
    IntentType.UNSUPPORTED: set(),
}
