# Phase 2A: Database Migrations — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 12 new database tables and extend 4 existing tables with new columns to support the full UNIFIED-SPEC.md data model (departments, fees, request timeline/messages, notifications, response letters, prompt templates, city profile, system catalog, connector templates).

**Architecture:** Single Alembic migration file (007_phase2_extensions.py) that adds all new tables and alters existing ones. Corresponding SQLAlchemy models in new model files following existing patterns: UUID PKs, `Mapped[Type]` annotations, `mapped_column()`, `server_default=func.now()` for timestamps.

**Tech Stack:** SQLAlchemy 2.x async, Alembic, PostgreSQL 17, Python 3.12

**Reference:** `docs/UNIFIED-SPEC.md` Section 5 (Data Model), Section 12.9 (Discovery tables)

**Working directory:** `C:\Users\scott\Desktop\Claude\civicrecords-ai\backend`

**Existing patterns (from exploration):**
- Models at `app/models/` in separate files, imported in `app/models/__init__.py`
- UUID PKs: `Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)`
- Timestamps: `Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())`
- JSON columns: `Mapped[dict] = mapped_column(JSONB, default=dict)`
- Enums: String columns with Python Enum or literal comments
- FKs: `ForeignKey("tablename.id", ondelete="CASCADE")`

---

## Task 1: Create New Model Files

**Files:**
- Create: `backend/app/models/departments.py`
- Create: `backend/app/models/fees.py`
- Create: `backend/app/models/request_workflow.py`
- Create: `backend/app/models/notifications.py`
- Create: `backend/app/models/prompts.py`
- Create: `backend/app/models/city_profile.py`
- Create: `backend/app/models/connectors.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Read the existing models/__init__.py to see current imports**

Read `backend/app/models/__init__.py`.

- [ ] **Step 2: Create departments.py**

Create `backend/app/models/departments.py`:

```python
import uuid
from datetime import datetime
from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models import Base


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(20), unique=True)
    contact_email: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

- [ ] **Step 3: Create fees.py**

Create `backend/app/models/fees.py`:

```python
import uuid
from datetime import datetime, date
from sqlalchemy import DateTime, String, Numeric, Integer, Date, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models import Base


class FeeSchedule(Base):
    __tablename__ = "fee_schedules"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    jurisdiction: Mapped[str] = mapped_column(String(100))
    fee_type: Mapped[str] = mapped_column(String(50))  # per_page/flat/hourly/waived
    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    description: Mapped[str | None] = mapped_column(String(500))
    effective_date: Mapped[date] = mapped_column(Date)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL")
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
```

- [ ] **Step 4: Create request_workflow.py**

Create `backend/app/models/request_workflow.py`:

```python
import uuid
from datetime import datetime
from sqlalchemy import DateTime, String, Text, Boolean, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models import Base


class RequestTimeline(Base):
    __tablename__ = "request_timeline"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("records_requests.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(50))
    # status_change, note_added, document_attached, document_removed,
    # fee_updated, clarification_sent, clarification_received,
    # deadline_extended, response_drafted, response_approved,
    # records_released, request_closed
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL")
    )
    actor_role: Mapped[str | None] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(Text)
    internal_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class RequestMessage(Base):
    __tablename__ = "request_messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("records_requests.id", ondelete="CASCADE"), index=True
    )
    sender_type: Mapped[str] = mapped_column(String(20))  # staff/requester/system
    sender_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL")
    )
    message_text: Mapped[str] = mapped_column(Text)
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ResponseLetter(Base):
    __tablename__ = "response_letters"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("records_requests.id", ondelete="CASCADE"), index=True
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("disclosure_templates.id", ondelete="SET NULL")
    )
    generated_content: Mapped[str] = mapped_column(Text)
    edited_content: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft/approved/sent
    generated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL")
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL")
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

- [ ] **Step 5: Create notifications.py**

Create `backend/app/models/notifications.py`:

```python
import uuid
from datetime import datetime
from sqlalchemy import DateTime, String, Text, Boolean, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models import Base


