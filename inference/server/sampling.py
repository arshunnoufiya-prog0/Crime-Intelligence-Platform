ZERO_HALLUCINATION_PRESET = {
    "temperature": 0.0,
    "top_k": 1,
    "top_p": 1.0,
    "repeat_penalty": 1.15,
    "min_p": 0.05,
}

MAX_TEMPERATURE_WITHOUT_CREATIVE = 0.5


def validate_sampling(sampling: dict, allow_creative: bool) -> dict:
    """Return a normalized sampling dict injected with zero-hallucination defaults
    for any caller-omitted field, and reject unsafe temperature."""
    preset = dict(ZERO_HALLUCINATION_PRESET)
    for key in ("temperature", "top_k", "top_p", "repeat_penalty", "min_p"):
        if key in sampling and sampling[key] is not None:
            try:
                coerced = float(sampling[key]) if key in ("temperature", "top_p", "repeat_penalty", "min_p") else int(sampling[key])
            except (TypeError, ValueError):
                coerced = preset[key]
            preset[key] = coerced

    temp = preset["temperature"]
    if temp > MAX_TEMPERATURE_WITHOUT_CREATIVE and not allow_creative:
        raise ValueError(
            f"temperature={temp} exceeds {MAX_TEMPERATURE_WITHOUT_CREATIVE} without X-Allow-Creative: true"
        )
    return preset
