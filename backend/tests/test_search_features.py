"""Tests for search department filter and CSV export (Item 4 — Debt Sprint)."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_search_filters_include_departments(client: AsyncClient, admin_token: str):
    """GET /search/filters returns departments list."""
    resp = await client.get(
        "/search/filters",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "departments" in data
    assert isinstance(data["departments"], list)
    # departments may be empty in test DB — just verify the field exists and is a list


@pytest.mark.asyncio
async def test_search_export_csv_returns_csv(client: AsyncClient, admin_token: str):
    """GET /search/export?query=test&format=csv returns CSV with correct headers.

    Mocks app.search.engine.embed_text so the test is hermetic — no outbound
    HTTP to Ollama. Matches the pattern already used in test_search_api.py.
    """
    with patch("app.search.engine.embed_text", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = [0.1] * 768
        resp = await client.get(
            "/search/export?query=test&format=csv",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert resp.status_code == 200
    assert "text/csv" in resp.headers.get("content-type", "")
    lines = resp.text.strip().split("\n")
    assert len(lines) >= 1  # At least the header row
    header = lines[0]
    assert "Rank" in header
    assert "Filename" in header
    assert "Content" in header


@pytest.mark.asyncio
async def test_search_export_requires_auth(client: AsyncClient):
    """GET /search/export without auth returns 401."""
    resp = await client.get("/search/export?query=test&format=csv")
    assert resp.status_code == 401