class NotificationTemplate(Base):
    __tablename__ = "notification_templates"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(50), unique=True)
    channel: Mapped[str] = mapped_column(String(20))  # email/in_app
    subject_template: Mapped[str] = mapped_column(String(500))
    body_template: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL")
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
```

- [ ] **Step 6: Create prompts.py**

Create `backend/app/models/prompts.py`:

```python
import uuid
from datetime import datetime
from sqlalchemy import DateTime, String, Text, Boolean, Integer, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models import Base


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    purpose: Mapped[str] = mapped_column(String(50))
    # search_synthesis, exemption_scan, scope_assessment,
    # response_generation, clarification_draft
    system_prompt: Mapped[str] = mapped_column(Text)
    user_prompt_template: Mapped[str] = mapped_column(Text)
    token_budget: Mapped[dict] = mapped_column(JSONB, default=dict)
    model_id: Mapped[int | None] = mapped_column(
        ForeignKey("model_registry.id", ondelete="SET NULL")
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

- [ ] **Step 7: Create city_profile.py**

Create `backend/app/models/city_profile.py`:

```python
import uuid
from datetime import datetime
from sqlalchemy import DateTime, String, Boolean, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models import Base


class CityProfile(Base):
    __tablename__ = "city_profile"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    city_name: Mapped[str] = mapped_column(String(200))
    state: Mapped[str] = mapped_column(String(2))
    county: Mapped[str | None] = mapped_column(String(200))
    population_band: Mapped[str | None] = mapped_column(String(50))
    email_platform: Mapped[str | None] = mapped_column(String(50))
    has_dedicated_it: Mapped[bool | None] = mapped_column(Boolean)
    monthly_request_volume: Mapped[str | None] = mapped_column(String(20))
    onboarding_status: Mapped[str] = mapped_column(
        String(20), default="not_started"
    )  # not_started/in_progress/complete
    profile_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    gap_map: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL")
    )
```

- [ ] **Step 8: Create connectors.py**

Create `backend/app/models/connectors.py`:

```python
import uuid
from datetime import datetime
from sqlalchemy import DateTime, String, Text, Integer, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models import Base


class SystemCatalog(Base):
    __tablename__ = "system_catalog"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    domain: Mapped[str] = mapped_column(String(100))
    function: Mapped[str] = mapped_column(String(200))
    vendor_name: Mapped[str] = mapped_column(String(200))
    vendor_version: Mapped[str | None] = mapped_column(String(50))
    access_protocol: Mapped[str] = mapped_column(String(50))
    data_shape: Mapped[str] = mapped_column(String(50))
    common_record_types: Mapped[dict] = mapped_column(JSONB, default=list)
    redaction_tier: Mapped[int] = mapped_column(Integer, default=1)
    discovery_hints: Mapped[dict] = mapped_column(JSONB, default=dict)
    connector_template_id: Mapped[int | None] = mapped_column(Integer)
    catalog_version: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ConnectorTemplate(Base):
    __tablename__ = "connector_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vendor_name: Mapped[str] = mapped_column(String(200))
    protocol: Mapped[str] = mapped_column(String(50))
    auth_method: Mapped[str] = mapped_column(String(50))
    # oauth2/odbc/api_key/service_account/none
    config_schema: Mapped[dict] = mapped_column(JSONB, default=dict)
    default_sync_schedule: Mapped[str | None] = mapped_column(String(50))
    default_rate_limit: Mapped[int | None] = mapped_column(Integer)
    redaction_tier: Mapped[int] = mapped_column(Integer, default=1)
    setup_instructions: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    catalog_version: Mapped[str] = mapped_column(String(20))
```

- [ ] **Step 9: Update models/__init__.py with new imports**

Read the current `__init__.py`, then add imports for all new model files. The imports need to bring the model classes into scope so Alembic can detect them.

Add these imports:

```python
from app.models.departments import Department
from app.models.fees import FeeSchedule, FeeLineItem
from app.models.request_workflow import RequestTimeline, RequestMessage, ResponseLetter
from app.models.notifications import NotificationTemplate, NotificationLog
from app.models.prompts import PromptTemplate
from app.models.city_profile import CityProfile
from app.models.connectors import SystemCatalog, ConnectorTemplate
```

- [ ] **Step 10: Verify models import without errors**

```bash
cd backend && python -c "from app.models import *; print('All models imported successfully')"
```

- [ ] **Step 11: Commit model files**

```bash
git add backend/app/models/
git commit -m "feat: add SQLAlchemy models for Phase 2 tables

- departments, fee_schedules, fee_line_items
- request_timeline, request_messages, response_letters
- notification_templates, notification_log
- prompt_templates, city_profile
- system_catalog, connector_templates
- 12 new tables matching UNIFIED-SPEC Section 5 and 12.9"
```

---

## Task 2: Create Alembic Migration

**Files:**
- Create: `backend/alembic/versions/007_phase2_extensions.py`

- [ ] **Step 1: Generate the migration**

```bash
cd backend
DATABASE_URL=postgresql+asyncpg://civicrecords:civicrecords@localhost:5432/civicrecords \
  python -m alembic revision --autogenerate -m "phase2 extensions: 12 new tables and column additions"
```

This should auto-detect all 12 new tables from the new model files.

- [ ] **Step 2: Review the generated migration**

Read the generated migration file in `backend/alembic/versions/`. Verify it creates all 12 tables. Check for any issues.

- [ ] **Step 3: Add column alterations for existing tables**

The autogenerate won't catch column additions to existing models (since we haven't modified those model files yet). Manually add these `ALTER TABLE` operations to the migration's `upgrade()` function:

