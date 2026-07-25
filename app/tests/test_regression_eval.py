"""
Regression eval suite.

Loads eval_dataset.json and asserts the real pure functions against every
entry. No server, no DB, no LLM calls — runs in pure Python in <2 s.

Function signatures verified against source before wiring:
  route(prompt: str, token_count: int) -> dict        (sync)
  scan_input(messages: list[dict]) -> GuardrailResult (async)
  scan_output(content: str) -> OutputGuardrailResult  (async)

Dataset layout:
  routing          – requires prompt, token_count (optional; fallback=word count), expected_tier
  guardrail_input  – requires prompt OR messages, expected_action
  guardrail_output – requires output_to_scan, expected_action, optional expected_types

Multi-message input cases store a messages list; single-message cases store
a prompt string that the runner wraps as [{"role":"user","content":prompt}].

To add cases: edit eval_dataset.json only — no Python changes needed.
To fix a failing case: adjust the dataset entry if the expectation was wrong.
Never loosen pipeline behaviour just to make a dataset entry pass.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from app.services.guardrails_in import scan_input
from app.services.guardrails_out import scan_output
from app.services.smart_router import route

# ── Load dataset ─────────────────────────────────────────────────────────────

_DATASET_PATH = Path(__file__).parent / "eval_dataset.json"

with _DATASET_PATH.open(encoding="utf-8") as _f:
    _DATASET: list[dict[str, Any]] = json.load(_f)

_routing_cases = [c for c in _DATASET if c["category"] == "routing"]
_input_cases = [c for c in _DATASET if c["category"] == "guardrail_input"]
_output_cases = [c for c in _DATASET if c["category"] == "guardrail_output"]


# ── Routing ───────────────────────────────────────────────────────────────────
# route() is a pure sync function — no asyncio needed.
# token_count: use the explicit field when present, otherwise fall back to
# the word count of the prompt (matches the spec runner's fallback strategy).

@pytest.mark.parametrize("case", _routing_cases, ids=lambda c: c["id"])
def test_routing_tier(case: dict[str, Any]) -> None:
    token_count: int = case.get("token_count", len(case["prompt"].split()))
    result = route(case["prompt"], token_count=token_count)
    assert result["tier"] == case["expected_tier"], (
        f"{case['id']}: expected tier={case['expected_tier']!r}, got {result['tier']!r}"
        f" (token_count={token_count}, reason={result.get('reason')!r})"
    )


# ── Input guardrails ──────────────────────────────────────────────────────────
# scan_input() is async and takes list[dict].
# Multi-message cases store a messages list; single-prompt cases are wrapped.

@pytest.mark.asyncio
@pytest.mark.parametrize("case", _input_cases, ids=lambda c: c["id"])
async def test_input_guardrail_action(case: dict[str, Any]) -> None:
    if "messages" in case:
        messages = case["messages"]
    else:
        messages = [{"role": "user", "content": case["prompt"]}]

    result = await scan_input(messages)
    assert result.action == case["expected_action"], (
        f"{case['id']}: expected action={case['expected_action']!r}, "
        f"got {result.action!r} (reason={result.reason!r})"
    )


# ── Output guardrails ─────────────────────────────────────────────────────────
# scan_output() is async and takes a plain string.
# expected_types (optional) is verified as a subset of result.redacted_types.

@pytest.mark.asyncio
@pytest.mark.parametrize("case", _output_cases, ids=lambda c: c["id"])
async def test_output_guardrail_action(case: dict[str, Any]) -> None:
    result = await scan_output(case["output_to_scan"])
    assert result.action == case["expected_action"], (
        f"{case['id']}: expected action={case['expected_action']!r}, "
        f"got {result.action!r} (reason={result.reason!r})"
    )
    if "expected_types" in case:
        expected = set(case["expected_types"])
        actual = set(result.redacted_types)
        missing = expected - actual
        assert not missing, (
            f"{case['id']}: expected PII types {expected}, "
            f"got {actual} — missing {missing}"
        )
