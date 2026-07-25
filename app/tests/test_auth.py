"""Phase 1 tests — auth endpoints."""
import pytest
from app.main import app


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_register_and_login(client):
    payload = {"email": "test@gateway.ai", "password": "hunter2"}

    # Register
    resp = await client.post("/auth/register", json=payload)
    assert resp.status_code == 201
    assert resp.json()["email"] == payload["email"]

    # Login
    resp = await client.post("/auth/login", json=payload)
    assert resp.status_code == 200
    token_data = resp.json()
    assert "access_token" in token_data

    return token_data["access_token"]


@pytest.mark.asyncio
async def test_create_api_key(client):
    # Register + login first
    payload = {"email": "keytest@gateway.ai", "password": "securepass"}
    await client.post("/auth/register", json=payload)
    login_resp = await client.post("/auth/login", json=payload)
    token = login_resp.json()["access_token"]

    # Create API key
    resp = await client.post(
        "/auth/keys",
        json={"label": "my test key"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["raw_key"].startswith("sk-gw_")
    assert data["label"] == "my test key"


@pytest.mark.asyncio
async def test_unauthenticated_proxy(client):
    resp = await client.post("/v1/chat/completions", json={
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "hello"}],
    })
    assert resp.status_code == 401  # 401 = no credentials; 403 = wrong credentials
