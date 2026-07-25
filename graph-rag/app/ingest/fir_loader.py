"""FIR loader: maps the actual JSON record shape (Phase 0) to graph nodes/edges.
Batch UNWIND writes (100 FIRs/tx). Computes and stores f.embedding via
embedder.embed_documents() on concatenated text fields at ingest time.
"""
from __future__ import annotations

import logging
from typing import Iterable

from ..config import settings
from ..graphstore.schema import (
    fir_key,
    person_key,
    NODE_LABELS,
    EDGE_TYPES,
    CONSTRAINT_CYPHER,
    INDEX_CYPHER,
    VECTOR_INDEX_CYPHER,
)
from ..embedding.embedder import embedder
from ..graphstore.neo4j_client import neo4j_client

logger = logging.getLogger("graph-rag.ingest.fir_loader")

BATCH_SIZE = 100


def _first(l):  # noqa: E731
    pass


def _build_embedding_text(fir: dict) -> str:
    """Concatenate all non-empty text fields from the FIR record for embedding."""
    parts = []
    fm = fir.get("fir_metadata", {}) or {}
    ol = fir.get("occurrence_location", {}) or {}
    od = fir.get("offence_details", {}) or {}
    occd = fir.get("occurrence_details", {}) or {}
    cd = fir.get("complainant_details", {}) or {}
    incd = fir.get("incident_details", {}) or {}
    cn = fir.get("criminal_network", {}) or {}
    de = fir.get("digital_evidence", {}) or {}
    ai = fir.get("ai_metadata", {}) or {}

    def add(val):
        if val:
            parts.append(str(val))

    add(fir.get("fir_id"))
    add(fm.get("district"))
    add(fm.get("police_station"))
    add(fm.get("case_status"))
    add(fm.get("case_category"))
    add(fm.get("fir_registration_date"))
    add(ol.get("address"))
    add(od.get("act"))
    add(" ".join(od.get("sections", [])))
    add(od.get("crime_head"))
    add(occd.get("date"))
    add(occd.get("time"))
    add(occd.get("type_of_information"))
    add(cd.get("name"))
    add(cd.get("occupation"))
    add(cd.get("address"))
    for a in fir.get("accused_details", []):
        add(a.get("name"))
    add(incd.get("truth_of_incident"))
    add(cn.get("gang"))
    add(cn.get("alias_group"))
    add(cn.get("suspected_mastermind"))
    add(" ".join(cn.get("known_associates", [])))
    add(" ".join(de.get("phone_numbers", [])))
    add(" ".join(de.get("imei_numbers", [])))
    add(" ".join(de.get("bank_accounts", [])))
    add(" ".join(de.get("upi_ids", [])))
    add(" ".join(de.get("companies", [])))
    add(" ".join(de.get("vehicle_numbers", [])))
    add(ai.get("crime_pattern_id"))
    add(" ".join(ai.get("linked_firs", [])))
    add(ai.get("predicted_suspect"))

    return " | ".join(parts)


