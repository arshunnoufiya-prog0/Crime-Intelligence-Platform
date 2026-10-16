#!/usr/bin/env python3
"""Step 1 — schema + citation contract discovery (spec v3.1 §5.1–§5.3).

Walks every record in data/bengaluru_40ps_1000_firs.json and emits:

  artifacts/schema_report.json              full field report + citation contract
  rag_service/ingest/_schema_constants.py   generated module — the ONLY
                                sanctioned home of dataset field-name literals

Gates (§15 Step 1): 1,000 records; fir_id present 100%; id_regex derived from
the observed ids, never assumed.

Deterministic output: no timestamps, stable ordering — so
tests/test_schema_contract.py re-runs discovery and asserts the committed
report is unchanged; a dataset swap fails loudly (§5.2 rule 2).

Stdlib only — runs before any venv exists.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from pprint import pformat
from statistics import fmean

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASET_REL = "data/bengaluru_40ps_1000_firs.json"
DATASET_PATH = REPO_ROOT / DATASET_REL
REPORT_PATH = REPO_ROOT / "artifacts" / "schema_report.json"
CONSTANTS_PATH = Path(__file__).resolve().parent / "_schema_constants.py"

# --- sanctioned literals: this file is the single origin of dataset field
# names (spec §5.2 rule 1). No other module may hardcode these strings. ---
ROOT_KEY = "firs"
ID_FIELD = "fir_id"
FIR_METADATA = "fir_metadata"
POLICE_STATION = "police_station"
DISTRICT = "district"
REG_DATE = "fir_registration_date"

SPARSE_PCT = 20.0
NARRATIVE_MIN_MEAN_LEN = 60.0
NARRATIVE_MIN_P90_LEN = 80.0
MAX_EXAMPLES = 5
EXAMPLE_TRUNC = 120
ENUM_MAX_CARDINALITY = 60
ENUM_MIN_PCT = 50.0

ALIASES = [
    ("POLICE_STATIONS", f"{ROOT_KEY}[].{FIR_METADATA}.{POLICE_STATION}"),
    ("DISTRICTS", f"{ROOT_KEY}[].{FIR_METADATA}.{DISTRICT}"),
    ("CASE_STATUSES", f"{ROOT_KEY}[].{FIR_METADATA}.case_status"),
    ("CASE_CATEGORIES", f"{ROOT_KEY}[].{FIR_METADATA}.case_category"),
    ("CRIME_HEADS", f"{ROOT_KEY}[].offence_details.crime_head"),
    ("ACTS", f"{ROOT_KEY}[].offence_details.act"),
    ("SECTIONS", f"{ROOT_KEY}[].offence_details.sections"),
    ("TYPES_OF_INFORMATION", f"{ROOT_KEY}[].occurrence_details.type_of_information"),
    ("WEAPONS", f"{ROOT_KEY}[].physical_evidence.weapon"),
]


def load_dataset(path: Path = DATASET_PATH) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"dataset missing: {path}")
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict) or not isinstance(data.get(ROOT_KEY), list):
        raise ValueError(f"dataset root must be a JSON object with a {ROOT_KEY!r} array")
    return data


def dataset_sha256(path: Path = DATASET_PATH) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _new_stat(path: str) -> dict:
    return {
        "path": path,
        "types": Counter(),
        "value_count": 0,
        "null_count": 0,
        "empty_count": 0,
        "records_touched": set(),
        "records_with_value": set(),
        "null_records": set(),
        "is_array": False,
        "max_array_len": 0,
        "distinct": set(),
        "examples": [],
        "examples_seen": set(),
        "lengths": [],
        "numbers": [],
    }


def _clip(s: str) -> str:
    s = " ".join(s.split())
    return s if len(s) <= EXAMPLE_TRUNC else s[: EXAMPLE_TRUNC - 1] + "…"


def _walk(value, path: str, rid: int, stats: dict) -> None:
    st = stats.setdefault(path, _new_stat(path))
    st["records_touched"].add(rid)
    if isinstance(value, dict):
        st["types"]["object"] += 1
        if not value:
            st["empty_count"] += 1
        for key, val in value.items():
            _walk(val, f"{path}.{key}", rid, stats)
    elif isinstance(value, list):
        st["types"]["array"] += 1
        st["is_array"] = True
        if len(value) > st["max_array_len"]:
            st["max_array_len"] = len(value)
        if not value:
            st["empty_count"] += 1
        else:
            st["records_with_value"].add(rid)
        for item in value:
            _walk(item, f"{path}[]", rid, stats)
    elif value is None:
        st["types"]["null"] += 1
        st["null_count"] += 1
        st["null_records"].add(rid)
    else:
        if isinstance(value, bool):
            st["types"]["boolean"] += 1
        elif isinstance(value, (int, float)):
            st["types"]["number"] += 1
        else:
            st["types"]["string"] += 1
            if value == "":
                st["empty_count"] += 1
                return
        st["value_count"] += 1
        st["records_with_value"].add(rid)
        if isinstance(value, str):
            st["lengths"].append(len(value))
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            st["numbers"].append(value)
        token = value if isinstance(value, str) else json.dumps(value)
        st["distinct"].add(token)
        if token not in st["examples_seen"]:
            st["examples_seen"].add(token)
            if len(st["examples"]) < MAX_EXAMPLES:
                st["examples"].append(_clip(token))


def _p90(lengths: list[int]) -> int:
    s = sorted(lengths)
    return s[int(0.9 * (len(s) - 1))]


def _finalize_field(st: dict, n: int, item_types: list | None) -> dict:
    if st["is_array"]:
        ftype = "array"
    else:
        non_null = [t for t in st["types"] if t != "null"]
        if len(non_null) == 1:
            ftype = non_null[0]
        elif not non_null:
            ftype = "null"
        else:
            ftype = "mixed"
    if ftype == "object":
        present = len(st["records_touched"] - st["null_records"])
    else:
        present = len(st["records_with_value"])
    present_pct = round(present / n * 100.0, 1) if n else 0.0
    entry = {
        "path": st["path"],
        "type": ftype,
        "present_count": present,
        "present_pct": present_pct,
        "null_count": st["null_count"],
        "missing_count": n - len(st["records_touched"]),
        "value_count": st["value_count"],
        "empty_count": st["empty_count"],
        "cardinality": len(st["distinct"]),
        "examples": st["examples"],
        "is_array": st["is_array"],
        "sparse": present_pct < SPARSE_PCT,
    }
    if st["is_array"]:
        entry["max_array_len"] = st["max_array_len"]
        if item_types is not None:
            entry["item_types"] = item_types
    if st["lengths"]:
        entry["mean_len"] = round(fmean(st["lengths"]), 1)
        entry["p90_len"] = _p90(st["lengths"])
    if st["numbers"]:
        entry["min"] = min(st["numbers"])
        entry["max"] = max(st["numbers"])
    return entry


def derive_id_regex(ids: list) -> tuple[str, dict, int]:
    templates: Counter = Counter()
    for raw in ids:
        templates[re.sub(r"\d+", lambda m: f"<{len(m.group())}>", str(raw))] += 1
    frags = []
    for tmpl in sorted(templates):
        parts = []
        i = 0
        while i < len(tmpl):
            if tmpl[i] == "<":
                j = tmpl.index(">", i)
                parts.append(r"\d{" + tmpl[i + 1: j] + "}")
                i = j + 1
            else:
                parts.append(re.escape(tmpl[i]))
                i += 1
        frags.append("".join(parts))
    regex = "^(?:" + "|".join(frags) + ")$"
    matches = sum(1 for raw in ids if re.match(regex, str(raw)))
    return regex, dict(sorted(templates.items())), matches


def id_uniqueness(records: list) -> dict:
    ids = [str(r.get(ID_FIELD)) if r.get(ID_FIELD) is not None else None for r in records]
    valid = [i for i in ids if i is not None]
    id_counter = Counter(valid)
    stations = [(r.get(FIR_METADATA) or {}).get(POLICE_STATION) for r in records]
    comp = Counter(zip(valid, stations))
    exact = sorted(((k, v) for k, v in comp.items() if v > 1), key=lambda kv: (-kv[1], kv[0]))
    year_match = 0
    for r in records:
        rid = str(r.get(ID_FIELD) or "")
        date = str((r.get(FIR_METADATA) or {}).get(REG_DATE) or "")
        if "/" in rid and len(date) >= 4:
            if rid.rsplit("/", 1)[1] == date[:4]:
                year_match += 1
    unique = len(id_counter) == len(valid)
    return {
        "total_ids": len(valid),
        "unique_fir_ids": len(id_counter),
        "fir_id_values_seen_more_than_once": sum(1 for c in id_counter.values() if c > 1),
        "max_reuse_of_one_fir_id": max(id_counter.values()) if id_counter else 0,
        "unique_fir_id_plus_station": len(comp),
        "exact_duplicate_pairs": [
            {"fir_id": k[0], "police_station": k[1], "count": v} for k, v in exact[:20]
        ],
        "registration_year_matches_id_year": year_match,
        "globally_unique": unique,
        "note": (
            "fir_id is globally unique in this dataset"
            if unique
            else "fir_id is NOT globally unique; citation keys and FIR lookups must carry "
            f"police_station for disambiguation ({len(comp - Counter())} composite keys observed). "
            "Step 6 must record this under model_deltas."
        ),
    }


def detect_narrative(fields: dict) -> dict:
    out = {}
    for path, f in fields.items():
        if f["type"] != "string":
            continue
        if f.get("mean_len", 0) >= NARRATIVE_MIN_MEAN_LEN and (f.get("p90_len") or 0) >= NARRATIVE_MIN_P90_LEN:
            out[path] = {
                "mean_len": f["mean_len"],
                "p90_len": f.get("p90_len"),
                "cardinality": f["cardinality"],
                "present_count": f["present_count"],
                "note": (
                    "Prose-like by length, but sentence templates repeat across records "
                    "(low cardinality) — chunks from repeated prose may legitimately share "
                    "text across FIRs; citations still key off (fir_id, chunk)."
                ),
            }
    return out


def build_report(dataset: dict) -> dict:
    records = dataset.get(ROOT_KEY)
    if not isinstance(records, list):
        raise ValueError(f"root key {ROOT_KEY!r} must be a list of records")
    n = len(records)
    sha = dataset_sha256()

    stats: dict = {}
    root = _new_stat(ROOT_KEY)
    root["is_array"] = True
    root["max_array_len"] = n
    root["types"]["array"] = 1
    root["records_touched"] = set(range(n))
    root["records_with_value"] = set(range(n))
    stats[ROOT_KEY] = root
    for idx, rec in enumerate(records):
        if not isinstance(rec, dict):
            raise ValueError(f"record {idx} is not a JSON object")
        for key, val in rec.items():
            _walk(val, f"{ROOT_KEY}[].{key}", idx, stats)

    fields: dict = {}
    distinct_by_path: dict = {}
    for path, st in stats.items():
        item_types = None
        if st["is_array"]:
            child = stats.get(f"{path}[]")
            if child is not None:
                item_types = sorted({t for t in child["types"] if t != "null"})
        fields[path] = _finalize_field(st, n, item_types)
        if st["distinct"]:
            distinct_by_path[path] = sorted(st["distinct"])

    enums: dict = {}
    for path, f in fields.items():
        if f["type"] != "string":
            continue
        if f["present_pct"] >= ENUM_MIN_PCT and 0 < f["cardinality"] <= ENUM_MAX_CARDINALITY:
            enums[path] = distinct_by_path[path]

    narrative = detect_narrative(fields)
    ids = [r.get(ID_FIELD) for r in records]
    id_regex, id_formats, id_matches = derive_id_regex([i for i in ids if i is not None])
    id_examples: list = []
    for raw in ids:
        s = str(raw)
        if s not in id_examples and len(id_examples) < 5:
            id_examples.append(s)

    contract = {
        "id_field": ID_FIELD,
        "id_path": f"{ROOT_KEY}[].{ID_FIELD}",
        "id_regex": id_regex,
        "id_regex_source": "derived from observed fir_id digit-run templates (spec §5.3) — never assumed",
        "id_format_templates": id_formats,
        "id_match_count": id_matches,
        "id_match_pct": round(id_matches / max(len([i for i in ids if i is not None]), 1) * 100.0, 1),
        "id_examples": id_examples,
        "id_uniqueness": id_uniqueness(records),
        "narrative_fields": list(narrative),
        "narrative_rule": (
            f"type=string leaf with mean value length >= {NARRATIVE_MIN_MEAN_LEN:g} chars and "
            f"p90 length >= {NARRATIVE_MIN_P90_LEN:g} (free-form prose by length; uniqueness "
            "NOT required — this corpus reuses narrative sentence templates across records)"
        ),
        "narrative_stats": narrative,
        "citable_leaf_paths": [p for p, f in fields.items() if f["type"] in ("string", "number", "boolean")],
        "per_field_provenance": True,
    }
    return {
        "generator": "rag_service/ingest/discover_schema.py",
        "spec": "ksp-iis-build-prompt-v3.1 §5.2, §5.3",
        "dataset": {
            "file": DATASET_REL,
            "sha256": sha,
            "root_key": ROOT_KEY,
            "n_records": n,
        },
        "fields": fields,
        "enums": enums,
        "sparse_paths": [p for p, f in fields.items() if f["sparse"]],
        "citation_contract": contract,
    }


def _const_name(path: str) -> str:
    base = path.replace("[]", "")
    return re.sub(r"[^A-Za-z0-9]+", "_", base).strip("_").upper()


def render_constants(report: dict) -> str:
    fields = report["fields"]
    cc = report["citation_contract"]
    consts: dict = {}
    for path in fields:
        if path == ROOT_KEY or path.endswith("[]"):
            continue
        name = _const_name(path)
        base, i = name, 2
        while name in consts:
            name = f"{base}_{i}"
            i += 1
        consts[name] = path
    inv = {path: name for name, path in consts.items()}

    enum_block: dict = {}
    for path, values in report["enums"].items():
        key = path[:-2] if path.endswith("[]") else path
        enum_block[inv[key]] = values

    lines = [
        '"""AUTO-GENERATED by rag_service/ingest/discover_schema.py — DO NOT EDIT.',
        "",
        "Regenerate:  python3 rag_service/ingest/discover_schema.py",
        "Source of truth: artifacts/schema_report.json",
        "Single sanctioned home of dataset field-name literals (spec §5.2):",
        "downstream modules import from here and never hardcode field strings.",
        '"""',
        "",
        f"ROOT_KEY = {ROOT_KEY!r}",
        f"N_RECORDS = {report['dataset']['n_records']!r}",
        f"DATASET_FILE = {DATASET_REL!r}",
        f"DATASET_SHA256 = {report['dataset']['sha256']!r}",
        "",
        f"ID_FIELD = {cc['id_field']!r}",
        f"ID_PATH = {cc['id_path']!r}",
        f"ID_REGEX = {cc['id_regex']!r}",
        f"ID_FORMATS = {cc['id_format_templates']!r}",
        f"ID_UNIQUENESS = {pformat(cc['id_uniqueness'], width=100, sort_dicts=False)}",
        "",
        f"NARRATIVE_PATHS = {cc['narrative_fields']!r}",
        f"NARRATIVE_RULE = {cc['narrative_rule']!r}",
        f"SPARSE_PATHS = {report['sparse_paths']!r}",
        f"CITABLE_LEAF_PATHS = {cc['citable_leaf_paths']!r}",
        "",
    ]
    for name, path in consts.items():
        lines.append(f"{name} = {path!r}")
    lines.append("")
    lines.append(f"FIELD_PATHS = {pformat(consts, width=100, sort_dicts=False)}")
    lines.append(f"ENUMS = {pformat(enum_block, width=100, sort_dicts=False)}")
    for alias, path in ALIASES:
        key = path[:-2] if path.endswith("[]") else path
        if key in inv and inv[key] in enum_block:
            lines.append(f"{alias} = ENUMS[{inv[key]!r}]")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    dataset = load_dataset()
    report = build_report(dataset)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    CONSTANTS_PATH.write_text(render_constants(report), encoding="utf-8")

    cc = report["citation_contract"]
    gates_ok = True

    def gate(label: str, ok: bool) -> None:
        nonlocal gates_ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
        if not ok:
            gates_ok = False

    n = report["dataset"]["n_records"]
    print(f"Step 1 — schema discovery: {len(report['fields'])} JSON paths across {n} records")
    gate(f"n_records == 1000 (got {n})", n == 1000)
    id_entry = report["fields"].get(cc["id_path"], {})
    gate(
        f"fir_id present 100% (got {id_entry.get('present_pct')}%)",
        id_entry.get("present_pct") == 100.0,
    )
    gate(
        f"id_regex derived & matches all ids: {cc['id_regex']} → {cc['id_match_pct']}%",
        cc["id_match_pct"] == 100.0,
    )
    gate(f"narrative fields found: {cc['narrative_fields']}", bool(cc["narrative_fields"]))
    u = cc["id_uniqueness"]
    print(
        f"  [NOTE] fir_id globally unique: {u['globally_unique']} "
        f"(unique {u['unique_fir_ids']}/{u['total_ids']}; +station → {u['unique_fir_id_plus_station']}; "
        f"exact dup pairs: {len(u['exact_duplicate_pairs'])})"
    )
    print(f"  [NOTE] sparse paths (<{SPARSE_PCT:g}% present): {len(report['sparse_paths'])}")
    print(f"  [NOTE] enums: {len(report['enums'])}")
    print(f"  [NOTE] stations: {len(report['enums'].get(f'{ROOT_KEY}[].{FIR_METADATA}.{POLICE_STATION}', []))}")
    print(f"Wrote {REPORT_PATH}")
    print(f"Wrote {CONSTANTS_PATH}")
    if not gates_ok:
        print("BLOCKED: Step 1 — one or more gates failed (§15 Step 1). Fix before proceeding.")
        return 1
    print("GATE PASS — Step 1 complete (§15 Step 1).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
