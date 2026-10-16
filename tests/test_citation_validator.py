#!/usr/bin/env python3
"""Step 15 gate — citation validator tests (spec §12.6).

Includes the two mandatory cases:
  * a deliberately FABRICATED id in the model output → suppression + strike;
  * a fabricated id that appears ONLY inside the thinking block → NOT flagged
    (reasoning is not an answer).

Run:  python3 tests/test_citation_validator.py   (also pytest-compatible)
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "rag_service"))
sys.path.insert(0, str(REPO_ROOT / "rag_service" / "ingest"))

from app.answer import citations  # noqa: E402


RETRIEVAL_IDS = {"17/2023", "2/2023", "99/2024"}


def test_grounded_ids_pass_through():
    answer = "Two burglaries match: (FIR 17/2023) at Jayanagar and (FIR 2/2023) at Indiranagar."
    clean, warnings = citations.validate_answer(answer, RETRIEVAL_IDS, cypher_row_count=2)
    assert clean == answer, "grounded answer must pass unchanged"
    assert warnings == [], f"unexpected warnings: {warnings}"


def test_fabricated_id_is_suppressed():
    answer = ("The burglary at Jayanagar is documented in (FIR 17/2023). "
              "A related case appears in (FIR 555/2099) per other records.")
    clean, warnings = citations.validate_answer(answer, RETRIEVAL_IDS, cypher_row_count=1)
    assert any(w["code"] == "UNGROUNDED_CITATION" and "555/2099" in w["ids"] for w in warnings)
    assert "555/2099" not in clean, "unverifiable reference must be struck"
    assert citations._STRIKE_MARKER in clean, "strike marker must be visible"
    assert "17/2023" in clean, "grounded reference must survive"


def test_fabricated_id_only_in_reasoning_is_not_flagged():
    reasoning = "Hmm, maybe (FIR 555/2099) is related… but the context only shows 17/2023."
    answer = "The burglary is documented in (FIR 17/2023)."
    cited_in_reasoning = citations.extract_cited_ids(reasoning)
    assert "555/2099" in cited_in_reasoning
    clean, warnings = citations.validate_answer(answer, RETRIEVAL_IDS, cypher_row_count=1)
    assert warnings == [], "reasoning must never be validated (§12.6 rule 1)"
    assert clean == answer


def test_unsourced_quantity_without_cypher_rows():
    answer = "There were 47 cases of burglary in the area this quarter."
    clean, warnings = citations.validate_answer(answer, RETRIEVAL_IDS, cypher_row_count=0)
    assert any(w["code"] == "UNSOURCED_QUANTITY" for w in warnings)


def test_quantity_with_cypher_rows_is_clean():
    answer = "The station registered 12 FIRs (FIR 17/2023 among them)."
    clean, warnings = citations.validate_answer(answer, RETRIEVAL_IDS, cypher_row_count=12)
    assert not any(w["code"] == "UNSOURCED_QUANTITY" for w in warnings)


def test_regex_is_derived_not_spec_example():
    """The spec's example format (FIR-2024-0188) does not exist in this corpus;
    the validator compiles the DERIVED ^\\d+/\\d{4}$ family (§5.3)."""
    assert citations.extract_cited_ids("see FIR-2024-0188") == []
    assert citations.extract_cited_ids("see (FIR 17/2023)") == ["17/2023"]


if __name__ == "__main__":
    for name in sorted(k for k in globals() if k.startswith("test_")):
        globals()[name]()
        print(f"PASS {name}")
    print("ALL CITATION VALIDATOR TESTS GREEN")
