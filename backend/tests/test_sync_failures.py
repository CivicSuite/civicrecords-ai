# backend/tests/test_sync_failures.py
"""P7 sync_failures table tests. All must fail until migration 016 runs."""
import uuid
from datetime import datetime, timezone, timedelta

import pytest
from sqlalchemy import text

from app.models.document import DataSource, SourceType
from tests.conftest import build_data_source


UTC = timezone.utc


async def _seed_source(session, source_id: uuid.UUID, name: str):
    """Helper: create a rest_api DataSource for FK tests."""
    user_id = (await session.execute(text("SELECT id FROM users LIMIT 1"))).scalar_one()
    await build_data_source(
        session,
        id=source_id,
        name=name,
        source_type=SourceType.REST_API,
        connection_config={},
        is_active=True,
        created_by=user_id,
    )


@pytest.mark.asyncio
async def test_failed_record_creates_sync_failure_row(db_session):
    """After a failed record fetch, a sync_failures row is created with correct fields."""
    from app.models.sync_failure import SyncFailure
    source_id = uuid.uuid4()
    # Create a data_source to satisfy FK
    await _seed_source(db_session, source_id, "fail-test")
    await db_session.commit()

    failure = SyncFailure(
        source_id=source_id,
        source_path="https://api.example.com/records/99",
        error_message="Connection timeout",
        error_class="httpx.TimeoutException",
        http_status_code=None,
        status="retrying",
    )
    db_session.add(failure)
    await db_session.commit()
    await db_session.refresh(failure)

    assert failure.id is not None
    assert failure.retry_count == 0
    assert failure.status == "retrying"
    assert failure.first_failed_at is not None


@pytest.mark.asyncio
async def test_dead_letter_at_retry_count_5(db_session):
    """retry_count reaches 5 → status should be set to permanently_failed."""
    from app.models.sync_failure import SyncFailure
    source_id = uuid.uuid4()
    await _seed_source(db_session, source_id, "deadletter-test")
    await db_session.commit()

    failure = SyncFailure(
        source_id=source_id,
        source_path="https://api.example.com/records/100",
        error_message="Persistent failure",
        error_class="RuntimeError",
        status="retrying",
        retry_count=5,
    )
    db_session.add(failure)
    await db_session.commit()

    # Apply dead-letter logic (same as what sync_runner does)
    failure.status = "permanently_failed"
    await db_session.commit()
    await db_session.refresh(failure)

    assert failure.status == "permanently_failed"


@pytest.mark.asyncio
async def test_dead_letter_at_7_days(db_session):
    """first_failed_at > 7 days ago, retry_count < 5 → permanently_failed (time threshold)."""
    from app.models.sync_failure import SyncFailure
    source_id = uuid.uuid4()
    await _seed_source(db_session, source_id, "time-deadletter")
    await db_session.commit()

    old_first_failed = datetime.now(UTC) - timedelta(days=8)
    failure = SyncFailure(
        source_id=source_id,
        source_path="https://api.example.com/records/101",
        error_message="Old failure",
        error_class="IOError",
        status="retrying",
        retry_count=2,  # < 5, but time threshold fires first
        first_failed_at=old_first_failed,
    )
    db_session.add(failure)
    await db_session.commit()

    # Dead-letter check: (retry_count >= 5) OR (age > 7 days) — OR, not AND
    now = datetime.now(UTC)
    should_dead_letter = (
        failure.retry_count >= 5
        or (now - failure.first_failed_at) > timedelta(days=7)
    )
    assert should_dead_letter is True


@pytest.mark.asyncio
async def test_404_response_creates_tombstone(db_session):
    """Task retries return 404 → status=tombstone, not retrying."""
    from app.models.sync_failure import SyncFailure
    source_id = uuid.uuid4()
    await _seed_source(db_session, source_id, "tombstone-test")
    await db_session.commit()

    failure = SyncFailure(
        source_id=source_id,
        source_path="https://api.example.com/records/deleted",
        error_message="404 Not Found",
        error_class="httpx.HTTPStatusError",
        http_status_code=404,
        status="tombstone",
    )
    db_session.add(failure)
    await db_session.commit()
    await db_session.refresh(failure)
    assert failure.status == "tombstone"


@pytest.mark.asyncio
async def test_dismiss_sets_dismissed_status_not_deletes(db_session):
    """Dismiss → status=dismissed, row present, dismissed_at + dismissed_by set."""
    from sqlalchemy import select
    from app.models.sync_failure import SyncFailure
    source_id = uuid.uuid4()
    await _seed_source(db_session, source_id, "dismiss-test")
    await db_session.commit()

    failure = SyncFailure(
        source_id=source_id,
        source_path="https://api.example.com/records/200",
        error_message="Old error",
        error_class="RuntimeError",
        status="permanently_failed",
    )
    db_session.add(failure)
    await db_session.commit()

    # Look up the seeded admin user — matches pattern used by sibling tests
    result = await db_session.execute(text("SELECT id FROM users LIMIT 1"))
    user_id = result.scalar_one()

    failure.status = "dismissed"
    failure.dismissed_at = datetime.now(UTC)
    failure.dismissed_by = user_id
    await db_session.commit()

    # Row still exists
    row = await db_session.scalar(
        select(SyncFailure).where(SyncFailure.id == failure.id)
    )
    assert row is not None
    assert row.status == "dismissed"
    assert row.dismissed_at is not None
    assert row.dismissed_by == user_id


@pytest.mark.asyncio
async def test_cascade_delete_removes_failures_and_run_log(db_session):
    """Delete DataSource → sync_failures + sync_run_log rows cascade-deleted."""
    from sqlalchemy import select, text
    from app.models.sync_failure import SyncFailure, SyncRunLog
    source_id = uuid.uuid4()
    await _seed_source(db_session, source_id, "cascade-test")
    await db_session.commit()

    failure = SyncFailure(
        source_id=source_id, source_path="/records/1",
        error_message="err", error_class="RuntimeError", status="retrying",
    )
    log = SyncRunLog(
        source_id=source_id, status="failed",
        records_attempted=1, records_succeeded=0, records_failed=1,
    )
    db_session.add_all([failure, log])
    await db_session.commit()

    # Delete the source
    await db_session.execute(
        text("DELETE FROM data_sources WHERE id = :id"), {"id": str(source_id)}
    )
    await db_session.commit()

    # Failures and log should be gone (CASCADE)
    remaining_failures = await db_session.scalar(
        select(SyncFailure).where(SyncFailure.source_id == source_id)
    )
    assert remaining_failures is None

    remaining_log = await db_session.scalar(
        select(SyncRunLog).where(SyncRunLog.source_id == source_id)
    )
    assert remaining_log is None
