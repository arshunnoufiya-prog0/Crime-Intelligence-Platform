#!/usr/bin/env python3
"""Step 10/15 gate — reasoning split tests (spec §1.3, §12.5).

Asserts on a recorded stream containing a ` Mattis` block that NO byte
emitted on the reasoning channel ever appears on the token channel — even
when the marker and the block close are split across stream deltas.

Run:  python3 tests/test_reasoning_split.py   (also pytest-compatible)
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "rag_service"))

from app.llm.reasoning import ReasoningSplitter  # noqa: E402


def _run_feed(chunks: list[str]) -> tuple[str, str]:
    splitter = ReasoningSplitter()
    reasoning, answer = [], []
    for chunk in chunks:
        for channel, text in splitter.feed(chunk):
            (reasoning if channel == "reasoning" else answer).append(text)
    for channel, text in splitter.close():
        (reasoning if channel == "reasoning" else answer).append(text)
    return "".join(reasoning), "".join(answer)


def test_thinking_block_is_split_correctly():
    stream = [" Mattis", "\nThe question asks about", " burglaries near", " Jayanagar.\n\n",
              "Between", " Jayanagar and", " Indiranagar."]
    reasoning, answer = _run_feed(stream)
    assert reasoning == "The question asks about burglaries near Jayanagar."
    assert answer == "Between Jayanagar and Indiranagar."


def test_no_byte_of_reasoning_ever_reaches_answer():
    stream = [" Mattis", "\ninternal deliberation 555/2099…\n\n", "The answer is ", "17/2023."]
    reasoning, answer = _run_feed(stream)
    assert "555/2099" in reasoning
    assert "555/2099" not in answer
    for fragment in [f for f in [reasoning[i:i + 4] for i in range(0, len(reasoning) - 3)] if len(f) == 4]:
        assert fragment not in answer, f"reasoning byte leaked into answer: {fragment!r}"


def test_marker_split_across_deltas():
    stream = [" Mat", "tis", "\nthinking…\n\n", "Answer", " text."]
    reasoning, answer = _run_feed(stream)
    assert reasoning == "thinking…"
    assert answer == "Answer text."


def test_no_thinking_stream_is_passthrough():
    stream = ["Direct answer", " without reasoning."]
    reasoning, answer = _run_feed(stream)
    assert reasoning == ""
    assert answer == "Direct answer without reasoning."


def test_stream_dying_inside_thinking_stays_reasoning():
    stream = [" Mattis", "\nunresolved deliberation…"]
    reasoning, answer = _run_feed(stream)
    assert "unresolved deliberation" in reasoning
    assert answer == ""


def test_repeated_probe_whitespace_then_answer():
    stream = ["  ", " Matt", "is\nthink\n\n", "ok"]
    reasoning, answer = _run_feed(stream)
    assert reasoning == "think"
    assert answer == "ok"


if __name__ == "__main__":
    for name in sorted(k for k in globals() if k.startswith("test_")):
        globals()[name]()
        print(f"PASS {name}")
    print("ALL REASONING SPLIT TESTS GREEN")
