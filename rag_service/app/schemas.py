from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Scope(BaseModel):
    """RBAC scope injected by Django from the validated JWT (§12).

    The RAG service NEVER accepts scope from the browser; a missing or
    malformed scope is a 400 at the schema layer.
    """

    role: Literal["SUPER_ADMIN", "ANALYST", "INVESTIGATOR", "READ_ONLY"]
    districts: list[str] = Field(default_factory=list)
    stations: list[str] = Field(default_factory=list)
    user_id: str = Field(min_length=1)

    @field_validator("districts", "stations")
    @classmethod
    def _uppercase_tokens(cls, v: list[str]) -> list[str]:
        out = []
        for token in v:
            token = token.strip().upper()
            if token and token not in out:
                out.append(token)
        return out


class HistoryItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class QueryRequest(BaseModel):
    """POST /v1/query body (§12). Max question length guards the §11.2 budget
    (400 tokens ≈ 1,600 chars at 4 chars/token; refuse early at the schema)."""

    question: str = Field(min_length=1, max_length=2000)
    scope: Scope
    conversation_id: str | None = None
    history: list[HistoryItem] = Field(default_factory=list)

    @field_validator("history")
    @classmethod
    def _cap_history(cls, v: list[HistoryItem]) -> list[HistoryItem]:
        if len(v) > 20:
            raise ValueError("history too long — summarize older turns (§11.2)")
        return v


class Citation(BaseModel):
    fir_id: str
    station: str | None = None
    chunk_id: str | None = None
    score: float | None = None


class SlotPayload(BaseModel):
    person_names: list[str] = Field(default_factory=list)
    stations: list[str] = Field(default_factory=list)
    date_from: str | None = None
    date_to: str | None = None
    crime_type: str | None = None
    vehicle: str | None = None
    phone: str | None = None
    fir_id: str | None = None
    gang: str | None = None
    free_text: str | None = None


IntentId = Literal[
    "FIR_LOOKUP", "PERSON_PROFILE", "PERSON_NETWORK", "PATTERN_SEARCH", "STATION_STATS",
    "CRIME_TREND", "REPEAT_OFFENDERS", "SHARED_IDENTIFIER", "GEO_CLUSTER",
    "MODUS_OPERANDI_MATCH", "EVIDENCE_TRAIL", "FREEFORM_SEARCH",
]

LightRagMode = Literal["local", "global", "hybrid", "mix", "naive"]


class Plan(BaseModel):
    """router/plan.py output: (intent, slots, scope) → execution plan (§12.2)."""

    intent: IntentId
    slots: SlotPayload = Field(default_factory=SlotPayload)
    cypher_template_id: str | None = None
    cypher_params: dict = Field(default_factory=dict)
    lightrag_mode: LightRagMode | None = None
    lightrag_query: str | None = None
    needs_centrality: bool = False
    response_shape: Literal["rows", "graph", "profile", "answer"] = "answer"