def _rows_from_fir(fir: dict) -> dict:
    """Transform a single FIR record into the batch rows dict for UNWIND."""
    fm = fir.get("fir_metadata", {}) or {}
    ol = fir.get("occurrence_location", {}) or {}
    od = fir.get("offence_details", {}) or {}
    occd = fir.get("occurrence_details", {}) or {}
    cd = fir.get("complainant_details", {}) or {}
    incd = fir.get("incident_details", {}) or {}
    cn = fir.get("criminal_network", {}) or {}
    de = fir.get("digital_evidence", {}) or {}
    pe = fir.get("physical_evidence", {}) or {}
    ai = fir.get("ai_metadata", {}) or {}
    io = fir.get("investigating_officer", {}) or {}

    fk = fir_key(fir["fir_id"], fm.get("police_station", "Unknown PS"))

    # FIR node
    fir_row = {
        "fir_key": fk,
        "fir_id": fir["fir_id"],
        "district_name": fm.get("district", "Bengaluru Urban"),
        "police_station_name": fm.get("police_station", "Unknown PS"),
        "case_status": fm.get("case_status", "Under Investigation"),
        "case_category": fm.get("case_category", "Non Heinous"),
        "registration_date": fm.get("fir_registration_date"),
        "crime_head": od.get("crime_head", ""),
        "sections": od.get("sections", []),
        "act": od.get("act", ""),
        "latitude": ol.get("latitude"),
        "longitude": ol.get("longitude"),
        "address": ol.get("address", ""),
        "occurrence_date": occd.get("date"),
        "occurrence_time": occd.get("time"),
        "type_of_information": occd.get("type_of_information", ""),
        "truth_of_incident": incd.get("truth_of_incident", ""),
        "criminal_network": cn,
        "digital_evidence": de,
        "physical_evidence": pe,
        "ai_metadata": ai,
        "investigating_officer_name": io.get("name"),
        "investigating_officer_rank": io.get("rank"),
        "investigating_officer_ps": io.get("police_station"),
        "embedding": None,  # filled later
    }

    # District
    district_row = {"name": fm.get("district", "Bengaluru Urban")}

    # PoliceStation
    ps_row = {"name": fm.get("police_station", "Unknown PS"), "district": fm.get("district", "Bengaluru Urban")}

    # Complainant person
    comp_pk = person_key(cd.get("name", "Unknown Complainant"), "complainant")
    complainant_row = {
        "person_key": comp_pk,
        "name": cd.get("name", "Unknown Complainant"),
        "role": "complainant",
        "occupation": cd.get("occupation", ""),
        "address": cd.get("address", ""),
    }

    # Accused persons (array)
    accused_rows = []
    for a in fir.get("accused_details", []):
        if not a.get("name"):
            continue
        ak = person_key(a["name"], "accused")
        accused_rows.append({
            "person_key": ak,
            "name": a["name"],
            "role": "accused",
            "identified": bool(a.get("identified", False)),
        })

    # Investigating officer
    off_pk = person_key(io.get("name", "Unknown Officer"), "officer")
    officer_row = {
        "person_key": off_pk,
        "name": io.get("name", "Unknown Officer"),
        "role": "officer",
        "rank": io.get("rank", ""),
        "police_station": io.get("police_station", ""),
    }

    # PhoneNumbers
    phone_rows = [{"number": n} for n in de.get("phone_numbers", [])]

    # VehicleNumbers
    vehicle_rows = [{"plate": n} for n in de.get("vehicle_numbers", [])]

    # BankAccounts
    account_rows = [{"account_id": n} for n in de.get("bank_accounts", [])]

    # Gang
    gang_row = None
    if cn.get("gang"):
        gang_row = {"name": cn["gang"], "alias_group": cn.get("alias_group", "")}

    # Known associates (persons)
    associate_rows = []
    for assoc in cn.get("known_associates", []):
        if assoc:
            associate_rows.append({
                "person_key": person_key(assoc, "associate"),
                "name": assoc,
                "role": "associate",
            })

    # Linked FIRs (SIMILAR_PATTERN edges)
    linked_firs = ai.get("linked_firs", [])
    # We'll create these edges in a second pass after all FIRs are written

    return {
        "fir": fir_row,
        "district": district_row,
        "police_station": ps_row,
        "complainant": complainant_row,
        "accused": accused_rows,
        "officer": officer_row,
        "phones": phone_rows,
        "vehicles": vehicle_rows,
        "accounts": account_rows,
        "gang": gang_row,
        "associates": associate_rows,
        "linked_firs": linked_firs,
        "fir_key": fk,
    }


# --- Cypher batch statements ---

FIR_MERGE = """
UNWIND $rows AS r
MERGE (f:FIR {fir_key: r.fir_key})
SET f.fir_id = r.fir_id,
    f.district_name = r.district_name,
    f.police_station_name = r.police_station_name,
    f.case_status = r.case_status,
    f.case_category = r.case_category,
    f.registration_date = r.registration_date,
    f.crime_head = r.crime_head,
    f.sections = r.sections,
    f.act = r.act,
    f.latitude = r.latitude,
    f.longitude = r.longitude,
    f.address = r.address,
    f.occurrence_date = r.occurrence_date,
    f.occurrence_time = r.occurrence_time,
    f.type_of_information = r.type_of_information,
    f.truth_of_incident = r.truth_of_incident,
    f.criminal_network = r.criminal_network,
    f.digital_evidence = r.digital_evidence,
    f.physical_evidence = r.physical_evidence,
    f.ai_metadata = r.ai_metadata,
    f.investigating_officer_name = r.investigating_officer_name,
    f.investigating_officer_rank = r.investigating_officer_rank,
    f.investigating_officer_ps = r.investigating_officer_ps,
    f.embedding = r.embedding
"""

