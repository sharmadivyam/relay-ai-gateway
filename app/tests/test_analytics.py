"""
Tests for GET /v1/analytics/* endpoints.

Uses the shared `client` fixture from conftest.py which provides an in-memory
SQLite database and a real FastAPI test client (no actual LLM calls needed).
"""
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RequestLog, User, UserTier
from app.db.session import get_db
from app.main import app


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

async def _create_user_and_token(client) -> tuple[str, str]:
    """Register a user, log in, return (user_id_str, jwt_token)."""
    email = f"analytics_{uuid.uuid4().hex[:8]}@test.local"
    pw = "testpass123"
    reg = await client.post("/auth/register", json={"email": email, "password": pw})
    assert reg.status_code == 201
    user_id = reg.json()["id"]

    login = await client.post("/auth/login", json={"email": email, "password": pw})
    assert login.status_code == 200
    token = login.json()["access_token"]
    return user_id, token


async def _seed_log(client, user_id: str, **kwargs) -> None:
    """Insert a RequestLog row directly into the test DB via the dependency override."""
    # Use the app's overridden get_db so we write to the same in-memory DB
    async for session in app.dependency_overrides[get_db]():
        row = RequestLog(
            user_id=uuid.UUID(user_id),
            model_requested="gpt-4o-mini",
            model_used=kwargs.get("model_used", "gpt-4o-mini"),
            was_cached=kwargs.get("was_cached", False),
            was_fallback=False,
            prompt_tokens=kwargs.get("prompt_tokens", 10),
            completion_tokens=kwargs.get("completion_tokens", 20),
            total_tokens=kwargs.get("total_tokens", 30),
            estimated_cost_usd=kwargs.get("estimated_cost_usd", 0.001),
            total_latency_ms=kwargs.get("total_latency_ms", 150.0),
            total_savings_usd=kwargs.get("total_savings_usd", 0.0),
            compression_savings_usd=kwargs.get("compression_savings_usd", 0.0),
            routing_tier=kwargs.get("routing_tier", "simple"),
            status_code=200,
            created_at=kwargs.get("created_at", datetime.now(timezone.utc)),
        )
        session.add(row)
        await session.commit()
        break


