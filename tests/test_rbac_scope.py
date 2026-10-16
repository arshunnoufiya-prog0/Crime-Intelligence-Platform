#!/usr/bin/env python3
"""Step 17 gate — RBAC scope tests (spec §17, §14.3 change 3).

Locally runnable: accounts/scope.py is dependency-free; router/plan.py runs
against a stubbed pydantic. The Django-side JWT pieces (jti, hashed rotation)
gate at stack launch via login→query→stream (test_e2e_query.py).

Run:  python3 tests/test_rbac_scope.py   (also pytest-compatible)
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

for name in ("pydantic", "pydantic_settings"):
    if name not in sys.modules:
        mod = types.ModuleType(name)
        if name == "pydantic":
            class _BaseModel:
                def __init__(self, **kwargs):
                    for k, v in kwargs.items():
                        setattr(self, k, v)
            mod.BaseModel = _BaseModel
            mod.Field = lambda *a, **k: None

            def _field_validator(*a, **k):
                def deco(fn):
                    return fn
                return deco
            mod.field_validator = _field_validator
        sys.modules[name] = mod

sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(REPO_ROOT / "rag_service"))

from app.router import plan as plan_mod  # noqa: E402
from apps.accounts.scope import build_scope  # noqa: E402


class _User:
    def __init__(self, id, role, districts=None, stations=None):
        self.id = id
        self.role = role
        self.districts = districts or []
        self.stations = stations or []


class _ScopeNS:
    """The wire-scope dict viewed the way the pydantic Scope object exposes it."""

    def __init__(self, payload: dict):
        self.role = payload["role"]
        self.districts = payload["districts"]
        self.stations = payload["stations"]
        self.user_id = payload["user_id"]


ADMIN = _User("11111111-1111-1111-1111-111111111111", "SUPER_ADMIN",
             districts=["should-be-ignored"])
ANALYST = _User("22222222-2222-2222-2222-222222222222", "ANALYST")
INVESTIGATOR = _User("33333333-3333-3333-3333-333333333333", "INVESTIGATOR",
                     districts=["bengaluru_urban"], stations=["jayanagar ps"])
READ_ONLY = _User("444444444-4444-4444-4444-444444444444", "READ_ONLY",
                  districts=["BENGALURU_URBAN"], stations=["MAGADI_ROAD_PS"])


def test_admin_and_analyst_are_unscoped():
    for user in (ADMIN, ANALYST):
        scope = build_scope(user)
        assert scope["districts"] == [] and scope["stations"] == [], (
            "SUPER_ADMIN/ANALYST see all records — no filters (§17 matrix)"
        )
        assert scope["role"] == user.role


def test_investigator_scope_uppercased_and_passed_through():
    scope = build_scope(INVESTIGATOR)
    assert scope["districts"] == ["BENGALURU_URBAN"]
    assert scope["stations"] == ["JAYANAGAR PS"]  # uppercase passthrough
    assert scope["user_id"].startswith("u_")


def test_read_only_keeps_read_scope():
    scope = build_scope(READ_ONLY)
    assert scope["role"] == "READ_ONLY"
    assert scope["districts"] == ["BENGALURU_URBAN"]


def test_every_plan_carries_the_scope():
    for intent in (
        "FIR_LOOKUP", "PERSON_PROFILE", "PERSON_NETWORK", "PATTERN_SEARCH",
        "STATION_STATS", "CRIME_TREND", "REPEAT_OFFENDERS", "SHARED_IDENTIFIER",
        "GEO_CLUSTER", "MODUS_OPERANDI_MATCH", "EVIDENCE_TRAIL", "FREEFORM_SEARCH",
    ):
        slots = plan_mod.SlotPayload()
        p = plan_mod.build_plan(intent, slots, _ScopeNS(build_scope(INVESTIGATOR)))
        assert "districts" in p.cypher_params and "stations" in p.cypher_params, (
            f"{intent}: plan params missing RBAC scope (§13)"
        )
        assert p.cypher_params["districts"] == ["BENGALURU_URBAN"]
        assert p.cypher_template_id is not None


def test_unscoped_admin_passes_null_filters():
    p = plan_mod.build_plan("PATTERN_SEARCH", plan_mod.SlotPayload(), _ScopeNS(build_scope(ADMIN)))
    assert p.cypher_params["districts"] is None and p.cypher_params["stations"] is None


if __name__ == "__main__":
    for name in sorted(k for k in globals() if k.startswith("test_")):
        globals()[name]()
        print(f"PASS {name}")
    print("ALL RBAC SCOPE TESTS GREEN")
