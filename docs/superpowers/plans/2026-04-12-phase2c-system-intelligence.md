# Phase 2C: System Intelligence — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add operational analytics API, city profile/onboarding API, Municipal Systems Catalog loader, and context manager for LLM token budgeting.

**Architecture:** New router modules following existing patterns. Analytics are computed on-demand from existing tables. City profile CRUD replaces localStorage with persistent storage. Systems catalog loaded from a bundled JSON file. Context manager is a service module used by search and exemption endpoints.

**Tech Stack:** FastAPI, SQLAlchemy 2.x async, Pydantic v2, Python 3.12

**Working directory:** `C:\Users\scott\Desktop\Claude\civicrecords-ai\backend`

---

## Task 1: Operational Analytics API

**Files:**
- Create: `backend/app/analytics/__init__.py`
- Create: `backend/app/analytics/router.py`
- Create: `backend/app/schemas/analytics.py`
- Modify: `backend/app/main.py` — register new router

- [ ] **Step 1: Read main.py to see how routers are registered**

- [ ] **Step 2: Create analytics schema**

Create `backend/app/schemas/analytics.py`:

```python
from pydantic import BaseModel


class OperationalMetrics(BaseModel):
    average_response_time_days: float | None
    median_response_time_days: float | None
    requests_by_status: dict[str, int]
    requests_by_department: dict[str, int]
    deadline_compliance_rate: float
    total_open: int
    total_closed: int
    total_overdue: int
    clarification_frequency: float
    top_request_topics: list[str]
```

- [ ] **Step 3: Create analytics router**

Create `backend/app/analytics/__init__.py` (empty).

Create `backend/app/analytics/router.py`:

```python
import uuid
from datetime import datetime, timedelta
from sqlalchemy import select, func, case, extract
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends

from app.database import get_async_session
from app.auth.dependencies import require_role, UserRole
from app.models.request import RecordsRequest, RequestStatus
from app.schemas.analytics import OperationalMetrics

router = APIRouter(tags=["analytics"])


@router.get("/analytics/operational", response_model=OperationalMetrics)
async def get_operational_metrics(
    session: AsyncSession = Depends(get_async_session),
    user=Depends(require_role(UserRole.STAFF)),
):
    now = datetime.utcnow()

    # Requests by status
    status_result = await session.execute(
        select(RecordsRequest.status, func.count())
        .group_by(RecordsRequest.status)
    )
    by_status = {str(row[0].value) if hasattr(row[0], 'value') else str(row[0]): row[1] for row in status_result.fetchall()}

    # Total open vs closed
    closed_statuses = {"fulfilled", "sent", "closed"}
    total_closed = sum(v for k, v in by_status.items() if k in closed_statuses)
    total_open = sum(v for k, v in by_status.items() if k not in closed_statuses)

    # Overdue
    overdue_result = await session.execute(
        select(func.count()).where(
            RecordsRequest.statutory_deadline < now,
            RecordsRequest.status.notin_([
                RequestStatus.FULFILLED, RequestStatus.SENT, RequestStatus.CLOSED
            ])
        )
    )
    total_overdue = overdue_result.scalar() or 0

    # Average response time (for closed requests with both dates)
    avg_result = await session.execute(
        select(
            func.avg(extract("epoch", RecordsRequest.closed_at - RecordsRequest.date_received) / 86400),
        ).where(RecordsRequest.closed_at.isnot(None))
    )
    avg_days = avg_result.scalar()

    # Deadline compliance (closed requests that were closed before deadline)
    compliance_result = await session.execute(
        select(
            func.count().filter(RecordsRequest.closed_at <= RecordsRequest.statutory_deadline),
            func.count(),
        ).where(
            RecordsRequest.closed_at.isnot(None),
            RecordsRequest.statutory_deadline.isnot(None),
        )
    )
    comp_row = compliance_result.fetchone()
    compliance_rate = (comp_row[0] / comp_row[1] * 100) if comp_row and comp_row[1] > 0 else 100.0

    # Clarification frequency
    total_all = total_open + total_closed
    clarification_count = by_status.get("clarification_needed", 0)
    clarification_freq = (clarification_count / total_all * 100) if total_all > 0 else 0.0

    return OperationalMetrics(
        average_response_time_days=round(avg_days, 1) if avg_days else None,
        median_response_time_days=None,  # Requires window function, deferred
        requests_by_status=by_status,
        requests_by_department={},  # Populated once departments are assigned
        deadline_compliance_rate=round(compliance_rate, 1),
        total_open=total_open,
        total_closed=total_closed,
        total_overdue=total_overdue,
        clarification_frequency=round(clarification_freq, 1),
        top_request_topics=[],  # Populated via NLP in future
    )
```

