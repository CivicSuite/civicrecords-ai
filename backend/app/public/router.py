"""T5D public surface — authenticated records-request submission for residents.

This router is mounted under ``/public`` by :mod:`app.main` **only when**
``settings.portal_mode == "public"`` (see the import guard in ``main.py``).
In private-mode deployments the module is never imported, so every
``/public/*`` path returns 404.

Per Scott's 2026-04-22 Option A decision:

* **Authenticated submission only.** Residents self-register via
  ``POST /auth/register`` (also gated on public mode in :mod:`app.auth.router`),
  which creates a :class:`UserRole.PUBLIC` account. They sign in through
  the normal JWT flow and submit records requests as themselves. The
  ``created_by`` foreign key on :class:`RecordsRequest` is populated with
  the submitter's user id, preserving clean audit ownership.
* **No anonymous walk-up submission.** A non-nullable ``created_by`` on
  ``records_requests`` would require a schema migration to support
  anonymous submission; that was explicitly rejected as out of T5D scope
  on 2026-04-22.
* **PUBLIC-only.** Only users with ``UserRole.PUBLIC`` can call this
  endpoint. Staff-level roles submit through the existing
  ``/requests/`` staff workbench surface; routing them through the
  public endpoint would muddy the audit trail.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.logger import write_audit_log
from app.auth.dependencies import current_active_user
from app.database import get_async_session
from app.models.request import RecordsRequest, RequestStatus
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)

router = APIRouter()


class PublicRequestSubmitBody(BaseModel):
    """Minimal public submission payload.

    The authenticated ``UserRole.PUBLIC`` user's ``full_name`` and ``email``
    are reused for ``requester_name`` / ``requester_email`` (they already
    own that identity via self-registration). Only the free-form
    description and optional phone are collected here.
    """

    description: str = Field(
        min_length=10,
        max_length=10_000,
        description=(
            "Plain-language description of the records being requested. "
            "At least 10 characters; the staff reviewer reads this verbatim."
        ),
    )
    phone: str | None = Field(
        default=None,
        max_length=50,
        description="Optional contact phone number.",
    )


class PublicRequestSubmitResponse(BaseModel):
    """What the resident sees after submitting.

    The tracking id is the database UUID of the request — the resident
    can reference it when contacting the records office. Expanded
    track-my-request functionality (status page, timeline view,
    downloads) is explicitly out of T5D scope.
    """

    request_id: uuid.UUID
    status: RequestStatus
    submitted_at: datetime
    message: str


def _require_public_role(user: User = Depends(current_active_user)) -> User:
    """Accept only ``UserRole.PUBLIC`` users on this surface.

    Staff-level roles have their own ``/requests/`` routes; routing them
    through the public submission endpoint would produce audit-log
    entries that look like resident submissions when they are not.
    """
    if user.role != UserRole.PUBLIC:
        # 403 rather than 404: the endpoint exists (public mode), the
        # caller is authenticated, but the role is wrong. The message is
        # deliberately actionable — staff know they have a different
        # workflow.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "This endpoint is for resident (public) accounts only. "
                "Staff users submit records requests through the internal "
                "workbench at /requests/."
            ),
        )
    return user


@router.post(
    "/requests",
    response_model=PublicRequestSubmitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a records request as an authenticated resident.",
)
async def submit_public_request(
    body: PublicRequestSubmitBody,
    user: User = Depends(_require_public_role),
    session: AsyncSession = Depends(get_async_session),
) -> PublicRequestSubmitResponse:
    """Create a records request on behalf of the signed-in PUBLIC user.

    The request lands in :class:`RequestStatus.RECEIVED` with
    ``created_by`` = the authenticated resident's id. ``requester_name``
    and ``requester_email`` are copied from the user record so staff
    reviewers see the submitter's registered identity verbatim. An audit
    log entry is written with ``action="public.requests.create"`` for
    full traceability.
    """
    # Pull the submitter's identity from their account rather than the
    # request body. This is the whole point of Option A — we are not
    # trusting form-posted identity for anonymous submitters; we are
    # using the authenticated user record as the source of truth.
    full_name = (user.full_name or "").strip() or user.email

    req = RecordsRequest(
        requester_name=full_name[:255],
        requester_email=user.email,
        requester_phone=(body.phone or "").strip() or None,
        requester_type="public",
        description=body.description.strip(),
        status=RequestStatus.RECEIVED,
        created_by=user.id,
        priority="normal",
        fee_waiver_requested=False,
    )
    session.add(req)
    await session.flush()  # emits INSERT so req.id is populated before audit

    # write_audit_log issues its own session.commit(), which also commits the
    # pending INSERT for ``req``. After this call the request row is durable.
    await write_audit_log(
        session=session,
        user_id=user.id,
        action="public.requests.create",
        resource_type="records_request",
        resource_id=str(req.id),
        details={"via": "public-portal", "portal_mode": "public"},
    )

    await session.refresh(req)

    logger.info(
        "T5D public submission: request_id=%s submitter_id=%s len(desc)=%d",
        req.id,
        user.id,
        len(req.description),
    )

    return PublicRequestSubmitResponse(
        request_id=req.id,
        status=req.status,
        submitted_at=req.created_at or datetime.now(timezone.utc),
        message=(
            "Your request has been submitted. Save your tracking id to "
            "reference this request when contacting the records office."
        ),
    )
