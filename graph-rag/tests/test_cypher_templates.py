"""Test Cypher templates are parameterized and static (no user/LLM interpolation)."""
import re

from app.cypher.templates import TEMPLATES
from app.intent.schema import IntentType


FORBIDDEN_PATTERNS = [
    re.compile(r"f[\"'].*\{"),  # f-strings
    re.compile(r"[\"']\s*[+\%]"),  # string concatenation / % formatting
    re.compile(r"\$\{"),  # template literals (JS-style)
]


def test_templates_static_and_parameterized():
    for intent, tmpl in TEMPLATES.items():
        assert isinstance(tmpl, str) and len(tmpl) > 0
        # Must contain parameter placeholders $param
        assert "$" in tmpl, f"{intent.value} has no $params"
        # No f-strings or string interpolation of user data
        for pat in FORBIDDEN_PATTERNS:
            matches = pat.findall(tmpl)
            assert not matches, f"{intent.value} contains forbidden interpolation: {matches}"


def test_all_intents_have_templates_except_semantic():
    for intent in IntentType:
        if intent == IntentType.SEMANTIC_SEARCH:
            assert intent not in TEMPLATES
        else:
            assert intent in TEMPLATES, f"missing template for {intent.value}"