DISTRICT_MERGE = """
UNWIND $rows AS r
MERGE (d:District {name: r.name})
"""

PS_MERGE = """
UNWIND $rows AS r
MERGE (ps:PoliceStation {name: r.name})
SET ps.district = r.district
WITH ps, r
MATCH (d:District {name: r.district})
MERGE (ps)-[:LOCATED_IN]->(d)
"""

PERSON_MERGE = """
UNWIND $rows AS r
MERGE (p:Person {person_key: r.person_key})
SET p.name = r.name, p.role = r.role, p.occupation = r.occupation, p.address = r.address,
    p.identified = r.identified, p.rank = r.rank, p.police_station = r.police_station
"""

PERSON_FIR_EDGE = """
UNWIND $rows AS r
MATCH (p:Person {person_key: r.person_key})
MATCH (f:FIR {fir_key: r.fir_key})
MERGE (f)-[:INVOLVES_ACCUSED {role: r.role}]->(p)
"""

FILED_BY_EDGE = """
UNWIND $rows AS r
MATCH (f:FIR {fir_key: r.fir_key})
MATCH (p:Person {person_key: r.person_key})
MERGE (f)-[:FILED_BY]->(p)
"""

INVESTIGATED_BY_EDGE = """
UNWIND $rows AS r
MATCH (f:FIR {fir_key: r.fir_key})
MATCH (p:Person {person_key: r.person_key})
MERGE (f)-[:INVESTIGATED_BY]->(p)
"""

REGISTERED_AT_EDGE = """
UNWIND $rows AS r
MATCH (f:FIR {fir_key: r.fir_key})
MATCH (ps:PoliceStation {name: r.police_station})
MERGE (f)-[:REGISTERED_AT]->(ps)
"""

PHONE_MERGE = """
UNWIND $rows AS r
MERGE (ph:PhoneNumber {number: r.number})
"""

PHONE_EDGE = """
UNWIND $rows AS r
MATCH (f:FIR {fir_key: r.fir_key})
MATCH (ph:PhoneNumber {number: r.number})
MERGE (f)-[:LINKED_PHONE]->(ph)
"""

VEHICLE_MERGE = """
UNWIND $rows AS r
MERGE (v:VehicleNumber {plate: r.plate})
"""

VEHICLE_EDGE = """
UNWIND $rows AS r
MATCH (f:FIR {fir_key: r.fir_key})
MATCH (v:VehicleNumber {plate: r.plate})
MERGE (f)-[:LINKED_VEHICLE]->(v)
"""

ACCOUNT_MERGE = """
UNWIND $rows AS r
MERGE (b:BankAccount {account_id: r.account_id})
"""

ACCOUNT_EDGE = """
UNWIND $rows AS r
MATCH (f:FIR {fir_key: r.fir_key})
MATCH (b:BankAccount {account_id: r.account_id})
MERGE (f)-[:LINKED_ACCOUNT]->(b)
"""

GANG_MERGE = """
UNWIND $rows AS r
MERGE (g:Gang {name: r.name})
SET g.alias_group = r.alias_group
"""

MEMBER_OF_EDGE = """
UNWIND $rows AS r
MATCH (p:Person {person_key: r.person_key})
MATCH (g:Gang {name: r.gang_name})
MERGE (p)-[:MEMBER_OF]->(g)
"""

LINKED_FIRS_EDGE = """
UNWIND $rows AS r
MATCH (f1:FIR {fir_key: r.root_key})
MATCH (f2:FIR {fir_id: r.linked_id})
MERGE (f1)-[:SIMILAR_PATTERN]-(f2)
"""


