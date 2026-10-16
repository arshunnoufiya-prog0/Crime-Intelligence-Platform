"""RBAC scope injection (spec §14.3 change 3, §17, §12).

The scope is built ONLY from the validated JWT / authenticated user — the
RAG service never accepts a browser-supplied scope. Values are uppercase
codes matching the graph properties (district / station_code).
"""
from __future__ import annotations

ALL_DISTRICTS: list[str] = []
ALL_STATIONS: list[str] = []


def build_scope(user) -> dict:
    """Scope payload attached to every RAG request (§12 request shape)."""
    districts = [str(d).upper() for d in (getattr(user, "districts", None) or [])]
    stations = [str(s).upper() for s in (getattr(user, "stations", None) or [])]
    if user.role in ("SUPER_ADMIN", "ANALYST"):
        districts, stations = [], []
    return {
        "role": user.role,
        "districts": districts,
        "stations": stations,
        "user_id": f"u_{user.id}",
    }
