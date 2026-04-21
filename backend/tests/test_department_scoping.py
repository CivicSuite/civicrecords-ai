import uuid
from unittest.mock import AsyncMock, patch

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
async def test_staff_gets_request_in_other_department_404(
    client: AsyncClient,
    staff_token_dept_a: str, staff_token_dept_b: str,
):
    """Cross-dept request access returns 404 (not 403) after the
    404-unification info-leak fix — the external response is identical to
    "request does not exist" so an attacker cannot probe for request IDs
    in other departments."""
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
    assert resp.status_code == 404


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
    # 404-unification: cross-dept workflow actions return 404 (not 403).
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_liaison_can_list_own_department_requests(
    client: AsyncClient,
    admin_token: str,
    liaison_token_dept_a: str,
    dept_a: uuid.UUID,
    dept_b: uuid.UUID,
):
    """LIAISON in dept A can GET /requests/ and only sees dept A requests — not dept B."""
    # Admin creates one request in dept A
    await client.post(
        "/requests/",
        json={
            "requester_name": "Public User",
            "description": "Admin-created dept A request",
            "department_id": str(dept_a),
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    # Admin creates one request in dept B — liaison must NOT see this
    await client.post(
        "/requests/",
        json={
            "requester_name": "Other User",
            "description": "Admin-created dept B request",
            "department_id": str(dept_b),
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = await client.get(
        "/requests/",
        headers={"Authorization": f"Bearer {liaison_token_dept_a}"},
    )
    assert resp.status_code == 200  # fails before fix (returns 403)
    data = resp.json()
    assert len(data) == 1  # only dept A request visible
    assert all(r["department_id"] == str(dept_a) for r in data)


@pytest.mark.asyncio
async def test_liaison_can_search(
    client: AsyncClient,
    liaison_token_dept_a: str,
):
    """LIAISON role should be able to POST /search/query (returns 200, not 403)."""
    with patch("app.search.engine.embed_text", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = [0.1] * 768
        resp = await client.post(
            "/search/query",
            json={"query": "test liaison search"},
            headers={"Authorization": f"Bearer {liaison_token_dept_a}"},
        )
    assert resp.status_code == 200  # fails before fix (returns 403)
    data = resp.json()
    assert "results" in data


@pytest.mark.asyncio
async def test_liaison_search_excludes_dept_b(
    client: AsyncClient,
    liaison_token_dept_a: str,
    dept_a: uuid.UUID,
    dept_b: uuid.UUID,
):
    """LIAISON in dept A must not see dept B documents in search results.

    Seeds a DataSource + Document + DocumentChunk in dept B with a distinctive
    content string and a high-similarity embedding, then verifies it is absent
    from liaison-dept-A search results.  The dept scoping filter injected by the
    router (effective_filters["department_id"] = user.department_id) is the
    security boundary under test.
    """
    from tests.conftest import test_session_maker, _create_test_user
    from app.models.document import DataSource, Document, DocumentChunk, SourceType
    from app.models.user import User, UserRole
    import sqlalchemy as sa

    unique_term = f"dept_b_classified_{uuid.uuid4().hex[:8]}"

    # Create a user to satisfy DataSource.created_by FK, then fetch their ID
    seed_email = f"seed-{uuid.uuid4().hex[:8]}@test.com"
    await _create_test_user(seed_email, "seedpass123", "Seed User", UserRole.ADMIN)
    async with test_session_maker() as session:
        seed_user = (await session.execute(
            sa.select(User).where(User.email == seed_email)
        )).scalar_one()
        seed_user_id = seed_user.id

    # Seed dept B DataSource → Document → DocumentChunk directly in test DB
    async with test_session_maker() as session:
        source_b = DataSource(
            name=f"Dept B Source {uuid.uuid4().hex[:6]}",
            source_type=SourceType.MANUAL_DROP,
            connection_config={},
            created_by=seed_user_id,
        )
        session.add(source_b)
        await session.flush()

        doc_b = Document(
            source_id=source_b.id,
            source_path=f"/seed/{unique_term}.pdf",
            filename=f"{unique_term}.pdf",
            file_type="pdf",
            file_hash=uuid.uuid4().hex,
            file_size=512,
            department_id=dept_b,
        )
        session.add(doc_b)
        await session.flush()

        # Use a non-zero embedding so the vector search considers this chunk
        chunk_b = DocumentChunk(
            document_id=doc_b.id,
            chunk_index=0,
            content_text=unique_term,
            embedding=[0.9] * 768,
            token_count=5,
        )
        session.add(chunk_b)
        await session.commit()

    # Search as liaison in dept A using an embedding that perfectly matches
    # the dept B chunk — scoping must exclude it regardless of similarity.
    with patch("app.search.engine.embed_text", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = [0.9] * 768
        resp = await client.post(
            "/search/query",
            json={"query": unique_term, "limit": 20},
            headers={"Authorization": f"Bearer {liaison_token_dept_a}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    result_texts = [r.get("content_text", "") for r in data["results"]]
    assert not any(unique_term in t for t in result_texts), (
        f"Dept B document '{unique_term}' appeared in liaison dept-A search results "
        f"— department scoping failure. Results: {result_texts}"
    )
