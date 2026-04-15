"""Tests for deadline notification Celery beat tasks.

Tests call the core async logic (check_deadline_approaching / check_deadline_overdue)
directly via test_session_maker — no Celery task infrastructure needed.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from httpx import AsyncClient

from app.models.request import RecordsRequest, RequestStatus
from app.models.notifications import NotificationLog, NotificationTemplate
from app.models.user import User
from app.requests.deadline_check import (
    check_deadline_approaching,
    check_deadline_overdue,
)
from tests.conftest import test_session_maker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _seed_deadline_templates(session) -> None:
    """Ensure both deadline templates exist in the test DB."""
    templates = [
        {
            "event_type": "request_deadline_approaching",
            "channel": "email",
            "subject_template": "Deadline Approaching — Records Request {request_id}",
            "body_template": (
                "Records request {request_id} has a statutory deadline approaching "
                "within 3 days. Please ensure all responsive documents have been "
                "reviewed and a response is prepared."
            ),
        },
        {
            "event_type": "request_deadline_overdue",
            "channel": "email",
            "subject_template": "OVERDUE — Records Request {request_id}",
            "body_template": (
                "Records request {request_id} is past its statutory deadline. "
                "Immediate action is required. Please contact your supervisor if "
                "you need assistance completing this request."
            ),
        },
    ]
    for tmpl in templates:
        existing = await session.execute(
            select(NotificationTemplate).where(
                NotificationTemplate.event_type == tmpl["event_type"]
            )
        )
        if existing.scalar_one_or_none():
            continue
        result = await session.execute(select(User).limit(1))
        user = result.scalar_one_or_none()
        session.add(NotificationTemplate(**tmpl, is_active=True, created_by=user.id if user else None))
    await session.commit()


async def _create_staff_user(session) -> User:
    """Create a staff user with a unique email for use as assigned_to."""
    from app.models.user import UserRole
    user = User(
        id=uuid.uuid4(),
        email=f"staff-deadline-{uuid.uuid4().hex[:8]}@test.gov",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
        is_verified=True,
        role=UserRole.STAFF,
    )
    session.add(user)
    await session.flush()
    return user


async def _create_request(session, *, deadline: datetime, status=RequestStatus.RECEIVED, assigned_to=None) -> RecordsRequest:
    """Create a RecordsRequest with the given deadline and optional assigned_to."""
    result = await session.execute(select(User).limit(1))
    creator = result.scalar_one()
    req = RecordsRequest(
        id=uuid.uuid4(),
        requester_name="Test Requester",
        requester_email="requester@example.com",
        description="Test request for deadline notification",
        status=status,
        statutory_deadline=deadline,
        assigned_to=assigned_to,
        created_by=creator.id,
    )
    session.add(req)
    await session.flush()
    return req


# ---------------------------------------------------------------------------
# check_deadline_approaching tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_approaching_fires_for_request_within_3_days(client: AsyncClient, admin_token: str):
    """check_deadline_approaching queues a notification for a request due in 2 days."""
    now = datetime.now(timezone.utc)
    async with test_session_maker() as session:
        await _seed_deadline_templates(session)
        staff = await _create_staff_user(session)
        req = await _create_request(session, deadline=now + timedelta(days=2), assigned_to=staff.id)
        await session.commit()

        result = await check_deadline_approaching(session)
        await session.commit()

    assert result["notified"] >= 1

    async with test_session_maker() as session:
        log = await session.execute(
            select(NotificationLog)
            .join(NotificationTemplate, NotificationLog.template_id == NotificationTemplate.id)
            .where(
                NotificationLog.request_id == req.id,
                NotificationTemplate.event_type == "request_deadline_approaching",
                NotificationLog.status == "queued",
            )
        )
        assert log.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_approaching_skips_request_outside_window(client: AsyncClient, admin_token: str):
    """check_deadline_approaching ignores requests due in more than 3 days."""
    now = datetime.now(timezone.utc)
    async with test_session_maker() as session:
        await _seed_deadline_templates(session)
        staff = await _create_staff_user(session)
        req = await _create_request(session, deadline=now + timedelta(days=5), assigned_to=staff.id)
        await session.commit()

        await check_deadline_approaching(session)
        await session.commit()

    async with test_session_maker() as session:
        log = await session.execute(
            select(NotificationLog)
            .join(NotificationTemplate, NotificationLog.template_id == NotificationTemplate.id)
            .where(
                NotificationLog.request_id == req.id,
                NotificationTemplate.event_type == "request_deadline_approaching",
            )
        )
        assert log.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_approaching_skips_fulfilled_request(client: AsyncClient, admin_token: str):
    """check_deadline_approaching ignores FULFILLED requests."""
    now = datetime.now(timezone.utc)
    async with test_session_maker() as session:
        await _seed_deadline_templates(session)
        staff = await _create_staff_user(session)
        req = await _create_request(
            session,
            deadline=now + timedelta(days=1),
            status=RequestStatus.FULFILLED,
            assigned_to=staff.id,
        )
        await session.commit()

        await check_deadline_approaching(session)
        await session.commit()

    async with test_session_maker() as session:
        log = await session.execute(
            select(NotificationLog).where(NotificationLog.request_id == req.id)
        )
        assert log.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_approaching_deduplicates_within_23_hours(client: AsyncClient, admin_token: str):
    """Calling check_deadline_approaching twice in a row produces only 1 log row."""
    now = datetime.now(timezone.utc)
    async with test_session_maker() as session:
        await _seed_deadline_templates(session)
        staff = await _create_staff_user(session)
        req = await _create_request(session, deadline=now + timedelta(days=2), assigned_to=staff.id)
        await session.commit()

        await check_deadline_approaching(session)
        await session.commit()
        await check_deadline_approaching(session)
        await session.commit()

    async with test_session_maker() as session:
        logs = await session.execute(
            select(NotificationLog)
            .join(NotificationTemplate, NotificationLog.template_id == NotificationTemplate.id)
            .where(
                NotificationLog.request_id == req.id,
                NotificationTemplate.event_type == "request_deadline_approaching",
            )
        )
        rows = logs.scalars().all()
        assert len(rows) == 1, f"Expected 1 log row, got {len(rows)}"


# ---------------------------------------------------------------------------
# check_deadline_overdue tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_overdue_fires_for_past_deadline(client: AsyncClient, admin_token: str):
    """check_deadline_overdue queues a notification for a request that missed its deadline."""
    now = datetime.now(timezone.utc)
    async with test_session_maker() as session:
        await _seed_deadline_templates(session)
        staff = await _create_staff_user(session)
        req = await _create_request(session, deadline=now - timedelta(days=1), assigned_to=staff.id)
        await session.commit()

        result = await check_deadline_overdue(session)
        await session.commit()

    assert result["notified"] >= 1

    async with test_session_maker() as session:
        log = await session.execute(
            select(NotificationLog)
            .join(NotificationTemplate, NotificationLog.template_id == NotificationTemplate.id)
            .where(
                NotificationLog.request_id == req.id,
                NotificationTemplate.event_type == "request_deadline_overdue",
                NotificationLog.status == "queued",
            )
        )
        assert log.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_overdue_skips_future_deadline(client: AsyncClient, admin_token: str):
    """check_deadline_overdue ignores requests with a future deadline."""
    now = datetime.now(timezone.utc)
    async with test_session_maker() as session:
        await _seed_deadline_templates(session)
        staff = await _create_staff_user(session)
        req = await _create_request(session, deadline=now + timedelta(days=1), assigned_to=staff.id)
        await session.commit()

        await check_deadline_overdue(session)
        await session.commit()

    async with test_session_maker() as session:
        log = await session.execute(
            select(NotificationLog)
            .join(NotificationTemplate, NotificationLog.template_id == NotificationTemplate.id)
            .where(
                NotificationLog.request_id == req.id,
                NotificationTemplate.event_type == "request_deadline_overdue",
            )
        )
        assert log.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_overdue_skips_closed_request(client: AsyncClient, admin_token: str):
    """check_deadline_overdue ignores CLOSED requests."""
    now = datetime.now(timezone.utc)
    async with test_session_maker() as session:
        await _seed_deadline_templates(session)
        staff = await _create_staff_user(session)
        req = await _create_request(
            session,
            deadline=now - timedelta(days=1),
            status=RequestStatus.CLOSED,
            assigned_to=staff.id,
        )
        await session.commit()

        await check_deadline_overdue(session)
        await session.commit()

    async with test_session_maker() as session:
        log = await session.execute(
            select(NotificationLog).where(NotificationLog.request_id == req.id)
        )
        assert log.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_overdue_deduplicates_within_23_hours(client: AsyncClient, admin_token: str):
    """Calling check_deadline_overdue twice in a row produces only 1 log row."""
    now = datetime.now(timezone.utc)
    async with test_session_maker() as session:
        await _seed_deadline_templates(session)
        staff = await _create_staff_user(session)
        req = await _create_request(session, deadline=now - timedelta(days=1), assigned_to=staff.id)
        await session.commit()

        await check_deadline_overdue(session)
        await session.commit()
        await check_deadline_overdue(session)
        await session.commit()

    async with test_session_maker() as session:
        logs = await session.execute(
            select(NotificationLog)
            .join(NotificationTemplate, NotificationLog.template_id == NotificationTemplate.id)
            .where(
                NotificationLog.request_id == req.id,
                NotificationTemplate.event_type == "request_deadline_overdue",
            )
        )
        rows = logs.scalars().all()
        assert len(rows) == 1, f"Expected 1 log row, got {len(rows)}"


@pytest.mark.asyncio
async def test_skips_request_with_no_assigned_user(client: AsyncClient, admin_token: str):
    """Both tasks skip requests with no assigned_to — no recipient, no notification."""
    now = datetime.now(timezone.utc)
    async with test_session_maker() as session:
        await _seed_deadline_templates(session)
        req_approaching = await _create_request(
            session, deadline=now + timedelta(days=2), assigned_to=None
        )
        req_overdue = await _create_request(
            session, deadline=now - timedelta(days=1), assigned_to=None
        )
        await session.commit()

        await check_deadline_approaching(session)
        await check_deadline_overdue(session)
        await session.commit()

    async with test_session_maker() as session:
        for req_id in [req_approaching.id, req_overdue.id]:
            log = await session.execute(
                select(NotificationLog).where(NotificationLog.request_id == req_id)
            )
            assert log.scalar_one_or_none() is None, \
                f"Expected no notification for unassigned request {req_id}"