```python
# Add new columns to existing tables
# data_sources
op.add_column('data_sources', sa.Column('discovered_source_id', sa.Uuid(), nullable=True))
op.add_column('data_sources', sa.Column('connector_template_id', sa.Integer(), nullable=True))
op.add_column('data_sources', sa.Column('sync_schedule', sa.String(50), nullable=True))
op.add_column('data_sources', sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True))
op.add_column('data_sources', sa.Column('last_sync_status', sa.String(20), nullable=True))
op.add_column('data_sources', sa.Column('health_status', sa.String(20), nullable=True))
op.add_column('data_sources', sa.Column('schema_hash', sa.String(64), nullable=True))

# documents
op.add_column('documents', sa.Column('display_name', sa.String(500), nullable=True))
op.add_column('documents', sa.Column('department_id', sa.Uuid(), nullable=True))
op.add_column('documents', sa.Column('redaction_status', sa.String(20), server_default='none', nullable=False))
op.add_column('documents', sa.Column('derivative_path', sa.String(1000), nullable=True))
op.add_column('documents', sa.Column('original_locked', sa.Boolean(), server_default='false', nullable=False))

# records_requests
op.add_column('records_requests', sa.Column('requester_phone', sa.String(50), nullable=True))
op.add_column('records_requests', sa.Column('requester_type', sa.String(20), nullable=True))
op.add_column('records_requests', sa.Column('scope_assessment', sa.String(20), nullable=True))
op.add_column('records_requests', sa.Column('department_id', sa.Uuid(), nullable=True))
op.add_column('records_requests', sa.Column('estimated_fee', sa.Numeric(10, 2), nullable=True))
op.add_column('records_requests', sa.Column('fee_status', sa.String(20), nullable=True))
op.add_column('records_requests', sa.Column('fee_waiver_requested', sa.Boolean(), server_default='false', nullable=False))
op.add_column('records_requests', sa.Column('priority', sa.String(20), server_default='normal', nullable=False))
op.add_column('records_requests', sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True))
op.add_column('records_requests', sa.Column('closure_reason', sa.String(500), nullable=True))

# search_results
op.add_column('search_results', sa.Column('normalized_score', sa.Integer(), nullable=True))

# exemption_flags
op.add_column('exemption_flags', sa.Column('review_note', sa.Text(), nullable=True))
op.add_column('exemption_flags', sa.Column('detection_tier', sa.Integer(), nullable=True))
op.add_column('exemption_flags', sa.Column('detection_method', sa.String(50), nullable=True))
op.add_column('exemption_flags', sa.Column('auto_detected', sa.Boolean(), server_default='false', nullable=False))

# model_registry
op.add_column('model_registry', sa.Column('context_window_size', sa.Integer(), nullable=True))
op.add_column('model_registry', sa.Column('supports_ner', sa.Boolean(), server_default='false', nullable=False))
op.add_column('model_registry', sa.Column('supports_vision', sa.Boolean(), server_default='false', nullable=False))

# users — add department_id
op.add_column('user', sa.Column('department_id', sa.Uuid(), nullable=True))
op.create_foreign_key('fk_user_department', 'user', 'departments', ['department_id'], ['id'])
```

And corresponding `downgrade()` operations to drop all added columns.

- [ ] **Step 4: Run the migration**

