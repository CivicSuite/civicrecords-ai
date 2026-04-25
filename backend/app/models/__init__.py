from app.models.audit import AuditLog
from app.models.document import DataSource, Document, DocumentChunk, IngestionStatus, SourceType
# Phase 2 Step 5c: ModelRegistry now lives in civiccore.llm.registry.
# Re-export here so existing imports (`from app.models import ModelRegistry`)
# keep working.
from civiccore.llm.registry import ModelRegistry
from app.models.exemption import DisclosureTemplate, ExemptionFlag, ExemptionRule, FlagStatus, RuleType
from app.models.request import DocumentCache, InclusionStatus, RecordsRequest, RequestDocument, RequestStatus
from app.models.search import SearchQuery, SearchResult, SearchSession
from app.models.service_account import ServiceAccount
from app.models.user import Base, User, UserRole

# Phase 2 models
from app.models.departments import Department
from app.models.fees import FeeSchedule, FeeLineItem, FeeWaiver
from app.models.request_workflow import RequestTimeline, RequestMessage, ResponseLetter
from app.models.notifications import NotificationTemplate, NotificationLog
# Phase 2 Step 5c: PromptTemplate now lives in civiccore.llm.templates.
# Re-export here so existing imports (`from app.models import PromptTemplate`)
# keep working.
from civiccore.llm.templates import PromptTemplate
from app.models.city_profile import CityProfile
from app.models.connectors import SystemCatalog, ConnectorTemplate

# P7 models
from app.models.sync_failure import SyncFailure, SyncRunLog

__all__ = [
    "Base", "User", "UserRole", "ServiceAccount", "AuditLog",
    "DataSource", "Document", "DocumentChunk", "IngestionStatus", "SourceType",
    "ModelRegistry",
    "SearchSession", "SearchQuery", "SearchResult",
    "RecordsRequest", "RequestDocument", "DocumentCache", "RequestStatus", "InclusionStatus",
    "ExemptionRule", "ExemptionFlag", "DisclosureTemplate", "RuleType", "FlagStatus",
    # Phase 2
    "Department", "FeeSchedule", "FeeLineItem", "FeeWaiver",
    "RequestTimeline", "RequestMessage", "ResponseLetter",
    "NotificationTemplate", "NotificationLog",
    "PromptTemplate", "CityProfile",
    "SystemCatalog", "ConnectorTemplate",
    # P7
    "SyncFailure", "SyncRunLog",
]
