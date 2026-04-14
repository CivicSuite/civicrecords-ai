"""Tests for coverage gap indicators (Item 5 — Debt Sprint)."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_coverage_gaps_endpoint(client: AsyncClient, admin_token: str):
    """GET /admin/coverage-gaps returns gap analysis."""
    resp = await client.get(
        "/admin/coverage-gaps",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "jurisdictions_without_rules" in data
    assert "departments_without_staff" in data
    assert "uncovered_categories" in data
    assert "total_gaps" in data
    assert isinstance(data["jurisdictions_without_rules"], list)
    assert isinstance(data["departments_without_staff"], list)
    assert isinstance(data["uncovered_categories"], list)
    assert isinstance(data["total_gaps"], int)


@pytest.mark.asyncio
async def test_coverage_gaps_requires_admin(client: AsyncClient):
    """GET /admin/coverage-gaps without auth returns 401."""
    resp = await client.get("/admin/coverage-gaps")
    assert resp.status_code == 401
