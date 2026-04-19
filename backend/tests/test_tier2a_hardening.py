"""Tests for Tier 2A security hardening.

Covers:
- UserSelfUpdate schema rejects role / department_id on PATCH /users/me
- /documents/ endpoints enforce fail-closed department scoping via
  require_department_scope

Matches plan docs/REMEDIATION-PLAN-2026-04-19.md §T2A.
"""

import uuid

import pytest
import sqlalchemy as sa
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# UserSelfUpdate — PATCH /users/me
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_patch_users_me_rejects_role_escalation(client: AsyncClient, staff_token: str):
    """A STAFF caller cannot self-escalate by sending {'role': 'admin'}.

    Before this fix the endpoint accepted UserUpdate (which included role) and
    would have written role=admin to the caller's own row. UserSelfUpdate
    rejects any payload containing role/department_id with HTTP 422 at parse
    time.
    """
    resp = await client.patch(
        "/users/me",
        json={"role": "admin"},
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert resp.status_code == 422, resp.text
    # Confirm the role did not change.
    me = await client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert me.status_code == 200
    assert me.json()["role"] == "staff"


@pytest.mark.asyncio
async def test_patch_users_me_rejects_department_id(client: AsyncClient, staff_token: str):
    """A STAFF caller cannot self-move departments via PATCH /users/me."""
    resp = await client.patch(
        "/users/me",
        json={"department_id": str(uuid.uuid4())},
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_patch_users_me_allows_full_name(client: AsyncClient, staff_token: str):
    """Non-privileged fields (full_name) are still settable via PATCH /users/me."""
    resp = await client.patch(
        "/users/me",
        json={"full_name": "Renamed Self"},
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["full_name"] == "Renamed Self"
    # Role unchanged.
    assert body["role"] == "staff"


@pytest.mark.asyncio
async def test_patch_users_me_rejects_role_and_allowed_field_together(
    client: AsyncClient, staff_token: str
):
    """Mixing role with an allowed field still fails — the privileged field
    must not sneak through because the rest of the payload is valid."""
    resp = await client.patch(
        "/users/me",
        json={"full_name": "Sneaky", "role": "admin"},
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# /documents/ — fail-closed department scoping
# ---------------------------------------------------------------------------

async def _seed_document_with_dept(dept_id: uuid.UUID | None, filename_suffix: str) -> uuid.UUID:
    """Seed (user, data_source, document) directly in the test DB.

    Returns the document's id. Matches the pattern used at the bottom of
    test_department_scoping.py.
    """
    from app.models.document import DataSource, Document, SourceType
    from app.models.user import User, UserRole
    from tests.conftest import _create_test_user, test_session_maker

    seed_email = f"seed-{uuid.uuid4().hex[:8]}@test.com"
    await _create_test_user(seed_email, "seedpass123", "Seed User", UserRole.ADMIN)
    async with test_session_maker() as session:
        seed_user = (await session.execute(
            sa.select(User).where(User.email == seed_email)
        )).scalar_one()
        source = DataSource(
            name=f"Src {uuid.uuid4().hex[:6]}",
            source_type=SourceType.UPLOAD,
            connection_config={},
            created_by=seed_user.id,
        )
        session.add(source)
        await session.flush()
        doc = Document(
            source_id=source.id,
            source_path=f"/seed/{filename_suffix}.pdf",
            filename=f"{filename_suffix}.pdf",
            file_type="pdf",
            file_hash=uuid.uuid4().hex,
            file_size=128,
            department_id=dept_id,
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)
        return doc.id


@pytest.mark.asyncio
async def test_list_documents_filters_by_department_for_non_admin(
    client: AsyncClient,
    admin_token: str,
    staff_token_dept_a: str,
    dept_a: uuid.UUID,
    dept_b: uuid.UUID,
):
    """Non-admin in dept A sees only dept A documents; admin sees all."""
    await _seed_document_with_dept(dept_a, "doc_a")
    await _seed_document_with_dept(dept_b, "doc_b")

    # Non-admin in dept A
    resp = await client.get(
        "/documents/",
        headers={"Authorization": f"Bearer {staff_token_dept_a}"},
    )
    assert resp.status_code == 200, resp.text
    names = [d["filename"] for d in resp.json()]
    assert names == ["doc_a.pdf"], names

    # Admin sees both
    resp = await client.get(
        "/documents/",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    names = sorted(d["filename"] for d in resp.json())
    assert names == ["doc_a.pdf", "doc_b.pdf"], names


@pytest.mark.asyncio
async def test_list_documents_denies_non_admin_with_no_department(
    client: AsyncClient,
    staff_token: str,  # plain staff fixture -> no department_id
):
    """Fail-closed: a non-admin user with no department assignment is
    denied with 403, not silently given an empty list."""
    resp = await client.get(
        "/documents/",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_get_document_blocks_cross_department(
    client: AsyncClient,
    staff_token_dept_a: str,
    dept_b: uuid.UUID,
):
    doc_b = await _seed_document_with_dept(dept_b, "cross_get")
    resp = await client.get(
        f"/documents/{doc_b}",
        headers={"Authorization": f"Bearer {staff_token_dept_a}"},
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_get_document_blocks_null_department_for_non_admin(
    client: AsyncClient,
    staff_token_dept_a: str,
):
    """Fail-closed: a document with no department_id is NOT a shared resource.
    Non-admin users must be denied."""
    orphan = await _seed_document_with_dept(None, "no_dept")
    resp = await client.get(
        f"/documents/{orphan}",
        headers={"Authorization": f"Bearer {staff_token_dept_a}"},
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_list_chunks_blocks_cross_department(
    client: AsyncClient,
    staff_token_dept_a: str,
    dept_b: uuid.UUID,
):
    doc_b = await _seed_document_with_dept(dept_b, "cross_chunks")
    resp = await client.get(
        f"/documents/{doc_b}/chunks",
        headers={"Authorization": f"Bearer {staff_token_dept_a}"},
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_admin_can_read_any_department_document(
    client: AsyncClient,
    admin_token: str,
    dept_b: uuid.UUID,
):
    """Admin bypass — confirms we did not over-correct."""
    doc_b = await _seed_document_with_dept(dept_b, "admin_any")
    resp = await client.get(
        f"/documents/{doc_b}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text
