import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.user import Base


class RequestStatus(str, enum.Enum):
    RECEIVED = "received"
    SEARCHING = "searching"
    IN_REVIEW = "in_review"
    DRAFTED = "drafted"
    APPROVED = "approved"
    SENT = "sent"


class InclusionStatus(str, enum.Enum):
    INCLUDED = "included"
    EXCLUDED = "excluded"
    PENDING = "pending"


class RecordsRequest(Base):
    __tablename__ = "records_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    requester_name: Mapped[str] = mapped_column(String(255))
    requester_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    date_received: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    statutory_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus, name="request_status", create_type=False, values_callable=lambda e: [m.value for m in e]),
        default=RequestStatus.RECEIVED,
    )
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    response_draft: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class RequestDocument(Base):
    __tablename__ = "request_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("records_requests.id"), index=True)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"), index=True)
    relevance_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    exemption_flags: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    inclusion_status: Mapped[InclusionStatus] = mapped_column(
        Enum(InclusionStatus, name="inclusion_status", create_type=False, values_callable=lambda e: [m.value for m in e]),
        default=InclusionStatus.PENDING,
    )
    attached_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    attached_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))


class DocumentCache(Base):
    __tablename__ = "document_cache"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"), index=True)
    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("records_requests.id"), index=True)
    cached_file_path: Mapped[str] = mapped_column(Text)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    cached_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
