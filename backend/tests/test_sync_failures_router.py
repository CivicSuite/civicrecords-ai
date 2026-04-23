# backend/tests/test_sync_failures_router.py
"""P7 sync-failures API endpoint tests."""
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import text, select, func

from app.models.document import DataSource, SourceType
from tests.conftest import build_data_source


async def _seed_source(session, source_id: uuid.UUID, name: str, **extra):
    user_id = (await session.execute(text("SELECT id FROM users LIMIT 1"))).scalar_one()
    await build_data_source(
        session,
        id=source_id,
        name=name,
        source_type=SourceType.REST_API,
        connection_config={},
        is_active=True,
        created_by=user_id,
        **extra,
    )


@pytest.mark.asyncio
async def test_retry_all_permanently_failed(client: AsyncClient, admin_token: str, db_session):
    """retry-all resets permanently_failed rows to retrying."""
    from app.models.sync_failure import SyncFailure

    source_id = uuid.uuid4()
    await _seed_source(db_session, source_id, "bulk-retry")
    await db_session.commit()

    for i in range(3):
        db_session.add(SyncFailure(
            source_id=source_id,
            source_path=f"/records/{i}",
            error_message="err", error_class="RuntimeError",
            status="permanently_failed",
        ))
    await db_session.commit()

    resp = await client.post(
        f"/datasources/{source_id}/sync-failures/retry-all?status=permanently_failed",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["updated"] == 3

    # Verify DB state
    db_session.expire_all()
    count = await db_session.scalar(
        select(func.count(SyncFailure.id)).where(
            SyncFailure.source_id == source_id,
            SyncFailure.status == "retrying",
        )
    )
    assert count == 3


@pytest.mark.asyncio
async def test_dismiss_all_permanently_failed(client: AsyncClient, admin_token: str, db_session):
    """dismiss-all soft-deletes permanently_failed rows (status=dismissed, dismissed_at set)."""
    from app.models.sync_failure import SyncFailure

    source_id = uuid.uuid4()
    await _seed_source(db_session, source_id, "bulk-dismiss")
    await db_session.commit()

    for i in range(2):
        db_session.add(SyncFailure(
            source_id=source_id,
            source_path=f"/records/{i}",
            error_message="err", error_class="RuntimeError",
            status="permanently_failed",
        ))
    await db_session.commit()

    resp = await client.post(
        f"/datasources/{source_id}/sync-failures/dismiss-all?status=permanently_failed",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["updated"] == 2

    db_session.expire_all()
    rows = (await db_session.execute(
        select(SyncFailure).where(SyncFailure.source_id == source_id)
    )).scalars().all()
    assert all(r.status == "dismissed" for r in rows)
    assert all(r.dismissed_at is not None for r in rows)


@pytest.mark.asyncio
async def test_list_sync_failures_requires_auth(client: AsyncClient):
    """GET /datasources/{id}/sync-failures without auth returns 401."""
    resp = await client.get(f"/datasources/{uuid.uuid4()}/sync-failures")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_unpause_source(client: AsyncClient, admin_token: str, db_session):
    """POST /datasources/{id}/unpause resets paused state."""
    from app.models.document import DataSource

    source_id = uuid.uuid4()
    await _seed_source(
        db_session,
        source_id,
        "unpause-test",
        sync_paused=True,
        consecutive_failure_count=5,
        sync_paused_reason="Circuit open after 5 failures",
    )
    await db_session.commit()

    resp = await client.post(
        f"/datasources/{source_id}/unpause",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["grace_period"] is True

    db_session.expire_all()
    source = await db_session.get(DataSource, source_id)
    assert source.sync_paused is False
    assert source.consecutive_failure_count == 0
    # Unpause sets sync_paused_reason to 'grace_period' sentinel — drops next-sync
    # circuit-open threshold from 5 to 2 (see sync_failures_router.unpause_source).
    assert source.sync_paused_reason == "grace_period"


@pytest.mark.asyncio
async def test_list_sync_failures_filters_by_status(client: AsyncClient, admin_token: str, db_session):
    """GET /datasources/{id}/sync-failures?status=retrying returns only retrying rows."""
    from app.models.sync_failure import SyncFailure

    source_id = uuid.uuid4()
    await _seed_source(db_session, source_id, "filter-test")
    await db_session.commit()

    db_session.add(SyncFailure(source_id=source_id, source_path="/r/1",
                               error_message="e", error_class="IOError", status="retrying"))
    db_session.add(SyncFailure(source_id=source_id, source_path="/r/2",
                               error_message="e", error_class="IOError", status="permanently_failed"))
    await db_session.commit()

    resp = await client.get(
        f"/datasources/{source_id}/sync-failures?status=retrying",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["status"] == "retrying"
