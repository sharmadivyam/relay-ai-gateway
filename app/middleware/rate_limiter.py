"""
Redis-based token-per-minute (TPM) rate limiter with in-memory fallback.

WORK LAPTOP NOTE (see MIGRATION_GUIDE.md):
  Redis is not running (no Docker). get_redis_client() detects this and yields
  None. check_rate_limit() falls back to an in-memory dict-based counter that
  is correct for a single-process dev server.

  In-memory counter limitations (acceptable for local dev only):
    - Not persistent across server restarts
    - Not shared across multiple uvicorn workers
    - No atomic guarantee (single-process, so no race conditions in practice)

  On personal laptop: docker compose up -d redis — the Redis pipeline path
  re-activates automatically with zero code changes.

Production path (Redis available):
  Sliding-window counter keyed by user_id + current minute bucket.
  Key format: ratelimit:{user_id}:{minute_epoch}
  TTL: 90 seconds (covers current + previous minute).
"""
import time
from typing import Optional

from fastapi import HTTPException, status
from redis.asyncio import Redis

from app.config import get_settings
from app.db.models import UserTier

settings = get_settings()

TIER_LIMITS: dict[UserTier, int] = {
    UserTier.free:       settings.rate_limit_free,
    UserTier.pro:        settings.rate_limit_pro,
    UserTier.enterprise: settings.rate_limit_enterprise,
}

# ── In-memory fallback counter ─────────────────────────────────────────────
# Keys: "{user_id}:{minute_bucket}" — the minute bucket is baked into the key
# so stale entries from previous minutes are naturally ignored without cleanup.
# MIGRATION NOTE: remove this dict on personal laptop (Redis handles state).
_memory_counters: dict[str, int] = {}


def _memory_check(user_id: str, tier: UserTier, tokens_requested: int) -> None:
    """
    In-memory rate limit check — used when Redis is unavailable.
    Raises HTTP 429 if the user has exceeded their TPM for the current minute.
    """
    limit = TIER_LIMITS.get(tier, settings.rate_limit_free)
    minute_bucket = int(time.time()) // 60
    key = f"{user_id}:{minute_bucket}"

    current = _memory_counters.get(key, 0) + tokens_requested
    _memory_counters[key] = current

    if current > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "rate_limit_exceeded",
                "message": (
                    f"TPM limit of {limit:,} exceeded for tier '{tier}'. "
                    f"Current usage: {current:,}. [in-memory limiter]"
                ),
                "retry_after_seconds": 60 - (int(time.time()) % 60),
            },
        )


# ── Shared entry point ─────────────────────────────────────────────────────

async def check_rate_limit(
    redis: Optional[Redis],
    user_id: str,
    tier: UserTier,
    tokens_requested: int,
) -> None:
    """
    Raises HTTP 429 if the user has exceeded their TPM.
    Uses Redis pipeline when available; falls back to in-memory when redis=None.
    proxy.py calls this identically regardless of which backend is active.
    """
    if redis is None:
        _memory_check(user_id, tier, tokens_requested)
        return

    # ── Redis path (production) ────────────────────────────────────────────
    limit = TIER_LIMITS.get(tier, settings.rate_limit_free)
    minute_bucket = int(time.time()) // 60
    key = f"ratelimit:{user_id}:{minute_bucket}"

    pipe = redis.pipeline()
    pipe.incrby(key, tokens_requested)
    pipe.expire(key, 90)
    results = await pipe.execute()
    current_count: int = results[0]

    if current_count > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "rate_limit_exceeded",
                "message": (
                    f"TPM limit of {limit:,} exceeded for tier '{tier}'. "
                    f"Current usage: {current_count:,}."
                ),
                "retry_after_seconds": 60 - (int(time.time()) % 60),
            },
        )


async def get_redis_client() -> Optional[Redis]:
    """
    FastAPI dependency. Yields a live Redis client when Redis is reachable,
    or None when it is not — proxy.py passes whatever it receives straight
    into check_rate_limit(), so it never needs to know which path is active.
    """
    client = Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=1,
        socket_timeout=1,
    )
    try:
        await client.ping()
        # Redis is up — yield real client
        try:
            yield client
        finally:
            await client.aclose()
    except Exception:
        # Redis is down — yield None, in-memory fallback will be used
        await client.aclose()
        yield None
