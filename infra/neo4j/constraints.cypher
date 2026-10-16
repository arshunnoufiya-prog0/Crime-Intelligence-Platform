// ksp-iis Neo4j constraints + indexes (spec §5.5, reconciled in Step 6).
//
// MODEL DELTA (spec §5.4 preamble: "the report wins, record the delta"):
//   schema_report.json → citation_contract.id_uniqueness shows fir_id is NOT
//   globally unique (700/1000; (fir_id, police_station) leaves 5 exact
//   duplicates). The FIR uniqueness constraint therefore moved from fir_id
//   to the composite `fir_key` ("<fir_id>@<STATION_CODE>" with an
//   occurrence suffix for the 5 exact-duplicate pairs). fir_id keeps a
//   NON-unique index for citation lookups.
//
// Fulltext index adjusted to the real narrative fields from §5.3: the only
// prose field in this corpus is incident_details.truth_of_incident, stored
// on the FIR node as `narrative`. There is no `summary` field.

CREATE CONSTRAINT fir_key_unique IF NOT EXISTS
  FOR (f:FIR) REQUIRE f.fir_key IS UNIQUE;
CREATE CONSTRAINT person_key_unique IF NOT EXISTS
  FOR (p:Person) REQUIRE p.person_key IS UNIQUE;
CREATE CONSTRAINT station_code_unique IF NOT EXISTS
  FOR (s:Station) REQUIRE s.station_code IS UNIQUE;
CREATE CONSTRAINT phone_unique IF NOT EXISTS
  FOR (p:Phone) REQUIRE p.msisdn IS UNIQUE;
CREATE CONSTRAINT vehicle_unique IF NOT EXISTS
  FOR (v:Vehicle) REQUIRE v.registration IS UNIQUE;
CREATE CONSTRAINT account_unique IF NOT EXISTS
  FOR (a:Account) REQUIRE a.account_ref IS UNIQUE;
CREATE CONSTRAINT device_unique IF NOT EXISTS
  FOR (d:Device) REQUIRE d.imei IS UNIQUE;
CREATE CONSTRAINT location_unique IF NOT EXISTS
  FOR (l:Location) REQUIRE l.location_key IS UNIQUE;
CREATE CONSTRAINT crimetype_unique IF NOT EXISTS
  FOR (c:CrimeType) REQUIRE c.crime_code IS UNIQUE;
CREATE CONSTRAINT section_unique IF NOT EXISTS
  FOR (s:Section) REQUIRE s.section_code IS UNIQUE;

// Indexes (spec §5.5) — FIR.date/district/person_name use the flattened
// properties created by the Step 6 loader.
CREATE INDEX fir_date     IF NOT EXISTS FOR (f:FIR) ON (f.occurred_on);
CREATE INDEX fir_district IF NOT EXISTS FOR (f:FIR) ON (f.district);
CREATE INDEX person_name  IF NOT EXISTS FOR (p:Person) ON (p.name_normalized);

// Model-delta indexes: fir_id (citation lookups) + station_code (RBAC scope
// filters inside every Cypher template, §13).
CREATE INDEX fir_id       IF NOT EXISTS FOR (f:FIR) ON (f.fir_id);
CREATE INDEX fir_station  IF NOT EXISTS FOR (f:FIR) ON (f.station_code);

// Fulltext over the real narrative field (§5.3: truth_of_incident only).
CREATE FULLTEXT INDEX fir_text IF NOT EXISTS
  FOR (f:FIR) ON EACH [f.narrative];
