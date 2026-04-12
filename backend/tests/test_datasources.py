import uuid
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_datasource(client: AsyncClient, admin_token: str):
    resp = await client.post("/datasources/", json={"name": f"test-source-{uuid.uuid4().hex[:8]}", "source_type": "directory", "connection_config": {"path": "/data/test"}}, headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["source_type"] == "directory"
    assert data["is_active"] is True

@pytest.mark.asyncio
async def test_create_datasource_requires_admin(client: AsyncClient, staff_token: str):
    resp = await client.post("/datasources/", json={"name": "test", "source_type": "upload"}, headers={"Authorization": f"Bearer {staff_token}"})
    assert resp.status_code == 403

@pytest.mark.asyncio
async def test_list_datasources(client: AsyncClient, admin_token: str):
    await client.post("/datasources/", json={"name": f"list-test-{uuid.uuid4().hex[:8]}", "source_type": "upload"}, headers={"Authorization": f"Bearer {admin_token}"})
    resp = await client.get("/datasources/", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert len(resp.json()) >= 1

@pytest.mark.asyncio
async def test_ingestion_stats(client: AsyncClient, admin_token: str):
    resp = await client.get("/datasources/stats", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "total_sources" in data
    assert "total_documents" in data
    assert "total_chunks" in data
