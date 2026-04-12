import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_write_audit_log_creates_entry(client: AsyncClient):
    from tests.conftest import test_session_maker
    from app.audit.logger import write_audit_log

    async with test_session_maker() as session:
        entry = await write_audit_log(
            session=session,
            action="test_action",
            resource_type="test_resource",
            resource_id="123",
            details={"key": "value"},
        )
        assert entry.id is not None
        assert entry.entry_hash != ""
        assert len(entry.entry_hash) == 64
        assert entry.prev_hash == "0" * 64


@pytest.mark.asyncio
async def test_hash_chain_links_entries(client: AsyncClient):
    from tests.conftest import test_session_maker
    from app.audit.logger import write_audit_log

    async with test_session_maker() as session:
        entry1 = await write_audit_log(
            session=session, action="first", resource_type="test"
        )
        entry2 = await write_audit_log(
            session=session, action="second", resource_type="test"
        )
        assert entry2.prev_hash == entry1.entry_hash


@pytest.mark.asyncio
async def test_verify_chain_passes(client: AsyncClient):
    from tests.conftest import test_session_maker
    from app.audit.logger import write_audit_log, verify_chain

    async with test_session_maker() as session:
        await write_audit_log(session=session, action="a", resource_type="test")
        await write_audit_log(session=session, action="b", resource_type="test")
        await write_audit_log(session=session, action="c", resource_type="test")

        is_valid, count, error = await verify_chain(session)
        assert is_valid is True
        assert count == 3
        assert error == ""


@pytest.mark.asyncio
async def test_middleware_logs_requests(client: AsyncClient):
    from tests.conftest import test_session_maker
    from sqlalchemy import select, func
    from app.models.audit import AuditLog

    # Health is in SKIP_PATHS, should not be logged
    await client.get("/health")

    async with test_session_maker() as session:
        result = await session.execute(select(func.count(AuditLog.id)))
        count = result.scalar()
        assert count == 0

    # Register hits a logged endpoint
    await client.post(
        "/auth/register",
        json={
            "email": "audit-test@example.com",
            "password": "testpass123",
            "full_name": "Audit Test",
        },
    )

    async with test_session_maker() as session:
        result = await session.execute(
            select(AuditLog).where(AuditLog.action.contains("/auth/register"))
        )
        entry = result.scalar_one_or_none()
        assert entry is not None
        assert entry.details["method"] == "POST"
        assert entry.details["status_code"] == 201


@pytest.mark.asyncio
async def test_audit_export_requires_admin(client: AsyncClient, staff_token: str):
    resp = await client.get(
        "/audit/export",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert resp.status_code == 403
