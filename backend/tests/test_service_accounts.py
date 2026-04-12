import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_service_account(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/service-accounts/",
        json={"name": "county-federation", "role": "read_only"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "county-federation"
    assert data["role"] == "read_only"
    assert data["api_key"].startswith("cr_")
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_create_service_account_requires_admin(client: AsyncClient, staff_token: str):
    resp = await client.post(
        "/service-accounts/",
        json={"name": "test-account", "role": "read_only"},
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_service_accounts(client: AsyncClient, admin_token: str):
    await client.post(
        "/service-accounts/",
        json={"name": "list-test-account", "role": "staff"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = await client.get(
        "/service-accounts/",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_deactivate_service_account(client: AsyncClient, admin_token: str):
    create = await client.post(
        "/service-accounts/",
        json={"name": "deactivate-test", "role": "read_only"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    account_id = create.json()["id"]

    resp = await client.patch(
        f"/service-accounts/{account_id}",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False
