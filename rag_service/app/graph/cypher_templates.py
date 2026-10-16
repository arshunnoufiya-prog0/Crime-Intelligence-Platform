"""Cypher template library (spec §13) — the injection defense.

Every template is a FROZEN string constant with $-parameters. No f-strings,
no .format(), no concatenation — checked structurally by
tests/test_cypher_templates.py (AST: template values must be plain constants).

Every template takes $districts and $stations and applies the RBAC scope
filter, even where it looks redundant — RBAC at one layer only is RBAC that
will eventually be bypassed (§13).

Invariants preserved from the §13 worked example:
  * LIMIT on every template — an unbounded 2-hop traversal hangs the demo;
  * variable-length patterns capped at *1..2 (never *1..3);
  * flat rows, never whole nodes — flat rows serialize to far fewer tokens.

Model deltas applied (Step 6): FIR identity is fir_key (composite);
edge provenance is source_fir = fir_key; Station/Person keys are the codes
created by ingest/normalize.py.

Free-text parameters that need case-insensitive matching are uppercased by
router/plan.py BEFORE they get here; templates then compare against the
normalized properties (name_normalized, station_code, district, crime_code).
"""
from __future__ import annotations

FIR_LOOKUP = """
MATCH (f:FIR {fir_id: $fir_id})
WHERE ($station IS NULL OR f.station_code = $station)
  AND ($districts IS NULL OR f.district IN $districts)
  AND ($stations IS NULL OR f.station_code IN $stations)
OPTIONAL MATCH (f)-[:REGISTERED_AT]->(st:Station)
OPTIONAL MATCH (f)-[:OCCURRED_AT]->(loc:Location)
OPTIONAL MATCH (f)-[:CLASSIFIED_AS]->(ct:CrimeType)
OPTIONAL MATCH (p:Person)-[a:ACCUSED_IN]->(f)
OPTIONAL MATCH (comp:Person)-[:COMPLAINANT_IN]->(f)
OPTIONAL MATCH (f)-[:INVESTIGATED_BY]->(io:Person)
RETURN f.fir_key AS fir_key, f.fir_id AS fir_id,
       f.station_code AS station_code, st.name AS station_name,
       f.occurred_on AS occurred_on, f.registered_on AS registered_on,
       f.case_status AS case_status, f.case_category AS case_category,
       ct.name AS crime_type, loc.address AS address,
       collect(DISTINCT p.name) AS accused, io.name AS investigating_officer
LIMIT 20
"""

PERSON_PROFILE = """
MATCH (p:Person {name_normalized: $person_name})-[r:ACCUSED_IN|COMPLAINANT_IN]-(f:FIR)
WHERE ($districts IS NULL OR f.district IN $districts)
  AND ($stations IS NULL OR f.station_code IN $stations)
RETURN p.person_key AS person_key, p.name AS person_name, p.role AS role,
       type(r) AS role_in_fir, f.fir_key AS fir_key, f.fir_id AS fir_id,
       f.crime_head AS crime_head, f.occurred_on AS occurred_on,
       f.station_name AS station_name, f.case_status AS case_status
ORDER BY f.occurred_on DESC
LIMIT 100
"""

PERSON_NETWORK = """
MATCH (p:Person {name_normalized: $person_name})
CALL {
  WITH p
  MATCH path = (p)-[:ASSOCIATE_OF|SAME_NAME_AS*1..2]-(other:Person)
  RETURN path
  LIMIT 400
}
UNWIND relationships(path) AS r
WITH p, r, startNode(r) AS a, endNode(r) AS b
MATCH (f:FIR {fir_key: r.source_fir})
WHERE ($districts IS NULL OR f.district IN $districts)
  AND ($stations IS NULL OR f.station_code IN $stations)
RETURN DISTINCT
  a.person_key AS src, a.name AS src_name,
  b.person_key AS dst, b.name AS dst_name,
  type(r) AS rel_type,
  coalesce(r.strength, r.confidence) AS weight,
  r.source_fir AS source_fir, f.fir_id AS source_fir_id
LIMIT 300
"""

