"""
Unit tests for app/services/smart_router.py

All tests are synchronous — route() is a pure function with no I/O.
Settings are patched via unittest.mock to avoid .env dependency.
"""
from unittest.mock import patch, MagicMock

import pytest

from app.services.smart_router import route

CHEAP = "gpt-4o-mini"
PREMIUM = "gpt-4o"


def _mock_settings():
    s = MagicMock()
    s.cheap_model = CHEAP
    s.premium_model = PREMIUM
    return s


# ── Simple tier tests ──────────────────────────────────────────────────────


def test_short_plain_prompt_is_simple():
    with patch("app.services.smart_router.get_settings", return_value=_mock_settings()):
        result = route("What is the capital?", token_count=10)
    assert result["tier"] == "simple"
    assert result["reason"] == "short_plain_prompt"


def test_simple_uses_cheap_model():
    with patch("app.services.smart_router.get_settings", return_value=_mock_settings()):
        result = route("Hello there", token_count=5)
    assert result["model"] == CHEAP


def test_exactly_150_tokens_is_simple():
    with patch("app.services.smart_router.get_settings", return_value=_mock_settings()):
        result = route("short plain text", token_count=150)
    assert result["tier"] == "simple"


# ── Complex tier — token length ────────────────────────────────────────────


def test_301_tokens_is_complex():
    with patch("app.services.smart_router.get_settings", return_value=_mock_settings()):
        result = route("short plain text", token_count=301)
    assert result["tier"] == "complex"
    assert result["reason"] == "length_or_code_or_keyword"


# ── Complex tier — code signals ────────────────────────────────────────────


def test_backtick_code_block_is_complex():
    with patch("app.services.smart_router.get_settings", return_value=_mock_settings()):
        result = route("here is some code:\n```python\nprint('hi')\n```", token_count=20)
    assert result["tier"] == "complex"


def test_def_keyword_is_complex():
    with patch("app.services.smart_router.get_settings", return_value=_mock_settings()):
        result = route("def my_function(): pass", token_count=10)
    assert result["tier"] == "complex"


def test_function_keyword_is_complex():
    with patch("app.services.smart_router.get_settings", return_value=_mock_settings()):
        result = route("function foo() { return 1; }", token_count=10)
    assert result["tier"] == "complex"


# ── Complex tier — keyword signals ────────────────────────────────────────


def test_explain_keyword_is_complex():
    with patch("app.services.smart_router.get_settings", return_value=_mock_settings()):
        result = route("Can you explain this concept to me?", token_count=10)
    assert result["tier"] == "complex"


def test_analyze_keyword_is_complex():
    with patch("app.services.smart_router.get_settings", return_value=_mock_settings()):
        result = route("Please analyze the following data", token_count=10)
    assert result["tier"] == "complex"


def test_step_by_step_keyword_is_complex():
    with patch("app.services.smart_router.get_settings", return_value=_mock_settings()):
        result = route("Show me step by step how to do this", token_count=10)
    assert result["tier"] == "complex"


def test_summarize_in_detail_keyword_is_complex():
    with patch("app.services.smart_router.get_settings", return_value=_mock_settings()):
        result = route("Please summarize in detail the report", token_count=10)
    assert result["tier"] == "complex"


def test_complex_uses_premium_model():
    with patch("app.services.smart_router.get_settings", return_value=_mock_settings()):
        result = route("explain quantum entanglement", token_count=10)
    assert result["model"] == PREMIUM


# ── Case insensitivity ─────────────────────────────────────────────────────


def test_keyword_matching_is_case_insensitive():
    with patch("app.services.smart_router.get_settings", return_value=_mock_settings()):
        result = route("EXPLAIN this to me", token_count=10)
    assert result["tier"] == "complex"
