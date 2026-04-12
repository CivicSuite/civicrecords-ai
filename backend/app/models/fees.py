import uuid
from datetime import datetime, date
from sqlalchemy import DateTime, String, Numeric, Integer, Date, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.user import Base


class FeeSchedule(Base):
    __tablename__ = "fee_schedules"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    jurisdiction: Mapped[str] = mapped_column(String(100))
    fee_type: Mapped[str] = mapped_column(String(50))  # per_page/flat/hourly/waived
    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    description: Mapped[str | None] = mapped_column(String(500))
    effective_date: Mapped[date] = mapped_column(Date)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class FeeLineItem(Base):
    __tablename__ = "fee_line_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("records_requests.id", ondelete="CASCADE")
    )
    fee_schedule_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("fee_schedules.id", ondelete="SET NULL")
    )
    description: Mapped[str] = mapped_column(String(500))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2))
    total: Mapped[float] = mapped_column(Numeric(10, 2))
    status: Mapped[str] = mapped_column(String(20), default="estimated")  # estimated/invoiced/paid/waived
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
