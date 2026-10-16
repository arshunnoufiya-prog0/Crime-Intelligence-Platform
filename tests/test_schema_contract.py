#!/usr/bin/env python3
"""Step 1 gate — schema contract test (spec §5.2 rule 2).

Re-runs discovery and asserts artifacts/schema_report.json is unchanged, so a
dataset swap fails loudly here instead of loaders silently dropping fields.

Run:  python3 tests/test_schema_contract.py      (also pytest-compatible)
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "rag_service" / "ingest"))

import discover_schema  # noqa: E402

_REPORT = REPO_ROOT / "artifacts" / "schema_report.json"
_CACHE: dict = {}


def _fresh() -> dict:
    if "report" not in _CACHE:
        _CACHE["report"] = discover_schema.build_report(discover_schema.load_dataset())
    return _CACHE["report"]


def test_report_matches_fresh_discovery():
    disk = json.loads(_REPORT.read_text(encoding="utf-8"))
    assert _fresh() == disk, (
        "artifacts/schema_report.json is stale — re-run "
        "rag_service/ingest/discover_schema.py and commit the updated report"
    )


def test_step1_gates():
    rep = _fresh()
    cc = rep["citation_contract"]
    assert rep["dataset"]["n_records"] == 1000, "spec §15 Step 1 gate: 1,000 records"
    assert rep["fields"][cc["id_path"]]["present_pct"] == 100.0, "fir_id must be present in 100% of records"
    assert cc["id_match_pct"] == 100.0, "derived id_regex must match every observed id"
    assert cc["narrative_fields"], "§5.3: no narrative fields — chunking strategy would change"
    assert cc["per_field_provenance"] is True
    stations = rep["enums"].get("firs[].fir_metadata.police_station", [])
    assert len(stations) == 40, f"spec §5.1: 40 police stations (got {len(stations)})"


def test_constants_module_consistent():
    sc = importlib.import_module("_schema_constants")
    rep = _fresh()
    cc = rep["citation_contract"]
    assert sc.N_RECORDS == rep["dataset"]["n_records"]
    assert sc.DATASET_SHA256 == rep["dataset"]["sha256"]
    assert sc.ID_FIELD == cc["id_field"] == "fir_id"
    assert sc.ID_REGEX == cc["id_regex"]
    assert sc.NARRATIVE_PATHS == cc["narrative_fields"]
    assert len(sc.POLICE_STATIONS) == 40
    assert isinstance(sc.FIELD_PATHS, dict) and sc.FIELD_PATHS


if __name__ == "__main__":
    test_report_matches_fresh_discovery()
    test_step1_gates()
    test_constants_module_consistent()
    print("PASS — schema contract intact: report current, gates hold, constants consistent")
