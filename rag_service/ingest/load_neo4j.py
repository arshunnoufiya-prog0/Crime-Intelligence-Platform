#!/usr/bin/env python3
"""Step 6 — Neo4j domain crime-graph loader (spec §5.4 + Step 1 report deltas).

Deterministic, idempotent batch loader (UNWIND + MERGE, 100 rows/tx). Every
relationship carries source_fir (the globally-unique fir_key; model delta:
fir_id alone is not unique — see schema_report.json id_uniqueness) plus
source_fir_id where a citable fir_id is useful.

Gate (§15 Step 6): node/rel counts must match the hand-computed expectation
derived from the normalized records; a mismatch fails loudly and writes
artifacts/ingest_report.json with both sides.

Run inside the rag container / venv (needs the `neo4j` driver):
    python ingest/load_neo4j.py
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import discover_schema  # noqa: E402
import normalize as N  # noqa: E402
from neo4j import GraphDatabase  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = REPO_ROOT / "artifacts" / "ingest_report.json"
BATCH = 100

FIR_NODES = """
UNWIND $rows AS r
MERGE (f:FIR {fir_key: r.fir_key})
SET f.fir_id = r.fir_id, f.district = r.district, f.district_name = r.district_name,
    f.station_code = r.station_code, f.station_name = r.station_name,
    f.registered_on = r.registered_on, f.occurred_on = r.occurred_on,
    f.occurrence_time = r.occurrence_time, f.case_status = r.case_status,
    f.case_category = r.case_category, f.crime_head = r.crime_head,
    f.crime_code = r.crime_code, f.act = r.act, f.sections = r.sections,
    f.narrative = r.narrative, f.address = r.address,
    f.latitude = r.lat, f.longitude = r.lon, f.weapon = r.weapon,
    f.stolen_items = r.stolen_items, f.fingerprints_found = r.fingerprints_found,
    f.dna_found = r.dna_found, f.cctv_available = r.cctv_available,
    f.gang = r.gang, f.alias_group = r.alias_group,
    f.accused_count = r.accused_count, f.accused_identified_count = r.accused_identified_count,
    f.complainant_name = r.complainant_name, f.io_name = r.io_name,
    f.ai_crime_pattern_id = r.ai_crime_pattern_id, f.ai_linked_firs = r.ai_linked_firs,
    f.ai_confidence_score = r.ai_confidence_score,
    f.ai_is_repeat_offender = r.ai_is_repeat_offender,
    f.ai_predicted_suspect = r.ai_predicted_suspect
"""

PERSON_NODES = """
UNWIND $rows AS r
MERGE (p:Person {person_key: r.person_key})
SET p.name = r.name, p.name_normalized = r.name_normalized, p.role = r.role,
    p.gang = r.gang, p.alias_group = r.alias_group
