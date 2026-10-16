"""Citation validation — the zero-hallucination gate (spec §12.6).

1. The id_regex is COMPILED FROM the schema report's derived
   citation_contract (§5.3) — never hand-written here.
2. ID-shaped tokens are extracted from the ANSWER TEXT ONLY — reasoning is
   never passed to this module (§12.6 rule 1) and a fabricated id that appears
   only inside a thinking block must NOT be flagged.
3. Any cited id NOT in the retrieval set (Cypher rows ∪ LightRAG chunk
   source_ids): the sentence is struck and marked
   '[removed: unverifiable reference]', and a
   {code: UNGROUNDED_CITATION, ids} warning is emitted.
4. A digit-bearing quantitative claim with no Cypher result retrieved emits
   {code: UNSOURCED_QUANTITY} (§12.6 rule 4) — numbers come from Cypher only.
5. Every warning is returned for the audit trail (§12.6 rule 5).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ingest"))

import _schema_constants as SC  # noqa: E402

_ID_VALIDATION_RE = re.compile(SC.ID_REGEX)


def _search_pattern(regex: str) -> str:
    """§12.6 extracts ID-shaped TOKENS from prose — the derived contract regex
    is anchored (^...$) for validation, so un-anchor the same alternation for
    searching. Lookarounds stop partial matches inside longer digit runs."""
    inner = regex
    if inner.startswith("^(?:") and inner.endswith(")$"):
        inner = inner[4:-2]
    return rf"(?<![\d/]){inner}(?![\d/])"


_ID_SEARCH_RE = re.compile(_search_pattern(SC.ID_REGEX))

_QUANTITY_RE = re.compile(
    r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|several|many|dozens?)\b"
    r"[\s-]*(fir|firs|case|cases|incident|incidents|vehicle|vehicles|phone|phones|person|people|suspect|suspects|arrest|arrests)\b",
    re.IGNORECASE,
)

_STRIKE_MARKER = "[removed: unverifiable reference]"


def extract_cited_ids(answer_text: str) -> list[str]:
    seen: list[str] = []
    for match in _ID_SEARCH_RE.finditer(answer_text):
        if match.group(0) not in seen:
            seen.append(match.group(0))
    return seen


def _strike_sentences(text: str, bad_ids: list[str]) -> str:
    for bad in bad_ids:
        pattern = re.compile(rf"(?is)[^.\n]*(?:{re.escape(bad)})[^.\n]*\.?")
        text = pattern.sub(_STRIKE_MARKER + " ", text)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def validate_answer(
    answer_text: str,
    retrieval_ids: set[str],
    cypher_row_count: int,
) -> tuple[str, list[dict]]:
    """Returns (possibly-struck answer, warnings). Reasoning never reaches here."""
    warnings: list[dict] = []
    cited = extract_cited_ids(answer_text)
    ungrounded = [c for c in cited if c not in retrieval_ids]
    if ungrounded:
        warnings.append({"code": "UNGROUNDED_CITATION", "ids": ungrounded})
        answer_text = _strike_sentences(answer_text, ungrounded)
    if cypher_row_count == 0 and _QUANTITY_RE.search(answer_text):
        warnings.append({
            "code": "UNSOURCED_QUANTITY",
            "detail": "Quantitative claim present with no structured (Cypher) results retrieved — "
                      "numbers may only originate from the graph database (§10.1).",
        })
    return answer_text, warnings