PATTERN_SEARCH = """
MATCH (f:FIR)
WHERE ($crime_code IS NULL OR f.crime_code = $crime_code)
  AND ($date_from IS NULL OR f.occurred_on >= $date_from)
  AND ($date_to IS NULL OR f.occurred_on <= $date_to)
  AND ($locality IS NULL OR toUpper(f.address) CONTAINS $locality)
  AND ($districts IS NULL OR f.district IN $districts)
  AND ($stations IS NULL OR f.station_code IN $stations)
RETURN f.fir_key AS fir_key, f.fir_id AS fir_id,
       f.crime_head AS crime_head, f.occurred_on AS occurred_on,
       f.station_name AS station_name, f.address AS address,
       f.stolen_items AS stolen_items
ORDER BY f.occurred_on DESC
LIMIT 100
"""

STATION_STATS = """
MATCH (f:FIR)-[:REGISTERED_AT]->(s:Station)
WHERE ($date_from IS NULL OR f.registered_on >= $date_from)
  AND ($date_to IS NULL OR f.registered_on <= $date_to)
  AND ($districts IS NULL OR f.district IN $districts)
  AND ($stations IS NULL OR f.station_code IN $stations)
RETURN s.station_code AS station_code, s.name AS station_name,
       count(f) AS fir_count, count(DISTINCT f.crime_code) AS crime_types
ORDER BY fir_count DESC
LIMIT 40
"""

CRIME_TREND = """
MATCH (f:FIR)
WHERE ($crime_code IS NULL OR f.crime_code = $crime_code)
  AND ($date_from IS NULL OR f.occurred_on >= $date_from)
  AND ($date_to IS NULL OR f.occurred_on <= $date_to)
  AND ($districts IS NULL OR f.district IN $districts)
  AND ($stations IS NULL OR f.station_code IN $stations)
RETURN f.crime_head AS crime_head,
       substring(f.occurred_on, 0, 7) AS month,
       count(*) AS fir_count
ORDER BY month, fir_count DESC
LIMIT 200
"""

REPEAT_OFFENDERS = """
MATCH (p:Person)-[:ACCUSED_IN]->(f:FIR)
WHERE ($districts IS NULL OR f.district IN $districts)
  AND ($stations IS NULL OR f.station_code IN $stations)
WITH p, count(f) AS fir_count, collect(f.fir_id)[..10] AS fir_ids
WHERE fir_count >= coalesce($min_firs, 2)
RETURN p.person_key AS person_key, p.name AS person_name,
       fir_count, fir_ids
ORDER BY fir_count DESC
LIMIT 50
"""

SHARED_IDENTIFIER = """
MATCH (f1:FIR)-[:HAS_EVIDENCE]->(x)<-[:HAS_EVIDENCE]-(f2:FIR)
WHERE elementId(f1) < elementId(f2)
  AND ($kind IS NULL OR $kind IN labels(x))
  AND ($value IS NULL OR coalesce(x.msisdn, x.registration, x.account_ref, x.imei) = $value)
  AND ($districts IS NULL OR f1.district IN $districts)
  AND ($stations IS NULL OR f1.station_code IN $stations)
  AND ($districts IS NULL OR f2.district IN $districts)
  AND ($stations IS NULL OR f2.station_code IN $stations)
RETURN labels(x)[0] AS evidence_kind,
       coalesce(x.msisdn, x.registration, x.account_ref, x.imei) AS identifier,
       f1.fir_key AS fir_key_1, f1.fir_id AS fir_id_1, f1.station_name AS station_1,
       f2.fir_key AS fir_key_2, f2.fir_id AS fir_id_2, f2.station_name AS station_2
LIMIT 100
"""

