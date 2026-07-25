"""
Read-only analytics endpoints.

All endpoints filter to request_logs for the currently authenticated
user (caller.user.id). No writes are made — safe, additive GET endpoints.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RequestLog, GuardrailAction
from app.db.session import get_db
from app.middleware.auth import AuthenticatedCaller, get_current_caller

router = APIRouter(prefix="/v1/analytics", tags=["analytics"])


# ──────────────────────────────────────────────
# Response shapes
# ──────────────────────────────────────────────

class OverviewResponse(BaseModel):
    # traffic
    total_requests: int
    total_savings_usd: float
    cache_hit_rate: float
    avg_latency_ms: float
    total_tokens: int
    total_cost_usd: float
    # gateway health
    blocked_requests: int
    redacted_requests: int
    fallback_requests: int
    error_requests: int
    # routing breakdown
    simple_requests: int
    complex_requests: int


class RequestLogEntry(BaseModel):
    id: str
    created_at: str
    model_used: Optional[str]
    routing_tier: Optional[str]
    was_cached: bool
    was_fallback: bool
    prompt_tokens: int
    completion_tokens: int
    estimated_cost_usd: float
    total_savings_usd: Optional[float]
    total_latency_ms: Optional[float]
    input_guardrail_action: Optional[str]
    output_guardrail_action: Optional[str]
    guardrail_reason: Optional[str]


class SavingsDay(BaseModel):
    date: str
    compression_savings_usd: float
    routing_savings_usd: float


class GuardrailDay(BaseModel):
    date: str
    blocked: int
    redacted: int
    passed: int


class ModelStat(BaseModel):
    model: str
    requests: int
    cost_usd: float


class GuardrailEvent(BaseModel):
    id: str
    created_at: str
    action: str
    reason: Optional[str]
    model_used: Optional[str]


# ──────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────

@router.get("/overview", response_model=OverviewResponse)
async def get_overview(
    caller: AuthenticatedCaller = Depends(get_current_caller),
    db: AsyncSession = Depends(get_db),
) -> OverviewResponse:
    """Aggregate metrics for the logged-in user's request history."""
    uid = caller.user.id

    row = (await db.execute(
        select(
            func.count(RequestLog.id).label("total_requests"),
            func.coalesce(
                func.sum(
                    func.coalesce(RequestLog.total_savings_usd, 0.0)
                    + func.coalesce(RequestLog.compression_savings_usd, 0.0)
                ),
                0.0,
            ).label("total_savings_usd"),
            func.coalesce(
                func.sum(case((RequestLog.was_cached == True, 1), else_=0)),  # noqa: E712
                0,
            ).label("cache_hits"),
            func.coalesce(func.avg(RequestLog.total_latency_ms), 0.0).label("avg_latency_ms"),
            func.coalesce(func.sum(RequestLog.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(RequestLog.estimated_cost_usd), 0.0).label("total_cost_usd"),
            # guardrails
            func.coalesce(
                func.sum(case((RequestLog.input_guardrail_action == GuardrailAction.blocked, 1), else_=0)),
                0,
            ).label("blocked_requests"),
            func.coalesce(
                func.sum(case((RequestLog.output_guardrail_action == GuardrailAction.redacted, 1), else_=0)),
                0,
            ).label("redacted_requests"),
            # reliability
            func.coalesce(
                func.sum(case((RequestLog.was_fallback == True, 1), else_=0)),  # noqa: E712
                0,
            ).label("fallback_requests"),
            func.coalesce(
                func.sum(case((RequestLog.status_code >= 400, 1), else_=0)),
                0,
            ).label("error_requests"),
            # routing tiers
            func.coalesce(
                func.sum(case((RequestLog.routing_tier == "simple", 1), else_=0)),
                0,
            ).label("simple_requests"),
            func.coalesce(
                func.sum(case((RequestLog.routing_tier == "complex", 1), else_=0)),
                0,
            ).label("complex_requests"),
        ).where(RequestLog.user_id == uid)
    )).one()

    total = row.total_requests or 0
    cache_hit_rate = (row.cache_hits / total) if total > 0 else 0.0

    return OverviewResponse(
        total_requests=total,
        total_savings_usd=float(row.total_savings_usd or 0.0),
        cache_hit_rate=round(cache_hit_rate, 4),
        avg_latency_ms=float(row.avg_latency_ms or 0.0),
        total_tokens=int(row.total_tokens or 0),
        total_cost_usd=float(row.total_cost_usd or 0.0),
        blocked_requests=int(row.blocked_requests or 0),
        redacted_requests=int(row.redacted_requests or 0),
        fallback_requests=int(row.fallback_requests or 0),
        error_requests=int(row.error_requests or 0),
        simple_requests=int(row.simple_requests or 0),
        complex_requests=int(row.complex_requests or 0),
    )


@router.get("/requests", response_model=list[RequestLogEntry])
async def get_requests(
    limit: int = Query(default=50, ge=1, le=500),
    caller: AuthenticatedCaller = Depends(get_current_caller),
    db: AsyncSession = Depends(get_db),
) -> list[RequestLogEntry]:
    """Most-recent requests for the logged-in user, newest first."""
    uid = caller.user.id

    rows = (await db.execute(
        select(RequestLog)
        .where(RequestLog.user_id == uid)
        .order_by(RequestLog.created_at.desc())
        .limit(limit)
    )).scalars().all()

    return [
        RequestLogEntry(
            id=str(row.id),
            created_at=row.created_at.isoformat() if row.created_at else "",
            model_used=row.model_used,
            routing_tier=row.routing_tier,
            was_cached=bool(row.was_cached),
            was_fallback=bool(row.was_fallback),
            prompt_tokens=int(row.prompt_tokens or 0),
            completion_tokens=int(row.completion_tokens or 0),
            estimated_cost_usd=float(row.estimated_cost_usd or 0.0),
            total_savings_usd=float(row.total_savings_usd or 0.0) if row.total_savings_usd is not None else None,
            total_latency_ms=float(row.total_latency_ms) if row.total_latency_ms is not None else None,
            input_guardrail_action=row.input_guardrail_action.value if row.input_guardrail_action else None,
            output_guardrail_action=row.output_guardrail_action.value if row.output_guardrail_action else None,
            guardrail_reason=row.guardrail_reason,
        )
        for row in rows
    ]


@router.get("/savings-timeseries", response_model=list[SavingsDay])
async def get_savings_timeseries(
    days: int = Query(default=7, ge=1, le=90),
    caller: AuthenticatedCaller = Depends(get_current_caller),
    db: AsyncSession = Depends(get_db),
) -> list[SavingsDay]:
    """Per-day savings breakdown over the last `days` days."""
    uid = caller.user.id
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    rows = (await db.execute(
        select(
            func.date(RequestLog.created_at).label("day"),
            func.coalesce(
                func.sum(func.coalesce(RequestLog.compression_savings_usd, 0.0)),
                0.0,
            ).label("compression_savings_usd"),
            func.coalesce(
                func.sum(func.coalesce(RequestLog.total_savings_usd, 0.0)),
                0.0,
            ).label("routing_savings_usd"),
        )
        .where(RequestLog.user_id == uid, RequestLog.created_at >= cutoff)
        .group_by(func.date(RequestLog.created_at))
        .order_by(func.date(RequestLog.created_at))
    )).all()

    return [
        SavingsDay(
            date=str(row.day),
            compression_savings_usd=float(row.compression_savings_usd or 0.0),
            routing_savings_usd=float(row.routing_savings_usd or 0.0),
        )
        for row in rows
    ]


@router.get("/guardrails-timeseries", response_model=list[GuardrailDay])
async def get_guardrails_timeseries(
    days: int = Query(default=7, ge=1, le=90),
    caller: AuthenticatedCaller = Depends(get_current_caller),
    db: AsyncSession = Depends(get_db),
) -> list[GuardrailDay]:
    """Per-day guardrail action counts over the last `days` days."""
    uid = caller.user.id
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    rows = (await db.execute(
        select(
            func.date(RequestLog.created_at).label("day"),
            func.coalesce(
                func.sum(case((RequestLog.input_guardrail_action == GuardrailAction.blocked, 1), else_=0)),
                0,
            ).label("blocked"),
            func.coalesce(
                func.sum(case((RequestLog.output_guardrail_action == GuardrailAction.redacted, 1), else_=0)),
                0,
            ).label("redacted"),
            func.count(RequestLog.id).label("total"),
        )
        .where(RequestLog.user_id == uid, RequestLog.created_at >= cutoff)
        .group_by(func.date(RequestLog.created_at))
        .order_by(func.date(RequestLog.created_at))
    )).all()

    return [
        GuardrailDay(
            date=str(row.day),
            blocked=int(row.blocked or 0),
            redacted=int(row.redacted or 0),
            passed=int(row.total or 0) - int(row.blocked or 0) - int(row.redacted or 0),
        )
        for row in rows
    ]


@router.get("/models", response_model=list[ModelStat])
async def get_model_stats(
    caller: AuthenticatedCaller = Depends(get_current_caller),
    db: AsyncSession = Depends(get_db),
) -> list[ModelStat]:
    """Request count and total cost grouped by model_used."""
    uid = caller.user.id

    rows = (await db.execute(
        select(
            RequestLog.model_used.label("model"),
            func.count(RequestLog.id).label("requests"),
            func.coalesce(func.sum(RequestLog.estimated_cost_usd), 0.0).label("cost_usd"),
        )
        .where(
            RequestLog.user_id == uid,
            RequestLog.model_used.isnot(None),
            RequestLog.model_used.notin_(["BLOCKED", "cache", "error"]),
        )
        .group_by(RequestLog.model_used)
        .order_by(func.count(RequestLog.id).desc())
    )).all()

    return [
        ModelStat(
            model=str(row.model),
            requests=int(row.requests),
            cost_usd=float(row.cost_usd or 0.0),
        )
        for row in rows
    ]


@router.get("/guardrail-events", response_model=list[GuardrailEvent])
async def get_guardrail_events(
    limit: int = Query(default=50, ge=1, le=200),
    caller: AuthenticatedCaller = Depends(get_current_caller),
    db: AsyncSession = Depends(get_db),
) -> list[GuardrailEvent]:
    """Recent requests where a guardrail fired (blocked or redacted), newest first."""
    uid = caller.user.id

    rows = (await db.execute(
        select(RequestLog)
        .where(
            RequestLog.user_id == uid,
            (RequestLog.input_guardrail_action == GuardrailAction.blocked)
            | (RequestLog.output_guardrail_action == GuardrailAction.redacted),
        )
        .order_by(RequestLog.created_at.desc())
        .limit(limit)
    )).scalars().all()

    def _action(row: RequestLog) -> str:
        if row.input_guardrail_action == GuardrailAction.blocked:
            return "blocked"
        if row.output_guardrail_action == GuardrailAction.redacted:
            return "redacted"
        return "passed"

    return [
        GuardrailEvent(
            id=str(row.id),
            created_at=row.created_at.isoformat() if row.created_at else "",
            action=_action(row),
            reason=row.guardrail_reason,
            model_used=row.model_used,
        )
        for row in rows
    ]
