import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_accuracy_endpoint_empty(client: AsyncClient, admin_token: str):
    resp = await client.get(
        "/exemptions/dashboard/accuracy",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_export_json(client: AsyncClient, admin_token: str):
    resp = await client.get(
        "/exemptions/dashboard/export?format=json",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_export_csv(client: AsyncClient, admin_token: str):
    resp = await client.get(
        "/exemptions/dashboard/export?format=csv",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_dashboard_accuracy_requires_admin(client: AsyncClient, staff_token: str):
    resp = await client.get(
        "/exemptions/dashboard/accuracy",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert resp.status_code == 403
