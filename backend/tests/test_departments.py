import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_department(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/departments/",
        json={"name": "Police Department", "code": "PD", "contact_email": "pd@city.gov"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Police Department"
    assert data["code"] == "PD"
    assert data["contact_email"] == "pd@city.gov"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_department_requires_admin(client: AsyncClient, staff_token: str):
    resp = await client.post(
        "/departments/",
        json={"name": "Finance", "code": "FIN"},
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_department_duplicate_code(client: AsyncClient, admin_token: str):
    await client.post(
        "/departments/",
        json={"name": "Police", "code": "PD"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = await client.post(
        "/departments/",
        json={"name": "Public Defense", "code": "PD"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_departments(client: AsyncClient, admin_token: str, staff_token: str):
    await client.post(
        "/departments/",
        json={"name": "Police", "code": "PD"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    await client.post(
        "/departments/",
        json={"name": "Finance", "code": "FIN"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = await client.get(
        "/departments/",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_update_department(client: AsyncClient, admin_token: str):
    create = await client.post(
        "/departments/",
        json={"name": "Police", "code": "PD"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    dept_id = create.json()["id"]
    resp = await client.patch(
        f"/departments/{dept_id}",
        json={"name": "Police Department (Updated)"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Police Department (Updated)"


@pytest.mark.asyncio
async def test_delete_empty_department(client: AsyncClient, admin_token: str):
    create = await client.post(
        "/departments/",
        json={"name": "Temp Dept", "code": "TMP"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    dept_id = create.json()["id"]
    resp = await client.delete(
        f"/departments/{dept_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_department_with_users_fails(
    client: AsyncClient, admin_token: str, staff_token_dept_a: str, dept_a
):
    resp = await client.delete(
        f"/departments/{dept_a}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 409
    assert "assigned users" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_department_crud_creates_audit_log(client: AsyncClient, admin_token: str):
    await client.post(
        "/departments/",
        json={"name": "Audit Test Dept", "code": "AUD"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = await client.get(
        "/admin/status",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.json()["audit_log_count"] > 0