"""

STATION_NODES = """
UNWIND $rows AS r
MERGE (s:Station {station_code: r.station_code})
SET s.name = r.name
"""

SECTION_NODES = """
UNWIND $rows AS r
MERGE (s:Section {section_code: r.section_code})
"""

CRIMETYPE_NODES = """
UNWIND $rows AS r
MERGE (c:CrimeType {crime_code: r.crime_code})
SET c.name = r.name
"""

VEHICLE_NODES = """
UNWIND $rows AS r
MERGE (v:Vehicle {registration: r.registration})
"""

PHONE_NODES = """
UNWIND $rows AS r
MERGE (p:Phone {msisdn: r.msisdn})
"""

ACCOUNT_NODES = """
UNWIND $rows AS r
MERGE (a:Account {account_ref: r.account_ref})
SET a.kind = r.kind
"""

DEVICE_NODES = """
UNWIND $rows AS r
MERGE (d:Device {imei: r.imei})
"""

LOCATION_NODES = """
UNWIND $rows AS r
MERGE (l:Location {location_key: r.location_key})
SET l.address = r.address, l.latitude = r.lat, l.longitude = r.lon
"""

REGISTERED_AT = """
UNWIND $rows AS r
MATCH (f:FIR {fir_key: r.fir_key}), (s:Station {station_code: r.station_code})
MERGE (f)-[e:REGISTERED_AT]->(s)
SET e.source_fir = r.fir_key, e.source_fir_id = r.fir_id
"""

OCCURRED_AT = """
UNWIND $rows AS r
MATCH (f:FIR {fir_key: r.fir_key}), (l:Location {location_key: r.location_key})
MERGE (f)-[e:OCCURRED_AT]->(l)
SET e.source_fir = r.fir_key, e.source_fir_id = r.fir_id
"""

CLASSIFIED_AS = """
UNWIND $rows AS r
MATCH (f:FIR {fir_key: r.fir_key}), (c:CrimeType {crime_code: r.crime_code})
MERGE (f)-[e:CLASSIFIED_AS]->(c)
SET e.source_fir = r.fir_key, e.source_fir_id = r.fir_id
"""

INVOKES = """
UNWIND $rows AS r
MATCH (f:FIR {fir_key: r.fir_key}), (s:Section {section_code: r.section_code})
MERGE (f)-[e:INVOKES]->(s)
SET e.source_fir = r.fir_key, e.source_fir_id = r.fir_id
"""

HAS_PHONE = """
UNWIND $rows AS r
MATCH (f:FIR {fir_key: r.fir_key}), (p:Phone {msisdn: r.msisdn})
MERGE (f)-[e:HAS_EVIDENCE {kind: 'PHONE'}]->(p)
SET e.source_fir = r.fir_key, e.source_fir_id = r.fir_id
"""

HAS_VEHICLE = """
UNWIND $rows AS r
MATCH (f:FIR {fir_key: r.fir_key}), (v:Vehicle {registration: r.registration})
MERGE (f)-[e:HAS_EVIDENCE {kind: 'VEHICLE'}]->(v)
SET e.source_fir = r.fir_key, e.source_fir_id = r.fir_id
"""

HAS_ACCOUNT = """
UNWIND $rows AS r
MATCH (f:FIR {fir_key: r.fir_key}), (a:Account {account_ref: r.account_ref})
MERGE (f)-[e:HAS_EVIDENCE {kind: r.kind}]->(a)
SET e.source_fir = r.fir_key, e.source_fir_id = r.fir_id
"""

HAS_DEVICE = """
UNWIND $rows AS r
MATCH (f:FIR {fir_key: r.fir_key}), (d:Device {imei: r.imei})
MERGE (f)-[e:HAS_EVIDENCE {kind: 'IMEI'}]->(d)
SET e.source_fir = r.fir_key, e.source_fir_id = r.fir_id
"""

ACCUSED_IN = """
UNWIND $rows AS r
MATCH (p:Person {person_key: r.person_key}), (f:FIR {fir_key: r.fir_key})
MERGE (p)-[e:ACCUSED_IN]->(f)
SET e.identified = r.identified, e.source_fir = r.fir_key, e.source_fir_id = r.fir_id
"""

COMPLAINANT_IN = """
UNWIND $rows AS r
MATCH (p:Person {person_key: r.person_key}), (f:FIR {fir_key: r.fir_key})
MERGE (p)-[e:COMPLAINANT_IN]->(f)
SET e.source_fir = r.fir_key, e.source_fir_id = r.fir_id
"""

INVESTIGATED_BY = """
UNWIND $rows AS r
MATCH (f:FIR {fir_key: r.fir_key}), (p:Person {person_key: r.person_key})
MERGE (f)-[e:INVESTIGATED_BY]->(p)
SET e.source_fir = r.fir_key, e.source_fir_id = r.fir_id
"""

ASSOCIATE_OF = """
UNWIND $rows AS r
MATCH (a:Person {person_key: r.a}), (b:Person {person_key: r.b})
MERGE (a)-[e:ASSOCIATE_OF]->(b)
SET e.strength = r.strength, e.basis = r.basis,
    e.source_fir = r.fir_key, e.source_fir_id = r.fir_id
