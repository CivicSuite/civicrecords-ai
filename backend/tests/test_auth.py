import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_user(client: AsyncClient):
    resp = await client.post(
        "/auth/register",
        json={
            "email": f"test-{uuid.uuid4().hex[:8]}@example.com",
            "password": "securepassword123",
            "full_name": "Jane Clerk",
            "role": "staff",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["full_name"] == "Jane Clerk"
    assert data["role"] == "staff"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_login_returns_jwt(client: AsyncClient):
    email = f"login-{uuid.uuid4().hex[:8]}@example.com"
    await client.post(
        "/auth/register",
        json={"email": email, "password": "testpass123", "full_name": "Test"},
    )
    resp = await client.post(
        "/auth/jwt/login",
        data={"username": email, "password": "testpass123"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_me_endpoint(client: AsyncClient):
    email = f"me-{uuid.uuid4().hex[:8]}@example.com"
    await client.post(
        "/auth/register",
        json={"email": email, "password": "testpass123", "full_name": "Me User", "role": "reviewer"},
    )
    login = await client.post(
        "/auth/jwt/login",
        data={"username": email, "password": "testpass123"},
    )
    token = login.json()["access_token"]
    resp = await client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == email
    assert resp.json()["role"] == "reviewer"


@pytest.mark.asyncio
async def test_unauthenticated_rejected(client: AsyncClient):
    resp = await client.get("/users/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_role_enforcement_rejects_insufficient_role(client: AsyncClient, staff_token: str):
    """Staff user should get 403 on admin-only endpoints."""
    # The /users endpoint (listing all users) requires is_superuser in fastapi-users
    resp = await client.get(
        "/users",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    # fastapi-users returns 403 for non-superuser accessing user list
    assert resp.status_code == 403
