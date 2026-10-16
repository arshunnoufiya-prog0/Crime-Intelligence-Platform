"""Per-task sampling presets (spec §11.5) + the verified Qwen3.5-4B card
defaults (§1.6, recorded in artifacts/verification.md).

'card' = the model card's Thinking-mode/general set, fetched from
https://huggingface.co/Qwen/Qwen3.5-4B on 2026-09-22:
    temperature=1.0, top_p=0.95, top_k=20, min_p=0.0,
    presence_penalty=1.5, repetition_penalty=1.0

Deterministic sub-tasks override to temperature=0, top_k=1 with thinking OFF
(§1.3 rule 3). Synthesis/profile thinking is decided by the Step 13 A/B gate
(KSP_THINKING_SYNTHESIS env, default true); both numbers must be recorded in
artifacts/verification.md before changing it.
"""
from __future__ import annotations

import os

CARD_THINKING_GENERAL = {
    "temperature": 1.0,
    "top_p": 0.95,
    "top_k": 20,
    "min_p": 0.0,
    "presence_penalty": 1.5,
    "repeat_penalty": 1.0,
}

PRESETS: dict[str, dict] = {
    "intent": {
        "temperature": 0.0, "top_p": 1.0, "top_k": 1,
        "n_predict": 16, "thinking": False,
    },
    "slots": {
        "temperature": 0.0, "top_p": 1.0, "top_k": 1,
        "n_predict": 96, "thinking": False,
    },
    "synthesis": {**CARD_THINKING_GENERAL, "n_predict": 1024},
    "profile": {**CARD_THINKING_GENERAL, "n_predict": 768},
    "summarize": {
        "temperature": 0.2, "top_p": 0.8, "top_k": 20,
        "n_predict": 160, "thinking": False,
    },
}


def synthesis_thinking_enabled() -> bool:
    return os.environ.get("KSP_THINKING_SYNTHESIS", "true").lower() in ("1", "true", "yes")


def sampling_for(task: str) -> dict:
    preset = dict(PRESETS[task])
    if task in ("synthesis", "profile"):
        preset["thinking"] = synthesis_thinking_enabled()
    return preset
