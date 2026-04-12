import uuid
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_request(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/requests/",
        json={
            "requester_name": "John Doe",
            "requester_email": "john@example.gov",
            "description": "Request for water quality reports from 2025",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["requester_name"] == "John Doe"
    assert data["status"] == "received"
    assert data["id"] is not None


@pytest.mark.asyncio
async def test_list_requests(client: AsyncClient, admin_token: str):
    await client.post(
        "/requests/",
        json={"requester_name": "List Test", "description": "Test request"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = await client.get("/requests/", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_get_request(client: AsyncClient, admin_token: str):
    create = await client.post(
        "/requests/",
        json={"requester_name": "Get Test", "description": "Test"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    req_id = create.json()["id"]
    resp = await client.get(f"/requests/{req_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert resp.json()["requester_name"] == "Get Test"


@pytest.mark.asyncio
async def test_request_not_found(client: AsyncClient, admin_token: str):
    resp = await client.get(f"/requests/{uuid.uuid4()}", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_status_transition_valid(client: AsyncClient, admin_token: str):
    create = await client.post(
        "/requests/",
        json={"requester_name": "Workflow Test", "description": "Test workflow"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    req_id = create.json()["id"]

    # received -> searching
    resp = await client.patch(
        f"/requests/{req_id}",
        json={"status": "searching"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "searching"


@pytest.mark.asyncio
async def test_status_transition_invalid(client: AsyncClient, admin_token: str):
    create = await client.post(
        "/requests/",
        json={"requester_name": "Invalid Test", "description": "Test"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    req_id = create.json()["id"]

    # received -> approved (skip steps — should fail)
    resp = await client.patch(
        f"/requests/{req_id}",
        json={"status": "approved"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_submit_for_review(client: AsyncClient, admin_token: str):
    create = await client.post(
        "/requests/",
        json={"requester_name": "Review Test", "description": "Test"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    req_id = create.json()["id"]

    # Move to searching first
    await client.patch(f"/requests/{req_id}", json={"status": "searching"}, headers={"Authorization": f"Bearer {admin_token}"})

    # Submit for review
    resp = await client.post(f"/requests/{req_id}/submit-review", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_review"


@pytest.mark.asyncio
async def test_request_stats(client: AsyncClient, admin_token: str):
    resp = await client.get("/requests/stats", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "total_requests" in data
    assert "by_status" in data
    assert "approaching_deadline" in data
    assert "overdue" in data


@pytest.mark.asyncio
async def test_request_requires_auth(client: AsyncClient):
    resp = await client.post("/requests/", json={"requester_name": "Test", "description": "Test"})
    assert resp.status_code == 401
