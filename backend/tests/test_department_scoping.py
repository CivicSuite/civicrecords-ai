import uuid
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_staff_lists_own_department_requests_only(
    client: AsyncClient, admin_token: str,
    staff_token_dept_a: str, staff_token_dept_b: str,
    dept_a: uuid.UUID, dept_b: uuid.UUID,
):
    await client.post(
        "/requests/",
        json={"requester_name": "Alice", "description": "Dept A request"},
        headers={"Authorization": f"Bearer {staff_token_dept_a}"},
    )
    await client.post(
        "/requests/",
        json={"requester_name": "Bob", "description": "Dept B request"},
        headers={"Authorization": f"Bearer {staff_token_dept_b}"},
    )
    resp = await client.get(
        "/requests/",
        headers={"Authorization": f"Bearer {staff_token_dept_a}"},
    )
    assert resp.status_code == 200
    requests = resp.json()
    assert len(requests) == 1
    assert requests[0]["description"] == "Dept A request"


@pytest.mark.asyncio
async def test_admin_sees_all_departments(
    client: AsyncClient, admin_token: str,
    staff_token_dept_a: str, staff_token_dept_b: str,
):
    await client.post(
        "/requests/",
        json={"requester_name": "Alice", "description": "Dept A"},
        headers={"Authorization": f"Bearer {staff_token_dept_a}"},
    )
    await client.post(
        "/requests/",
        json={"requester_name": "Bob", "description": "Dept B"},
        headers={"Authorization": f"Bearer {staff_token_dept_b}"},
    )
    resp = await client.get(
        "/requests/",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_staff_gets_request_in_own_department(
    client: AsyncClient, staff_token_dept_a: str,
):
    create = await client.post(
        "/requests/",
        json={"requester_name": "Alice", "description": "My dept"},
        headers={"Authorization": f"Bearer {staff_token_dept_a}"},
    )
    req_id = create.json()["id"]
    resp = await client.get(
        f"/requests/{req_id}",
        headers={"Authorization": f"Bearer {staff_token_dept_a}"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_staff_gets_request_in_other_department_403(
    client: AsyncClient,
    staff_token_dept_a: str, staff_token_dept_b: str,
):
    create = await client.post(
        "/requests/",
        json={"requester_name": "Bob", "description": "Dept B"},
        headers={"Authorization": f"Bearer {staff_token_dept_b}"},
    )
    req_id = create.json()["id"]
    resp = await client.get(
        f"/requests/{req_id}",
        headers={"Authorization": f"Bearer {staff_token_dept_a}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_request_auto_sets_department_from_user(
    client: AsyncClient, staff_token_dept_a: str, dept_a: uuid.UUID,
):
    resp = await client.post(
        "/requests/",
        json={"requester_name": "Alice", "description": "Auto dept"},
        headers={"Authorization": f"Bearer {staff_token_dept_a}"},
    )
    assert resp.status_code == 201
    assert resp.json()["department_id"] == str(dept_a)


@pytest.mark.asyncio
async def test_admin_can_specify_any_department(
    client: AsyncClient, admin_token: str, dept_b: uuid.UUID,
):
    resp = await client.post(
        "/requests/",
        json={
            "requester_name": "Admin Request",
            "description": "Cross-dept",
            "department_id": str(dept_b),
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["department_id"] == str(dept_b)


@pytest.mark.asyncio
async def test_reviewer_approves_own_department(
    client: AsyncClient,
    staff_token_dept_a: str, reviewer_token_dept_a: str,
):
    create = await client.post(
        "/requests/",
        json={"requester_name": "Alice", "description": "Review me"},
        headers={"Authorization": f"Bearer {staff_token_dept_a}"},
    )
    req_id = create.json()["id"]
    await client.patch(
        f"/requests/{req_id}",
        json={"status": "searching"},
        headers={"Authorization": f"Bearer {staff_token_dept_a}"},
    )
    await client.post(
        f"/requests/{req_id}/submit-review",
        headers={"Authorization": f"Bearer {staff_token_dept_a}"},
    )
    resp = await client.post(
        f"/requests/{req_id}/ready-for-release",
        headers={"Authorization": f"Bearer {reviewer_token_dept_a}"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_reviewer_cannot_approve_other_department(
    client: AsyncClient,
    staff_token_dept_b: str, reviewer_token_dept_a: str,
):
    create = await client.post(
        "/requests/",
        json={"requester_name": "Bob", "description": "Other dept"},
        headers={"Authorization": f"Bearer {staff_token_dept_b}"},
    )
    req_id = create.json()["id"]
    await client.patch(
        f"/requests/{req_id}",
        json={"status": "searching"},
        headers={"Authorization": f"Bearer {staff_token_dept_b}"},
    )
    await client.post(
        f"/requests/{req_id}/submit-review",
        headers={"Authorization": f"Bearer {staff_token_dept_b}"},
    )
    resp = await client.post(
        f"/requests/{req_id}/ready-for-release",
        headers={"Authorization": f"Bearer {reviewer_token_dept_a}"},
    )
    assert resp.status_code == 403