GEO_CLUSTER = """
MATCH (f:FIR)
WHERE ($locality IS NULL OR toUpper(f.address) CONTAINS $locality)
  AND ($lat IS NULL OR $lon IS NULL OR
       point.distance(point({latitude: f.latitude, longitude: f.longitude}),
                      point({latitude: $lat, longitude: $lon})) <= coalesce($radius_m, 2000))
  AND ($districts IS NULL OR f.district IN $districts)
  AND ($stations IS NULL OR f.station_code IN $stations)
RETURN f.fir_key AS fir_key, f.fir_id AS fir_id, f.address AS address,
       f.latitude AS latitude, f.longitude AS longitude,
       f.crime_head AS crime_head, f.occurred_on AS occurred_on
ORDER BY f.occurred_on DESC
LIMIT 100
"""

MODUS_OPERANDI_MATCH = """
MATCH (f:FIR)
WHERE ($crime_code IS NULL OR f.crime_code = $crime_code)
  AND ($stolen_item IS NULL OR any(s IN f.stolen_items WHERE toUpper(s) = $stolen_item))
  AND ($weapon IS NULL OR toUpper(f.weapon) = $weapon)
  AND ($districts IS NULL OR f.district IN $districts)
  AND ($stations IS NULL OR f.station_code IN $stations)
RETURN f.fir_key AS fir_key, f.fir_id AS fir_id, f.crime_head AS crime_head,
       f.stolen_items AS stolen_items, f.weapon AS weapon,
       f.occurred_on AS occurred_on, f.station_name AS station_name
ORDER BY f.occurred_on DESC
LIMIT 100
"""

EVIDENCE_TRAIL = """
MATCH (f:FIR)
WHERE ($fir_id IS NULL OR f.fir_id = $fir_id)
  AND ($person_name IS NULL OR EXISTS {
        MATCH (p:Person {name_normalized: $person_name})-[r:ACCUSED_IN|COMPLAINANT_IN]-(f)
      })
  AND ($districts IS NULL OR f.district IN $districts)
  AND ($stations IS NULL OR f.station_code IN $stations)
OPTIONAL MATCH (f)-[h:HAS_EVIDENCE]->(x)
RETURN f.fir_key AS fir_key, f.fir_id AS fir_id, f.crime_head AS crime_head,
       f.station_name AS station_name, f.occurred_on AS occurred_on,
       labels(x)[0] AS evidence_kind,
       coalesce(x.msisdn, x.registration, x.account_ref, x.imei) AS evidence_ref,
       h.source_fir_id AS source_fir_id
LIMIT 200
"""

FREEFORM_SEARCH = """
CALL db.index.fulltext.queryNodes('fir_text', $query_text)
YIELD node AS f
WHERE ($districts IS NULL OR f.district IN $districts)
  AND ($stations IS NULL OR f.station_code IN $stations)
RETURN f.fir_key AS fir_key, f.fir_id AS fir_id, f.crime_head AS crime_head,
       f.narrative AS narrative, f.station_name AS station_name,
       f.occurred_on AS occurred_on
LIMIT 50
"""

TEMPLATES: dict[str, str] = {
    "FIR_LOOKUP": FIR_LOOKUP,
    "PERSON_PROFILE": PERSON_PROFILE,
    "PERSON_NETWORK": PERSON_NETWORK,
    "PATTERN_SEARCH": PATTERN_SEARCH,
    "STATION_STATS": STATION_STATS,
    "CRIME_TREND": CRIME_TREND,
    "REPEAT_OFFENDERS": REPEAT_OFFENDERS,
    "SHARED_IDENTIFIER": SHARED_IDENTIFIER,
    "GEO_CLUSTER": GEO_CLUSTER,
    "MODUS_OPERANDI_MATCH": MODUS_OPERANDI_MATCH,
    "EVIDENCE_TRAIL": EVIDENCE_TRAIL,
    "FREEFORM_SEARCH": FREEFORM_SEARCH,
}

INTENT_IDS = tuple(TEMPLATES.keys())
