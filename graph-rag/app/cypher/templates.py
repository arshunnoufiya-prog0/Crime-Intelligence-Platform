"""ALL Cypher lives here, static and parameterized.
NO user/LLM text is ever interpolated. Per the locked key decision, single-param
templates match on the globally-unique `fir_key`; multi-result / list templates
match on `fir_id` (allowing duplicate fir_id across stations to surface as
separate rows).
"""
from ..intent.schema import IntentType


def _linked_match_on(prop: str) -> str:
    return f"MATCH (root:FIR {{{{{prop}: ${prop}}}}})"


FIND_FIR_BY_ID = """
MATCH (f:FIR {fir_key: $fir_key})
OPTIONAL MATCH (f)-[:REGISTERED_AT]->(ps:PoliceStation)
OPTIONAL MATCH (f)-[:INVOLVES_ACCUSED]->(a:Person {role:'accused'})
RETURN f.fir_key AS fir_key, f.fir_id AS fir_id, ps.name AS police_station,
       f.crime_head AS crime_head, f.case_status AS case_status,
       f.case_category AS case_category, f.registration_date AS registration_date,
       f.latitude AS latitude, f.longitude AS longitude,
       collect(DISTINCT a.name) AS accused
LIMIT 1
""".strip()


FIND_FIRS_BY_CRIME_TYPE = """
MATCH (f:FIR)
WHERE toLower(f.crime_head) CONTAINS toLower($crime_head)
  AND ($district IS NULL OR toLower(f.district_name) = toLower($district))
  AND ($date_from IS NULL OR f.registration_date >= $date_from)
  AND ($date_to IS NULL OR f.registration_date <= $date_to)
RETURN f.fir_key AS fir_key, f.fir_id AS fir_id, f.crime_head AS crime_head,
       f.case_status AS case_status, f.district_name AS district_name,
       f.police_station_name AS police_station_name, f.registration_date AS registration_date
ORDER BY f.registration_date DESC LIMIT 50
""".strip()


FIND_FIRS_BY_LOCATION = """
MATCH (f:FIR)-[:REGISTERED_AT]->(ps:PoliceStation)-[:LOCATED_IN]->(d:District)
WHERE ($district IS NULL OR toLower(d.name) = toLower($district))
  AND ($police_station IS NULL OR toLower(ps.name) = toLower($police_station))
RETURN f.fir_key AS fir_key, f.fir_id AS fir_id, ps.name AS police_station,
       d.name AS district, f.crime_head AS crime_head, f.case_status AS case_status,
       f.registration_date AS registration_date
ORDER BY f.registration_date DESC LIMIT 100
""".strip()


FIND_LINKED_FIRS = """
MATCH (root:FIR {fir_key: $fir_key})-[:SIMILAR_PATTERN]-(linked:FIR)
RETURN linked.fir_key AS fir_key, linked.fir_id AS fir_id,
       linked.crime_head AS crime_head, linked.case_status AS case_status,
       linked.police_station_name AS police_station_name,
       linked.registration_date AS registration_date
""".strip()


FIND_SUSPECT_NETWORK = """
MATCH (g:Gang {name: $gang_name})<-[:MEMBER_OF]-(p:Person)
OPTIONAL MATCH (p)<-[:INVOLVES_ACCUSED]-(f:FIR)
RETURN g.name AS gang, collect(DISTINCT p.name) AS members,
       collect(DISTINCT f.fir_key) AS fir_keys,
       collect(DISTINCT f.fir_id) AS fir_ids
""".strip()


FIND_BY_DIGITAL_EVIDENCE = """
MATCH (f:FIR)-[:LINKED_PHONE]->(ph:PhoneNumber {number: $phone_number})
RETURN f.fir_key AS fir_key, f.fir_id AS fir_id, f.crime_head AS crime_head,
       f.case_status AS case_status
UNION
MATCH (f:FIR)-[:LINKED_VEHICLE]->(v:VehicleNumber {plate: $vehicle_number})
RETURN f.fir_key AS fir_key, f.fir_id AS fir_id, f.crime_head AS crime_head,
       f.case_status AS case_status
""".strip()


TEMPLATES: dict[IntentType, str] = {
    IntentType.FIND_FIR_BY_ID: FIND_FIR_BY_ID,
    IntentType.FIND_FIRS_BY_CRIME_TYPE: FIND_FIRS_BY_CRIME_TYPE,
    IntentType.FIND_FIRS_BY_LOCATION: FIND_FIRS_BY_LOCATION,
    IntentType.FIND_LINKED_FIRS: FIND_LINKED_FIRS,
    IntentType.FIND_SUSPECT_NETWORK: FIND_SUSPECT_NETWORK,
    IntentType.FIND_BY_PHONE_OR_VEHICLE: FIND_BY_DIGITAL_EVIDENCE,
    # SEMANTIC_SEARCH has no Cypher template — uses neo4j_client.vector_search()
}


SEMANTIC_INTENTS = {IntentType.SEMANTIC_SEARCH}