- [ ] **Step 4: Register the router in main.py**

Add to `backend/app/main.py`:
```python
from app.analytics.router import router as analytics_router
app.include_router(analytics_router)
```

- [ ] **Step 5: Run tests and commit**

```bash
cd backend && DATABASE_URL=postgresql+asyncpg://civicrecords:civicrecords@localhost:5432/civicrecords python -m pytest tests/ -q
git add backend/app/analytics/ backend/app/schemas/analytics.py backend/app/main.py
git commit -m "feat: add operational analytics API endpoint

- GET /analytics/operational returns metrics computed from requests table
- Average response time, deadline compliance, overdue count
- Requests by status, clarification frequency
- Auth: staff role required"
```

---

## Task 2: City Profile API

**Files:**
- Create: `backend/app/city_profile/__init__.py`
- Create: `backend/app/city_profile/router.py`
- Create: `backend/app/schemas/city_profile.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create city profile schema**

Create `backend/app/schemas/city_profile.py`:

```python
import uuid
from datetime import datetime
from pydantic import BaseModel


class CityProfileCreate(BaseModel):
    city_name: str
    state: str
    county: str | None = None
    population_band: str | None = None
    email_platform: str | None = None
    has_dedicated_it: bool | None = None
    monthly_request_volume: str | None = None
    profile_data: dict = {}
    gap_map: dict = {}


