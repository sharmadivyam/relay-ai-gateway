"""
Async telemetry logger.

Runs as a FastAPI BackgroundTask so it never blocks the main response loop.
The entire function body is wrapped in a single try/except so that BOTH
connection failures (Postgres not yet running) and write failures (constraint
violations, schema mismatches) are caught and printed — the FastAPI server
never crashes due to a telemetry failure.
"""
import logging

from app.config import get_settings
from app.db.models import RequestLog
from app.db.schemas import TelemetryPayload
from app.db.session import AsyncSessionLocal
from app.services.llm_router import estimate_cost, COST_PER_1K, _strip_provider_prefix

logger = logging.getLogger(__name__)


async def log_request(payload: TelemetryPayload) -> None:
    """
    Persists one request log row to PostgreSQL.
    Safe to call from a BackgroundTasks instance — does not require
    the request's own DB session to still be open.

    Failure behaviour:
      - If Postgres is not running: AsyncSessionLocal() raises on connect;
        caught here, printed to terminal, server continues unaffected.
      - If the INSERT fails (constraint, schema mismatch, etc.): caught here,
        rolled back, printed to terminal, server continues unaffected.
    """
    try:
        _settings = get_settings()

        # Compression savings: tokens saved × input price of the model actually used.
        # Only non-zero when prompt was actually compressed (flag was on and threshold met).
        if payload.compression_compressed and payload.original_tokens and payload.compressed_tokens:
            _clean = _strip_provider_prefix(payload.model_used)
            _rate = COST_PER_1K.get(_clean, {"input": 0.001})["input"]
            compression_savings_usd = (
                (payload.original_tokens - payload.compressed_tokens) / 1000 * _rate
            )
        else:
            compression_savings_usd = 0.0

        # Routing savings: what the premium model would have cost vs. what was paid.
        # When routing is disabled model_used == premium_model so savings == 0.
        #
        # Cache hits are a special case: no LLM was called at all, so actual
        # cost is a true zero — NOT estimate_cost("cache", ...), which would
        # silently fall through to the unknown-model fallback rate ($0.001/
        # $0.002 per 1K) and understate the real savings. The premium-model
        # cost is still computed normally, using the real token counts of the
        # cached prompt/response (see proxy.py) — that's the dollar amount
        # actually avoided by serving from cache instead of calling the LLM.
        premium_cost_usd = estimate_cost(
            _settings.premium_model, payload.prompt_tokens, payload.completion_tokens
        )
        if payload.was_cached:
            actual_cost_usd = 0.0
        else:
            actual_cost_usd = estimate_cost(
                payload.model_used, payload.prompt_tokens, payload.completion_tokens
            )
        total_savings_usd = premium_cost_usd - actual_cost_usd

        async with AsyncSessionLocal() as session:
            row = RequestLog(
                user_id=payload.user_id,
                api_key_prefix=payload.api_key_prefix,
                request_id=payload.request_id,
                model_requested=payload.model_requested,
                model_used=payload.model_used,
                was_cached=payload.was_cached,
                was_fallback=payload.was_fallback,
                prompt_tokens=payload.prompt_tokens,
                completion_tokens=payload.completion_tokens,
                total_tokens=payload.total_tokens,
                estimated_cost_usd=payload.estimated_cost_usd,
                ttft_ms=payload.ttft_ms,
                total_latency_ms=payload.total_latency_ms,
                input_guardrail_action=payload.input_guardrail_action,
                output_guardrail_action=payload.output_guardrail_action,
                guardrail_reason=payload.guardrail_reason,
                status_code=payload.status_code,
                error_message=payload.error_message,
                # Phase 4: savings columns
                original_tokens=payload.original_tokens,
                compressed_tokens=payload.compressed_tokens,
                compression_savings_usd=compression_savings_usd,
                routing_tier=payload.routing_tier,
                routing_reason=payload.routing_reason,
                premium_cost_usd=premium_cost_usd,
                actual_cost_usd=actual_cost_usd,
                total_savings_usd=total_savings_usd,
            )
            session.add(row)
            await session.commit()
    except Exception as exc:
        # Telemetry failures must never crash the main server flow.
        # When Postgres is not yet running this will fire on every request —
        # that is expected behaviour during local development pre-Docker.
        # In production, route this to a dead-letter queue or Sentry.
        logger.error("[TELEMETRY ERROR] Failed to log request %s: %s", payload.request_id, exc)