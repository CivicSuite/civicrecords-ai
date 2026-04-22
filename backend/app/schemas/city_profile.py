import uuid
from datetime import datetime

from pydantic import BaseModel


class CityProfileCreate(BaseModel):
    city_name: str
    # T5A: state is optional on create so the onboarding interview can persist
    # after the first answer (city_name) without a placeholder value. The
    # POST /city-profile form-mode flow still sends state (FE validates) so
    # this is backward-compatible for the form path.
    state: str | None = None
    county: str | None = None
    population_band: str | None = None
    email_platform: str | None = None
    has_dedicated_it: bool | None = None
    monthly_request_volume: str | None = None
    profile_data: dict = {}
    gap_map: dict = {}


class CityProfileRead(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    city_name: str
    # T5A: state is nullable in the model; read schema must reflect that or
    # Pydantic raises on in-progress rows.
    state: str | None
    county: str | None
    population_band: str | None
    email_platform: str | None
    has_dedicated_it: bool | None
    monthly_request_volume: str | None
    onboarding_status: str
    profile_data: dict
    gap_map: dict
    created_at: datetime
    updated_at: datetime


class CityProfileUpdate(BaseModel):
    city_name: str | None = None
    state: str | None = None
    county: str | None = None
    population_band: str | None = None
    email_platform: str | None = None
    has_dedicated_it: bool | None = None
    monthly_request_volume: str | None = None
    onboarding_status: str | None = None
    profile_data: dict | None = None
    gap_map: dict | None = None
