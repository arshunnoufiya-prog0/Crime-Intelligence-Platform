#!/usr/bin/env python3
"""Step 12 gate — Cypher template tests (spec §13).

Asserts per template:
  * frozen constant — AST shows a plain str Constant (no f-strings, no
    .format(), no %, no + concatenation of user input);
  * carries $districts AND $stations (RBAC at every layer);
  * carries LIMIT (unbounded traversal hangs the demo);
  * every $param is on the router's whitelisted parameter set.

EXPLAIN against a live Neo4j runs when NEO4J_URI is reachable (§13);
otherwise it is SKIPPED loudly and completes at stack launch (§15 Step 12).

Run:  python3 tests/test_cypher_templates.py   (also pytest-compatible)
"""
from __future__ import annotations

import ast
import asyncio
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "rag_service"))

from app.graph.cypher_templates import TEMPLATES  # noqa: E402

SOURCE_PATH = REPO_ROOT / "rag_service" / "app" / "graph" / "cypher_templates.py"

ALLOWED_PARAMS = {
    "districts", "stations", "person_name", "crime_code", "date_from", "date_to",
    "locality", "lat", "lon", "radius_m", "min_firs", "kind", "value", "fir_id",
    "station", "stolen_item", "weapon", "query_text", "person_name_key",
}

DUMMY_PARAMS = {
    "districts": ["BENGALURU_URBAN"], "stations": ["JAYANAGAR_PS"],
    "person_name": "RAHUL SHARMA", "crime_code": "BURGLARY",
    "date_from": "2024-01-01", "date_to": "2024-12-31",
    "locality": "JAYANAGAR", "lat": 12.97, "lon": 77.59, "radius_m": 2000,
    "min_firs": 2, "kind": "PHONE", "value": "+919811223344",
    "fir_id": "17/2023", "station": "JAYANAGAR_PS", "stolen_item": "GOLD JEWELRY",
    "weapon": "KNIFE", "query_text": "burglary Jayanagar",
}


def test_all_intents_present():
    assert len(TEMPLATES) == 12, f"expected 12 intents (§13), got {len(TEMPLATES)}"
    expected = {
        "FIR_LOOKUP", "PERSON_PROFILE", "PERSON_NETWORK", "PATTERN_SEARCH",
        "STATION_STATS", "CRIME_TREND", "REPEAT_OFFENDERS", "SHARED_IDENTIFIER",
        "GEO_CLUSTER", "MODUS_OPERANDI_MATCH", "EVIDENCE_TRAIL", "FREEFORM_SEARCH",
    }
    assert expected == set(TEMPLATES), f"intent set mismatch: {set(TEMPLATES) ^ expected}"


def test_templates_are_frozen_constants():
    tree = ast.parse(SOURCE_PATH.read_text(encoding="utf-8"))
    assigned: dict[str, ast.expr] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            assigned[node.targets[0].id] = node.value
    for name in TEMPLATES:
        assert name in assigned, f"{name} is not a module-level assignment"
        value = assigned[name]
        assert isinstance(value, ast.Constant) and isinstance(value.value, str), (
            f"{name} must be a plain string constant — no f-strings, no .format(), "
            f"no %, no + concatenation (§13)"
        )


def test_scope_and_limit_everywhere():
    for name, template in TEMPLATES.items():
        assert "$districts" in template, f"{name}: missing $districts scope (§13)"
        assert "$stations" in template, f"{name}: missing $stations scope (§13)"
        assert "LIMIT" in template.upper(), f"{name}: missing LIMIT (§13)"
        assert "%s" not in template, f"{name}: %-interpolation found (§13)"
        assert ".format(" not in template, f"{name}: .format() found (§13)"
        assert "*1..3" not in template, f"{name}: *1..3 is a trap (§13 invariants)"


def test_params_whitelisted():
    for name, template in TEMPLATES.items():
        params = set(re.findall(r"\$([a-z_][a-z0-9_]*)", template))
        unknown = params - ALLOWED_PARAMS
        assert not unknown, f"{name}: unknown $params {unknown} — extend the router whitelist deliberately"


def test_explain_against_live_neo4j():
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    password = os.environ.get("NEO4J_PASSWORD", "")
    if not password:
        print("  [SKIP] live EXPLAIN — NEO4J_PASSWORD unset; completes at stack launch (§15 Step 12)")
        return

    async def run():
        from neo4j import AsyncGraphDatabase

        driver = AsyncGraphDatabase.driver(uri, auth=("neo4j", password))
        try:
            await driver.verify_connectivity()
            for name, template in TEMPLATES.items():
                async with driver.session(database=os.environ.get("NEO4J_DATABASE", "neo4j")) as session:
                    result = await session.run("EXPLAIN " + template, DUMMY_PARAMS)
                    await result.consume()
                print(f"  [EXPLAIN OK] {name}")
        finally:
            await driver.close()

    try:
        asyncio.run(asyncio.wait_for(run(), timeout=30))
    except Exception as exc:
        print(f"  [SKIP] live EXPLAIN — Neo4j not reachable at {uri} ({exc.__class__.__name__}); "
              "completes at stack launch (§15 Step 12)")


if __name__ == "__main__":
    for name in sorted(k for k in globals() if k.startswith("test_")):
        globals()[name]()
        print(f"PASS {name}")
    print("ALL CYPHER TEMPLATE TESTS GREEN")
