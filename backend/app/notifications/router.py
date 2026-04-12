import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.logger import write_audit_log
from app.auth.dependencies import UserRole, require_role
from app.database import get_async_session
from app.models.notifications import NotificationLog, NotificationTemplate
from app.schemas.notifications import (
    NotificationLogRead,
    NotificationTemplateCreate,
    NotificationTemplateRead,
    NotificationTemplateUpdate,
)

router = APIRouter(tags=["notifications"])


@router.get("/notifications/templates", response_model=list[NotificationTemplateRead])
async def list_templates(
    session: AsyncSession = Depends(get_async_session),
    user=Depends(require_role(UserRole.STAFF)),
):
    """List all notification templates."""
    result = await session.execute(
        select(NotificationTemplate).order_by(NotificationTemplate.event_type)
    )
    return result.scalars().all()


@router.post(
    "/notifications/templates",
    response_model=NotificationTemplateRead,
    status_code=201,
)
async def create_template(
    payload: NotificationTemplateCreate,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(require_role(UserRole.ADMIN)),
):
    """Create a new notification template (admin only)."""
    # Check for duplicate event_type
    existing = await session.execute(
        select(NotificationTemplate).where(
            NotificationTemplate.event_type == payload.event_type
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"Template for event_type '{payload.event_type}' already exists",
        )

    template = NotificationTemplate(
        event_type=payload.event_type,
        channel=payload.channel,
        subject_template=payload.subject_template,
        body_template=payload.body_template,
        created_by=user.id,
    )
    session.add(template)
    await session.flush()

    await write_audit_log(
        session=session,
        action="create_notification_template",
        resource_type="notification_template",
        resource_id=str(template.id),
        user_id=user.id,
        details={"event_type": payload.event_type, "channel": payload.channel},
    )
    await session.commit()
    await session.refresh(template)
    return template


@router.patch(
    "/notifications/templates/{template_id}",
    response_model=NotificationTemplateRead,
)
async def update_template(
    template_id: uuid.UUID,
    payload: NotificationTemplateUpdate,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(require_role(UserRole.ADMIN)),
):
    """Update a notification template (admin only)."""
    template = await session.get(NotificationTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    changes: dict = {}
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(template, field, value)
        changes[field] = value

    if not changes:
        raise HTTPException(status_code=400, detail="No fields to update")

    await write_audit_log(
        session=session,
        action="update_notification_template",
        resource_type="notification_template",
        resource_id=str(template.id),
        user_id=user.id,
        details=changes,
    )
    await session.commit()
    await session.refresh(template)
    return template


@router.get("/notifications/log", response_model=list[NotificationLogRead])
async def list_notification_log(
    limit: int = Query(default=50, le=200),
    request_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_async_session),
    user=Depends(require_role(UserRole.STAFF)),
):
    """List recent notification log entries."""
    query = select(NotificationLog).order_by(NotificationLog.created_at.desc())
    if request_id:
        query = query.where(NotificationLog.request_id == request_id)
    query = query.limit(limit)
    result = await session.execute(query)
    return result.scalars().all()
