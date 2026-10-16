#!/usr/bin/env python3
"""Ingest orchestrator (spec §15 Steps 6 + 8): Neo4j domain load, then the
deterministic LightRAG custom-KG ingest. Both gates must pass.

Run inside the rag container:  python ingest/run_ingest.py   (make ingest)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import build_custom_kg  # noqa: E402
import load_neo4j  # noqa: E402


def main() -> int:
    rc = load_neo4j.main()
    if rc != 0:
        print("BLOCKED: ingest — Step 6 (Neo4j load) failed; not proceeding to Step 8 (§0.6 DAG order).")
        return rc
    return build_custom_kg.main()


if __name__ == "__main__":
    sys.exit(main())
