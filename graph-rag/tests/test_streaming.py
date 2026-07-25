"""Test SSE streaming generators handle CancelledError cleanly."""
from __future__ import annotations

import asyncio
import pytest

from app.core.streaming import safe_relay, no_template_match_event, no_context_event, token_event, done_event


async def gen_ok():
    yield no_template_match_event("q", "rid")
    yield token_event("hello", "rid")
    yield done_event([], 0, 10, "rid")


async def gen_error():
    yield token_event("x", "rid")
    raise ValueError("boom")


async def gen_cancel():
    yield token_event("x", "rid")
    raise asyncio.CancelledError()


@pytest.mark.asyncio
async def test_safe_relay_ok():
    events = []
    async for ev in safe_relay(gen_ok()):
        events.append(ev)
    assert len(events) == 3


@pytest.mark.asyncio
async def test_safe_relay_error():
    events = []
    async for ev in safe_relay(gen_error()):
        events.append(ev)
    assert len(events) == 2  # token + error
    assert events[-1]["event"] == "error"


@pytest.mark.asyncio
async def test_safe_relay_cancel():
    events = []
    with pytest.raises(asyncio.CancelledError):
        async for ev in safe_relay(gen_cancel()):
            events.append(ev)
    # The generator should exit cleanly without raising beyond CancelledError