"""Zero-hallucination sampling preset shared with inference/.
Deterministic greedy decode: temperature=0, top_k=1.
"""

ZERO_HALLUCINATION_PRESET = {
    "temperature": 0.0,
    "top_k": 1,
    "top_p": 1.0,
    "repeat_penalty": 1.15,
    "min_p": 0.05,
}


def synthesis_params() -> dict:
    return dict(ZERO_HALLUCINATION_PRESET)
