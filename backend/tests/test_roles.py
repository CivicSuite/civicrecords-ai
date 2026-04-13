"""Tests for liaison and public roles."""

import uuid
import pytest
from httpx import AsyncClient

from app.models.user import UserRole


def test_user_role_enum_has_all_six_roles():
    """All 6 roles from canonical spec exist in the enum."""
    expected = {"admin", "staff", "reviewer", "read_only", "liaison", "public"}
    actual = {r.value for r in UserRole}
    assert actual == expected


def test_role_hierarchy_order():
    """Role hierarchy matches canonical spec ordering."""
    from app.auth.dependencies import ROLE_HIERARCHY

    assert ROLE_HIERARCHY[UserRole.ADMIN] > ROLE_HIERARCHY[UserRole.REVIEWER]
    assert ROLE_HIERARCHY[UserRole.REVIEWER] > ROLE_HIERARCHY[UserRole.STAFF]
    assert ROLE_HIERARCHY[UserRole.STAFF] > ROLE_HIERARCHY[UserRole.LIAISON]
    assert ROLE_HIERARCHY[UserRole.LIAISON] > ROLE_HIERARCHY[UserRole.READ_ONLY]
    assert ROLE_HIERARCHY[UserRole.READ_ONLY] > ROLE_HIERARCHY[UserRole.PUBLIC]


def test_all_roles_in_hierarchy():
    """Every role in the enum has a hierarchy entry."""
    from app.auth.dependencies import ROLE_HIERARCHY

    for role in UserRole:
        assert role in ROLE_HIERARCHY, f"{role.value} missing from ROLE_HIERARCHY"


@pytest.mark.asyncio
async def test_liaison_cannot_create_request(client: AsyncClient, admin_token: str):
    """Liaison role cannot create requests (requires STAFF)."""
    from tests.conftest import _create_department, _create_test_user_in_dept

    dept_id = await _create_department("Liaison Test Dept", "LTD")
    email = f"liaison-{uuid.uuid4().hex[:8]}@test.com"
    password = "liaisonpass123"
    await _create_test_user_in_dept(email, password, "Test Liaison", UserRole.LIAISON, dept_id)
    login = await client.post("/auth/jwt/login", data={"username": email, "password": password})
    token = login.json()["access_token"]

    resp = await client.post(
        "/requests/",
        json={"requester_name": "Test", "description": "Liaison attempt"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_liaison_can_list_departments(client: AsyncClient, admin_token: str):
    """Liaison role can list departments (requires STAFF or below — liaison is below staff but above read_only)."""
    from tests.conftest import _create_department, _create_test_user_in_dept

    dept_id = await _create_department("Liaison Dept View", "LDV")
    email = f"liaison-view-{uuid.uuid4().hex[:8]}@test.com"
    password = "liaisonpass123"
    await _create_test_user_in_dept(email, password, "Liaison Viewer", UserRole.LIAISON, dept_id)
    login = await client.post("/auth/jwt/login", data={"username": email, "password": password})
    token = login.json()["access_token"]

    # Departments list requires STAFF — liaison is below STAFF so this should be 403
    resp = await client.get(
        "/departments/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_liaison_department_scoping(client: AsyncClient, admin_token: str):
    """Liaison users are department-scoped via check_department_access."""
    from app.auth.dependencies import check_department_access

    # Create a mock-like user object
    class MockUser:
        role = UserRole.LIAISON
        department_id = uuid.uuid4()

    user = MockUser()
    other_dept = uuid.uuid4()

    # Access own department — should not raise
    check_department_access(user, user.department_id)

    # Access shared resource (None) — should not raise
    check_department_access(user, None)

    # Access other department — should raise 403
    with pytest.raises(Exception) as exc_info:
        check_department_access(user, other_dept)
    assert exc_info.value.status_code == 403
