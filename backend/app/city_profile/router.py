"""City profile router.

Design decision (T2A, 2026-04-19): city-profile is intentionally NOT
department-scoped. The resource is a singleton per deployment — one row
describing the entire city — and is shared configuration, not department-owned
data. Access control:

- GET  /city-profile  — any authenticated STAFF role or higher (read).
- POST /city-profile  — ADMIN only (create the single row).
- PATCH /city-profile — ADMIN only (update the single row).

``require_department_scope`` is deliberately not applied here. Forcing it
onto a null-department global record would be false rigor. If city-profile
ever becomes department-partitioned in the future, this docstring should be
updated in the same commit as the model change.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.logger import write_audit_log
from app.auth.dependencies import UserRole, require_role
from app.database import get_async_session
from app.models.city_profile import CityProfile
from app.schemas.city_profile import CityProfileCreate, CityProfileRead, CityProfileUpdate

router = APIRouter(tags=["city-profile"])


@router.get("/city-profile", response_model=CityProfileRead | None)
async def get_city_profile(
    session: AsyncSession = Depends(get_async_session),
    user=Depends(require_role(UserRole.STAFF)),
):
    result = await session.execute(select(CityProfile).limit(1))
    profile = result.scalar_one_or_none()
    return profile


@router.post("/city-profile", response_model=CityProfileRead, status_code=201)
async def create_city_profile(
    data: CityProfileCreate,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(require_role(UserRole.ADMIN)),
):
    # Only one profile per instance
    existing = await session.execute(select(CityProfile).limit(1))
    if existing.scalar_one_or_none():
        raise HTTPException(409, "City profile already exists. Use PATCH to update.")

    profile = CityProfile(
        city_name=data.city_name,
        state=data.state,
        county=data.county,
        population_band=data.population_band,
        email_platform=data.email_platform,
        has_dedicated_it=data.has_dedicated_it,
        monthly_request_volume=data.monthly_request_volume,
        onboarding_status="complete",
        profile_data=data.profile_data,
        gap_map=data.gap_map,
        updated_by=user.id,
    )
    session.add(profile)
    await session.commit()
    await session.refresh(profile)

    await write_audit_log(
        session, "city_profile_created", "city_profile", str(profile.id), user.id, {}
    )
    return profile


@router.patch("/city-profile", response_model=CityProfileRead)
async def update_city_profile(
    data: CityProfileUpdate,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(require_role(UserRole.ADMIN)),
):
    result = await session.execute(select(CityProfile).limit(1))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(404, "No city profile exists. Use POST to create one.")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(profile, key, value)
    profile.updated_by = user.id

    await session.commit()
    await session.refresh(profile)

    await write_audit_log(
        session,
        "city_profile_updated",
        "city_profile",
        str(profile.id),
        user.id,
        update_data,
    )
    return profile
