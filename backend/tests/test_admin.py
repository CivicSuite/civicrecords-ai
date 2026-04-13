import pytest
from httpx import AsyncClient

from app.config import APP_VERSION


@pytest.mark.asyncio
async def test_admin_status_returns_system_info(client: AsyncClient, admin_token: str):
    resp = await client.get(
        "/admin/status",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == APP_VERSION
    assert data["database"] == "connected"
    assert isinstance(data["user_count"], int)
    assert isinstance(data["audit_log_count"], int)


@pytest.mark.asyncio
async def test_admin_status_requires_admin(client: AsyncClient, staff_token: str):
    resp = await client.get(
        "/admin/status",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_models_endpoint(client: AsyncClient, admin_token: str):
    resp = await client.get(
        "/admin/models",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "models" in data
