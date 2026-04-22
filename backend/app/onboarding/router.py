"""Onboarding LLM-guided adaptive interview endpoint.

The interview endpoint walks a fixed list of CityProfile fields in priority
order. On each POST, if the caller supplies the previous answer, this
endpoint **persists that answer** onto the singleton CityProfile row
(creating the row on the first answer if none exists) and then generates
the next question for the first remaining empty field.

T5A (2026-04-22): this endpoint was previously pure-generation — the
frontend was expected to call PATCH /city-profile on its own to persist.
That split produced two failure modes:

  1. No profile exists yet: frontend PATCH returns 404 and the UI silently
     swallows the error. Answer is lost.
  2. ``has_dedicated_it`` was in the CityProfile model but never asked by
     the interview because it was missing from ``_PROFILE_FIELDS``.
  3. ``onboarding_status`` was never transitioned by the interview path;
     rows created via interview stayed ``not_started`` forever.

T5A closes all three gaps in the single place the flow should own: the
interview endpoint itself.
"""

import logging

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

# Fields the interview walks, in priority order. Order matters:
#   - ``city_name`` first because a CityProfile cannot be created without it.
#   - ``state`` next so the profile has a meaningful location record early.
#   - Remaining fields mirror the Onboarding form's step-1 layout so the two
#     modes feel like the same flow.
#
# Must stay in sync with ``app/models/city_profile.py`` field names.
_PROFILE_FIELDS: list[tuple[str, str]] = [
    ("city_name", "What is the name of your city or municipality?"),
    ("state", "Which US state is your municipality in? (two-letter code, e.g. CO)"),
    ("county", "What county is your municipality in?"),
    ("population_band", "What is your municipality's approximate population? (Under 5,000 / 5,000-25,000 / 25,000-100,000 / 100,000-500,000 / Over 500,000)"),
    ("email_platform", "What email platform does your municipality use? (Microsoft 365, Google Workspace, or other)"),
    # T5A: has_dedicated_it was present in the model but missing from the
    # interview walk. Answer is yes/no; ``_parse_answer`` normalizes to bool.
    ("has_dedicated_it", "Does your municipality have a dedicated IT department? (yes or no)"),
    ("monthly_request_volume", "How many public records requests does your office handle per month on average?"),
]

_FIELD_NAMES: set[str] = {name for name, _ in _PROFILE_FIELDS}

_YES_ANSWERS: frozenset[str] = frozenset({"yes", "y", "true", "1"})
_NO_ANSWERS: frozenset[str] = frozenset({"no", "n", "false", "0"})


_SYSTEM_PROMPT = """You are a friendly municipal records system setup assistant. Your job is
to help a city clerk configure CivicRecords AI for their municipality.

Ask ONE question at a time. Be conversational but concise. If the user's
previous answer was unclear, ask a brief clarifying follow-up. Otherwise,
move to the next incomplete field.

Do NOT update any settings yourself — just ask the question and wait for the answer.
Keep responses under 3 sentences."""


class InterviewRequest(BaseModel):
    last_answer: str | None = None
    last_field: str | None = None
    # T5A skip-truth: fields the operator chose to skip in this walk. Server
    # does not persist anything for these — they stay null in the DB and keep
    # onboarding_status in_progress until answered via a later turn or the
    # Manual Form. Honoring this list in the walk makes the Skip button
    # actually advance instead of silently re-asking the same question.
    skipped_fields: list[str] | None = None


class InterviewResponse(BaseModel):
    question: str
    target_field: str | None  # The profile field this question targets, or None if all complete
    all_complete: bool
    completed_fields: list[str]
    # T5A: surface the lifecycle state so the frontend (and test suite) can
    # assert on transitions without a separate GET /city-profile round-trip.
    onboarding_status: str
    # T5A skip-truth: echo back which fields the walk is currently ignoring.
    # Lets the client render a truthful closure when every non-skipped field
    # is populated but skipped fields remain empty.
    skipped_fields: list[str]


def _parse_answer(field_name: str, raw: str) -> object | None:
    """Normalize a text answer into the value the CityProfile column expects.

    Returns ``None`` if the raw answer is empty/whitespace or — for the
    boolean ``has_dedicated_it`` field — unparseable as yes/no. A ``None``
    return tells the caller not to persist this turn; the interview will
    re-ask the same field rather than store a garbage value.
    """
    if raw is None:
        return None
    stripped = raw.strip()
    if not stripped:
        return None
    if field_name == "has_dedicated_it":
        lowered = stripped.lower()
        if lowered in _YES_ANSWERS:
            return True
        if lowered in _NO_ANSWERS:
            return False
        return None  # unparseable — don't persist, re-ask
    return stripped


def _compute_status(profile: CityProfile | None) -> str:
    """Derive the onboarding_status from the row's populated fields.

    - No profile row OR every tracked field empty: ``not_started``.
    - At least one tracked field populated but not all: ``in_progress``.
    - Every field in ``_PROFILE_FIELDS`` populated: ``complete``.
    """
    if profile is None:
        return "not_started"
    populated = 0
    for field_name, _ in _PROFILE_FIELDS:
        value = getattr(profile, field_name, None)
        if field_name == "has_dedicated_it":
            # Boolean; count True/False as populated, None as empty.
            if value is not None:
                populated += 1
        else:
            if value is not None and str(value).strip():
                populated += 1
    if populated == 0:
        return "not_started"
    if populated == len(_PROFILE_FIELDS):
        return "complete"
    return "in_progress"


