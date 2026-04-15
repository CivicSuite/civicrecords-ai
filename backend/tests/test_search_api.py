import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_search_requires_auth(client: AsyncClient):
    resp = await client.post(
        "/search/query",
        json={"query": "test", "limit": 5},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_search_empty_db(client: AsyncClient, admin_token: str):
    """Search on empty DB should return 0 results, not error."""
    with patch("app.search.engine.embed_text", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = [0.1] * 768
        resp = await client.post(
            "/search/query",
            json={"query": "water quality report", "limit": 5},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["results_count"] == 0
    assert data["results"] == []
    assert data["session_id"] is not None


@pytest.mark.asyncio
async def test_search_creates_session(client: AsyncClient, admin_token: str):
    """First search should create a session."""
    with patch("app.search.engine.embed_text", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = [0.1] * 768
        resp = await client.post(
            "/search/query",
            json={"query": "test query", "limit": 5},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert resp.status_code == 200
    session_id = resp.json()["session_id"]
    assert session_id is not None

    # List sessions should include it
    sessions_resp = await client.get(
        "/search/sessions",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert sessions_resp.status_code == 200
    sessions = sessions_resp.json()
    assert len(sessions) >= 1


@pytest.mark.asyncio
async def test_search_filters_endpoint(client: AsyncClient, admin_token: str):
    resp = await client.get(
        "/search/filters",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "file_types" in data
    assert "source_names" in data


@pytest.mark.asyncio
async def test_search_session_not_found(client: AsyncClient, admin_token: str):
    resp = await client.get(
        f"/search/sessions/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_export_dept_scoping(
    client: AsyncClient,
    staff_token_dept_a: str,
    dept_a: uuid.UUID,
):
    """Liaison follow-up #4: export must inject server-side dept scoping for non-admin users."""
    captured_filters = {}

    async def fake_hybrid_search(session, query_text, limit, filters):
        captured_filters.update(filters or {})
        return []

    with patch("app.search.router.hybrid_search", side_effect=fake_hybrid_search):
        resp = await client.get(
            "/search/export",
            params={"query": "budget"},
            headers={"Authorization": f"Bearer {staff_token_dept_a}"},
        )

    assert resp.status_code == 200
    assert captured_filters.get("department_id") == str(dept_a), (
        f"Expected dept scoping to dept_a ({dept_a}), got filters={captured_filters}"
    )