class CityProfileRead(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    city_name: str
    state: str
    county: str | None
    population_band: str | None
    email_platform: str | None
    has_dedicated_it: bool | None
    monthly_request_volume: str | None
    onboarding_status: str
    profile_data: dict
    gap_map: dict
    created_at: datetime
    updated_at: datetime


class CityProfileUpdate(BaseModel):
    city_name: str | None = None
    state: str | None = None
    county: str | None = None
    population_band: str | None = None
    email_platform: str | None = None
    has_dedicated_it: bool | None = None
    monthly_request_volume: str | None = None
    onboarding_status: str | None = None
    profile_data: dict | None = None
    gap_map: dict | None = None
```

- [ ] **Step 2: Create city profile router**

Create `backend/app/city_profile/__init__.py` (empty).

Create `backend/app/city_profile/router.py`:

```python
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException

from app.database import get_async_session
from app.auth.dependencies import require_role, UserRole
from app.models.city_profile import CityProfile
from app.schemas.city_profile import CityProfileCreate, CityProfileRead, CityProfileUpdate
from app.audit import write_audit_log

router = APIRouter(tags=["city-profile"])


@router.get("/city-profile", response_model=CityProfileRead | None)
async def get_city_profile(
    session: AsyncSession = Depends(get_async_session),
    user=Depends(require_role(UserRole.STAFF)),
):
    result = await session.execute(select(CityProfile).limit(1))
    profile = result.scalar_one_or_none()
    return profile


@router.post("/city-profile", response_model=CityProfileRead, status_code=201)
async def create_city_profile(
    data: CityProfileCreate,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(require_role(UserRole.ADMIN)),
):
    # Only one profile per instance
    existing = await session.execute(select(CityProfile).limit(1))
    if existing.scalar_one_or_none():
        raise HTTPException(409, "City profile already exists. Use PATCH to update.")

    profile = CityProfile(
        city_name=data.city_name,
        state=data.state,
        county=data.county,
        population_band=data.population_band,
        email_platform=data.email_platform,
        has_dedicated_it=data.has_dedicated_it,
        monthly_request_volume=data.monthly_request_volume,
        onboarding_status="complete",
        profile_data=data.profile_data,
        gap_map=data.gap_map,
        updated_by=user.id,
    )
    session.add(profile)
    await session.commit()
    await session.refresh(profile)

    await write_audit_log(session, "city_profile_created", "city_profile", str(profile.id), user.id, {})
    return profile


@router.patch("/city-profile", response_model=CityProfileRead)
async def update_city_profile(
    data: CityProfileUpdate,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(require_role(UserRole.ADMIN)),
):
    result = await session.execute(select(CityProfile).limit(1))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(404, "No city profile exists. Use POST to create one.")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(profile, key, value)
    profile.updated_by = user.id

    await session.commit()
    await session.refresh(profile)

    await write_audit_log(session, "city_profile_updated", "city_profile", str(profile.id), user.id, update_data)
    return profile
```

- [ ] **Step 3: Register router in main.py**

```python
from app.city_profile.router import router as city_profile_router
app.include_router(city_profile_router)
```

- [ ] **Step 4: Run tests and commit**

```bash
cd backend && DATABASE_URL=postgresql+asyncpg://civicrecords:civicrecords@localhost:5432/civicrecords python -m pytest tests/ -q
git add backend/app/city_profile/ backend/app/schemas/city_profile.py backend/app/main.py
git commit -m "feat: add city profile CRUD API

- GET /city-profile returns the singleton city profile
- POST /city-profile creates (admin only, one per instance)
- PATCH /city-profile updates (admin only)
- Replaces localStorage-based onboarding persistence"
```

---

## Task 3: Municipal Systems Catalog

**Files:**
- Create: `backend/data/systems_catalog.json`
- Create: `backend/app/catalog/__init__.py`
- Create: `backend/app/catalog/router.py`
- Create: `backend/app/catalog/loader.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create the catalog JSON**

Create `backend/data/systems_catalog.json` with the 12 functional domains from the spec. Each entry has domain, function, vendor_name, access_protocol, data_shape, common_record_types, redaction_tier, discovery_hints:

```json
{
  "catalog_version": "1.0.0",
  "domains": [
    {
      "domain": "Finance & Budgeting",
      "systems": [
        {"vendor_name": "Tyler Munis", "access_protocol": "rest_api", "data_shape": "structured", "common_record_types": ["purchase_orders", "vendor_payments", "budget_reports", "payroll"], "redaction_tier": 1, "discovery_hints": {"ports": [8080, 443], "db_patterns": ["MUN_*", "TYLER_*"]}},
        {"vendor_name": "Caselle", "access_protocol": "odbc", "data_shape": "structured", "common_record_types": ["purchase_orders", "vendor_payments", "budget_reports"], "redaction_tier": 1, "discovery_hints": {"ports": [1433], "db_patterns": ["CASELLE*"]}},
        {"vendor_name": "OpenGov", "access_protocol": "rest_api", "data_shape": "structured", "common_record_types": ["budget_reports", "financial_transparency"], "redaction_tier": 1, "discovery_hints": {}}
      ]
    },
    {
      "domain": "Public Safety",
      "systems": [
        {"vendor_name": "Mark43", "access_protocol": "rest_api", "data_shape": "mixed", "common_record_types": ["incident_reports", "arrest_records", "cad_logs"], "redaction_tier": 2, "discovery_hints": {"ports": [443]}},
        {"vendor_name": "Axon", "access_protocol": "vendor_sdk", "data_shape": "media", "common_record_types": ["body_camera", "evidence"], "redaction_tier": 3, "discovery_hints": {}},
        {"vendor_name": "Tyler New World", "access_protocol": "odbc", "data_shape": "structured", "common_record_types": ["incident_reports", "cad_logs"], "redaction_tier": 2, "discovery_hints": {"db_patterns": ["NW_*"]}}
      ]
    },
    {
      "domain": "Land Use & Permitting",
      "systems": [
        {"vendor_name": "Accela", "access_protocol": "rest_api", "data_shape": "structured", "common_record_types": ["building_permits", "inspections", "code_violations"], "redaction_tier": 1, "discovery_hints": {"ports": [443]}},
        {"vendor_name": "CityWorks", "access_protocol": "rest_api", "data_shape": "structured", "common_record_types": ["work_orders", "inspections"], "redaction_tier": 1, "discovery_hints": {}}
      ]
    },
    {
      "domain": "Human Resources",
      "systems": [
        {"vendor_name": "NEOGOV", "access_protocol": "rest_api", "data_shape": "structured", "common_record_types": ["job_postings", "hiring_records", "salary_data"], "redaction_tier": 2, "discovery_hints": {}},
        {"vendor_name": "ADP", "access_protocol": "rest_api", "data_shape": "structured", "common_record_types": ["payroll", "benefits"], "redaction_tier": 2, "discovery_hints": {}}
      ]
    },
    {
      "domain": "Document Management",
      "systems": [
        {"vendor_name": "Laserfiche", "access_protocol": "rest_api", "data_shape": "documents", "common_record_types": ["meeting_minutes", "ordinances", "contracts", "resolutions"], "redaction_tier": 1, "discovery_hints": {"service_accounts": ["svc_laserfiche"], "db_patterns": ["LASER*"]}},
        {"vendor_name": "OnBase", "access_protocol": "odbc", "data_shape": "documents", "common_record_types": ["scanned_documents", "forms"], "redaction_tier": 1, "discovery_hints": {"db_patterns": ["ONBASE*"]}}
      ]
    },
    {
      "domain": "Email & Communication",
      "systems": [
        {"vendor_name": "Microsoft 365", "access_protocol": "rest_api", "data_shape": "documents", "common_record_types": ["email", "calendar", "teams_messages"], "redaction_tier": 1, "discovery_hints": {}},
        {"vendor_name": "Google Workspace", "access_protocol": "rest_api", "data_shape": "documents", "common_record_types": ["email", "calendar", "drive_files"], "redaction_tier": 1, "discovery_hints": {}}
      ]
    },
    {
      "domain": "Utilities & Public Works",
      "systems": [
        {"vendor_name": "CIS Infinity", "access_protocol": "odbc", "data_shape": "structured", "common_record_types": ["utility_billing", "meter_data"], "redaction_tier": 1, "discovery_hints": {"db_patterns": ["CIS*"]}},
        {"vendor_name": "Cartegraph", "access_protocol": "rest_api", "data_shape": "structured", "common_record_types": ["work_orders", "maintenance_logs"], "redaction_tier": 1, "discovery_hints": {}}
      ]
    },
    {
      "domain": "Courts & Legal",
      "systems": [
        {"vendor_name": "Tyler Odyssey", "access_protocol": "odbc", "data_shape": "structured", "common_record_types": ["court_dockets", "case_filings"], "redaction_tier": 2, "discovery_hints": {"db_patterns": ["ODYSSEY*"]}}
      ]
    },
    {
      "domain": "Parks & Recreation",
      "systems": [
        {"vendor_name": "RecTrac", "access_protocol": "odbc", "data_shape": "structured", "common_record_types": ["facility_reservations", "program_registrations"], "redaction_tier": 1, "discovery_hints": {}},
        {"vendor_name": "CivicRec", "access_protocol": "rest_api", "data_shape": "structured", "common_record_types": ["facility_reservations", "rental_agreements"], "redaction_tier": 1, "discovery_hints": {}}
      ]
    },
    {
      "domain": "Asset & Fleet Management",
      "systems": [
        {"vendor_name": "Samsara", "access_protocol": "rest_api", "data_shape": "structured", "common_record_types": ["vehicle_gps", "maintenance_records", "fuel_purchases"], "redaction_tier": 1, "discovery_hints": {}}
      ]
    },
    {
      "domain": "Geographic Information",
      "systems": [
        {"vendor_name": "Esri ArcGIS", "access_protocol": "rest_api", "data_shape": "spatial", "common_record_types": ["property_boundaries", "zoning_maps", "infrastructure"], "redaction_tier": 1, "discovery_hints": {"ports": [6443, 443]}}
      ]
    },
    {
      "domain": "Legacy & Custom",
      "systems": [
        {"vendor_name": "Generic ODBC", "access_protocol": "odbc", "data_shape": "structured", "common_record_types": ["historical_records"], "redaction_tier": 1, "discovery_hints": {}},
        {"vendor_name": "File Export", "access_protocol": "file_system", "data_shape": "documents", "common_record_types": ["exported_reports", "scanned_archives"], "redaction_tier": 1, "discovery_hints": {}}
      ]
    }
  ]
}
```

- [ ] **Step 2: Create catalog loader**

Create `backend/app/catalog/loader.py`:

```python
import json
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.connectors import SystemCatalog


CATALOG_PATH = Path(__file__).parent.parent.parent / "data" / "systems_catalog.json"


async def load_catalog(session: AsyncSession) -> int:
    """Load or refresh the systems catalog from the bundled JSON file.
    Returns count of entries loaded."""
    with open(CATALOG_PATH) as f:
        data = json.load(f)

    catalog_version = data["catalog_version"]

    # Check if already loaded at this version
    existing = await session.execute(
        select(SystemCatalog).where(SystemCatalog.catalog_version == catalog_version).limit(1)
    )
    if existing.scalar_one_or_none():
        return 0  # Already loaded

    count = 0
    for domain_entry in data["domains"]:
        domain = domain_entry["domain"]
        for system in domain_entry["systems"]:
            entry = SystemCatalog(
                domain=domain,
                function=domain,
                vendor_name=system["vendor_name"],
                access_protocol=system["access_protocol"],
                data_shape=system["data_shape"],
                common_record_types=system["common_record_types"],
                redaction_tier=system["redaction_tier"],
                discovery_hints=system.get("discovery_hints", {}),
                catalog_version=catalog_version,
            )
            session.add(entry)
            count += 1

    await session.commit()
    return count
```

- [ ] **Step 3: Create catalog router**

Create `backend/app/catalog/__init__.py` (empty).

Create `backend/app/catalog/router.py`:

```python
from sqlalchemy import select, distinct
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends

from app.database import get_async_session
from app.auth.dependencies import require_role, UserRole
from app.models.connectors import SystemCatalog
from app.catalog.loader import load_catalog

router = APIRouter(tags=["catalog"])


@router.get("/catalog/domains")
async def list_domains(
    session: AsyncSession = Depends(get_async_session),
    user=Depends(require_role(UserRole.STAFF)),
):
    """List all functional domains in the systems catalog."""
    result = await session.execute(
        select(distinct(SystemCatalog.domain)).order_by(SystemCatalog.domain)
    )
    return {"domains": [row[0] for row in result.fetchall()]}


@router.get("/catalog/systems")
async def list_systems(
    domain: str | None = None,
    session: AsyncSession = Depends(get_async_session),
    user=Depends(require_role(UserRole.STAFF)),
):
    """List systems in the catalog, optionally filtered by domain."""
    query = select(SystemCatalog).order_by(SystemCatalog.domain, SystemCatalog.vendor_name)
    if domain:
        query = query.where(SystemCatalog.domain == domain)
    result = await session.execute(query)
    systems = result.scalars().all()
    return {
        "systems": [
            {
                "id": s.id,
                "domain": s.domain,
                "vendor_name": s.vendor_name,
                "access_protocol": s.access_protocol,
                "data_shape": s.data_shape,
                "common_record_types": s.common_record_types,
                "redaction_tier": s.redaction_tier,
            }
            for s in systems
        ]
    }


@router.post("/catalog/load", status_code=200)
async def trigger_catalog_load(
    session: AsyncSession = Depends(get_async_session),
    user=Depends(require_role(UserRole.ADMIN)),
):
    """Load or refresh the systems catalog from the bundled JSON."""
    count = await load_catalog(session)
    if count == 0:
        return {"message": "Catalog already loaded at current version", "loaded": 0}
    return {"message": f"Loaded {count} system entries", "loaded": count}
```

- [ ] **Step 4: Register router and add startup loader**

In `backend/app/main.py`, add:
```python
from app.catalog.router import router as catalog_router
app.include_router(catalog_router)
```

Also add a startup event to auto-load the catalog:
```python
@app.on_event("startup")
async def load_systems_catalog():
    from app.catalog.loader import load_catalog
    from app.database import async_session_maker
    async with async_session_maker() as session:
        count = await load_catalog(session)
        if count > 0:
            print(f"Loaded {count} systems catalog entries")
```

(Or use the existing startup pattern if one exists — read main.py first.)

- [ ] **Step 5: Run tests and commit**

```bash
cd backend && DATABASE_URL=postgresql+asyncpg://civicrecords:civicrecords@localhost:5432/civicrecords python -m pytest tests/ -q
git add backend/app/catalog/ backend/data/ backend/app/main.py
git commit -m "feat: add Municipal Systems Catalog with auto-loader

- 12 functional domains, 25+ vendor systems in bundled JSON
- GET /catalog/domains lists all domains
- GET /catalog/systems?domain=X lists systems with filtering
- POST /catalog/load triggers manual catalog refresh (admin)
- Auto-loads on startup if not already at current version"
```

---

## Task 4: Context Manager Service

**Files:**
- Create: `backend/app/llm/context_manager.py`

This is a service module (not a router) that assembles LLM prompts within token budgets. Used by search synthesis and future response letter generation.

- [ ] **Step 1: Read the existing LLM module to understand patterns**

Read whatever LLM-related files exist (likely `app/llm/` or `app/search/` that calls Ollama).

- [ ] **Step 2: Create the context manager**

Create `backend/app/llm/context_manager.py`:

```python
"""Context Manager for Local LLM Token Budgeting.

Assembles prompts within configurable token budgets for Ollama.
Adapted from context-mode architectural patterns.
"""

from dataclasses import dataclass, field


@dataclass
class TokenBudget:
    """Token budget allocation for an LLM call."""
    system_instruction: int = 500
    request_context: int = 500
    retrieved_chunks: int = 5000
    exemption_rules: int = 500
    output_reservation: int = 1500
    safety_margin: int = 192

    @property
    def total(self) -> int:
        return (
            self.system_instruction
            + self.request_context
            + self.retrieved_chunks
            + self.exemption_rules
            + self.output_reservation
            + self.safety_margin
        )


@dataclass
class ContextBlock:
    """A block of content with its role and estimated token count."""
    role: str  # system, request, chunk, rule, instruction
    content: str
    estimated_tokens: int = 0

    def __post_init__(self):
        if self.estimated_tokens == 0:
            # Rough estimate: 1 token ≈ 4 characters for English text
            self.estimated_tokens = max(1, len(self.content) // 4)


def estimate_tokens(text: str) -> int:
    """Rough token estimate: 1 token ≈ 4 characters."""
    return max(1, len(text) // 4)


def assemble_context(
    system_prompt: str,
    request_context: str | None = None,
    chunks: list[str] | None = None,
    exemption_rules: list[str] | None = None,
    budget: TokenBudget | None = None,
    max_context_tokens: int | None = None,
) -> list[ContextBlock]:
    """Assemble context blocks within token budget.

    Prioritizes: system > request > top-k chunks > exemption rules.
    Chunks are added in order until budget is exhausted.
    """
    if budget is None:
        budget = TokenBudget()

    if max_context_tokens:
        # Scale budget proportionally to model context window
        scale = max_context_tokens / budget.total
        budget = TokenBudget(
            system_instruction=int(budget.system_instruction * scale),
            request_context=int(budget.request_context * scale),
            retrieved_chunks=int(budget.retrieved_chunks * scale),
            exemption_rules=int(budget.exemption_rules * scale),
            output_reservation=int(budget.output_reservation * scale),
            safety_margin=int(budget.safety_margin * scale),
        )

    blocks: list[ContextBlock] = []
    tokens_used = 0

    # 1. System instruction (always included)
    sys_block = ContextBlock("system", system_prompt)
    if sys_block.estimated_tokens <= budget.system_instruction:
        blocks.append(sys_block)
        tokens_used += sys_block.estimated_tokens

    # 2. Request context
    if request_context:
        req_block = ContextBlock("request", request_context)
        if req_block.estimated_tokens <= budget.request_context:
            blocks.append(req_block)
            tokens_used += req_block.estimated_tokens

    # 3. Retrieved chunks (top-k that fit)
    if chunks:
        chunk_budget = budget.retrieved_chunks
        for chunk_text in chunks:
            block = ContextBlock("chunk", chunk_text)
            if block.estimated_tokens <= chunk_budget:
                blocks.append(block)
                chunk_budget -= block.estimated_tokens
                tokens_used += block.estimated_tokens
            else:
                break  # Budget exhausted

    # 4. Exemption rules
    if exemption_rules:
        rule_budget = budget.exemption_rules
        for rule_text in exemption_rules:
            block = ContextBlock("rule", rule_text)
            if block.estimated_tokens <= rule_budget:
                blocks.append(block)
                rule_budget -= block.estimated_tokens
                tokens_used += block.estimated_tokens

    return blocks


def blocks_to_prompt(blocks: list[ContextBlock]) -> str:
    """Convert context blocks to a single prompt string."""
    sections = []
    for block in blocks:
        if block.role == "system":
            sections.append(block.content)
        elif block.role == "request":
            sections.append(f"\n--- Request Context ---\n{block.content}")
        elif block.role == "chunk":
            sections.append(f"\n--- Document Excerpt ---\n{block.content}")
        elif block.role == "rule":
            sections.append(f"\n--- Exemption Rule ---\n{block.content}")
    return "\n".join(sections)
```

- [ ] **Step 3: Verify it imports**

```bash
cd backend && python -c "from app.llm.context_manager import assemble_context, TokenBudget; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/llm/context_manager.py
git commit -m "feat: add context manager for LLM token budgeting

- TokenBudget dataclass with configurable section allocations
- assemble_context() prioritizes system > request > chunks > rules
- Rough token estimation (1 token ≈ 4 chars)
- Scales budget proportionally for different model context windows
- blocks_to_prompt() for final prompt assembly"
```

---

## Summary

After Phase 2C:
- `GET /analytics/operational` — real-time operational metrics
- `GET/POST/PATCH /city-profile` — persistent city profile (replaces localStorage)
- `GET /catalog/domains` and `GET /catalog/systems` — browsable systems catalog
- `POST /catalog/load` — catalog refresh + auto-load on startup
- Context manager service for token-budgeted LLM calls
- 25+ vendor systems in bundled JSON catalog
