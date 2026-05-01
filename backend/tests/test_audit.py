import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_write_audit_log_creates_entry(client: AsyncClient):
    from tests.conftest import test_session_maker
    from app.audit.logger import write_audit_log
    from civiccore.audit import compute_persisted_audit_hash

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
        assert entry.entry_hash == compute_persisted_audit_hash(
            previous_hash=entry.prev_hash,
            timestamp=entry.timestamp,
            actor_id=entry.user_id,
            action=entry.action,
            details=entry.details,
        )


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
async def test_verify_chain_detects_tampered_civiccore_hash_payload(client: AsyncClient):
    from sqlalchemy import update
    from tests.conftest import test_session_maker
    from app.audit.logger import write_audit_log, verify_chain
    from app.models.audit import AuditLog

    async with test_session_maker() as session:
        entry = await write_audit_log(session=session, action="created", resource_type="test")
        await session.execute(
            update(AuditLog)
            .where(AuditLog.id == entry.id)
            .values(details={"tampered": True})
        )
        await session.commit()

        is_valid, count, error = await verify_chain(session)
        assert is_valid is False
        assert count == 0
        assert f"Entry {entry.id}: hash mismatch" in error


@pytest.mark.asyncio
async def test_write_audit_log_direct(client: AsyncClient):
    """Verify audit log entries can be written and read back."""
    from tests.conftest import test_session_maker
    from app.audit.logger import write_audit_log
    from sqlalchemy import select
    from app.models.audit import AuditLog

    async with test_session_maker() as session:
        await write_audit_log(
            session=session,
            action="test_middleware_replacement",
            resource_type="http_request",
            details={"method": "GET", "path": "/test", "status_code": 200},
        )

    async with test_session_maker() as session:
        result = await session.execute(
            select(AuditLog).where(AuditLog.action == "test_middleware_replacement")
        )
        entry = result.scalar_one_or_none()
        assert entry is not None
        assert entry.details["method"] == "GET"
        assert entry.details["status_code"] in (200, "200")


@pytest.mark.asyncio
async def test_audit_export_requires_admin(client: AsyncClient, staff_token: str):
    resp = await client.get(
        "/audit/export",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert resp.status_code == 403