# ──────────────────────────────────────────────
# /v1/analytics/overview
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_overview_unauthenticated(client):
    resp = await client.get("/v1/analytics/overview")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_overview_empty(client):
    """Overview returns zeroes when there are no request_logs yet."""
    _, token = await _create_user_and_token(client)
    resp = await client.get(
        "/v1/analytics/overview",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_requests"] == 0
    assert data["total_savings_usd"] == 0.0
    assert data["cache_hit_rate"] == 0.0
    assert data["avg_latency_ms"] == 0.0
    assert data["total_tokens"] == 0


@pytest.mark.asyncio
async def test_overview_with_data(client):
    """Overview aggregates correctly over multiple logs."""
    user_id, token = await _create_user_and_token(client)

    await _seed_log(client, user_id, total_tokens=100, total_latency_ms=200.0,
                    was_cached=False, total_savings_usd=0.01, compression_savings_usd=0.005)
    await _seed_log(client, user_id, total_tokens=200, total_latency_ms=400.0,
                    was_cached=True, total_savings_usd=0.0, compression_savings_usd=0.0)

    resp = await client.get(
        "/v1/analytics/overview",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_requests"] == 2
    assert data["total_tokens"] == 300
    assert data["cache_hit_rate"] == 0.5
    # avg of 200 and 400 = 300
    assert abs(data["avg_latency_ms"] - 300.0) < 0.01
    # total savings = 0.01 + 0.005 + 0.0 + 0.0 = 0.015
    assert abs(data["total_savings_usd"] - 0.015) < 1e-6


@pytest.mark.asyncio
async def test_overview_scoped_to_user(client):
    """Users see only their own data — another user's logs are invisible."""
    user_id_a, token_a = await _create_user_and_token(client)
    user_id_b, token_b = await _create_user_and_token(client)

    # Seed 3 rows for user A, 1 for user B
    for _ in range(3):
        await _seed_log(client, user_id_a, total_tokens=50)
    await _seed_log(client, user_id_b, total_tokens=999)

    resp_a = await client.get(
        "/v1/analytics/overview", headers={"Authorization": f"Bearer {token_a}"}
    )
    resp_b = await client.get(
        "/v1/analytics/overview", headers={"Authorization": f"Bearer {token_b}"}
    )

    assert resp_a.json()["total_requests"] == 3
    assert resp_b.json()["total_requests"] == 1
    assert resp_b.json()["total_tokens"] == 999


# ──────────────────────────────────────────────
# /v1/analytics/requests
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_requests_unauthenticated(client):
    resp = await client.get("/v1/analytics/requests")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_requests_empty(client):
    _, token = await _create_user_and_token(client)
    resp = await client.get(
        "/v1/analytics/requests",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_requests_returns_list(client):
    user_id, token = await _create_user_and_token(client)
    await _seed_log(client, user_id, model_used="gpt-4o-mini", routing_tier="simple")
    await _seed_log(client, user_id, model_used="gpt-4o", routing_tier="complex", was_cached=True)

    resp = await client.get(
        "/v1/analytics/requests",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    # newest first
    entry = data[0]
    assert "id" in entry
    assert "created_at" in entry
    assert "model_used" in entry
    assert "was_cached" in entry
    assert "routing_tier" in entry


@pytest.mark.asyncio
async def test_requests_limit_param(client):
    user_id, token = await _create_user_and_token(client)
    for i in range(10):
        await _seed_log(client, user_id)

    resp = await client.get(
        "/v1/analytics/requests?limit=3",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 3


@pytest.mark.asyncio
async def test_requests_scoped_to_user(client):
    user_id_a, token_a = await _create_user_and_token(client)
    user_id_b, _ = await _create_user_and_token(client)

    await _seed_log(client, user_id_a)
    await _seed_log(client, user_id_b)
    await _seed_log(client, user_id_b)

    resp = await client.get(
        "/v1/analytics/requests",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert len(resp.json()) == 1


# ──────────────────────────────────────────────
# /v1/analytics/savings-timeseries
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_timeseries_unauthenticated(client):
    resp = await client.get("/v1/analytics/savings-timeseries")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_timeseries_empty(client):
    _, token = await _create_user_and_token(client)
    resp = await client.get(
        "/v1/analytics/savings-timeseries?days=7",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_timeseries_groups_by_day(client):
    user_id, token = await _create_user_and_token(client)

    today = datetime.now(timezone.utc)
    await _seed_log(client, user_id,
                    compression_savings_usd=0.01, total_savings_usd=0.02,
                    created_at=today)
    await _seed_log(client, user_id,
                    compression_savings_usd=0.03, total_savings_usd=0.04,
                    created_at=today)

    resp = await client.get(
        "/v1/analytics/savings-timeseries?days=1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    day = data[0]
    assert "date" in day
    assert abs(day["compression_savings_usd"] - 0.04) < 1e-6
    assert abs(day["routing_savings_usd"] - 0.06) < 1e-6


@pytest.mark.asyncio
async def test_timeseries_scoped_to_user(client):
    user_id_a, token_a = await _create_user_and_token(client)
    user_id_b, _ = await _create_user_and_token(client)

    today = datetime.now(timezone.utc)
    await _seed_log(client, user_id_a, compression_savings_usd=0.5, total_savings_usd=1.0,
                    created_at=today)
    # User B's data must not bleed into user A's response
    await _seed_log(client, user_id_b, compression_savings_usd=99.0, total_savings_usd=99.0,
                    created_at=today)

    resp = await client.get(
        "/v1/analytics/savings-timeseries?days=1",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    data = resp.json()
    assert len(data) == 1
    assert abs(data[0]["compression_savings_usd"] - 0.5) < 1e-6
