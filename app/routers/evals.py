"""
Eval demo endpoints.

Runs a curated subset of the regression dataset (app/tests/eval_dataset.json)
through the real pure functions — route(), scan_input(), scan_output() — one
case at a time, for a live demo page in the dashboard.

No LLM calls, no network, no API-key usage: these are deterministic local
checks (pattern matching + token counting), identical to what the pytest
regression suite asserts. See app/tests/test_regression_eval.py.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.middleware.auth import AuthenticatedCaller, get_current_caller
from app.services.guardrails_in import scan_input
from app.services.guardrails_out import scan_output
from app.services.smart_router import route

router = APIRouter(prefix="/v1/evals", tags=["evals"])


# ──────────────────────────────────────────────
# Dataset — single source of truth (reused from the pytest suite)
# ──────────────────────────────────────────────

_DATASET_PATH = Path(__file__).resolve().parents[1] / "tests" / "eval_dataset.json"

with _DATASET_PATH.open(encoding="utf-8") as _f:
    _DATASET: list[dict[str, Any]] = json.load(_f)

_CASE_BY_ID: dict[str, dict[str, Any]] = {c["id"]: c for c in _DATASET}

# Curated demo subset — 3 per type, each chosen to PASS while showing
# distinct, easy-to-narrate behaviour. Order defines display + run order.
DEMO_CASE_IDS: list[str] = [
    # Routing
    "simple_001",   # short prompt -> cheap model
    "complex_002",  # code block -> premium model
    "complex_009",  # "explain ..." keyword -> premium model
    # Input guardrails
    "clean_001",    # safe question -> passed
    "override_001", # prompt injection -> blocked
    "multiturn_001",# attack in 3rd turn of a conversation -> blocked
    # Output guardrails
    "out_clean_001",# clean text -> passed
    "out_ssn_001",  # SSN -> redacted
    "out_multi_001",# email + SSN + phone + card -> redacted (4 types)
]

# Human-friendly labels for the demo cards.
_LABELS: dict[str, str] = {
    "simple_001": "Short prompt routes to the cheap model",
    "complex_002": "Code block routes to the premium model",
    "complex_009": "Reasoning keyword routes to the premium model",
    "clean_001": "Safe question passes the input guardrail",
    "override_001": "Prompt injection is blocked",
    "multiturn_001": "Injection mid-conversation is blocked",
    "out_clean_001": "Clean response passes the output guardrail",
    "out_ssn_001": "SSN in a response is redacted",
    "out_multi_001": "Email, SSN, phone and card are all redacted",
}

_CATEGORY_LABELS: dict[str, str] = {
    "routing": "Smart routing",
    "guardrail_input": "Input guardrails",
    "guardrail_output": "Output guardrails",
}


# ──────────────────────────────────────────────
# Response shapes
# ──────────────────────────────────────────────

class EvalCase(BaseModel):
    id: str
    category: str
    category_label: str
    label: str
    input_preview: str
    expected: str


class EvalResult(BaseModel):
    id: str
    category: str
    label: str
    passed: bool
    expected: str
    actual: str
    input: str
    output: Optional[str] = None
    model: Optional[str] = None
    reason: Optional[str] = None
    redacted_types: list[str] = []
    duration_ms: float


class RunCaseRequest(BaseModel):
    id: str


class SandboxRequest(BaseModel):
    mode: str  # "routing" | "guardrail_input" | "guardrail_output"
    text: str


class SandboxResult(BaseModel):
    mode: str
    input: str
    action: str
    model: Optional[str] = None
    reason: Optional[str] = None
    output: Optional[str] = None
    redacted_types: list[str] = []
    duration_ms: float


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _input_preview(case: dict[str, Any]) -> str:
    """A compact, human-readable preview of the case input."""
    if case["category"] == "routing":
        return case.get("prompt", "")
    if case["category"] == "guardrail_input":
        if "messages" in case:
            return " ↳ ".join(
                f'{m["role"]}: {m["content"]}' for m in case["messages"]
            )
        return case.get("prompt", "")
    # guardrail_output
    return case.get("output_to_scan", "")


def _expected(case: dict[str, Any]) -> str:
    if case["category"] == "routing":
        return case["expected_tier"]
    return case["expected_action"]


# ──────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────

@router.get("/cases", response_model=list[EvalCase])
async def get_cases(
    caller: AuthenticatedCaller = Depends(get_current_caller),
) -> list[EvalCase]:
    """Return the curated demo cases in display order (no execution)."""
    cases: list[EvalCase] = []
    for cid in DEMO_CASE_IDS:
        case = _CASE_BY_ID.get(cid)
        if case is None:
            continue
        cases.append(
            EvalCase(
                id=cid,
                category=case["category"],
                category_label=_CATEGORY_LABELS.get(case["category"], case["category"]),
                label=_LABELS.get(cid, cid),
                input_preview=_input_preview(case),
                expected=_expected(case),
            )
        )
    return cases


@router.post("/run-case", response_model=EvalResult)
async def run_case(
    body: RunCaseRequest,
    caller: AuthenticatedCaller = Depends(get_current_caller),
) -> EvalResult:
    """Execute a single curated case through the real pipeline function."""
    if body.id not in DEMO_CASE_IDS:
        raise HTTPException(status_code=404, detail=f"Unknown demo case: {body.id}")

    case = _CASE_BY_ID[body.id]
    category = case["category"]
    label = _LABELS.get(body.id, body.id)

    start = time.perf_counter()

    if category == "routing":
        token_count = case.get("token_count", len(case["prompt"].split()))
        result = route(case["prompt"], token_count=token_count)
        expected = case["expected_tier"]
        actual = result["tier"]
        passed = actual == expected
        duration_ms = (time.perf_counter() - start) * 1000
        return EvalResult(
            id=body.id, category=category, label=label, passed=passed,
            expected=expected, actual=actual, input=case["prompt"],
            model=result.get("model"), reason=result.get("reason"),
            duration_ms=duration_ms,
        )

    if category == "guardrail_input":
        messages = case.get("messages") or [
            {"role": "user", "content": case["prompt"]}
        ]
        scanned_input = "\n".join(
            f'{m["role"]}: {m["content"]}' for m in messages
        )
        res = await scan_input(messages)
        expected = case["expected_action"]
        actual = res.action
        passed = actual == expected
        duration_ms = (time.perf_counter() - start) * 1000
        return EvalResult(
            id=body.id, category=category, label=label, passed=passed,
            expected=expected, actual=actual, input=scanned_input,
            reason=res.reason, duration_ms=duration_ms,
        )

    # guardrail_output
    res = await scan_output(case["output_to_scan"])
    expected = case["expected_action"]
    actual = res.action
    passed = actual == expected
    if "expected_types" in case:
        expected_types = set(case["expected_types"])
        passed = passed and expected_types <= set(res.redacted_types)
    duration_ms = (time.perf_counter() - start) * 1000
    return EvalResult(
        id=body.id, category=category, label=label, passed=passed,
        expected=expected, actual=actual, input=case["output_to_scan"],
        output=res.content, reason=res.reason,
        redacted_types=res.redacted_types, duration_ms=duration_ms,
    )


_MAX_SANDBOX_CHARS = 5000
_SANDBOX_MODES = {"routing", "guardrail_input", "guardrail_output"}


@router.post("/sandbox", response_model=SandboxResult)
async def sandbox(
    body: SandboxRequest,
    caller: AuthenticatedCaller = Depends(get_current_caller),
) -> SandboxResult:
    """Run arbitrary user-supplied text through the real pipeline function.

    Same deterministic local functions as the curated cases — proof that
    results are computed, not hardcoded. No LLM / no quota.
    """
    if body.mode not in _SANDBOX_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown mode: {body.mode}. Expected one of {sorted(_SANDBOX_MODES)}",
        )
    text = body.text or ""
    if not text.strip():
        raise HTTPException(status_code=400, detail="Text must not be empty")
    if len(text) > _MAX_SANDBOX_CHARS:
        raise HTTPException(
            status_code=400,
            detail=f"Text too long ({len(text)} chars); max is {_MAX_SANDBOX_CHARS}",
        )

    start = time.perf_counter()

    if body.mode == "routing":
        result = route(text, token_count=len(text.split()))
        duration_ms = (time.perf_counter() - start) * 1000
        return SandboxResult(
            mode=body.mode, input=text, action=result["tier"],
            model=result.get("model"), reason=result.get("reason"),
            duration_ms=duration_ms,
        )

    if body.mode == "guardrail_input":
        res = await scan_input([{"role": "user", "content": text}])
        duration_ms = (time.perf_counter() - start) * 1000
        return SandboxResult(
            mode=body.mode, input=text, action=res.action,
            reason=res.reason, duration_ms=duration_ms,
        )

    # guardrail_output
    res = await scan_output(text)
    duration_ms = (time.perf_counter() - start) * 1000
    return SandboxResult(
        mode=body.mode, input=text, action=res.action, output=res.content,
        reason=res.reason, redacted_types=res.redacted_types,
        duration_ms=duration_ms,
    )
