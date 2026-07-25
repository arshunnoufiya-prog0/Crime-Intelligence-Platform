"""Graph schema for the Bengaluru 40-PS / 1000-FIR dataset.

Node/edge property names are derived from the actual
`bengaluru_40ps_1000_firs.json` top-level keys (read at build time):
fir_id, fir_metadata, occurrence_location, offence_details,
occurrence_details, complainant_details, accused_details,
incident_details, criminal_network, digital_evidence,
physical_evidence, ai_metadata, investigating_officer.

KEY STRATEGY
------------
`fir_id` is NOT globally unique in the dataset (700 unique out of 1000;
composite (fir_id, police_station) is ~995-unique). We therefore synthesise
a globally-unique property `fir_key = "<fir_id>@<police_station>"` and use it
as the unique constraint + the match key for all single-param templates
and the subgraph endpoint. The original `fir_id` is preserved as a secondary
indexed property so multi-result templates (search by crime type, semantic
search) still return rows naturally.
"""

NODE_LABELS = [
    "FIR",
    "District",
    "PoliceStation",
    "Person",
    "PhoneNumber",
    "VehicleNumber",
    "BankAccount",
    "Gang",
]

EDGE_TYPES = [
    "REGISTERED_AT",     # (FIR)->(PoliceStation)
    "LOCATED_IN",        # (PoliceStation)->(District)
    "INVOLVES_ACCUSED",  # (FIR)->(Person {role:'accused'})
    "FILED_BY",          # (FIR)->(Person {role:'complainant'})
    "INVESTIGATED_BY",   # (FIR)->(Person {role:'officer'})
    "LINKED_PHONE",      # (FIR)->(PhoneNumber)
    "LINKED_VEHICLE",    # (FIR)->(VehicleNumber)
    "LINKED_ACCOUNT",    # (FIR)->(BankAccount)
    "MEMBER_OF",         # (Person)->(Gang)
    "SIMILAR_PATTERN",   # (FIR)-(FIR) from ai_metadata.linked_firs
]

# All Cypher here is parameterized and static. The multi-statement init script
# is executed by scripts/setup_neo4j_schema.py against Neo4j 5.x.
CONSTRAINT_CYPHER = [
    "CREATE CONSTRAINT fir_key_unique IF NOT EXISTS FOR (f:FIR) REQUIRE f.fir_key IS UNIQUE",
    "CREATE CONSTRAINT district_name_unique IF NOT EXISTS FOR (d:District) REQUIRE d.name IS UNIQUE",
    "CREATE CONSTRAINT ps_name_unique IF NOT EXISTS FOR (ps:PoliceStation) REQUIRE ps.name IS UNIQUE",
    # Person uniqueness is by (name, role) -> modelled as a single composite-typed key is not supported as
    # a simple constraint on property, so we key on a synthetic `person_key`.
    "CREATE CONSTRAINT person_key_unique IF NOT EXISTS FOR (p:Person) REQUIRE p.person_key IS UNIQUE",
    "CREATE CONSTRAINT phone_number_unique IF NOT EXISTS FOR (ph:PhoneNumber) REQUIRE ph.number IS UNIQUE",
    "CREATE CONSTRAINT vehicle_plate_unique IF NOT EXISTS FOR (v:VehicleNumber) REQUIRE v.plate IS UNIQUE",
    "CREATE CONSTRAINT bank_account_unique IF NOT EXISTS FOR (b:BankAccount) REQUIRE b.account_id IS UNIQUE",
    "CREATE CONSTRAINT gang_name_unique IF NOT EXISTS FOR (g:Gang) REQUIRE g.name IS UNIQUE",
]

INDEX_CYPHER = [
    "CREATE INDEX fir_id_index IF NOT EXISTS FOR (f:FIR) ON (f.fir_id)",
    "CREATE INDEX fir_crime_head_index IF NOT EXISTS FOR (f:FIR) ON (f.crime_head)",
    "CREATE INDEX fir_case_status_index IF NOT EXISTS FOR (f:FIR) ON (f.case_status)",
    "CREATE INDEX fir_registration_date_index IF NOT EXISTS FOR (f:FIR) ON (f.registration_date)",
]

VECTOR_INDEX_CYPHER = """
CREATE VECTOR INDEX fir_embedding_index IF NOT EXISTS
FOR (f:FIR) ON (f.embedding)
OPTIONS {indexConfig: {
  `vector.dimensions`: 1024,
  `vector.similarity_function`: 'cosine'
}}
""".strip()


def fir_key(fir_id: str, police_station: str) -> str:
    """Synthesise a globally-unique FIR key from (fir_id, police_station)."""
    return f"{fir_id}@{police_station}"


def person_key(name: str, role: str) -> str:
    """Synthesise a unique key for a Person node by (name, role)."""
    return f"{name}::{role}"
