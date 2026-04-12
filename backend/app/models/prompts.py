import uuid
from datetime import datetime
from sqlalchemy import DateTime, String, Text, Boolean, Integer, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.user import Base


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    purpose: Mapped[str] = mapped_column(String(50))
    # search_synthesis, exemption_scan, scope_assessment,
    # response_generation, clarification_draft
    system_prompt: Mapped[str] = mapped_column(Text)
    user_prompt_template: Mapped[str] = mapped_column(Text)
    token_budget: Mapped[dict] = mapped_column(JSONB, default=dict)
    model_id: Mapped[int | None] = mapped_column(
        ForeignKey("model_registry.id", ondelete="SET NULL")
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
