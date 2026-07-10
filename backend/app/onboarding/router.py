"""Onboarding LLM-guided adaptive interview endpoint.

The interview endpoint walks a shared list of CityProfile fields in priority
order. On each POST, if the caller supplies the previous answer, this
endpoint persists that answer onto the singleton CityProfile row
(creating the row on the first answer if none exists) and then generates
the next question for the first remaining empty field.

T5A (2026-04-22): this endpoint was previously pure-generation; the
frontend was expected to call PATCH /city-profile on its own to persist.
That split produced three failure modes:

1. No profile exists yet: frontend PATCH returns 404 and the UI silently
   swallows the error. Answer is lost.
2. ``has_dedicated_it`` was in the CityProfile model but never asked by
   the interview because it was missing from the tracked field walk.
3. ``onboarding_status`` was never transitioned by the interview path;
   rows created via interview stayed ``not_started`` forever.

The shared ``civiccore.onboarding`` helpers now own the field order,
normalization, completion-state calculation, and skip-aware next-question
selection so this router does not drift from the rest of the suite.
"""

from __future__ import annotations

import logging

from civiccore.onboarding import (
    DEFAULT_PROFILE_FIELDS,
    compute_onboarding_status,
    next_profile_prompt,
    parse_profile_answer,
)
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.database import get_async_session
from app.llm.client import generate
from app.models.city_profile import CityProfile
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

_FIELD_NAMES: set[str] = {field.name for field in DEFAULT_PROFILE_FIELDS}

_SYSTEM_PROMPT = """You are a friendly municipal records system setup assistant. Your job is
to help a city clerk configure CivicSunshine for their municipality.

Ask ONE question at a time. Be conversational but concise. If the user's
previous answer was unclear, ask a brief clarifying follow-up. Otherwise,
move to the next incomplete field.

Do NOT update any settings yourself - just ask the question and wait for the answer.
Keep responses under 3 sentences."""


class InterviewRequest(BaseModel):
    last_answer: str | None = None
    last_field: str | None = None
    # T5A skip-truth: fields the operator chose to skip in this walk. Server
    # does not persist anything for these; they stay null in the DB and keep
    # onboarding_status in_progress until answered via a later turn or the
    # manual form.
    skipped_fields: list[str] | None = None


class InterviewResponse(BaseModel):
    question: str
    target_field: str | None
    all_complete: bool
    completed_fields: list[str]
    onboarding_status: str
    skipped_fields: list[str]


async def _persist_answer(
    session: AsyncSession,
    profile: CityProfile | None,
    field_name: str,
    value: object,
    user_id,
) -> CityProfile:
    """Create or update the singleton CityProfile with ``field_name=value``."""

    if profile is None:
        if field_name != "city_name":
            logger.warning(
                "Onboarding interview received answer for %r with no existing profile; "
                "only %r can create the row. Skipping persistence.",
                field_name,
                "city_name",
            )
            return profile  # type: ignore[return-value]
        profile = CityProfile(city_name=value, updated_by=user_id)  # type: ignore[arg-type]
        session.add(profile)
    else:
        setattr(profile, field_name, value)
        profile.updated_by = user_id

    profile.onboarding_status = compute_onboarding_status(profile)
    await session.commit()
    await session.refresh(profile)
    return profile


@router.post("/interview", response_model=InterviewResponse)
async def get_next_question(
    body: InterviewRequest,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Generate the next onboarding question and persist the last answer."""

    result = await session.execute(select(CityProfile).limit(1))
    profile = result.scalar_one_or_none()

    if body.last_field and body.last_field in _FIELD_NAMES and body.last_answer is not None:
        parsed = parse_profile_answer(body.last_field, body.last_answer)
        if parsed is not None:
            profile = await _persist_answer(session, profile, body.last_field, parsed, user.id)

    progress = next_profile_prompt(profile, skipped_fields=body.skipped_fields or [])
    completed = list(progress.completed_fields)
    skipped_list = list(progress.skipped_fields)
    status_value = compute_onboarding_status(profile)
    next_field = progress.next_field
    next_default_question = progress.next_question

    if next_field is None:
        if progress.all_complete:
            closure = (
                "Your city profile is complete! You can review your settings on the "
                "City Profile page."
            )
        else:
            closure = (
                "You skipped: "
                + ", ".join(skipped_list)
                + ". Switch to Manual Form to fill them in, or restart the guided "
                "interview to revisit them."
            )
        return InterviewResponse(
            question=closure,
            target_field=None,
            all_complete=progress.all_complete,
            completed_fields=completed,
            onboarding_status=status_value,
            skipped_fields=skipped_list,
        )

    context_parts = [f"Completed fields: {', '.join(completed) if completed else 'none yet'}"]
    if profile and profile.city_name:
        context_parts.append(f"City: {profile.city_name}")
    if body.last_answer and body.last_field:
        context_parts.append(
            f"User just answered '{body.last_answer}' for the '{body.last_field}' field"
        )
    context_parts.append(f"Next field to ask about: {next_field}")
    context_parts.append(f"Default question: {next_default_question}")

    try:
        question = await generate(
            system_prompt=_SYSTEM_PROMPT,
            user_content="\n".join(context_parts),
        )
        if not question.strip():
            question = next_default_question
    except Exception:
        logger.exception("LLM interview question generation failed")
        question = next_default_question

    return InterviewResponse(
        question=question.strip() if question else next_default_question,
        target_field=next_field,
        all_complete=False,
        completed_fields=completed,
        onboarding_status=status_value,
        skipped_fields=skipped_list,
    )
