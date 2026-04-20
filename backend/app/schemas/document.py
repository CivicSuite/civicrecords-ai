import uuid
from datetime import datetime
from pydantic import BaseModel, field_validator, model_validator
from app.models.document import IngestionStatus, SourceType


class DataSourceCreate(BaseModel):
    name: str
    source_type: SourceType
    connection_config: dict = {}
    sync_schedule: str | None = None
    schedule_enabled: bool = True

    @field_validator("sync_schedule")
    @classmethod
    def validate_sync_schedule(cls, v: str | None) -> str | None:
        if v is not None:
            from app.ingestion.cron_utils import validate_cron_expression
            validate_cron_expression(v)
        return v


class DataSourceRead(BaseModel):
    """Redacted datasource shape — safe for non-admin roles. connection_config omitted."""
    id: uuid.UUID
    name: str
    source_type: SourceType
    sync_schedule: str | None = None
    schedule_enabled: bool = True
    next_sync_at: datetime | None = None
    is_active: bool
    created_by: uuid.UUID
    created_at: datetime
    last_ingestion_at: datetime | None
    last_sync_at: datetime | None = None
    last_sync_status: str | None = None
    last_error_message: str | None = None
    consecutive_failure_count: int = 0
    sync_paused: bool = False
    health_status: str = "healthy"
    active_failure_count: int = 0
    connector_type: str | None = None
    updated_at: datetime | None = None
    model_config = {"from_attributes": True}

    @field_validator("health_status", mode="before")
    @classmethod
    def _default_health_status(cls, v):
        return v if v is not None else "healthy"


class DataSourceAdminRead(DataSourceRead):
    """Full datasource shape including connection_config. Returned only by admin-gated endpoints."""
    connection_config: dict


class DataSourceUpdate(BaseModel):
    name: str | None = None
    connection_config: dict | None = None
    sync_schedule: str | None = None
    schedule_enabled: bool | None = None
    is_active: bool | None = None

    @field_validator("sync_schedule")
    @classmethod
    def validate_sync_schedule(cls, v: str | None) -> str | None:
        if v is not None:
            from app.ingestion.cron_utils import validate_cron_expression
            validate_cron_expression(v)
        return v


class DocumentRead(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    source_path: str
    filename: str
    file_type: str
    file_hash: str
    file_size: int
    ingestion_status: IngestionStatus
    ingestion_error: str | None
    chunk_count: int
    ingested_at: datetime | None
    connector_type: str | None = None
    updated_at: datetime | None = None
    model_config = {"from_attributes": True}


class DocumentChunkRead(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    content_text: str
    token_count: int
    page_number: int | None
    model_config = {"from_attributes": True}


class IngestionStats(BaseModel):
    total_sources: int
    active_sources: int
    total_documents: int
    documents_by_status: dict[str, int]
    total_chunks: int
