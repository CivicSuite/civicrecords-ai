import enum
import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean, DateTime, Enum, ForeignKey, Index, Integer,
    String, Text, TypeDecorator, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.user import Base
from app.security.at_rest import decrypt_json, encrypt_json, is_encrypted

# Phase 2 Step 5c: ModelRegistry ORM moved to civiccore.llm.registry. Re-export
# here so legacy import paths (`from app.models.document import ModelRegistry`)
# keep working without code changes elsewhere.
from civiccore.llm.registry import ModelRegistry  # noqa: F401,E402


class EncryptedJSONB(TypeDecorator):
    """T6 / ENG-001 — transparent at-rest encryption for a JSONB dict column.

    Writes go through :func:`app.security.at_rest.encrypt_json` and are
    stored as the versioned envelope ``{"v": 1, "ct": "..."}`` in the
    underlying JSONB cell. Reads go through ``decrypt_json`` and caller
    code sees the original plain dict. No connector, router, or ingestion
    caller needs to know encryption exists.

    The column is still JSONB in Postgres — no schema migration beyond a
    one-shot data re-encryption. Anything that already looks encrypted
    (shape ``{"v": int, "ct": str}``) is passed through on write without
    re-encryption so the migration and its downgrade can round-trip
    without double-wrapping.
    """

    impl = JSONB
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        # Idempotent write: already encrypted payloads (e.g. coming from
        # the Alembic migration) pass through unmodified.
        if is_encrypted(value):
            return value
        return encrypt_json(value)

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        return decrypt_json(value)



class SourceType(str, enum.Enum):
    MANUAL_DROP = "manual_drop"
    FILE_SYSTEM = "file_system"
    REST_API = "rest_api"
    ODBC = "odbc"


class IngestionStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DataSource(Base):
    __tablename__ = "data_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    source_type: Mapped[SourceType] = mapped_column(Enum(SourceType, name="source_type", create_type=False, values_callable=lambda e: [m.value for m in e]))
    # T6 / ENG-001 — at-rest encrypted via EncryptedJSONB TypeDecorator.
    # Storage shape in Postgres is JSONB (unchanged from 002_documents),
    # but the cell contents are the versioned envelope
    # ``{"v": 1, "ct": "<fernet-token>"}``. Caller code still sees a
    # plain dict thanks to process_result_value / process_bind_param.
    connection_config: Mapped[dict] = mapped_column(EncryptedJSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_ingestion_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Phase 2 columns
    discovered_source_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    connector_template_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sync_schedule: Mapped[str | None] = mapped_column(String(50), nullable=True)
    schedule_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_cursor: Mapped[str | None] = mapped_column(String, nullable=True)
    last_sync_status: Mapped[str | None] = mapped_column(String(20), nullable=True)

    consecutive_failure_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_paused: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    sync_paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_paused_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    retry_batch_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retry_time_limit_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    health_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    schema_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("data_sources.id"), index=True)
    source_path: Mapped[str] = mapped_column(Text)
    filename: Mapped[str] = mapped_column(String(500))
    file_type: Mapped[str] = mapped_column(String(50))
    file_hash: Mapped[str] = mapped_column(String(64), index=True)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    ingestion_status: Mapped[IngestionStatus] = mapped_column(Enum(IngestionStatus, name="ingestion_status", create_type=False, values_callable=lambda e: [m.value for m in e]), default=IngestionStatus.PENDING)
    ingestion_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    # P6a: idempotency split
    connector_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Phase 2 columns
    display_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    department_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    redaction_status: Mapped[str] = mapped_column(String(20), server_default="none")
    derivative_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    original_locked: Mapped[bool] = mapped_column(Boolean, server_default="false")

    __table_args__ = (Index("ix_documents_source_hash", "source_id", "file_hash"),)


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    content_text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list | None] = mapped_column(Vector(768), nullable=True)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (Index("ix_chunks_doc_index", "document_id", "chunk_index"),)


# NOTE: The local ``class ModelRegistry(Base)`` definition was removed in
# Phase 2 Step 5c. ``ModelRegistry`` is now imported above from
# ``civiccore.llm.registry`` and re-exported for backward compatibility.
