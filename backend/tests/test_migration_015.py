"""Tests for migration 015 - schedule_minutes allowlist conversion."""
import pytest
from sqlalchemy import text

from app.models.document import DataSource, SourceType
from tests.conftest import build_data_source


_ALLOWLIST = {
    5:    "*/5 * * * *",
    15:   "*/15 * * * *",
    30:   "*/30 * * * *",
    60:   "0 * * * *",
    1440: "0 2 * * *",
}


@pytest.mark.asyncio
async def test_schedule_minutes_allowlist_converts_correctly(db_session):
    """schedule_minutes in allowlist -> correct cron expressions."""
    for minutes, expected_cron in [(15, "*/15 * * * *"), (1440, "0 2 * * *")]:
        cron = _ALLOWLIST.get(minutes)
        assert cron == expected_cron, f"minutes={minutes} -> expected {expected_cron}, got {cron}"


@pytest.mark.asyncio
async def test_schedule_minutes_non_allowlist_nulled_with_report(db_session):
    """schedule_minutes not in allowlist -> sync_schedule=NULL, schedule_enabled=False."""
    non_allowlist = [45, 90, 3, 100]
    for minutes in non_allowlist:
        assert minutes not in _ALLOWLIST, f"{minutes} should NOT be in allowlist"

    expected_keys = {5, 15, 30, 60, 1440}
    assert set(_ALLOWLIST.keys()) == expected_keys


@pytest.mark.asyncio
async def test_schedule_minutes_non_allowlist_nulled_integration(db_session):
    """End-to-end: seed source, apply logic, verify NULL + disabled."""
    import uuid

    await db_session.execute(text("""
        INSERT INTO users (id, email, hashed_password, full_name, role, is_active, is_superuser, is_verified)
        VALUES ('00000000-0000-0000-0000-000000000001', 'mig015-seed@test', 'x', 'Seed', 'admin', true, true, true)
        ON CONFLICT (id) DO NOTHING
    """))
    await db_session.commit()

    source_id = uuid.uuid4()
    user_id = (await db_session.execute(text("SELECT id FROM users LIMIT 1"))).scalar_one()
    await build_data_source(
        db_session,
        id=source_id,
        name="test-nonallowlist",
        source_type=SourceType.REST_API,
        connection_config={},
        is_active=True,
        created_by=user_id,
    )
    await db_session.commit()

    await db_session.execute(text("""
        UPDATE data_sources
        SET sync_schedule = NULL, schedule_enabled = false
        WHERE id = :id
    """), {"id": str(source_id)})
    await db_session.commit()

    row = await db_session.execute(
        text("SELECT sync_schedule, schedule_enabled FROM data_sources WHERE id = :id"),
        {"id": str(source_id)},
    )
    result = row.fetchone()
    assert result[0] is None
    assert result[1] is False
