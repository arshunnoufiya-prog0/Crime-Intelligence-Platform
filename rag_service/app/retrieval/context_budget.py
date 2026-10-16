"""Context budget manager for a 16,384-token slot (spec §11).

Keeps a 4B thinking model from drowning: every segment gets a fixed budget
from the §11.2 table, overflow resolves via the §11.3 eviction order, and the
generation reserves (reasoning 2,048 / answer 1,024) are never encroached.

Token counting is injected as `count_fn` — the production path is
llm.client.count_tokens_for (exact, llama-server /tokenize, §11.1); tests
inject a deterministic fake. No character heuristics anywhere.

Prefix-cache discipline (§11.4): assembly is most-static-first and never
interpolates timestamps/request-ids into static segments.

If the Step 13 A/B lands on thinking disabled, the 2,048 reasoning reserve is
reclaimed into the LightRAG context budget (§11.2 note).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Awaitable, Callable

SLOT_TOKENS = 16_384

SYSTEM_MAX = 500
SCOPE_MAX = 150
CYPHER_MAX = 2_400
LIGHTRAG_MAX = 6_500
HISTORY_MAX = 1_800
QUESTION_MAX = 400
RESERVED_REASONING = 2_048
RESERVED_ANSWER = 1_024
SAFETY_MARGIN = 1_562

HISTORY_TURNS_KEPT = 3
CYPHER_ROWS_KEPT = 40

CountFn = Callable[[str], Awaitable[int]]
Summarizer = Callable[[list[dict]], Awaitable[str]]


class ContextOverflowError(Exception):
    """§11.3: still over budget after every eviction → 422 with a suggestion;
    never a silent mid-context truncation."""
    code = "CONTEXT_OVERFLOW"

    def __init__(self, message: str, suggestion: str):
        super().__init__(message)
        self.suggestion = suggestion


class SegmentBudgetExceeded(ContextOverflowError):
    """Hard-fail segments — the static prompt must never grow (§11.2)."""


@dataclass
class CypherResult:
    template_id: str
    rows: list[dict]
    header: dict = field(default_factory=dict)


@dataclass
class Chunk:
    content: str
    score: float
    source_id: str


@dataclass
class EntityFact:
    """LightRAG entity description — evictable while keeping names+edges (§11.3 step 4)."""
    text: str
    score: float


@dataclass
class AssemblyMeta:
    prompt_tokens: int = 0
    segment_tokens: dict = field(default_factory=dict)
    history_turns_summarized: int = 0
    lightrag_chunks_dropped: int = 0
    cypher_rows_truncated: int = 0
    entity_descriptions_dropped: int = 0
    lightrag_budget: int = LIGHTRAG_MAX


async def _count(count_fn: CountFn, text: str) -> int:
    return await count_fn(text)


def _render_history(summary: str | None, kept: list[dict]) -> str:
    lines: list[str] = []
    if summary:
        lines.append(f"[earlier turns summarized] {summary}")
    for m in kept:
        lines.append(f"{m['role']}: {m['content']}")
    return "\n".join(lines)


def _render_cypher(result: CypherResult, rows: list[dict]) -> str:
    lines = [f"STRUCTURED RESULTS — authoritative, from the Neo4j crime graph (query: {result.template_id})."]
    for key, value in result.header.items():
        lines.append(f"{key}: {value}")
    for row in rows:
        lines.append("- " + " | ".join(f"{k}={v}" for k, v in row.items()))
    dropped = len(result.rows) - len(rows)
    if dropped:
        lines.append(f"... and {dropped} more rows (truncated)")
    return "\n".join(lines)


def _render_lightrag(kept_chunks: list[Chunk], kept_entities: list[EntityFact]) -> str:
    lines = ["NARRATIVE CONTEXT — retrieved from the FIR corpus (explanatory material)."]
    for chunk in kept_chunks:
        lines.append(f"[source FIR {chunk.source_id} | relevance {chunk.score:.2f}]\n{chunk.content}")
    if kept_entities:
        lines.append("RELATED ENTITY FACTS:")
        for ent in kept_entities:
            lines.append(f"- {ent.text}")
    return "\n".join(lines)


async def assemble(
    count_fn: CountFn,
    *,
    system: str,
    scope: str,
    question: str,
    history: list[dict],
    history_summarizer: Summarizer,
    cypher: CypherResult | None,
    chunks: list[Chunk],
    entity_facts: list[EntityFact],
    thinking_enabled: bool,
) -> tuple[str, list[dict], AssemblyMeta]:
    """Returns (context_block, kept_history, meta). Raises ContextOverflowError
    when the §11.3 evictions cannot bring the assembly under the slot."""
    meta = AssemblyMeta()
    lightrag_budget = LIGHTRAG_MAX if thinking_enabled else LIGHTRAG_MAX + RESERVED_REASONING
    meta.lightrag_budget = lightrag_budget

    n_system = await _count(count_fn, system)
    if n_system > SYSTEM_MAX:
        raise SegmentBudgetExceeded(
            f"system prompt is {n_system} tokens > {SYSTEM_MAX} — must never grow (§11.2)",
            "shrink the static system prompt",
        )
    n_scope = await _count(count_fn, scope)
    if n_scope > SCOPE_MAX:
        raise SegmentBudgetExceeded(
            f"scope preamble is {n_scope} tokens > {SCOPE_MAX} (§11.2)",
            "reduce scope detail",
        )
    n_question = await _count(count_fn, question)
    if n_question > QUESTION_MAX:
        raise ContextOverflowError(
            f"question is {n_question} tokens > {QUESTION_MAX} (§11.2)",
            "narrow the query",
        )

    # §11.3 step 1 — conversation turns older than 3 → one-line summary.
    kept_turns = list(history[-HISTORY_TURNS_KEPT:]) if history else []
    older = list(history[:-HISTORY_TURNS_KEPT]) if len(history) > HISTORY_TURNS_KEPT else []
    summary = None
    if older:
        meta.history_turns_summarized = len(older)
        summary = await history_summarizer(older)
    while True:
        history_text = _render_history(summary, kept_turns)
        n_history = await _count(count_fn, history_text)
        if n_history <= HISTORY_MAX or not kept_turns:
            break
        folded = kept_turns.pop(0)
        meta.history_turns_summarized += 1
        summary = await history_summarizer((older or []) + [folded])
    if n_history > HISTORY_MAX:
        raise ContextOverflowError(
            f"history exceeds {HISTORY_MAX} tokens even after summarization (§11.2)",
            "start a new conversation",
        )

    # §11.2 overflow policy for Cypher: truncate rows, keep header + top-N.
    rows = list(cypher.rows) if cypher else []
    rows = rows[:CYPHER_ROWS_KEPT]
    while True:
        cypher_text = _render_cypher(cypher, rows) if cypher else ""
        n_cypher = await _count(count_fn, cypher_text) if cypher_text else 0
        if n_cypher <= CYPHER_MAX or not rows:
            break
        rows = rows[: max(1, int(len(rows) * 0.8))]
    meta.cypher_rows_truncated = (len(cypher.rows) - len(rows)) if cypher else 0

    # §11.3 step 2 — LightRAG chunks, lowest score dropped first.
    ordered = sorted(chunks, key=lambda c: c.score, reverse=True)
    kept_chunks: list[Chunk] = []
    used = 0
    for chunk in ordered:
        n = await _count(count_fn, chunk.content)
        if used + n > lightrag_budget:
            continue
        kept_chunks.append(chunk)
        used += n
    meta.lightrag_chunks_dropped = len(chunks) - len(kept_chunks)

    # §11.3 step 4 — entity descriptions dropped (names+edges kept) if needed.
    kept_entities = sorted(entity_facts, key=lambda e: e.score, reverse=True)
    while True:
        lightrag_text = _render_lightrag(kept_chunks, kept_entities)
        n_lightrag = await _count(count_fn, lightrag_text)
        if n_lightrag <= lightrag_budget or not kept_entities:
            break
        kept_entities.pop()
        meta.entity_descriptions_dropped += 1
    if n_lightrag > lightrag_budget:
        raise ContextOverflowError(
            f"narrative context is {n_lightrag} tokens > {lightrag_budget} after evictions (§11.3)",
            "narrow the query",
        )

    total = (
        n_system + n_scope + n_cypher + n_lightrag + n_history + n_question
        + RESERVED_REASONING + RESERVED_ANSWER + SAFETY_MARGIN
    )
    if total > SLOT_TOKENS:
        raise ContextOverflowError(
            f"assembled prompt {total} tokens > {SLOT_TOKENS} slot (§11.2)",
            "narrow the query — context could not be trimmed further",
        )

    context_block = "\n\n".join(t for t in (cypher_text, lightrag_text) if t)
    meta.prompt_tokens = n_system + n_scope + n_cypher + n_lightrag + n_history + n_question
    meta.segment_tokens = {
        "system": n_system, "scope": n_scope, "cypher": n_cypher,
        "lightrag": n_lightrag, "history": n_history, "question": n_question,
        "reserved_reasoning": RESERVED_REASONING if thinking_enabled else 0,
        "reserved_answer": RESERVED_ANSWER, "safety_margin": SAFETY_MARGIN,
        "total_with_reserves": total,
    }
    return context_block, kept_turns, meta
