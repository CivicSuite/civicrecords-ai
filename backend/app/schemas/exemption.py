import uuid
from datetime import datetime
from pydantic import BaseModel

from app.models.exemption import RuleType, FlagStatus


class ExemptionRuleCreate(BaseModel):
    state_code: str
    category: str
    rule_type: RuleType
    rule_definition: str
    description: str | None = None
    enabled: bool = True


class ExemptionRuleRead(BaseModel):
    id: uuid.UUID
    state_code: str
    category: str
    rule_type: RuleType
    rule_definition: str
    description: str | None
    enabled: bool
    created_by: uuid.UUID
    created_at: datetime
    model_config = {"from_attributes": True}


class ExemptionRuleUpdate(BaseModel):
    rule_definition: str | None = None
    description: str | None = None
    enabled: bool | None = None


class ExemptionFlagRead(BaseModel):
    id: uuid.UUID
    chunk_id: uuid.UUID
    rule_id: uuid.UUID | None
    request_id: uuid.UUID
    category: str
    matched_text: str | None
    confidence: float
    status: FlagStatus
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None
    review_reason: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


class ExemptionFlagReview(BaseModel):
    status: FlagStatus
    review_reason: str | None = None


class DisclosureTemplateCreate(BaseModel):
    template_type: str
    state_code: str | None = None
    content: str


class DisclosureTemplateRead(BaseModel):
    id: uuid.UUID
    template_type: str
    state_code: str | None
    content: str
    version: int
    updated_by: uuid.UUID
    updated_at: datetime
    model_config = {"from_attributes": True}


class ExemptionDashboard(BaseModel):
    total_flags: int
    by_status: dict[str, int]
    by_category: dict[str, int]
    acceptance_rate: float
    total_rules: int
    active_rules: int
