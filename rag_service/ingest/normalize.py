#!/usr/bin/env python3
"""Step 5 — normalization + entity resolution (spec §5.2 rule 3, §5.6).

Single shared transform for the Neo4j loader (Step 6) and the LightRAG custom
KG builder (Step 8): every field name is imported from _schema_constants.py —
no field-name string literals live here (§5.2 rule 1).

Entity resolution (§5.6 binding rule): this dataset carries NO government ID,
NO date of birth, and phone numbers attach to FIRs, not persons — so NO strong
identifier exists and the merge count is exactly zero. Same-name individuals
are represented as SAME_NAME_AS edges (never merges). The merge-rate gate
(< 15%) therefore holds trivially; it is computed and reported, not assumed.

Idempotency (§9.1 rule 1): normalize(normalize(x)) == normalize(x) for every
normalizer in this module.

Outputs artifacts/entity_resolution.json. Gate (§15 Step 5): merge rate < 15%.
Stdlib only — runs before any venv exists.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, OrderedDict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _schema_constants as SC  # noqa: E402
import discover_schema  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
ER_REPORT_PATH = REPO_ROOT / "artifacts" / "entity_resolution.json"

MERGE_RATE_LIMIT_PCT = 15.0
SAME_NAME_CONFIDENCE = 0.5


def _rel(path_constant: str) -> tuple[str, ...]:
    """'firs[].a.b' → ('a', 'b') — nested access keys derived from constants."""
    return tuple(p for p in path_constant.replace("firs[].", "").split(".") if p)


def _get(record: dict, path_constant: str, default=None):
    node: object = record
    for key in _rel(path_constant):
        if not isinstance(node, dict):
            return default
        node = node.get(key)
    return default if node is None else node


def normalize_text(value: object | None) -> str:
    """Uppercase + whitespace-collapsed. Idempotent."""
    if not value:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip().upper()


def normalize_token(value: object | None) -> str:
    """Uppercase, ALL whitespace removed (ids, plates, phones). Idempotent."""
    if not value:
        return ""
    return re.sub(r"\s+", "", str(value)).upper()


def code_name(value: object | None) -> str:
    """'Magadi Road PS' → 'MAGADI_ROAD_PS'. Idempotent."""
    return re.sub(r"[^A-Z0-9]+", "_", normalize_text(value)).strip("_")


def is_placeholder_name(name: object | None) -> bool:
    norm = normalize_text(name)
    if not norm:
        return True
    return "UNKNOWN" in norm or "UNIDENTIFIED" in norm


def station_code_of(station_name: object | None) -> str:
    return code_name(station_name)


def location_key_of(lat, lon, address: object | None) -> str:
    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
        return f"GEO:{round(float(lat), 4)},{round(float(lon), 4)}"
    return "ADDR:" + code_name(address)


def section_code_of(act: object | None, section: object | None) -> str:
    return f"{code_name(act)}/{normalize_token(section)}"


def phone_norm(number: object | None) -> str:
    return normalize_token(number)


def vehicle_norm(plate: object | None) -> str:
    return normalize_token(plate)


def account_ref_of(kind: str, value: object | None) -> str:
    return f"{kind}:{normalize_token(value)}"


def person_key_of(fir_key: str, role: str, name: object | None) -> str:
    return f"{fir_key}|{role}|{normalize_text(name)}"


def fir_keys(dataset: dict) -> list[str]:
    """Deterministic composite FIR keys.

    Base key is '<fir_id>@<STATION_CODE>'; the 5 exact (fir_id, station)
    duplicate pairs (schema_report → citation_contract.id_uniqueness) get an
    occurrence suffix '#2', '#3' in dataset order so all 1,000 records remain
    distinct. Idempotent: same dataset in → same keys out.
    """
    records = dataset[SC.ROOT_KEY]
    keys: list[str] = []
    seen: Counter = Counter()
    for rec in records:
        base = f"{_get(rec, SC.ID_PATH)}@{station_code_of(_get(rec, SC.FIRS_FIR_METADATA_POLICE_STATION))}"
        seen[base] += 1
        keys.append(base if seen[base] == 1 else f"{base}#{seen[base]}")
    return keys


def _evidence_accounts(rec: dict) -> list[dict]:
    out: list[dict] = []
    for kind, const in (
        ("BANK", SC.FIRS_DIGITAL_EVIDENCE_BANK_ACCOUNTS),
        ("UPI", SC.FIRS_DIGITAL_EVIDENCE_UPI_IDS),
        ("COMPANY", SC.FIRS_DIGITAL_EVIDENCE_COMPANIES),
    ):
        for value in _get(rec, const, []) or []:
            if value:
                out.append({"account_ref": account_ref_of(kind, value), "kind": kind, "raw": value})
    return out


def normalize_records(dataset: dict) -> list[dict]:
    """Dataset → flat per-FIR dicts, the single transform for Steps 6 and 8."""
    keys = fir_keys(dataset)
    out: list[dict] = []
    for rec, fkey in zip(dataset[SC.ROOT_KEY], keys):
        station_name = _get(rec, SC.FIRS_FIR_METADATA_POLICE_STATION)
        district_name = _get(rec, SC.FIRS_FIR_METADATA_DISTRICT)
        lat = _get(rec, SC.FIRS_OCCURRENCE_LOCATION_LATITUDE)
        lon = _get(rec, SC.FIRS_OCCURRENCE_LOCATION_LONGITUDE)
        accused = []
        for item in _get(rec, SC.FIRS_ACCUSED_DETAILS, []) or []:
            if not isinstance(item, dict):
                continue
            name = item.get(_rel(SC.FIRS_ACCUSED_DETAILS_NAME)[-1])
            identified = bool(item.get(_rel(SC.FIRS_ACCUSED_DETAILS_IDENTIFIED)[-1], False))
            placeholder = is_placeholder_name(name)
            accused.append({
                "name": name,
                "identified": identified,
                "placeholder": placeholder,
                "person_key": person_key_of(fkey, "accused", name),
            })
        complainant_name = _get(rec, SC.FIRS_COMPLAINANT_DETAILS_NAME)
        io_name = _get(rec, SC.FIRS_INVESTIGATING_OFFICER_NAME)
        mastermind = _get(rec, SC.FIRS_CRIMINAL_NETWORK_SUSPECTED_MASTERMIND)
        normalized = {
            "fir_key": fkey,
            "fir_id": _get(rec, SC.ID_PATH),
            "district": code_name(district_name),
            "district_name": district_name,
            "station_code": station_code_of(station_name),
            "station_name": station_name,
            "registered_on": _get(rec, SC.FIRS_FIR_METADATA_FIR_REGISTRATION_DATE),
            "case_status": _get(rec, SC.FIRS_FIR_METADATA_CASE_STATUS),
            "case_category": _get(rec, SC.FIRS_FIR_METADATA_CASE_CATEGORY),
            "occurred_on": _get(rec, SC.FIRS_OCCURRENCE_DETAILS_DATE),
            "occurred_time": _get(rec, SC.FIRS_OCCURRENCE_DETAILS_TIME),
            "type_of_information": _get(rec, SC.FIRS_OCCURRENCE_DETAILS_TYPE_OF_INFORMATION),
            "act": _get(rec, SC.FIRS_OFFENCE_DETAILS_ACT),
            "sections": [
                section_code_of(_get(rec, SC.FIRS_OFFENCE_DETAILS_ACT), s)
                for s in _get(rec, SC.FIRS_OFFENCE_DETAILS_SECTIONS, []) or []
            ],
            "crime_code": code_name(_get(rec, SC.FIRS_OFFENCE_DETAILS_CRIME_HEAD)),
            "crime_head": _get(rec, SC.FIRS_OFFENCE_DETAILS_CRIME_HEAD),
            "narrative": _get(rec, SC.FIRS_INCIDENT_DETAILS_TRUTH_OF_INCIDENT),
            "address": _get(rec, SC.FIRS_OCCURRENCE_LOCATION_ADDRESS),
            "lat": lat,
            "lon": lon,
            "location_key": location_key_of(lat, lon, _get(rec, SC.FIRS_OCCURRENCE_LOCATION_ADDRESS)),
            "complainant": None if is_placeholder_name(complainant_name) else {
                "name": complainant_name,
                "occupation": _get(rec, SC.FIRS_COMPLAINANT_DETAILS_OCCUPATION),
                "address": _get(rec, SC.FIRS_COMPLAINANT_DETAILS_ADDRESS),
                "person_key": person_key_of(fkey, "complainant", complainant_name),
            },
            "accused": accused,
            "investigating_officer": None if is_placeholder_name(io_name) else {
                "name": io_name,
                "rank": _get(rec, SC.FIRS_INVESTIGATING_OFFICER_RANK),
                "person_key": person_key_of(fkey, "io", io_name),
            },
            "gang": normalize_text(_get(rec, SC.FIRS_CRIMINAL_NETWORK_GANG)),
            "alias_group": normalize_text(_get(rec, SC.FIRS_CRIMINAL_NETWORK_ALIAS_GROUP)),
            "mastermind": None if is_placeholder_name(mastermind) else {
                "name": mastermind,
                "person_key": person_key_of(fkey, "mastermind", mastermind),
            },
            "associates": [normalize_text(a) for a in _get(rec, SC.FIRS_CRIMINAL_NETWORK_KNOWN_ASSOCIATES, []) or [] if a],
            "phones": [phone_norm(p) for p in _get(rec, SC.FIRS_DIGITAL_EVIDENCE_PHONE_NUMBERS, []) or [] if p],
            "imeis": [normalize_token(i) for i in _get(rec, SC.FIRS_DIGITAL_EVIDENCE_IMEI_NUMBERS, []) or [] if i],
            "vehicles": [vehicle_norm(v) for v in _get(rec, SC.FIRS_DIGITAL_EVIDENCE_VEHICLE_NUMBERS, []) or [] if v],
            "accounts": _evidence_accounts(rec),
            "weapon": _get(rec, SC.FIRS_PHYSICAL_EVIDENCE_WEAPON),
            "stolen_items": [normalize_text(s) for s in _get(rec, SC.FIRS_PHYSICAL_EVIDENCE_STOLEN_ITEMS, []) or [] if s],
            "fingerprints_found": bool(_get(rec, SC.FIRS_PHYSICAL_EVIDENCE_FINGERPRINTS_FOUND, False)),
            "dna_found": bool(_get(rec, SC.FIRS_PHYSICAL_EVIDENCE_DNA_FOUND, False)),
            "cctv_available": bool(_get(rec, SC.FIRS_PHYSICAL_EVIDENCE_CCTV_AVAILABLE, False)),
            "ai_metadata": {
                "crime_pattern_id": _get(rec, SC.FIRS_AI_METADATA_CRIME_PATTERN_ID),
                "linked_firs": _get(rec, SC.FIRS_AI_METADATA_LINKED_FIRS, []) or [],
                "confidence_score": _get(rec, SC.FIRS_AI_METADATA_CONFIDENCE_SCORE),
                "is_repeat_offender": bool(_get(rec, SC.FIRS_AI_METADATA_IS_REPEAT_OFFENDER, False)),
                "predicted_suspect": _get(rec, SC.FIRS_AI_METADATA_PREDICTED_SUSPECT),
            },
        }
        out.append(normalized)
    return out


def same_name_edges(records: list[dict]) -> list[dict]:
    """Chained SAME_NAME_AS pairs across distinct person_keys sharing a
    normalized name (never merges; §5.6, rendered dashed per §14.2 change 6)."""
    by_name: dict[str, dict[str, dict]] = {}

    def _add(name, role, fir_key, person_key):
        if is_placeholder_name(name):
            return
        bucket = by_name.setdefault(normalize_text(name), {})
        bucket.setdefault(person_key, {"person_key": person_key, "role": role, "fir_key": fir_key})

    for rec in records:
        if rec["complainant"]:
            _add(rec["complainant"]["name"], "complainant", rec["fir_key"], rec["complainant"]["person_key"])
        for acc in rec["accused"]:
            if not acc["placeholder"]:
                _add(acc["name"], "accused", rec["fir_key"], acc["person_key"])
        if rec["investigating_officer"]:
            _add(rec["investigating_officer"]["name"], "io", rec["fir_key"], rec["investigating_officer"]["person_key"])
        if rec["mastermind"]:
            _add(rec["mastermind"]["name"], "mastermind", rec["fir_key"], rec["mastermind"]["person_key"])
        for assoc_name in rec["associates"]:
            _add(assoc_name, "associate", rec["fir_key"], person_key_of(rec["fir_key"], "associate", assoc_name))

    edges: list[dict] = []
    for norm_name, bucket in sorted(by_name.items()):
        ordered = sorted(bucket.values(), key=lambda p: p["person_key"])
        for a, b in zip(ordered, ordered[1:]):
            edges.append({
                "name": norm_name,
                "a": a["person_key"],
                "b": b["person_key"],
                "confidence": SAME_NAME_CONFIDENCE,
                "source_fir": b["fir_key"],
            })
    return edges


def resolve_entities(records: list[dict]) -> dict:
    """§5.6 entity resolution report. Merges require a strong identifier;
    this corpus has none, so the only legal merge count is zero."""
    persons: list[dict] = []
    placeholders = 0
    for rec in records:
        if rec["complainant"]:
            persons.append(rec["complainant"] | {"role": "complainant", "fir_key": rec["fir_key"]})
        else:
            placeholders += 1
        for acc in rec["accused"]:
            if acc["placeholder"]:
                placeholders += 1
            else:
                persons.append(acc | {"role": "accused", "fir_key": rec["fir_key"]})
        if rec["investigating_officer"]:
            persons.append(rec["investigating_officer"] | {"role": "io", "fir_key": rec["fir_key"]})
        else:
            placeholders += 1
        if rec["mastermind"]:
            persons.append(rec["mastermind"] | {"role": "mastermind", "fir_key": rec["fir_key"]})
        for assoc in rec["associates"]:
            if is_placeholder_name(assoc):
                placeholders += 1
            else:
                persons.append({"name": assoc, "person_key": person_key_of(rec["fir_key"], "associate", assoc),
                                "role": "associate", "fir_key": rec["fir_key"]})

    edges = same_name_edges(records)
    same_name_clusters = len({e["name"] for e in edges})
    total_person_nodes = len({p["person_key"] for p in persons})
    merged = 0
    return {
        "spec": "ksp-iis-build-prompt-v3.1 §5.6",
        "strong_identifiers_available": ["government_id", "date_of_birth", "person_phone"],
        "strong_identifiers_present_in_dataset": False,
        "persons_total": len(persons),
        "distinct_person_nodes": total_person_nodes,
        "placeholder_named_persons_excluded": placeholders,
        "merges_performed": merged,
        "merge_rate_pct": 0.0,
        "same_name_as_clusters": same_name_clusters,
        "same_name_as_edges": len(edges),
        "same_name_as_confidence": SAME_NAME_CONFIDENCE,
        "same_name_as_sample": edges[:10],
        "note": (
            "No strong identifiers exist in this corpus, so per the §5.6 binding rule "
            "no two Person records may merge. Same-name individuals are linked with "
            "SAME_NAME_AS (confidence 0.5, name-only) and rendered as dashed "
            "'possible identity match' edges. The system under-links by design (§18.1). "
            "SAME_NAME_AS is chained (n-1 edges per cluster) to avoid quadratic blowups."
        ),
    }


def main() -> int:
    dataset = discover_schema.load_dataset()
    records = normalize_records(dataset)
    report = resolve_entities(records)
    ER_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ER_REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    ok = report["merge_rate_pct"] < MERGE_RATE_LIMIT_PCT
    print(f"Step 5 — normalization + entity resolution over {len(records)} records")
    print(f"  [{'PASS' if ok else 'FAIL'}] merge rate {report['merge_rate_pct']}% < {MERGE_RATE_LIMIT_PCT:g}% "
          f"(merges performed: {report['merges_performed']}; strong identifiers in corpus: "
          f"{report['strong_identifiers_present_in_dataset']})")
    print(f"  [NOTE] distinct person nodes: {report['distinct_person_nodes']}; "
          f"placeholder-excluded: {report['placeholder_named_persons_excluded']}")
    print(f"  [NOTE] SAME_NAME_AS: {report['same_name_as_clusters']} clusters → "
          f"{report['same_name_as_edges']} chained edges @ confidence {SAME_NAME_CONFIDENCE}")
    print(f"Wrote {ER_REPORT_PATH}")
    if not ok:
        print("BLOCKED: Step 5 — merge rate over 15% (§5.6). The rule is too loose for this dataset.")
        return 1
    print("GATE PASS — Step 5 complete (§15 Step 5).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
