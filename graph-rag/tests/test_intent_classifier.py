"""Test intent classifier with mocked LLM."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from app.intent.schema import ClassifiedIntent, ExtractedEntities, IntentType
from app.intent.classifier import IntentClassifier


class MockChain:
    def __init__(self, response):
        self.response = response

    async def ainvoke(self, _):
        return self.response


@pytest.mark.asyncio
async def test_find_fir_by_id():
    resp = ClassifiedIntent(
        intent=IntentType.FIND_FIR_BY_ID,
        entities=ExtractedEntities(fir_id="4/2023"),
        confidence=0.95,
    )
    with patch("app.intent.classifier.IntentClassifier._get_chain", return_value=MockChain(resp)):
        clf = IntentClassifier()
        ci = await clf.classify("show me FIR 4/2023")
        assert ci.intent == IntentType.FIND_FIR_BY_ID
        assert ci.entities.fir_id == "4/2023"


@pytest.mark.asyncio
async def test_find_firs_by_crime_type():
    resp = ClassifiedIntent(
        intent=IntentType.FIND_FIRS_BY_CRIME_TYPE,
        entities=ExtractedEntities(crime_head="ROBBERY"),
        confidence=0.9,
    )
    with patch("app.intent.classifier.IntentClassifier._get_chain", return_value=MockChain(resp)):
        clf = IntentClassifier()
        ci = await clf.classify("list all robbery cases")
        assert ci.intent == IntentType.FIND_FIRS_BY_CRIME_TYPE
        assert ci.entities.crime_head == "ROBBERY"


@pytest.mark.asyncio
async def test_semantic_search():
    resp = ClassifiedIntent(
        intent=IntentType.SEMANTIC_SEARCH,
        entities=ExtractedEntities(free_text="what happened with the cyber fraud ring in Indiranagar"),
        confidence=0.8,
    )
    with patch("app.intent.classifier.IntentClassifier._get_chain", return_value=MockChain(resp)):
        clf = IntentClassifier()
        ci = await clf.classify("what happened with the cyber fraud ring in Indiranagar")
        assert ci.intent == IntentType.SEMANTIC_SEARCH


@pytest.mark.asyncio
async def test_unsupported():
    resp = ClassifiedIntent(
        intent=IntentType.UNSUPPORTED,
        entities=ExtractedEntities(),
        confidence=0.1,
    )
    with patch("app.intent.classifier.IntentClassifier._get_chain", return_value=MockChain(resp)):
        clf = IntentClassifier()
        ci = await clf.classify("this is gibberish xyz")
        assert ci.intent == IntentType.UNSUPPORTED