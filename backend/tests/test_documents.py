import uuid
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_list_documents_empty(client: AsyncClient, admin_token: str):
    resp = await client.get("/documents/", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert resp.json() == []

@pytest.mark.asyncio
async def test_get_document_not_found(client: AsyncClient, admin_token: str):
    resp = await client.get(f"/documents/{uuid.uuid4()}", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 404