async def _persist_answer(
    session: AsyncSession,
    profile: CityProfile | None,
    field_name: str,
    value: object,
    user_id,
) -> CityProfile:
    """Create or update the singleton CityProfile with ``field_name=value``.

    Returns the persisted row (refreshed). Requires that ``field_name`` is a
    real CityProfile column — caller validates against ``_FIELD_NAMES``.
    """
    if profile is None:
        # First answer. city_name is the only valid first field (and the
        # caller has validated against _PROFILE_FIELDS order via the walk).
        if field_name != "city_name":
            # Defensive: the walk always asks city_name first, but if the
            # client somehow POSTs a different last_field with no existing
            # profile, create with that field and a placeholder city_name
            # would be a lie. Reject by not creating — caller should re-ask.
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
    profile.onboarding_status = _compute_status_after_set(profile, field_name, value)
    await session.commit()
    await session.refresh(profile)
    return profile


def _compute_status_after_set(profile: CityProfile, field_name: str, value: object) -> str:
    """Compute onboarding_status given a row AND the field we just set.

    Separated from ``_compute_status`` because SQLAlchemy may not see the
    unflushed attribute yet when we query during the same request; the
    caller has the canonical value in hand.
    """
    # Build a view of populated-ness using the row plus the in-flight update.
    populated = 0
    for fname, _ in _PROFILE_FIELDS:
        if fname == field_name:
            current_value = value
        else:
            current_value = getattr(profile, fname, None)
        if fname == "has_dedicated_it":
            if current_value is not None:
                populated += 1
        else:
            if current_value is not None and str(current_value).strip():
                populated += 1
    if populated == 0:
        return "not_started"
    if populated == len(_PROFILE_FIELDS):
        return "complete"
    return "in_progress"


@router.post("/interview", response_model=InterviewResponse)
async def get_next_question(
    body: InterviewRequest,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Generate the next onboarding interview question and persist the last answer.

    Persistence semantics (T5A):
      - If ``last_answer`` + ``last_field`` are supplied AND ``last_field`` is
        a real tracked CityProfile field: parse the answer (yes/no → bool for
        ``has_dedicated_it``), upsert the singleton row, and transition
        ``onboarding_status``.
      - If parsing yields ``None`` (empty or unparseable): the interview
        re-asks the same field rather than storing a bad value.
      - Returns the next question for the first remaining empty field, along
        with the computed ``onboarding_status``.
    """
    result = await session.execute(select(CityProfile).limit(1))
    profile = result.scalar_one_or_none()

    # ── Persist the previous answer, if provided and valid ──────────────
    if body.last_field and body.last_field in _FIELD_NAMES and body.last_answer is not None:
        parsed = _parse_answer(body.last_field, body.last_answer)
        if parsed is not None:
            profile = await _persist_answer(
                session, profile, body.last_field, parsed, user.id
            )
        # parsed is None → the answer was empty/unparseable; fall through to
        # re-ask the same field below.

    # ── Determine completion (skip-aware walk) ──────────────────────────
    # T5A skip-truth: `skipped_fields` in the request tells us which fields
    # the operator elected to pass over in this walk. We do NOT persist for
    # them and we do NOT offer them as the next question. They stay null in
    # the DB and keep `onboarding_status` at `in_progress`.
    skipped_set = set(body.skipped_fields or [])
    # A field cannot be both "populated" and "skipped" in any meaningful
    # sense — if it's populated, it's not skipped anymore. Drop any skips
    # that have since been answered (via form mode, say) so the echoed list
    # reflects only genuinely-empty skips.
    completed: list[str] = []
    next_field: str | None = None
    next_default_question: str | None = None

    for field_name, default_question in _PROFILE_FIELDS:
        value = getattr(profile, field_name, None) if profile else None
        is_populated = (
            (field_name == "has_dedicated_it" and value is not None)
            or (field_name != "has_dedicated_it" and value is not None and str(value).strip())
        )
        if is_populated:
            completed.append(field_name)
            skipped_set.discard(field_name)
        elif field_name in skipped_set:
            continue  # walk past — do not offer as next question
        elif next_field is None:
            next_field = field_name
            next_default_question = default_question

    status_value = _compute_status(profile)
    skipped_list = [f for f in (body.skipped_fields or []) if f in skipped_set]
    all_complete = len(completed) == len(_PROFILE_FIELDS)

    if next_field is None:
        # Two sub-cases:
        #  (a) every field genuinely populated  → all_complete=True.
        #  (b) every non-skipped field populated but skips remain empty →
        #      all_complete=False; closure message lists the skipped fields
        #      so the operator knows onboarding is not done yet.
        if all_complete:
            closure = "Your city profile is complete! You can review your settings on the City Profile page."
        else:
            closure = (
                "You skipped: "
                + ", ".join(skipped_list)
                + ". Switch to Manual Form to fill them in, or restart the guided interview to revisit them."
            )
        return InterviewResponse(
            question=closure,
            target_field=None,
            all_complete=all_complete,
            completed_fields=completed,
            onboarding_status=status_value,
            skipped_fields=skipped_list,
        )

    # ── Generate the next question via LLM, with a default fallback ─────
    context_parts = [f"Completed fields: {', '.join(completed) if completed else 'none yet'}"]
    if profile and profile.city_name:
        context_parts.append(f"City: {profile.city_name}")
    if body.last_answer and body.last_field:
        context_parts.append(f"User just answered '{body.last_answer}' for the '{body.last_field}' field")
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
