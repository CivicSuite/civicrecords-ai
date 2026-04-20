"""Regression tests for the child-before-parent info-leak follow-up PR.

Two handlers were fixed in this PR, with different fix patterns because
their URL shapes differ:

1. ``PATCH /requests/{request_id}/response-letter/{letter_id}`` —
   ``update_response_letter`` in backend/app/requests/router.py. Both IDs
   are path params, so the fix is a straightforward **reorder**: load the
   parent request and run the dept check BEFORE the letter lookup.

2. ``PATCH /exemptions/flags/{flag_id}`` — ``review_flag`` in
   backend/app/exemptions/router.py. Only flag_id is in the path, so the
   flag must load first to know which parent request to check. Reorder
   isn't possible. Fix is **404-unification**: every failure mode (flag
   missing, parent request missing, cross-department) returns the same
   404 "Flag not found" response so an attacker cannot distinguish
   "exists in another dept" from "does not exist" via status code.

See docs/FINDING-2026-04-19-info-leak-child-before-parent.md for the
original finding and the full fix rationale.
"""

import uuid

import pytest
import sqlalchemy as sa
from httpx import AsyncClient


async def _create_request_in_dept(client: AsyncClient, token: str, description: str) -> str:
    """POST /requests/ with the given token and return the new request id.

    Duplicated from test_tier2a_hardening.py so this file is self-contained.
    """
    resp = await client.post(
        "/requests/",
        json={"requester_name": "Test Requester", "description": description},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["id"]


async def _seed_exemption_flag_on_request(
    request_id: str, dept_id: uuid.UUID
) -> uuid.UUID:
    """Seed (user → data_source → document → document_chunk → exemption_flag)
    directly in the test DB. The flag is attached to the given request_id and
    its document is department-scoped to dept_id so the dept check on the
    parent request resolves correctly.

    Returns the flag's id.
    """
    from app.models.document import DataSource, Document, DocumentChunk, SourceType
    from app.models.exemption import ExemptionFlag, FlagStatus
    from app.models.user import User, UserRole
    from tests.conftest import _create_test_user, test_session_maker

    seed_email = f"seed-flag-{uuid.uuid4().hex[:8]}@test.com"
    await _create_test_user(seed_email, "seedpass123", "Seed User", UserRole.ADMIN)
    async with test_session_maker() as session:
        seed_user = (await session.execute(
            sa.select(User).where(User.email == seed_email)
        )).scalar_one()
        source = DataSource(
            name=f"FlagSrc {uuid.uuid4().hex[:6]}",
            source_type=SourceType.UPLOAD,
            connection_config={},
            created_by=seed_user.id,
        )
        session.add(source)
        await session.flush()
        doc = Document(
            source_id=source.id,
            source_path=f"/seed/flag-doc-{uuid.uuid4().hex[:6]}.pdf",
            filename=f"flag-doc.pdf",
            file_type="pdf",
            file_hash=uuid.uuid4().hex,
            file_size=128,
            department_id=dept_id,
        )
        session.add(doc)
        await session.flush()
        chunk = DocumentChunk(
            document_id=doc.id,
            chunk_index=0,
            content_text="flagged text",
            token_count=2,
        )
        session.add(chunk)
        await session.flush()
        flag = ExemptionFlag(
            chunk_id=chunk.id,
            request_id=uuid.UUID(request_id),
            category="test_category",
            matched_text="flagged text",
            confidence=1.0,
            status=FlagStatus.FLAGGED,
        )
        session.add(flag)
        await session.commit()
        await session.refresh(flag)
        return flag.id


# ---------------------------------------------------------------------------
# update_response_letter — reorder closes the info-leak fully
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_response_letter_patch_placeholder_letter_id_returns_403_cross_dept(
    client: AsyncClient,
    staff_token_dept_b: str,
    reviewer_token_dept_a: str,
):
    """With a placeholder (non-existent) letter_id, a cross-dept caller
    previously got 404 "Response letter not found" because the letter
    lookup fired before the dept check. After the reorder, the dept check
    fires first and returns 403. This proves the info-leak is closed —
    status code no longer distinguishes "letter exists in another dept"
    from "letter does not exist"."""
    req_b_id = await _create_request_in_dept(client, staff_token_dept_b, "letter probe")
    fake_letter_id = str(uuid.uuid4())  # almost certainly doesn't exist
    resp = await client.patch(
        f"/requests/{req_b_id}/response-letter/{fake_letter_id}",
        json={},
        headers={"Authorization": f"Bearer {reviewer_token_dept_a}"},
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_response_letter_patch_real_letter_id_returns_403_cross_dept(
    client: AsyncClient,
    staff_token_dept_b: str,
    reviewer_token_dept_a: str,
):
    """With a real dept-B letter_id, cross-dept reviewer still gets 403.
    This is the same behavior as before the reorder — confirms we didn't
    regress the existing case."""
    req_b_id = await _create_request_in_dept(client, staff_token_dept_b, "real letter")
    letter_resp = await client.post(
        f"/requests/{req_b_id}/response-letter",
        json={},
        headers={"Authorization": f"Bearer {staff_token_dept_b}"},
    )
    assert letter_resp.status_code in (200, 201), letter_resp.text
    letter_b_id = letter_resp.json()["id"]
    resp = await client.patch(
        f"/requests/{req_b_id}/response-letter/{letter_b_id}",
        json={},
        headers={"Authorization": f"Bearer {reviewer_token_dept_a}"},
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_response_letter_patch_admin_still_works(
    client: AsyncClient,
    admin_token: str,
    staff_token_dept_b: str,
):
    """Admin can still PATCH a response letter in any department."""
    req_b_id = await _create_request_in_dept(client, staff_token_dept_b, "admin letter")
    letter_resp = await client.post(
        f"/requests/{req_b_id}/response-letter",
        json={},
        headers={"Authorization": f"Bearer {staff_token_dept_b}"},
    )
    assert letter_resp.status_code in (200, 201), letter_resp.text
    letter_b_id = letter_resp.json()["id"]
    resp = await client.patch(
        f"/requests/{req_b_id}/response-letter/{letter_b_id}",
        json={"edited_content": "<p>admin edit</p>"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# review_flag — 404-unification closes the info-leak where reorder can't
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_review_flag_placeholder_id_returns_404(
    client: AsyncClient,
    reviewer_token_dept_a: str,
):
    """Placeholder flag_id returns 404 — unchanged from pre-PR behavior."""
    fake_flag_id = str(uuid.uuid4())
    resp = await client.patch(
        f"/exemptions/flags/{fake_flag_id}",
        json={"status": "accepted", "review_reason": "probe"},
        headers={"Authorization": f"Bearer {reviewer_token_dept_a}"},
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_review_flag_cross_department_returns_404_not_403(
    client: AsyncClient,
    staff_token_dept_b: str,
    reviewer_token_dept_a: str,
    dept_b: uuid.UUID,
):
    """A real dept-B flag accessed by a dept-A reviewer returns **404**, not
    403. This is the 404-unification pattern — the external response is the
    same as "flag does not exist", so an attacker cannot distinguish via
    status code whether the flag_id exists in another department."""
    req_b_id = await _create_request_in_dept(client, staff_token_dept_b, "flag probe")
    flag_b_id = await _seed_exemption_flag_on_request(req_b_id, dept_b)
    resp = await client.patch(
        f"/exemptions/flags/{flag_b_id}",
        json={"status": "accepted", "review_reason": "nope"},
        headers={"Authorization": f"Bearer {reviewer_token_dept_a}"},
    )
    assert resp.status_code == 404, resp.text
    # Body should be the uniform "Flag not found" — not a 403-style message
    assert "Flag not found" in resp.text


@pytest.mark.asyncio
async def test_review_flag_admin_still_works(
    client: AsyncClient,
    admin_token: str,
    staff_token_dept_b: str,
    dept_b: uuid.UUID,
):
    """Admin can still review flags in any department. Confirms the
    404-unification did not overshoot and break legitimate admin access."""
    req_b_id = await _create_request_in_dept(client, staff_token_dept_b, "admin flag")
    flag_b_id = await _seed_exemption_flag_on_request(req_b_id, dept_b)
    resp = await client.patch(
        f"/exemptions/flags/{flag_b_id}",
        json={"status": "accepted", "review_reason": "admin ok"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text


