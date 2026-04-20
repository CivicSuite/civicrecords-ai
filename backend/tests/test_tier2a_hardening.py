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


# ---------------------------------------------------------------------------
# /analytics/operational — fail-closed department scope on aggregate metrics
# ---------------------------------------------------------------------------

async def _create_request_in_dept(client: AsyncClient, token: str, description: str) -> str:
    """POST /requests/ with the given token and return the new request's id."""
    resp = await client.post(
        "/requests/",
        json={"requester_name": "Test Requester", "description": description},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_analytics_operational_filters_by_department_for_non_admin(
    client: AsyncClient,
    staff_token_dept_a: str,
    staff_token_dept_b: str,
):
    """Non-admin sees only counts from their own department. Dept B's single
    request must not appear in Dept A's aggregate."""
    await _create_request_in_dept(client, staff_token_dept_a, "A-only")
    await _create_request_in_dept(client, staff_token_dept_b, "B-only")
    await _create_request_in_dept(client, staff_token_dept_b, "B-only-2")

    resp = await client.get(
        "/analytics/operational",
        headers={"Authorization": f"Bearer {staff_token_dept_a}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    # Only the one dept-A request contributes to the aggregate.
    assert data["total_open"] + data["total_closed"] == 1, data


@pytest.mark.asyncio
async def test_analytics_operational_admin_sees_all_departments(
    client: AsyncClient,
    admin_token: str,
    staff_token_dept_a: str,
    staff_token_dept_b: str,
):
    await _create_request_in_dept(client, staff_token_dept_a, "A-open")
    await _create_request_in_dept(client, staff_token_dept_b, "B-open")
    resp = await client.get(
        "/analytics/operational",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total_open"] + data["total_closed"] == 2, data


@pytest.mark.asyncio
async def test_analytics_operational_denies_non_admin_with_null_department(
    client: AsyncClient,
    staff_token: str,  # plain staff -> no department
):
    resp = await client.get(
        "/analytics/operational",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert resp.status_code == 403, resp.text


# ---------------------------------------------------------------------------
# /requests/{id}/timeline + /messages — fail-closed migration
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_timeline_get_blocks_cross_department(
    client: AsyncClient,
    staff_token_dept_a: str,
    staff_token_dept_b: str,
):
    req_b_id = await _create_request_in_dept(client, staff_token_dept_b, "B timeline")
    resp = await client.get(
        f"/requests/{req_b_id}/timeline",
        headers={"Authorization": f"Bearer {staff_token_dept_a}"},
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_timeline_post_blocks_cross_department(
    client: AsyncClient,
    staff_token_dept_a: str,
    staff_token_dept_b: str,
):
    req_b_id = await _create_request_in_dept(client, staff_token_dept_b, "B timeline post")
    resp = await client.post(
        f"/requests/{req_b_id}/timeline",
        json={"event_type": "note", "description": "Should not land"},
        headers={"Authorization": f"Bearer {staff_token_dept_a}"},
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_messages_get_blocks_cross_department(
    client: AsyncClient,
    staff_token_dept_a: str,
    staff_token_dept_b: str,
):
    req_b_id = await _create_request_in_dept(client, staff_token_dept_b, "B messages")
    resp = await client.get(
        f"/requests/{req_b_id}/messages",
        headers={"Authorization": f"Bearer {staff_token_dept_a}"},
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_messages_post_blocks_cross_department(
    client: AsyncClient,
    staff_token_dept_a: str,
    staff_token_dept_b: str,
):
    req_b_id = await _create_request_in_dept(client, staff_token_dept_b, "B messages post")
    resp = await client.post(
        f"/requests/{req_b_id}/messages",
        json={"message_text": "Should not land", "is_internal": False},
        headers={"Authorization": f"Bearer {staff_token_dept_a}"},
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_timeline_messages_deny_non_admin_with_null_department(
    client: AsyncClient,
    staff_token: str,  # plain staff -> no department
    staff_token_dept_a: str,
):
    """A null-dept non-admin must be denied even on a dept-A request that
    they would normally not see anyway. Under the fail-closed helper,
    null user dept always denies for non-admin."""
    req_a_id = await _create_request_in_dept(client, staff_token_dept_a, "A probe")
    for method, path in [
        ("GET", f"/requests/{req_a_id}/timeline"),
        ("GET", f"/requests/{req_a_id}/messages"),
    ]:
        resp = await client.get(path, headers={"Authorization": f"Bearer {staff_token}"})
        assert resp.status_code == 403, f"{method} {path}: {resp.text}"


# ---------------------------------------------------------------------------
# Parameterized cross-endpoint enforcement — the T2A ratchet
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parameterized_cross_department_access_denied(
    client: AsyncClient,
    reviewer_token_dept_a: str,
    staff_token_dept_b: str,
    dept_b: uuid.UUID,
):
    """Iterates every dept-scoped endpoint in the codebase and asserts that
    a dept-A reviewer is denied cross-department access on every one.

    Uses a REVIEWER token (not STAFF) for the cross-dept caller because
    several workflow endpoints (/approve, /reject, /ready-for-release) are
    gated at REVIEWER. Reviewer satisfies STAFF too, so one token covers all
    cases. A failing role check would produce 403 for the wrong reason, but
    since REVIEWER passes every role gate here, a 403 here is always from
    the department gate.

    Coverage after the T2A-cleanup PR: every ``require_department_scope``
    call site in ``requests/router.py`` (17 sites — includes fee-waiver
    review, added after auditor feedback on the first cleanup pass),
    ``documents/router.py`` (2), and ``exemptions/router.py`` (2 of 3; the
    third — PATCH /exemptions/flags/{flag_id} — needs a seeded flag and is
    covered by a targeted test instead).

    New dept-scoped endpoints added after this must be appended below to
    prevent silent regression. If a route is intentionally global (like
    /city-profile), it does not belong here.
    """
    # Seed one dept-B request and one dept-B document.
    req_b_id = await _create_request_in_dept(client, staff_token_dept_b, "param probe")
    doc_b_id = await _seed_document_with_dept(dept_b, "param_probe")

    # Seed a real response letter on the dept-B request. The PATCH
    # /response-letter/{letter_id} handler loads the letter BEFORE the
    # parent request, so a placeholder id 404s before the dept check runs.
    # Using a real letter_id guarantees the 403 is the dept check.
    letter_resp = await client.post(
        f"/requests/{req_b_id}/response-letter",
        json={},
        headers={"Authorization": f"Bearer {staff_token_dept_b}"},
    )
    assert letter_resp.status_code in (200, 201), letter_resp.text
    letter_b_id = letter_resp.json()["id"]

    # Seed a real fee waiver on the dept-B request so the review PATCH case
    # exercises the dept check against a real waiver record, not a placeholder.
    waiver_resp = await client.post(
        f"/requests/{req_b_id}/fee-waiver",
        json={"waiver_type": "other", "reason": "seed"},
        headers={"Authorization": f"Bearer {staff_token_dept_b}"},
    )
    assert waiver_resp.status_code in (200, 201), waiver_resp.text
    waiver_b_id = waiver_resp.json()["id"]

    # Placeholder child IDs for routes where the handler loads the parent
    # request first (and dept check runs before any child lookup).
    placeholder_doc = str(uuid.uuid4())

    cases = [
        # documents (PR #16)
        ("GET",    f"/documents/{doc_b_id}",                              None),
        ("GET",    f"/documents/{doc_b_id}/chunks",                       None),
        # requests — core
        ("GET",    f"/requests/{req_b_id}",                               None),
        ("PATCH",  f"/requests/{req_b_id}",                               {}),
        # requests — attached documents
        ("POST",   f"/requests/{req_b_id}/documents",
                   {"document_id": str(uuid.uuid4()), "relevance_note": "nope"}),
        ("GET",    f"/requests/{req_b_id}/documents",                     None),
        ("DELETE", f"/requests/{req_b_id}/documents/{placeholder_doc}",   None),
        # requests — workflow
        ("POST",   f"/requests/{req_b_id}/submit-review",                 None),
        ("POST",   f"/requests/{req_b_id}/ready-for-release",             None),
        ("POST",   f"/requests/{req_b_id}/approve",                       None),
        ("POST",   f"/requests/{req_b_id}/reject",                        None),
        # requests — fees
        ("GET",    f"/requests/{req_b_id}/fees",                          None),
        ("POST",   f"/requests/{req_b_id}/fees",
                   {"description": "nope", "unit_price": 0.0, "quantity": 1}),
        ("POST",   f"/requests/{req_b_id}/estimate-fees",
                   {"page_count": 1, "fee_schedule_id": str(uuid.uuid4())}),
        ("POST",   f"/requests/{req_b_id}/fee-waiver",
                   {"waiver_type": "other", "reason": "nope"}),
        ("PATCH",  f"/requests/{req_b_id}/fee-waiver/{waiver_b_id}",
                   {"status": "approved", "review_notes": "nope"}),
        # requests — response letter
        ("POST",   f"/requests/{req_b_id}/response-letter",               {}),
        ("GET",    f"/requests/{req_b_id}/response-letter",               None),
        ("PATCH",  f"/requests/{req_b_id}/response-letter/{letter_b_id}", {}),
        # requests — timeline + messages (PR #17)
        ("GET",    f"/requests/{req_b_id}/timeline",                      None),
        ("POST",   f"/requests/{req_b_id}/timeline",
                   {"event_type": "note", "description": "nope"}),
        ("GET",    f"/requests/{req_b_id}/messages",                      None),
        ("POST",   f"/requests/{req_b_id}/messages",
                   {"message_text": "nope", "is_internal": False}),
        # exemptions
        ("POST",   f"/exemptions/scan/{req_b_id}",                        None),
        ("GET",    f"/exemptions/flags/{req_b_id}",                       None),
    ]

    headers = {"Authorization": f"Bearer {reviewer_token_dept_a}"}
    failures = []
    for method, path, body in cases:
        if method == "GET":
            resp = await client.get(path, headers=headers)
        elif method == "POST":
            resp = await client.post(path, headers=headers, json=body)
        elif method == "PATCH":
            resp = await client.patch(path, headers=headers, json=body)
        elif method == "DELETE":
            resp = await client.delete(path, headers=headers)
        else:
            raise AssertionError(f"Unsupported method {method!r}")
        if resp.status_code != 403:
            failures.append(f"{method} {path} -> {resp.status_code}: {resp.text[:120]}")
    assert not failures, (
        "Cross-department enforcement regressed on the following routes:\n  "
        + "\n  ".join(failures)
    )
