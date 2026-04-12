import uuid
from datetime import datetime
from sqlalchemy import DateTime, String, Boolean, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.user import Base


class CityProfile(Base):
    __tablename__ = "city_profile"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    city_name: Mapped[str] = mapped_column(String(200))
    state: Mapped[str] = mapped_column(String(2))
    county: Mapped[str | None] = mapped_column(String(200))
    population_band: Mapped[str | None] = mapped_column(String(50))
    email_platform: Mapped[str | None] = mapped_column(String(50))
    has_dedicated_it: Mapped[bool | None] = mapped_column(Boolean)
    monthly_request_volume: Mapped[str | None] = mapped_column(String(20))
    onboarding_status: Mapped[str] = mapped_column(
        String(20), default="not_started"
    )  # not_started/in_progress/complete
    profile_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    gap_map: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
