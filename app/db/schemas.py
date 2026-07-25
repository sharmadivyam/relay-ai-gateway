"""Pydantic schemas — the shape of data coming IN and going OUT of the API."""
from __future__ import annotations
from datetime import datetime
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field
import uuid


# ──────────────────────────────────────────────
# OpenAI-compatible request / response shapes
# ──────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "function", "tool"]
    content: str | None = None
    name: Optional[str] = None


class ChatCompletionRequest(BaseModel):
    model: str = Field(default="gpt-4o-mini")
    messages: list[ChatMessage]
    temperature: Optional[float] = 1.0
    max_tokens: Optional[int] = None
    stream: bool = False
    user: Optional[str] = None          # optional end-user identifier
    # Allow any extra OpenAI params to pass through
    model_config = {"extra": "allow"}


class UsageInfo(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: Optional[str] = None


class ChatCompletionResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:24]}")
    object: str = "chat.completion"
    model: str
    choices: list[ChatCompletionChoice]
    usage: UsageInfo
    # Gateway-specific extras (stripped before returning to client if desired)
    gateway_cached: bool = False
    gateway_fallback: bool = False


# ──────────────────────────────────────────────
# Auth schemas
# ──────────────────────────────────────────────

class UserCreate(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    tier: str

    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ApiKeyCreate(BaseModel):
    label: Optional[str] = None


class ApiKeyOut(BaseModel):
    id: uuid.UUID
    key_prefix: str
    label: Optional[str]
    raw_key: Optional[str] = None   # only returned once at creation time
    created_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────
# Telemetry / internal
# ──────────────────────────────────────────────

class TelemetryPayload(BaseModel):
    user_id: Optional[uuid.UUID]
    api_key_prefix: Optional[str]
    request_id: Optional[str] = None   # gateway response ID — ties DB row to API response
    model_requested: str
    model_used: str
    was_cached: bool
    was_fallback: bool
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    ttft_ms: Optional[float]
    total_latency_ms: float
    input_guardrail_action: str
    output_guardrail_action: str
    guardrail_reason: Optional[str]
    status_code: int
    error_message: Optional[str]

    # Phase 4: savings logging (all optional — blocked/cached/error paths leave these as defaults)
    original_tokens: Optional[int] = None
    compressed_tokens: Optional[int] = None
    compression_compressed: bool = False       # True only when prompt was actually compressed
    routing_tier: Optional[str] = None        # "simple" | "complex" | "n/a"
    routing_reason: Optional[str] = None
