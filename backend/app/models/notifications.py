import uuid
from datetime import datetime
from sqlalchemy import DateTime, String, Text, Boolean, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.user import Base


class NotificationTemplate(Base):
    __tablename__ = "notification_templates"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(50), unique=True)
    channel: Mapped[str] = mapped_column(String(20))  # email/in_app
    subject_template: Mapped[str] = mapped_column(String(500))
    body_template: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class NotificationLog(Base):
    __tablename__ = "notification_log"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("notification_templates.id", ondelete="SET NULL")
    )
    recipient_email: Mapped[str] = mapped_column(String(255))
    request_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("records_requests.id", ondelete="SET NULL")
    )
    channel: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued/sent/failed
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
