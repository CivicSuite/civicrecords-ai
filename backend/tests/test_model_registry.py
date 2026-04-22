import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_model(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/admin/models/registry",
        json={
            "model_name": "gemma4:e4b",
            "model_version": "4.0",
            "parameter_count": "4B",
            "license": "Apache 2.0",
            "model_card_url": "https://ai.google.dev/gemma",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["model_name"] == "gemma4:e4b"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_register_model_requires_admin(client: AsyncClient, staff_token: str):
    resp = await client.post(
        "/admin/models/registry",
        json={"model_name": "test"},
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_model_registry(client: AsyncClient, admin_token: str):
    await client.post(
        "/admin/models/registry",
        json={"model_name": "gemma4:e4b"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = await client.get(
        "/admin/models/registry",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_update_model_registry(client: AsyncClient, admin_token: str):
    create = await client.post(
        "/admin/models/registry",
        json={"model_name": "gemma4:e4b"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    model_id = create.json()["id"]
    resp = await client.patch(
        f"/admin/models/registry/{model_id}",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_delete_model_registry(client: AsyncClient, admin_token: str):
    create = await client.post(
        "/admin/models/registry",
        json={"model_name": "delete-me"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    model_id = create.json()["id"]
    resp = await client.delete(
        f"/admin/models/registry/{model_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_existing_models_endpoint_still_works(client: AsyncClient, admin_token: str):
    resp = await client.get(
        "/admin/models",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert "status" in resp.json()
