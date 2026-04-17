import uuid
from datetime import datetime
from pydantic import BaseModel
from app.models.document import IngestionStatus, SourceType

class DataSourceCreate(BaseModel):
    name: str
    source_type: SourceType
    connection_config: dict = {}
    schedule_minutes: int | None = None

class DataSourceRead(BaseModel):
    id: uuid.UUID
    name: str
    source_type: SourceType
    connection_config: dict
    schedule_minutes: int | None
    is_active: bool
    created_by: uuid.UUID
    created_at: datetime
    last_ingestion_at: datetime | None
    # P6a additions
    connector_type: str | None = None
    updated_at: datetime | None = None
    sync_schedule: str | None = None
    # P6b stubs — will be populated by scheduler in P6b
    schedule_enabled: bool = False
    next_sync_at: datetime | None = None
    model_config = {"from_attributes": True}

class DataSourceUpdate(BaseModel):
    name: str | None = None
    connection_config: dict | None = None
    schedule_minutes: int | None = None
    is_active: bool | None = None

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
