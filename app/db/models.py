from datetime import datetime, timezone, timedelta
import uuid

# Indian Standard Time — UTC+5:30.  Used for all stored timestamps so that
# created_at / last_used_at values are human-readable in IST without conversion.
IST = timezone(timedelta(hours=5, minutes=30))
from sqlalchemy import (
    Column, String, Integer, BigInteger, Float, Boolean,
    DateTime, ForeignKey, Text, Uuid, Enum as SAEnum
)
# MIGRATION NOTE: Uuid (sqlalchemy.Uuid) is backend-agnostic — renders as
# UUID on PostgreSQL and CHAR(32) on SQLite. Do NOT use
# sqlalchemy.dialects.postgresql.UUID here; it breaks SQLite.
from sqlalchemy.orm import DeclarativeBase, relationship
import enum


class Base(DeclarativeBase):
    pass


class UserTier(str, enum.Enum):
    free = "free"
    pro = "pro"
    enterprise = "enterprise"


class GuardrailAction(str, enum.Enum):
    passed = "passed"
    blocked = "blocked"
    redacted = "redacted"


class User(Base):
    __tablename__ = "users"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    tier = Column(SAEnum(UserTier), default=UserTier.free, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(IST))

    api_keys = relationship("ApiKey", back_populates="user", cascade="all, delete-orphan")
    request_logs = relationship("RequestLog", back_populates="user")


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    # Stored as a hash; never store raw keys
    key_hash = Column(String(64), unique=True, nullable=False, index=True)
    key_prefix = Column(String(8), nullable=False)   # e.g. "sk-gw_ab" for display
    label = Column(String(100))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(IST))
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="api_keys")


class RequestLog(Base):
    """
    One row per LLM request that passes through the gateway.

    Phase 2 Superset dashboard readiness — all mandatory columns confirmed:
      prompt_tokens       -> prompt_tokens        (Integer)
      completion_tokens   -> completion_tokens     (Integer)
      total_cost          -> estimated_cost_usd    (Float)   [SQL alias: AS total_cost_usd]
      latency_ms          -> total_latency_ms      (Float)   [SQL alias: AS avg_latency_ms]
      model_used          -> model_used            (String)

    Column names match the 5 pre-built queries in superset/dashboard_queries.sql exactly.
    """
    __tablename__ = "request_logs"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    api_key_prefix = Column(String(8))

    # Correlation: client-provided or gateway-generated ID for request tracing (Phase 2)
    request_id = Column(String(64), nullable=True, index=True)

    # Request metadata
    model_requested = Column(String(100))
    model_used = Column(String(100))      # may differ if fallback triggered
    was_cached = Column(Boolean, default=False)
    was_fallback = Column(Boolean, default=False)

    # Token accounting — mandatory for Phase 2 Superset cost charts
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    estimated_cost_usd = Column(Float, default=0.0)

    # Latency — mandatory for Phase 2 Superset latency charts
    ttft_ms = Column(Float, nullable=True)   # Time-To-First-Token in milliseconds
    total_latency_ms = Column(Float, nullable=True)

    # Guardrails
    input_guardrail_action = Column(SAEnum(GuardrailAction), default=GuardrailAction.passed)
    output_guardrail_action = Column(SAEnum(GuardrailAction), default=GuardrailAction.passed)
    guardrail_reason = Column(Text, nullable=True)

    # HTTP
    status_code = Column(Integer)
    error_message = Column(Text, nullable=True)

    # Phase 0: smart-routing + compression telemetry (all nullable, flags-gated)
    original_tokens = Column(Integer, nullable=True)
    compressed_tokens = Column(Integer, nullable=True)
    compression_savings_usd = Column(Float, nullable=True, default=0.0)

    routing_tier = Column(String, nullable=True)    # "simple" | "complex"
    routing_reason = Column(String, nullable=True)
    premium_cost_usd = Column(Float, nullable=True)
    actual_cost_usd = Column(Float, nullable=True)
    total_savings_usd = Column(Float, nullable=True, default=0.0)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(IST), index=True)

    user = relationship("User", back_populates="request_logs")
