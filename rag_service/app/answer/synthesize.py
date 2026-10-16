"""Answer synthesis + history summarization + offender profiles (§12.5, §11.5).

stream_answer yields ('reasoning'|'token', text) — the reasoning channel is
excluded from citation validation and from the audit log's answer field
(§1.3 rule 2). History summarization replaces turns older than three with a
one-line digest (§11.3 step 1) at the 'summarize' preset (temp 0.2, thinking
off, 160 tokens).
"""
from __future__ import annotations

from typing import AsyncGenerator

from ..llm import client, prompts, sampling


async def stream_answer(scope, context_block: str, kept_history: list[dict],
                       question: str) -> AsyncGenerator[tuple[str, str], None]:
    preset = sampling.sampling_for("synthesis")
    messages = prompts.build_synthesis_messages(scope, context_block, kept_history, question)
    async for channel, token in client.stream(messages, preset, thinking=preset["thinking"]):
        yield channel, token


async def history_summarizer(turns: list[dict]) -> str:
    """One-line digest of older conversation turns (§11.3 step 1)."""
    if not turns:
        return ""
    convo = "\n".join(f"{t['role']}: {t['content']}" for t in turns[-6:])
    preset = sampling.sampling_for("summarize")
    messages = [
        {"role": "system", "content": "Summarize this conversation between an investigator and an "
                                      "assistant into ONE factual line (max 25 words). Keep FIR "
                                      "numbers, person and station names. Output the line only."},
        {"role": "user", "content": convo},
    ]
    try:
        summary = await client.chat(messages, preset, thinking=False)
        return " ".join(summary.split())[:700]
    except client.LLMUpstreamError:
        return "earlier turns unavailable"


async def offender_profile(person_name: str, rows: list[dict]) -> str:
    """Grounded offender-profile summary (§11.5 'Offender profile summary':
    card sampling, 768 tokens, thinking per A/B). Numbers in `rows` come from
    Cypher; the model is told not to compute new ones."""
    preset = sampling.sampling_for("profile")
    facts = "\n".join(
        "- " + " | ".join(f"{k}={v}" for k, v in row.items()) for row in rows[:40]
    )
    messages = [
        {"role": "system", "content": (
            "Write a compact investigative profile from the STRUCTURED FACTS only. "
            "Never compute counts not present in the facts. Every FIR id mentioned "
            "must appear in the facts. 3–6 sentences, plain text."
        )},
        {"role": "user", "content": f"PERSON: {person_name}\nSTRUCTURED FACTS:\n{facts}"},
    ]
    return await client.chat(messages, preset, thinking=preset["thinking"])
