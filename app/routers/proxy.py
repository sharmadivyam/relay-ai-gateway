"""
/v1/chat/completions — the main proxy endpoint.

Orchestrates the full 6-step gateway lifecycle:
  1. Auth + Rate Limit   (middleware/auth + middleware/rate_limiter)
  2. Input Guardrails    (services/guardrails_in)
  3. Semantic Cache      (services/cache)
  4. LLM Execution       (services/llm_router)
  5. Output Guardrails   (services/guardrails_out)
  6. Async Telemetry     (services/telemetry)
"""
import time
import uuid
import tiktoken
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis

from app.config import get_settings
from app.db.schemas import (
    ChatCompletionRequest, ChatCompletionResponse,
    ChatCompletionChoice, ChatMessage, UsageInfo, TelemetryPayload,
)
from app.middleware.auth import AuthenticatedCaller, get_current_caller
from app.middleware.rate_limiter import check_rate_limit, get_redis_client
from app.services.cache import semantic_cache
from app.services.guardrails_in import scan_input
from app.services.guardrails_out import scan_output
from app.services.llm_router import call_llm, stream_llm
from app.services.prompt_compressor import maybe_compress
from app.services.smart_router import route
from app.services.telemetry import log_request

settings = get_settings()

router = APIRouter(prefix="/v1", tags=["proxy"])


def extract_prompt_text(messages) -> str:
    """Join all user message contents into a single string for routing/compression."""
    return " ".join(m.content or "" for m in messages if m.role == "user")


def count_tokens(messages) -> int:
    """Count tokens across all messages using cl100k_base (GPT-4 tokenizer)."""
    enc = tiktoken.get_encoding("cl100k_base")
    return sum(len(enc.encode(m.content or "")) for m in messages)


