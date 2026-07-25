"""
Unit tests for app/services/prompt_compressor.py

get_compressor() is mocked in all above-threshold tests so no model weights
are downloaded and the suite stays fast and offline-safe.
"""
from unittest.mock import patch, MagicMock

from app.services.prompt_compressor import maybe_compress

THRESHOLD = 1500
SHORT_PROMPT = "What is the capital of France?"
SHORT_TOKENS = 10

LONG_PROMPT = " ".join(["word"] * 200)   # synthetic prompt above threshold
LONG_TOKENS = 2000


# ── Below-threshold (pass-through) ────────────────────────────────────────


def test_below_threshold_not_compressed():
    result = maybe_compress(SHORT_PROMPT, SHORT_TOKENS, THRESHOLD)
    assert result["compressed"] is False


def test_below_threshold_prompt_unchanged():
    result = maybe_compress(SHORT_PROMPT, SHORT_TOKENS, THRESHOLD)
    assert result["prompt"] == SHORT_PROMPT


def test_below_threshold_tokens_unchanged():
    result = maybe_compress(SHORT_PROMPT, SHORT_TOKENS, THRESHOLD)
    assert result["original_tokens"] == SHORT_TOKENS
    assert result["final_tokens"] == SHORT_TOKENS


def test_just_below_threshold_not_compressed():
    """token_count = threshold - 1 is strictly below — pass-through path."""
    result = maybe_compress(SHORT_PROMPT, THRESHOLD - 1, THRESHOLD)
    assert result["compressed"] is False


def test_at_threshold_is_compressed():
    """token_count == threshold: condition is token_count < threshold which is False, so compresses."""
    with patch(
        "app.services.prompt_compressor.get_compressor",
        return_value=_mock_compressor(THRESHOLD, 750, "compressed"),
    ):
        result = maybe_compress(SHORT_PROMPT, THRESHOLD, THRESHOLD)
    assert result["compressed"] is True


# ── Above-threshold (compression path) ────────────────────────────────────


def _mock_compressor(original_tokens: int, compressed_tokens: int, compressed_text: str):
    mock = MagicMock()
    mock.compress_prompt.return_value = {
        "compressed_prompt": compressed_text,
        "compressed_tokens": compressed_tokens,
    }
    return mock


def test_above_threshold_is_compressed():
    with patch(
        "app.services.prompt_compressor.get_compressor",
        return_value=_mock_compressor(LONG_TOKENS, 1000, "compressed text"),
    ):
        result = maybe_compress(LONG_PROMPT, LONG_TOKENS, THRESHOLD)
    assert result["compressed"] is True


def test_above_threshold_final_tokens_less_than_original():
    with patch(
        "app.services.prompt_compressor.get_compressor",
        return_value=_mock_compressor(LONG_TOKENS, 1000, "compressed text"),
    ):
        result = maybe_compress(LONG_PROMPT, LONG_TOKENS, THRESHOLD)
    assert result["final_tokens"] < result["original_tokens"]


def test_above_threshold_original_tokens_preserved():
    with patch(
        "app.services.prompt_compressor.get_compressor",
        return_value=_mock_compressor(LONG_TOKENS, 1000, "compressed text"),
    ):
        result = maybe_compress(LONG_PROMPT, LONG_TOKENS, THRESHOLD)
    assert result["original_tokens"] == LONG_TOKENS


def test_above_threshold_compressed_prompt_returned():
    compressed_text = "compressed text"
    with patch(
        "app.services.prompt_compressor.get_compressor",
        return_value=_mock_compressor(LONG_TOKENS, 1000, compressed_text),
    ):
        result = maybe_compress(LONG_PROMPT, LONG_TOKENS, THRESHOLD)
    assert result["prompt"] == compressed_text


def test_one_above_threshold_is_compressed():
    """token_count = threshold + 1 should trigger compression."""
    with patch(
        "app.services.prompt_compressor.get_compressor",
        return_value=_mock_compressor(THRESHOLD + 1, 750, "compressed"),
    ):
        result = maybe_compress(LONG_PROMPT, THRESHOLD + 1, THRESHOLD)
    assert result["compressed"] is True