```bash
cd backend
DATABASE_URL=postgresql+asyncpg://civicrecords:civicrecords@localhost:5432/civicrecords \
  python -m alembic upgrade head
```

- [ ] **Step 5: Verify migration applied**

```bash
cd backend
DATABASE_URL=postgresql+asyncpg://civicrecords:civicrecords@localhost:5432/civicrecords \
  python -c "
import asyncio
from sqlalchemy import text
from app.database import engine

async def check():
    async with engine.begin() as conn:
        result = await conn.execute(text(
            \"SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name\"
        ))
        tables = [r[0] for r in result.fetchall()]
        print(f'Tables ({len(tables)}):')
        for t in tables:
            print(f'  {t}')

asyncio.run(check())
"
```

Expected: 28+ tables (16 existing + 12 new).

- [ ] **Step 6: Run existing tests to verify no regression**

```bash
cd backend
DATABASE_URL=postgresql+asyncpg://civicrecords:civicrecords@localhost:5432/civicrecords \
  python -m pytest tests/ -q
```

Expected: 80/80 passing.

- [ ] **Step 7: Commit migration**

```bash
git add backend/alembic/
git commit -m "feat: add Alembic migration 007 — 12 new tables, extend 6 existing tables

- New: departments, fee_schedules, fee_line_items, request_timeline,
  request_messages, response_letters, notification_templates,
  notification_log, prompt_templates, city_profile, system_catalog,
  connector_templates
- Extended: data_sources, documents, records_requests, search_results,
  exemption_flags, model_registry, user
- All columns match UNIFIED-SPEC Section 5 and Section 12.9"
```

---

## Task 3: Update Existing Model Files with New Columns

**Files:**
- Modify: `backend/app/models/documents.py` (or equivalent)
- Modify: `backend/app/models/requests.py` (or equivalent)
- Modify: `backend/app/models/search.py` (or equivalent)
- Modify: `backend/app/models/exemptions.py` (or equivalent)

The migration adds columns at the database level, but the SQLAlchemy model classes also need the new column definitions so the ORM can read/write them.

- [ ] **Step 1: Read each existing model file and add the new columns**

For each model that got new columns, add the `mapped_column` definitions matching what the migration created. The model files to modify depend on how they're organized — read them first to find the right classes.

Add to the `DataSource` model:
```python
discovered_source_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
connector_template_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
sync_schedule: Mapped[str | None] = mapped_column(String(50), nullable=True)
last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
last_sync_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
health_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
schema_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
```

Add to the `Document` model:
```python
display_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
department_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
redaction_status: Mapped[str] = mapped_column(String(20), server_default="none")
derivative_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
original_locked: Mapped[bool] = mapped_column(Boolean, server_default="false")
```

Add to the `RecordsRequest` model:
```python
requester_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
requester_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
scope_assessment: Mapped[str | None] = mapped_column(String(20), nullable=True)
department_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
estimated_fee: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
fee_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
fee_waiver_requested: Mapped[bool] = mapped_column(Boolean, server_default="false")
priority: Mapped[str] = mapped_column(String(20), server_default="normal")
closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
closure_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
```

Add to `SearchResult`, `ExemptionFlag`, `ModelRegistry`, and `User` models similarly.

- [ ] **Step 2: Verify models still import**

```bash
cd backend && python -c "from app.models import *; print('OK')"
```

- [ ] **Step 3: Run tests**

```bash
cd backend
DATABASE_URL=postgresql+asyncpg://civicrecords:civicrecords@localhost:5432/civicrecords \
  python -m pytest tests/ -q
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/
git commit -m "feat: add new columns to existing SQLAlchemy models

- DataSource: discovery, connector, sync, health fields
- Document: display_name, department, redaction, derivative
- RecordsRequest: phone, type, scope, fees, priority, closure
- SearchResult: normalized_score
- ExemptionFlag: detection_tier, method, auto_detected, review_note
- ModelRegistry: context_window_size, supports_ner/vision
- User: department_id"
```

---

## Summary

After Phase 2A:
- 12 new SQLAlchemy model classes across 7 new model files
- 1 Alembic migration (007) creating 12 tables and extending 6 existing tables
- ~30 new columns on existing tables
- All 80 existing tests still passing
- Database schema matches UNIFIED-SPEC Section 5 + Section 12.9
