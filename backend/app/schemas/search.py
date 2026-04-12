import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str
    session_id: uuid.UUID | None = None
    filters: dict | None = None
    limit: int = Field(default=10, le=50)
    synthesize: bool = False


class SearchResultItem(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    file_type: str
    source_path: str
    page_number: int | None
    content_text: str
    similarity_score: float
    rank: int

    model_config = {"from_attributes": True}


class SearchResponse(BaseModel):
    query_id: uuid.UUID
    session_id: uuid.UUID
    query_text: str
    results: list[SearchResultItem]
    results_count: int
    synthesized_answer: str | None = None
    ai_generated: bool = False


class SearchSessionRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    queries: list[dict] = []

    model_config = {"from_attributes": True}


class SearchFilterOptions(BaseModel):
    file_types: list[str]
    source_names: list[str]
    date_range: dict | None = None
