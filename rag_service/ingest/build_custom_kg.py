#!/usr/bin/env python3
"""Step 8 — deterministic LightRAG custom-KG builder (spec §2.2, §9.1).

ZERO LLM calls at index time: entities, relationships and chunks are all
template-generated from the structured FIR JSON via normalize.py. The
INDEXING_IN_PROGRESS flag in app.retrieval.lightrag_engine makes
llm_model_func RAISE while indexing, so the guarantee is enforced, and this
script asserts after the run that it was never violated (§15 Step 8 gate).

Weights (§9.1 rule 5): 1.0 explicit-in-FIR · 0.7 criminal-network co-occurrence ·
0.4 shared identifier / name-only match · never below 0.4, omitted otherwise.

source_id is the citable fir_id (§9.1 rules 2/6 — this is what makes
citation-by-fir_id mechanically possible); descriptions carry the station so
ambiguous fir_ids stay distinguishable in the KG.

Chunks: real narrative prose found in Step 1 (§5.3), token-counted exactly via
the llama-server /tokenize endpoint (§11.1) — no heuristics.

Batches of 200 FIRs per insert_custom_kg call (§9.1 rule 7). Gate: entities>0,
INDEXING_IN_PROGRESS never violated, wall clock < 10 min.

Run inside the rag container:  python ingest/run_ingest.py
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

RAG_SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAG_SERVICE_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import httpx  # noqa: E402

import discover_schema  # noqa: E402
import normalize as N  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.retrieval import lightrag_engine as engine  # noqa: E402
from app.llm.tokens import count_tokens  # noqa: E402

KG_REPORT_PATH = REPO_ROOT / "artifacts" / "kg_ingest_report.json"
BATCH_FIRS = 200
WALL_CLOCK_LIMIT_S = 600.0

W_EXPLICIT = 1.0
W_COOCCURRENCE = 0.7
W_SHARED = 0.4
SAME_NAME_CONFIDENCE = 0.5

REL_KEYWORDS = {
    "ACCUSED_IN": "accused, charged, named, case",
    "COMPLAINANT_IN": "complainant, filed, reported, victim",
    "INVESTIGATED_BY": "investigating officer, handles, investigates",
    "ASSOCIATE_OF": "associate, accomplice, criminal network, linked",
    "MEMBER_OF": "member, gang, belongs, network",
    "SAME_NAME_AS": "same name, possible identity, unconfirmed",
    "REGISTERED_AT": "registered, filed at, police station",
    "OCCURRED_AT": "occurred, location, place, area",
    "CLASSIFIED_AS": "classified, crime type, head, category",
    "INVOKES": "invokes, charged under, section, act",
    "HAS_EVIDENCE": "evidence, linked, seized, recovered",
}


def _fir_entity_name(fir_id: str, station_code: str, ambiguous: bool) -> str:
    """§9.1 rule 2 lets LightRAG merge same-name entities across FIRs — but
    two DIFFERENT FIRs sharing a duplicated fir_id must never merge, so the
    300 ambiguous fir_ids get their station in the entity name."""
    return f"FIR {fir_id} ({station_code})" if ambiguous else f"FIR {fir_id}"


def _fir_desc(rec: dict) -> str:
    return (
        f"FIR {rec['fir_id']} ({rec['crime_head']}) registered at "
        f"{rec['station_name']} on {rec['registered_on']}. Status: {rec['case_status']}."
    )


def _person_desc(name: str, role: str, rec: dict) -> str:
    """§9.1 rule 3 template, adjusted for this corpus (no age field — recorded
    as a model delta in artifacts/kg_ingest_report.json)."""
    return (
        f"{name}, {role} in {rec['fir_id']} ({rec['crime_head']}) registered at "
        f"{rec['station_name']} on {rec['registered_on']}."
    )


def build_custom_kg_payload(records: list[dict], same_name: list[dict]) -> dict:
    """Pure, deterministic payload builder — no I/O, no LLM. One entity entry
    per (entity, source FIR) so LightRAG merges cross-FIR entities itself
    (§9.1 rule 2)."""
    fir_id_counts: dict[str, int] = {}
    for rec in records:
        fir_id_counts[rec["fir_id"]] = fir_id_counts.get(rec["fir_id"], 0) + 1
    identifier_fir_counts: dict[tuple[str, str], set[str]] = {}

    for rec in records:
        for phone in rec["phones"]:
            identifier_fir_counts.setdefault(("PHONE", phone), set()).add(rec["fir_key"])
        for vehicle in rec["vehicles"]:
            identifier_fir_counts.setdefault(("VEHICLE", vehicle), set()).add(rec["fir_key"])
        for account in rec["accounts"]:
            identifier_fir_counts.setdefault((account["kind"], account["account_ref"]), set()).add(rec["fir_key"])
        for imei in rec["imeis"]:
            identifier_fir_counts.setdefault(("IMEI", imei), set()).add(rec["fir_key"])

    chunks: list[dict] = []
    entities: list[dict] = []
    relationships: list[dict] = []
    fir_key_to_entity: dict[str, str] = {}

    def rel(src: str, tgt: str, rtype: str, description: str, weight: float, source_id: str) -> None:
        relationships.append({
            "src_id": src, "tgt_id": tgt, "description": description,
            "keywords": REL_KEYWORDS[rtype], "weight": weight, "source_id": source_id,
        })

    for rec in records:
        fid, fk = rec["fir_id"], rec["fir_key"]
        fir_entity = _fir_entity_name(fid, rec["station_code"], fir_id_counts[fid] > 1)
        fir_key_to_entity[fk] = fir_entity
        entities.append({
            "entity_name": fir_entity, "entity_type": "FIR",
            "description": _fir_desc(rec), "source_id": fid,
        })

        def add_person(name: str, role: str, key: str) -> str:
            ename = N.normalize_text(name)
            entities.append({
                "entity_name": ename, "entity_type": "Person",
                "description": _person_desc(name, role, rec), "source_id": fid,
            })
            return ename

        if rec["complainant"]:
            e = add_person(rec["complainant"]["name"], "complainant", rec["complainant"]["person_key"])
            rel(e, fir_entity, "COMPLAINANT_IN",
                f"{rec['complainant']['name']} filed FIR {fid} at {rec['station_name']}.",
                W_EXPLICIT, fid)
        for acc in rec["accused"]:
            if acc["placeholder"]:
                continue
            e = add_person(acc["name"], "accused", acc["person_key"])
            rel(e, fir_entity, "ACCUSED_IN",
                f"{acc['name']} is accused in FIR {fid} at {rec['station_name']}.",
                W_EXPLICIT, fid)
        if rec["investigating_officer"]:
            e = add_person(rec["investigating_officer"]["name"], "investigating officer",
                           rec["investigating_officer"]["person_key"])
            rel(fir_entity, e, "INVESTIGATED_BY",
                f"FIR {fid} is investigated by {rec['investigating_officer']['name']}.",
                W_EXPLICIT, fid)

        station_entity = N.normalize_text(rec["station_name"])
        entities.append({"entity_name": station_entity, "entity_type": "Station",
                          "description": f"{rec['station_name']} police station, {rec['district_name']}.",
                          "source_id": fid})
        rel(fir_entity, station_entity, "REGISTERED_AT",
            f"FIR {fid} was registered at {rec['station_name']}.", W_EXPLICIT, fid)

        location_entity = N.code_name(rec["address"]) or rec["location_key"]
        entities.append({"entity_name": location_entity, "entity_type": "Location",
                          "description": f"Occurrence location of FIR {fid}: {rec['address']}.",
                          "source_id": fid})
        rel(fir_entity, location_entity, "OCCURRED_AT",
            f"FIR {fid} occurred at {rec['address']}.", W_EXPLICIT, fid)

        crime_entity = N.normalize_text(rec["crime_head"])
        entities.append({"entity_name": crime_entity, "entity_type": "CrimeType",
                         "description": f"Crime classification {rec['crime_head']}.", "source_id": fid})
        rel(fir_entity, crime_entity, "CLASSIFIED_AS",
            f"FIR {fid} is classified as {rec['crime_head']}.", W_EXPLICIT, fid)

        for section in rec["sections"]:
            entities.append({"entity_name": section, "entity_type": "Section",
                             "description": f"Legal section {section} invoked in FIR {fid}.",
                             "source_id": fid})
            rel(fir_entity, section, "INVOKES",
                f"FIR {fid} invokes section {section}.", W_EXPLICIT, fid)

        def add_identifier(kind: str, value: str, evidence_desc: str) -> None:
            shared = len(identifier_fir_counts[(kind, value)]) > 1
            entities.append({"entity_name": value, "entity_type": kind,
                             "description": evidence_desc, "source_id": fid})
            rel(fir_entity, value, "HAS_EVIDENCE",
                f"FIR {fid} references {kind.lower()} {value}.",
                W_SHARED if shared else W_EXPLICIT, fid)

        for phone in rec["phones"]:
            add_identifier("PHONE", phone, f"Phone number linked to FIR {fid}.")
        for vehicle in rec["vehicles"]:
            add_identifier("VEHICLE", vehicle, f"Vehicle {vehicle} linked to FIR {fid}.")
        for account in rec["accounts"]:
            add_identifier(account["kind"], account["account_ref"],
                           f"{account['kind'].title()} {account['raw']} linked to FIR {fid}.")
        for imei in rec["imeis"]:
            add_identifier("IMEI", imei, f"Device IMEI {imei} linked to FIR {fid}.")

        if rec["gang"]:
            gang_entity = N.normalize_text(rec["gang"])
            network_persons: list[str] = []
            if rec["mastermind"]:
                me = add_person(rec["mastermind"]["name"], "suspected mastermind", rec["mastermind"]["person_key"])
                network_persons.append(me)
            for assoc in rec["associates"]:
                ae = add_person(assoc, "known associate", N.person_key_of(fk, "associate", assoc))
                network_persons.append(ae)
                rel(ae, gang_entity, "MEMBER_OF",
                    f"{assoc} is linked to gang {rec['gang']} in FIR {fid}.",
                    W_COOCCURRENCE, fid)
            for i, a in enumerate(network_persons):
                for b in network_persons[i + 1:]:
                    rel(a, b, "ASSOCIATE_OF",
                        f"{a} and {b} co-occur in the criminal network of FIR {fid}.",
                        W_COOCCURRENCE, fid)

        chunks.append({
            "content": (
                f"FIR {fid} | {rec['station_name']} | {rec['occurred_on']} | "
                f"{rec['crime_head']}\n{rec['narrative']}"
            ),
            "source_id": fid,
        })

    fir_key_by_index = {rec["fir_key"]: i for i, rec in enumerate(records)}
    same_name_rels: list[dict] = []
    name_persons: dict[str, str] = {}
    for rec in records:
        if rec["complainant"]:
            name_persons[rec["complainant"]["person_key"]] = N.normalize_text(rec["complainant"]["name"])
        for acc in rec["accused"]:
            if not acc["placeholder"]:
                name_persons[acc["person_key"]] = N.normalize_text(acc["name"])
        if rec["investigating_officer"]:
            name_persons[rec["investigating_officer"]["person_key"]] = N.normalize_text(rec["investigating_officer"]["name"])
        if rec["mastermind"]:
            name_persons[rec["mastermind"]["person_key"]] = N.normalize_text(rec["mastermind"]["name"])
        for assoc in rec["associates"]:
            name_persons[N.person_key_of(rec["fir_key"], "associate", assoc)] = N.normalize_text(assoc)
    for edge in same_name:
        a_name = name_persons.get(edge["a"])
        b_name = name_persons.get(edge["b"])
        if not a_name or not b_name:
            continue
        source_fir_id = edge["source_fir"].split("@")[0].split("#")[0]
        same_name_rels.append({
            "src_id": a_name, "tgt_id": b_name,
            "description": (
                f"{a_name} and {b_name} share the same name across FIRs — "
                "possible identity match, not confirmed (§5.6/§18.1)."
            ),
            "keywords": REL_KEYWORDS["SAME_NAME_AS"],
            "weight": W_SHARED, "source_id": source_fir_id,
        })

    return {
        "chunks": chunks, "entities": entities,
        "relationships": relationships + same_name_rels,
    }


async def verify_chunk_tokens(payload: dict) -> None:
    """Exact token counting for every chunk via llama-server /tokenize (§11.1).
    Fails loud if any chunk exceeds the embedding budget (§7/§9)."""
    settings = get_settings()
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
        for chunk in payload["chunks"]:
            n = await count_tokens(client, settings.embed_tokenize_url, chunk["content"])
            if n > settings.chunk_token_size:
                raise RuntimeError(
                    f"chunk for source {chunk['source_id']} is {n} tokens > "
                    f"cap {settings.chunk_token_size} (§9) — split the narrative"
                )


async def assert_qdrant_collections() -> dict[str, int]:
    """§10.3: LightRAG manages its own collections — do not create them by
    hand, but DO assert they exist post-ingest with vector size 1024."""
    settings = get_settings()
    dims: dict[str, int] = {}
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        r = await client.get(f"{settings.qdrant_url.rstrip('/')}/collections")
        r.raise_for_status()
        names = [c["name"] for c in r.json()["result"]["collections"]]
        if not names:
            raise RuntimeError("Qdrant has no collections after ingest (§10.3)")
        for name in names:
            rr = await client.get(f"{settings.qdrant_url.rstrip('/')}/collections/{name}")
            rr.raise_for_status()
            size = rr.json()["result"]["config"]["params"]["vectors"]["size"]
            if size != settings.embed_dim:
                raise RuntimeError(
                    f"Qdrant collection {name} has vector size {size} != {settings.embed_dim} (§10.3)"
                )
            dims[name] = size
    return dims


async def run() -> int:
    settings = get_settings()
    dataset = discover_schema.load_dataset()
    records = N.normalize_records(dataset)
    same_name = N.same_name_edges(records)
    payload = build_custom_kg_payload(records, same_name)

    print(f"Step 8 — custom KG: {len(payload['entities'])} entities, "
          f"{len(payload['relationships'])} relationships, {len(payload['chunks'])} chunks")
    await verify_chunk_tokens(payload)

    engine.INDEXING_IN_PROGRESS = True
    engine.llm_calls_during_indexing = 0
    started = time.monotonic()
    rag = None
    try:
        rag = await engine.open_engine()
        for i in range(0, len(records), BATCH_FIRS):
            batch_firs = records[i:i + BATCH_FIRS]
            batch_keys = {r["fir_key"] for r in batch_firs}
            batch_fir_ids = {r["fir_id"] for r in batch_firs}
            batch_payload = {
                "chunks": [c for c in payload["chunks"] if c["source_id"] in batch_fir_ids],
                "entities": [e for e in payload["entities"] if e["source_id"] in batch_fir_ids],
                "relationships": [r for r in payload["relationships"] if r["source_id"] in batch_fir_ids],
            }
            await engine.insert_custom_kg(rag, batch_payload)
            print(f"  inserted batch {i // BATCH_FIRS + 1}: {len(batch_firs)} FIRs "
                  f"(cumulative entities {len(batch_payload['entities'])})")
        if engine.llm_calls_during_indexing != 0:
            raise RuntimeError(
                f"zero-LLM-indexing contract violated: {engine.llm_calls_during_indexing} "
                "LLM calls attempted during ingest (§15 Step 8 gate)"
            )
        qdrant_dims = await assert_qdrant_collections()
    finally:
        engine.INDEXING_IN_PROGRESS = False
        await engine.close_engine(rag)

    elapsed = time.monotonic() - started
    gates_ok = (
        len(payload["entities"]) > 0
        and engine.llm_calls_during_indexing == 0
        and elapsed < WALL_CLOCK_LIMIT_S
    )
    report = {
        "spec": "ksp-iis-build-prompt-v3.1 §2.2/§9.1",
        "entities": len(payload["entities"]),
        "relationships": len(payload["relationships"]),
        "chunks": len(payload["chunks"]),
        "batches": (len(records) + BATCH_FIRS - 1) // BATCH_FIRS,
        "wall_clock_s": round(elapsed, 1),
        "llm_calls_during_indexing": engine.llm_calls_during_indexing,
        "qdrant_collections": qdrant_dims,
        "gates_pass": gates_ok,
        "model_deltas": [
            "No age field in corpus — §9.1 rule 3 description template omits age.",
            "source_id = fir_id (citable); station in description disambiguates the "
            "300 duplicated fir_ids. FIR entity names append station for those.",
            "SAME_NAME_AS weight 0.4 (name-only, never merges; §5.6) chained n-1 per cluster.",
            "Identifier evidence weight: 1.0 when an identifier appears in one FIR, "
            "0.4 when shared across FIRs (§9.1 rule 5).",
        ],
    }
    KG_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    KG_REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"  wall clock: {elapsed:.1f}s | LLM calls during indexing: "
          f"{engine.llm_calls_during_indexing} | qdrant: {qdrant_dims}")
    print(f"Wrote {KG_REPORT_PATH}")
    if not gates_ok:
        print(f"BLOCKED: Step 8 — gate failed (entities>0: {len(payload['entities']) > 0}, "
              f"zero-LLM: {engine.llm_calls_during_indexing == 0}, "
              f"under 10 min: {elapsed < WALL_CLOCK_LIMIT_S}).")
        return 1
    print("GATE PASS — Step 8 complete (§15 Step 8): deterministic KG ingested, zero LLM calls.")
    return 0


def main() -> int:
    return asyncio.run(run())


if __name__ == "__main__":
    sys.exit(main())
