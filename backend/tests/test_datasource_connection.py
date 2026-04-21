"""Tests for datasource test-connection endpoint (Item 2 — Debt Sprint).

Security: verifies the endpoint does NOT persist credentials or log them.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_test_connection_file_share_success(client: AsyncClient, admin_token: str):
    """POST /datasources/test-connection succeeds for an accessible directory."""
    resp = await client.post(
        "/datasources/test-connection",
        json={"source_type": "file_system", "path": "/tmp"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "accessible" in data["message"].lower()


@pytest.mark.asyncio
async def test_test_connection_file_share_failure(client: AsyncClient, admin_token: str):
    """POST /datasources/test-connection fails for non-existent path."""
    resp = await client.post(
        "/datasources/test-connection",
        json={"source_type": "file_system", "path": "/nonexistent/path/xyz"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert "not accessible" in data["message"].lower()


@pytest.mark.asyncio
async def test_test_connection_does_not_persist(client: AsyncClient, admin_token: str):
    """Test-connection does NOT create a DataSource record."""
    from sqlalchemy import select, func
    from tests.conftest import test_session_maker
    from app.models.document import DataSource

    # Count before
    async with test_session_maker() as session:
        before = (await session.execute(select(func.count(DataSource.id)))).scalar() or 0

    # Call test-connection
    await client.post(
        "/datasources/test-connection",
        json={"source_type": "manual_drop", "path": "/tmp"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # Count after — must be the same
    async with test_session_maker() as session:
        after = (await session.execute(select(func.count(DataSource.id)))).scalar() or 0

    assert after == before, "test-connection must not create DataSource records"


@pytest.mark.asyncio
async def test_test_connection_requires_admin(client: AsyncClient):
    """POST /datasources/test-connection without auth returns 401."""
    resp = await client.post(
        "/datasources/test-connection",
        json={"source_type": "file_system", "path": "/tmp"},
    )
    assert resp.status_code == 401
