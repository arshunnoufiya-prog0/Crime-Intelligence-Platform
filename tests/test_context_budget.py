#!/usr/bin/env python3
"""Step 11 gate — context budget tests (spec §11.2/§11.3/§11.4).

Run:  python3 tests/test_context_budget.py   (also pytest-compatible)
Uses a deterministic fake count_fn (chars/4); the production path uses the
exact llama-server /tokenize counter (§11.1) — behaviors tested here are the
budget rules, eviction order and overflow failures.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "rag_service"))

from app.retrieval import context_budget as cb  # noqa: E402


async def fake_count(text: str) -> int:
    return max(1, (len(text) + 3) // 4)


async def fake_summarizer(turns: list[dict]) -> str:
    return f"summary of {len(turns)} older turns"


def _base_kwargs() -> dict:
    return dict(
        system="S" * 100, scope="Role X. Districts ALL.", question="Who robbed in Jayanagar?",
        history=[], history_summarizer=fake_summarizer,
        cypher=cb.CypherResult(template_id="PATTERN_SEARCH", rows=[{"fir_id": "17/2023", "crime": "ROBBERY"}]),
        chunks=[cb.Chunk(content="Chain snatching near Jayanagar.", score=0.81, source_id="17/2023")],
        entity_facts=[cb.EntityFact(text="JAYA is a person seen in FIR 17/2023.", score=0.7)],
        thinking_enabled=True,
    )


async def _assemble(**overrides) -> tuple:
    kwargs = _base_kwargs()
    kwargs.update(overrides)
    return await cb.assemble(fake_count, **kwargs)


def test_fits_without_eviction():
    async def run():
        block, kept, meta = await _assemble()
        assert block and "PATTERN_SEARCH" in block and "17/2023" in block
        assert meta.lightrag_chunks_dropped == 0
        assert meta.cypher_rows_truncated == 0
        assert meta.history_turns_summarized == 0
        assert meta.prompt_tokens == sum(
            meta.segment_tokens[k] for k in ("system", "scope", "cypher", "lightrag", "history", "question")
        )
    asyncio.run(run())


def test_lowest_scored_chunks_evicted_first():
    async def run():
        chunks = [cb.Chunk(content=f"chunk {i} " + "x" * 3000, score=float(i), source_id=f"{i}/2023")
                  for i in range(40)]
        block, kept, meta = await _assemble(chunks=chunks)
        assert meta.lightrag_chunks_dropped > 0
        assert meta.segment_tokens["lightrag"] <= cb.LIGHTRAG_MAX
        assert "chunk 39" in block and "chunk 0" not in block
    asyncio.run(run())


def test_history_over_three_turns_summarized():
    async def run():
        history = [{"role": "user", "content": f"turn {i}"} for i in range(6)]
        block, kept, meta = await _assemble(history=history)
        assert meta.history_turns_summarized == 3
        assert len(kept) == 3
        assert "summary of 3" in block or meta.segment_tokens["history"] <= cb.HISTORY_MAX
    asyncio.run(run())


def test_cypher_rows_beyond_40_truncated():
    async def run():
        rows = [{"fir_id": f"{i}/2023", "crime_head": "BURGLARY"} for i in range(120)]
        block, kept, meta = await _assemble(cypher=cb.CypherResult(template_id="PATTERN_SEARCH", rows=rows))
        assert meta.cypher_rows_truncated == 80
        assert "... and 80 more rows (truncated)" in block
    asyncio.run(run())


def test_question_over_budget_raises():
    async def run():
        try:
            await _assemble(question="q" * 4000)
        except cb.ContextOverflowError as exc:
            assert isinstance(exc, cb.ContextOverflowError)
            assert exc.suggestion
            return
        raise AssertionError("expected ContextOverflowError")
    asyncio.run(run())


def test_system_prompt_growth_hard_fails():
    async def run():
        try:
            await _assemble(system="S" * 4000)
        except cb.SegmentBudgetExceeded:
            return
        raise AssertionError("expected SegmentBudgetExceeded")
    asyncio.run(run())


def test_thinking_disabled_reclaims_reasoning_reserve():
    async def run():
        block, kept, meta = await _assemble(thinking_enabled=False)
        assert meta.lightrag_budget == cb.LIGHTRAG_MAX + cb.RESERVED_REASONING
        assert meta.segment_tokens["reserved_reasoning"] == 0
    asyncio.run(run())


def test_total_slot_never_exceeded():
    async def run():
        block, kept, meta = await _assemble()
        assert meta.segment_tokens["total_with_reserves"] <= cb.SLOT_TOKENS
    asyncio.run(run())


if __name__ == "__main__":
    for name, fn in sorted({k: v for k, v in globals().items() if k.startswith("test_")}.items()):
        fn()
        print(f"PASS {name}")
    print("ALL CONTEXT BUDGET TESTS GREEN")