@router.post("/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(
    request: ChatCompletionRequest,
    background_tasks: BackgroundTasks,
    caller: AuthenticatedCaller = Depends(get_current_caller),
    redis: Redis = Depends(get_redis_client),
):
    t_start = time.perf_counter()

    # Generate one correlation ID up-front so every code path (blocked,
    # cached, error, success) shares the same ID in both the HTTP response
    # and the telemetry DB row — makes Superset debugging traceable.
    response_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"

    # ── 1. Rate Limiting ───────────────────────────────────────────────────
    estimated_tokens = (request.max_tokens or 1000)
    await check_rate_limit(redis, str(caller.user.id), caller.tier, estimated_tokens)

    # ── 2. Input Guardrails ────────────────────────────────────────────────
    messages_raw = [m.model_dump(exclude_none=True) for m in request.messages]
    input_result = await scan_input(messages_raw)

    if input_result.action == "blocked":
        # NOTE: background_tasks.add_task() only fires if it's attached to
        # the Response that actually gets returned. raise HTTPException makes
        # Starlette build a brand-new error response instead — this
        # background_tasks object (and anything queued on it) is discarded,
        # not delayed. So for any path that raises rather than returns, we
        # must await log_request() directly instead.
        await log_request(
            TelemetryPayload(
                user_id=caller.user.id,
                api_key_prefix=caller.api_key_prefix,
                request_id=response_id,
                model_requested=request.model,
                model_used="BLOCKED",
                was_cached=False, was_fallback=False,
                prompt_tokens=0, completion_tokens=0, total_tokens=0,
                estimated_cost_usd=0.0,
                ttft_ms=None,
                total_latency_ms=(time.perf_counter() - t_start) * 1000,
                input_guardrail_action="blocked",
                output_guardrail_action="passed",
                guardrail_reason=input_result.reason,
                status_code=403,
                error_message=input_result.reason,
            ),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "input_blocked", "reason": input_result.reason},
        )

    # ── 3. Semantic Cache ──────────────────────────────────────────────────
    prompt_text = extract_prompt_text(request.messages)
    cached_response = await semantic_cache.lookup(prompt_text)

    if cached_response is not None:
        latency_ms = (time.perf_counter() - t_start) * 1000

        # Real token counts, not hardcoded zeros — this is what lets
        # telemetry.py attribute a real dollar figure to this cache hit
        # (what the premium model would have cost for this exact prompt/
        # response size) instead of recording $0 saved on every cache hit.
        enc = tiktoken.get_encoding("cl100k_base")
        cache_prompt_tokens = len(enc.encode(prompt_text))
        cache_completion_tokens = len(enc.encode(cached_response))

        background_tasks.add_task(
            log_request,
            TelemetryPayload(
                user_id=caller.user.id,
                api_key_prefix=caller.api_key_prefix,
                request_id=response_id,
                model_requested=request.model, model_used="cache",
                was_cached=True, was_fallback=False,
                prompt_tokens=cache_prompt_tokens,
                completion_tokens=cache_completion_tokens,
                total_tokens=cache_prompt_tokens + cache_completion_tokens,
                estimated_cost_usd=0.0,
                ttft_ms=latency_ms, total_latency_ms=latency_ms,
                input_guardrail_action="passed", output_guardrail_action="passed",
                guardrail_reason=None, status_code=200, error_message=None,
            ),
        )
        return ChatCompletionResponse(
            id=response_id,
            model=request.model,
            choices=[ChatCompletionChoice(
                index=0,
                message=ChatMessage(role="assistant", content=cached_response),
                finish_reason="cache_hit",
            )],
            usage=UsageInfo(
                prompt_tokens=cache_prompt_tokens,
                completion_tokens=cache_completion_tokens,
                total_tokens=cache_prompt_tokens + cache_completion_tokens,
            ),
            gateway_cached=True,
        )

    # ── 3.5 Compression + Smart Routing (flags-gated) ─────────────────────
    # With both flags False these blocks are skipped entirely and model_for_llm
    # equals request.model — so the LLM call is byte-for-byte unchanged.
    token_count = count_tokens(request.messages)

    compression_result = {
        "prompt": prompt_text,
        "compressed": False,
        "original_tokens": token_count,
        "final_tokens": token_count,
    }
    if settings.enable_prompt_compression:
        compression_result = maybe_compress(
            prompt_text, token_count, settings.compression_threshold_tokens
        )

    routing_result = {
        "model": request.model,
        "tier": "n/a",
        "reason": "routing_disabled",
    }
    if settings.enable_smart_routing:
        routing_result = route(
            compression_result["prompt"], compression_result["final_tokens"]
        )

    model_for_llm = routing_result["model"]

    # ── 4. LLM Execution ──────────────────────────────────────────────────
    if request.stream:
        return StreamingResponse(
            _stream_response(request),
            media_type="text/event-stream",
        )

    try:
        llm_result = await call_llm(request, model_override=model_for_llm)
    except Exception as exc:
        # Same reasoning as the blocked-path fix above: this branch raises,
        # so background_tasks.add_task() here would be silently discarded.
        await log_request(
            TelemetryPayload(
                user_id=caller.user.id,
                api_key_prefix=caller.api_key_prefix,
                request_id=response_id,
                model_requested=request.model, model_used="error",
                was_cached=False, was_fallback=False,
                prompt_tokens=0, completion_tokens=0, total_tokens=0,
                estimated_cost_usd=0.0, ttft_ms=None,
                total_latency_ms=(time.perf_counter() - t_start) * 1000,
                input_guardrail_action="passed", output_guardrail_action="passed",
                guardrail_reason=None, status_code=502, error_message=str(exc),
            ),
        )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    # ── 5. Output Guardrails ───────────────────────────────────────────────
    output_result = await scan_output(llm_result.content)

    # Store the (possibly redacted) response in cache for future hits
    await semantic_cache.store(prompt_text, output_result.content)

    # ── 6. Async Telemetry ─────────────────────────────────────────────────
    # add_task registers the DB write; FastAPI returns the HTTP response to
    # the client first, then executes background tasks — 0ms added latency.
    background_tasks.add_task(
        log_request,
        TelemetryPayload(
            user_id=caller.user.id,
            api_key_prefix=caller.api_key_prefix,
            request_id=response_id,
            model_requested=request.model,
            model_used=llm_result.model_used,
            was_cached=False,
            was_fallback=llm_result.was_fallback,
            prompt_tokens=llm_result.prompt_tokens,
            completion_tokens=llm_result.completion_tokens,
            total_tokens=llm_result.total_tokens,
            estimated_cost_usd=llm_result.cost_usd,
            ttft_ms=llm_result.ttft_ms,
            total_latency_ms=llm_result.total_latency_ms,
            input_guardrail_action="passed",
            output_guardrail_action=output_result.action,
            guardrail_reason=output_result.reason,
            status_code=200,
            error_message=None,
            # Phase 4: savings logging
            original_tokens=compression_result["original_tokens"],
            compressed_tokens=compression_result["final_tokens"],
            compression_compressed=compression_result["compressed"],
            routing_tier=routing_result["tier"],
            routing_reason=routing_result["reason"],
        ),
    )

    return ChatCompletionResponse(
        id=response_id,
        model=llm_result.model_used,
        choices=[ChatCompletionChoice(
            index=0,
            message=ChatMessage(role="assistant", content=output_result.content),
            finish_reason="stop",
        )],
        usage=UsageInfo(
            prompt_tokens=llm_result.prompt_tokens,
            completion_tokens=llm_result.completion_tokens,
            total_tokens=llm_result.total_tokens,
        ),
        gateway_fallback=llm_result.was_fallback,
    )


async def _stream_response(request: ChatCompletionRequest):
    """SSE generator for streaming mode."""
    async for chunk in stream_llm(request):
        yield f"data: {chunk}\n\n"
    yield "data: [DONE]\n\n"