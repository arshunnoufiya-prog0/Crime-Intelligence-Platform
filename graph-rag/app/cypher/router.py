"""dispatch: ClassifiedIntent -> (template, params) | None.
For FIR-keyed intents, validator.build_params resolves fir_id→fir_key async.
"""
from __future__ import annotations

from ..intent.schema import ClassifiedIntent, IntentType
from ..cypher.templates import TEMPLATES
from ..cypher import validator


async def route(classified: ClassifiedIntent) -> tuple[str, dict] | None:
    if classified.intent not in TEMPLATES:
        return None  # caller emits no_template_match_event; no Cypher, no LLM
    template = TEMPLATES[classified.intent]
    params = await validator.build_params(classified)
    return template, params