async def load_batch(firs: list[dict]) -> int:
    """Process a batch of FIR records, embed, and write to Neo4j."""
    # Transform all records
    transformed = [_rows_from_fir(f) for f in firs]

    # Build embedding texts
    texts = [_build_embedding_text(f) for f in firs]
    embeddings = await embedder.embed_documents(texts)

    # Attach embeddings
    for t, emb in zip(transformed, embeddings):
        t["fir"]["embedding"] = emb

    # Prepare UNWIND row lists
    fir_rows = [t["fir"] for t in transformed]
    district_rows = [t["district"] for t in transformed]
    ps_rows = [t["police_station"] for t in transformed]
    person_rows = []
    person_fir_edges = []  # {person_key, fir_key, role}
    filed_by_edges = []
    investigated_by_edges = []
    registered_edges = []
    phone_rows = []
    phone_edges = []
    vehicle_rows = []
    vehicle_edges = []
    account_rows = []
    account_edges = []
    gang_rows = []
    member_edges = []
    linked_fir_rows = []

    for t in transformed:
        fk = t["fir_key"]
        # Persons
        person_rows.append(t["complainant"])
        filed_by_edges.append({"fir_key": fk, "person_key": t["complainant"]["person_key"]})
        person_rows.append(t["officer"])
        investigated_by_edges.append({"fir_key": fk, "person_key": t["officer"]["person_key"]})
        registered_edges.append({"fir_key": fk, "police_station": t["police_station"]["name"]})
        for a in t["accused"]:
            person_rows.append(a)
            person_fir_edges.append({"fir_key": fk, "person_key": a["person_key"], "role": "accused"})
        for assoc in t["associates"]:
            person_rows.append(assoc)
            member_edges.append({"person_key": assoc["person_key"], "gang_name": t["gang"]["name"] if t["gang"] else None})
        # Phones
        for ph in t["phones"]:
            phone_rows.append(ph)
            phone_edges.append({"fir_key": fk, "number": ph["number"]})
        # Vehicles
        for v in t["vehicles"]:
            vehicle_rows.append(v)
            vehicle_edges.append({"fir_key": fk, "plate": v["plate"]})
        # Accounts
        for ac in t["accounts"]:
            account_rows.append(ac)
            account_edges.append({"fir_key": fk, "account_id": ac["account_id"]})
        # Gang
        if t["gang"]:
            gang_rows.append(t["gang"])
            # members for accused/associates already queued in member_edges
        # Linked FIRs (will resolve after batch)
        for linked in t["linked_firs"]:
            linked_fir_rows.append({"root_key": fk, "linked_id": linked})

    # Write in order: nodes first, then edges
    await neo4j_client.write_batch(FIR_MERGE, fir_rows)
    await neo4j_client.write_batch(DISTRICT_MERGE, district_rows)
    await neo4j_client.write_batch(PS_MERGE, ps_rows)
    await neo4j_client.write_batch(PERSON_MERGE, person_rows)
    await neo4j_client.write_batch(PERSON_FIR_EDGE, person_fir_edges)
    await neo4j_client.write_batch(FILED_BY_EDGE, filed_by_edges)
    await neo4j_client.write_batch(INVESTIGATED_BY_EDGE, investigated_by_edges)
    await neo4j_client.write_batch(REGISTERED_AT_EDGE, registered_edges)
    await neo4j_client.write_batch(PHONE_MERGE, phone_rows)
    await neo4j_client.write_batch(PHONE_EDGE, phone_edges)
    await neo4j_client.write_batch(VEHICLE_MERGE, vehicle_rows)
    await neo4j_client.write_batch(VEHICLE_EDGE, vehicle_edges)
    await neo4j_client.write_batch(ACCOUNT_MERGE, account_rows)
    await neo4j_client.write_batch(ACCOUNT_EDGE, account_edges)
    await neo4j_client.write_batch(GANG_MERGE, gang_rows)
    await neo4j_client.write_batch(MEMBER_OF_EDGE, [e for e in member_edges if e["gang_name"]])
    await neo4j_client.write_batch(LINKED_FIRS_EDGE, linked_fir_rows)

    return len(firs)