"""

SAME_NAME_AS = """
UNWIND $rows AS r
MATCH (a:Person {person_key: r.a}), (b:Person {person_key: r.b})
MERGE (a)-[e:SAME_NAME_AS]->(b)
SET e.confidence = r.confidence, e.source_fir = r.source_fir
"""

MODEL_DELTAS = [
    "FIR uniqueness moved from fir_id (§5.4) to composite fir_key '<fir_id>@<STATION_CODE>' "
    "with '#n' occurrence suffix for the 5 exact-duplicate pairs (schema_report id_uniqueness).",
    "Placeholder-named persons (Unknown/Unidentified) are excluded from Person nodes; "
    "FIR keeps accused_count / accused_identified_count instead. Under-linking by design (§18.1).",
    "No USES or CONTACTED edges: FIR data links evidence to FIRs, not persons, and carries "
    "no CDR data — the §5.4 relationships are not derivable without fabrication.",
    "SAME_NAME_AS is chained (n-1 edges per name cluster) with confidence 0.5; source_fir is "
    "the fir_key of the second person's FIR.",
    "ASSOCIATE_OF built inside each criminal_network block (mastermind↔associates, "
    "associates pairwise), strength 0.7, basis 'criminal_network' (§9.1 rule 5 semantics).",
    "Account covers BANK/UPI/COMPANY kinds (digital_evidence.companies is sparse but real).",
    "INVESTIGATED_BY added (additive to §5.4 — investigating_officer is ground truth).",
    "Section.section_code = '<ACT>/<section>'; CrimeType.crime_code = normalized crime_head.",
    "Gang/alias_group stored as properties on FIR + network persons (no Gang label in §5.4).",
    "source_fir on every edge = fir_key (globally unique), source_fir_id = citable fir_id; "
    "the §13 worked example's `MATCH (f:FIR {fir_id: r.source_fir})` joins on fir_key instead.",
]


def _chunk(rows: list, size: int = BATCH):
    for i in range(0, len(rows), size):
        yield rows[i:i + size]


def build_graph_payload(records: list[dict]) -> dict:
    firs: list[dict] = []
    persons: dict[str, dict] = {}
    stations: dict[str, dict] = {}
    sections: dict[str, dict] = {}
    crimetypes: dict[str, dict] = {}
    vehicles: dict[str, dict] = {}
    phones: dict[str, dict] = {}
    accounts: dict[str, dict] = {}
    devices: dict[str, dict] = {}
    locations: dict[str, dict] = {}
    edges = {
        "registered": [], "occurred": [], "classified": [], "invokes": [],
        "ev_phone": [], "ev_vehicle": [], "ev_account": [], "ev_device": [],
        "accused_in": [], "complainant_in": [], "investigated_by": [], "associate_of": [],
    }

    def add_person(key, name, role, gang="", alias_group=""):
        if key not in persons:
            persons[key] = {
                "person_key": key, "name": name or "",
                "name_normalized": N.normalize_text(name), "role": role,
                "gang": gang, "alias_group": alias_group,
            }

    for rec in records:
        fk, fid = rec["fir_key"], rec["fir_id"]
        stations.setdefault(rec["station_code"], {"station_code": rec["station_code"], "name": rec["station_name"]})
        for sec in rec["sections"]:
            sections.setdefault(sec, {"section_code": sec})
        crimetypes.setdefault(rec["crime_code"], {"crime_code": rec["crime_code"], "name": rec["crime_head"]})
        for v in rec["vehicles"]:
            vehicles.setdefault(v, {"registration": v})
        for p in rec["phones"]:
            phones.setdefault(p, {"msisdn": p})
        for a in rec["accounts"]:
            accounts.setdefault(a["account_ref"], a)
        for i in rec["imeis"]:
            devices.setdefault(i, {"imei": i})
        locations.setdefault(rec["location_key"], {
            "location_key": rec["location_key"], "address": rec["address"],
            "lat": rec["lat"], "lon": rec["lon"],
        })

        firs.append({
            "fir_key": fk, "fir_id": fid, "district": rec["district"],
            "district_name": rec["district_name"], "station_code": rec["station_code"],
            "station_name": rec["station_name"], "registered_on": rec["registered_on"],
            "occurred_on": rec["occurred_on"], "occurrence_time": rec["occurred_time"],
            "case_status": rec["case_status"], "case_category": rec["case_category"],
            "crime_head": rec["crime_head"], "crime_code": rec["crime_code"],
            "act": rec["act"], "sections": rec["sections"], "narrative": rec["narrative"],
            "address": rec["address"], "lat": rec["lat"], "lon": rec["lon"],
            "weapon": rec["weapon"], "stolen_items": rec["stolen_items"],
            "fingerprints_found": rec["fingerprints_found"], "dna_found": rec["dna_found"],
            "cctv_available": rec["cctv_available"], "gang": rec["gang"],
            "alias_group": rec["alias_group"],
            "accused_count": len(rec["accused"]),
            "accused_identified_count": sum(1 for a in rec["accused"] if a["identified"]),
            "complainant_name": rec["complainant"]["name"] if rec["complainant"] else "",
            "io_name": rec["investigating_officer"]["name"] if rec["investigating_officer"] else "",
            "ai_crime_pattern_id": rec["ai_metadata"]["crime_pattern_id"],
            "ai_linked_firs": rec["ai_metadata"]["linked_firs"],
            "ai_confidence_score": rec["ai_metadata"]["confidence_score"],
            "ai_is_repeat_offender": rec["ai_metadata"]["is_repeat_offender"],
            "ai_predicted_suspect": rec["ai_metadata"]["predicted_suspect"],
        })

        base = {"fir_key": fk, "fir_id": fid}
        edges["registered"].append(base | {"station_code": rec["station_code"]})
        edges["occurred"].append(base | {"location_key": rec["location_key"]})
        edges["classified"].append(base | {"crime_code": rec["crime_code"]})
        for sec in rec["sections"]:
            edges["invokes"].append(base | {"section_code": sec})
        for p in rec["phones"]:
            edges["ev_phone"].append(base | {"msisdn": p})
        for v in rec["vehicles"]:
            edges["ev_vehicle"].append(base | {"registration": v})
        for a in rec["accounts"]:
            edges["ev_account"].append(base | {"account_ref": a["account_ref"], "kind": a["kind"]})
        for i in rec["imeis"]:
            edges["ev_device"].append(base | {"imei": i})

        if rec["complainant"]:
            add_person(rec["complainant"]["person_key"], rec["complainant"]["name"], "complainant")
            edges["complainant_in"].append(base | {"person_key": rec["complainant"]["person_key"]})
        for acc in rec["accused"]:
            if acc["placeholder"]:
                continue
            add_person(acc["person_key"], acc["name"], "accused")
            edges["accused_in"].append(base | {"person_key": acc["person_key"], "identified": acc["identified"]})
        if rec["investigating_officer"]:
            add_person(rec["investigating_officer"]["person_key"], rec["investigating_officer"]["name"], "io")
            edges["investigated_by"].append(base | {"person_key": rec["investigating_officer"]["person_key"]})

        network: list[str] = []
        if rec["mastermind"]:
            add_person(rec["mastermind"]["person_key"], rec["mastermind"]["name"],
                       "mastermind", rec["gang"], rec["alias_group"])
            network.append(rec["mastermind"]["person_key"])
        for assoc in rec["associates"]:
            pk = N.person_key_of(fk, "associate", assoc)
            add_person(pk, assoc, "associate", rec["gang"], rec["alias_group"])
            network.append(pk)
        for i, a in enumerate(network):
            for b in network[i + 1:]:
                edges["associate_of"].append(base | {"a": a, "b": b, "strength": 0.7, "basis": "criminal_network"})

    return {
        "firs": firs, "persons": list(persons.values()),
        "stations": list(stations.values()), "sections": list(sections.values()),
        "crimetypes": list(crimetypes.values()), "vehicles": list(vehicles.values()),
        "phones": list(phones.values()), "accounts": list(accounts.values()),
        "devices": list(devices.values()), "locations": list(locations.values()),
        "edges": edges,
    }


def expected_counts(payload: dict, same_name: list[dict]) -> dict:
    nodes = {
        "FIR": len(payload["firs"]), "Person": len(payload["persons"]),
        "Station": len(payload["stations"]), "Section": len(payload["sections"]),
        "CrimeType": len(payload["crimetypes"]), "Vehicle": len(payload["vehicles"]),
        "Phone": len(payload["phones"]), "Account": len(payload["accounts"]),
        "Device": len(payload["devices"]), "Location": len(payload["locations"]),
    }
    e = payload["edges"]
    rels = {
        "REGISTERED_AT": len(e["registered"]), "OCCURRED_AT": len(e["occurred"]),
        "CLASSIFIED_AS": len(e["classified"]), "INVOKES": len(e["invokes"]),
        "HAS_EVIDENCE": len(e["ev_phone"]) + len(e["ev_vehicle"]) + len(e["ev_account"]) + len(e["ev_device"]),
        "ACCUSED_IN": len(e["accused_in"]), "COMPLAINANT_IN": len(e["complainant_in"]),
        "INVESTIGATED_BY": len(e["investigated_by"]), "ASSOCIATE_OF": len(e["associate_of"]),
        "SAME_NAME_AS": len(same_name),
    }
    return {"nodes": nodes, "relationships": rels}


def load(driver, database: str, payload: dict, same_name: list[dict]) -> None:
    stages = [
        ("Station nodes", STATION_NODES, payload["stations"]),
        ("Section nodes", SECTION_NODES, payload["sections"]),
        ("CrimeType nodes", CRIMETYPE_NODES, payload["crimetypes"]),
        ("Vehicle nodes", VEHICLE_NODES, payload["vehicles"]),
        ("Phone nodes", PHONE_NODES, payload["phones"]),
        ("Account nodes", ACCOUNT_NODES, payload["accounts"]),
        ("Device nodes", DEVICE_NODES, payload["devices"]),
        ("Location nodes", LOCATION_NODES, payload["locations"]),
        ("Person nodes", PERSON_NODES, payload["persons"]),
        ("FIR nodes", FIR_NODES, payload["firs"]),
        ("REGISTERED_AT", REGISTERED_AT, payload["edges"]["registered"]),
        ("OCCURRED_AT", OCCURRED_AT, payload["edges"]["occurred"]),
        ("CLASSIFIED_AS", CLASSIFIED_AS, payload["edges"]["classified"]),
        ("INVOKES", INVOKES, payload["edges"]["invokes"]),
        ("HAS_EVIDENCE/PHONE", HAS_PHONE, payload["edges"]["ev_phone"]),
        ("HAS_EVIDENCE/VEHICLE", HAS_VEHICLE, payload["edges"]["ev_vehicle"]),
        ("HAS_EVIDENCE/ACCOUNT", HAS_ACCOUNT, payload["edges"]["ev_account"]),
        ("HAS_EVIDENCE/DEVICE", HAS_DEVICE, payload["edges"]["ev_device"]),
        ("ACCUSED_IN", ACCUSED_IN, payload["edges"]["accused_in"]),
        ("COMPLAINANT_IN", COMPLAINANT_IN, payload["edges"]["complainant_in"]),
        ("INVESTIGATED_BY", INVESTIGATED_BY, payload["edges"]["investigated_by"]),
        ("ASSOCIATE_OF", ASSOCIATE_OF, payload["edges"]["associate_of"]),
        ("SAME_NAME_AS", SAME_NAME_AS, same_name),
    ]
    with driver.session(database=database) as session:
        for name, cypher, rows in stages:
            done = 0
            for batch in _chunk(rows):
                session.run(cypher, rows=batch).consume()
                done += len(batch)
            print(f"  {name:<24} {done} rows")


def actual_counts(driver, database: str) -> dict:
    nodes: Counter = Counter()
    rels: Counter = Counter()
    with driver.session(database=database) as session:
        for rec in session.run("MATCH (n) UNWIND labels(n) AS l RETURN l AS item, count(*) AS c"):
            nodes[rec["item"]] = rec["c"]
        for rec in session.run("MATCH ()-[r]->() RETURN type(r) AS item, count(*) AS c"):
            rels[rec["item"]] = rec["c"]
    return {"nodes": dict(nodes), "relationships": dict(rels)}


def main() -> int:
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "")
    database = os.environ.get("NEO4J_DATABASE", "neo4j")
    if not password:
        print("BLOCKED: Step 6 — NEO4J_PASSWORD is not set (spec §0.4 fail loud).")
        return 1

    dataset = discover_schema.load_dataset()
    records = N.normalize_records(dataset)
    same_name = N.same_name_edges(records)
    payload = build_graph_payload(records)
    expected = expected_counts(payload, same_name)

    print(f"Step 6 — loading domain graph into {uri} (db={database})")
    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        driver.verify_connectivity()
        load(driver, database, payload, same_name)
        actual = actual_counts(driver, database)
    finally:
        driver.close()

    ok = actual == expected
    mismatches = []
    for kind in ("nodes", "relationships"):
        for item in sorted(set(expected[kind]) | set(actual[kind])):
            e, a = expected[kind].get(item, 0), actual[kind].get(item, 0)
            mark = "PASS" if e == a else "FAIL"
            if e != a:
                ok = False
                mismatches.append(f"{kind}/{item}: expected {e}, actual {a}")
            print(f"  [{mark}] {kind:<13} {item:<15} expected={e:<6} actual={a}")

    report = {
        "spec": "ksp-iis-build-prompt-v3.1 §5.4/§5.5 + Step 1 report deltas",
        "expected": expected, "actual": actual, "match": ok,
        "model_deltas": MODEL_DELTAS,
        "entity_resolution": "artifacts/entity_resolution.json",
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {REPORT_PATH}")
    if not ok:
        print(f"BLOCKED: Step 6 — count mismatch: {'; '.join(mismatches)} (§15 Step 6 gate).")
        return 1
    print("GATE PASS — Step 6 complete (§15 Step 6): counts match hand-computed expectation.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
