CivicRecords AI
Unified Design Specification
Version 3.1 — Repo-Verified Canonical
April 13, 2026

| Field | Value |
|---|---|
| Status | Canonical — verified against repository at commit head |
| Supersedes | All prior spec versions (v2.0, v2.2, v3.0, v3.0.1) |
| Repository | github.com/scottconverse/civicrecords-ai |
| Current release | v1.1.0 (April 13, 2026) — versions aligned across all files |
| Test suite | 276 automated tests across 45 test modules (274 at v1.1.0; +2 unreleased post-v1.1.0 for `request_received` dispatch) |
| Method | GitHub API crawl of repo structure, README, CHANGELOG, config files, module directories, and in-repo RECONCILIATION doc |

Status Legend: [IMPLEMENTED] evidenced in code, tests, and routes. [PARTIAL] present but incomplete. [UI SHELL] interface exists without full backend capability. [PLANNED] not implemented. [NEW in v1.1.0] added in current release.

## 1. Purpose of This Document
This is the single source of truth for CivicRecords AI. It merges comprehensive design detail with implementation status verified directly against the repository at commit head. Every feature is tagged with its actual implementation state.
When narrative claims and repository evidence disagree, repository evidence wins. This document replaces all prior spec versions.

### 1.1 Version Alignment (Resolved)
As of v1.1.0, version numbers are aligned across all four authoritative files:
backend/app/config.py: APP_VERSION = "1.1.0"
backend/pyproject.toml: version = "1.1.0"
frontend/package.json: version = "1.1.0"
CHANGELOG.md: [1.1.0] - 2026-04-13
The version drift documented in prior spec versions has been resolved. The CHANGELOG now covers three releases: 0.1.0 (foundation), 1.0.0 (design system + core features), and 1.1.0 (department scoping, compliance, and feature sprint).

## 2. Product Summary

### 2.1 What It Is
Open-source, locally-hosted AI system for municipal open records request processing. Runs on commodity hardware via Docker. No cloud, no vendor lock-in, no telemetry.

### 2.2 North-Star Statement
Any resident should be able to search for public records, request what is missing, and understand the status of their request without needing insider knowledge of city government.
Staff corollary: Any records clerk should be able to triage, search, review, redact, and respond to records requests from a single calm interface without falling back to email, spreadsheets, or paper.

### 2.3 What It Is Not
Not a records management system — it indexes and searches what already exists.
Not a legal advisor — it surfaces suggestions, staff make all decisions.
Not a cloud service — every deployment is a sovereign instance owned by the city.
Not a public-facing portal yet — internal staff tool first. Public portal is [PLANNED].

### 2.4 Design Stance & Principles
Transparent, calm, accessible, and government-appropriate. Trust through clarity, not visual excitement.
Clarity over bureaucracy — residents should not need to understand government structure.
Transparency over mystery — statuses, timelines, costs, and next actions always visible.
Consistency over one-off screens — shared patterns reduce confusion and cost.
Accessibility over compliance theater — forms must be usable, not merely valid.
Operational calm over case chaos — staff views aid triage, not add clutter.
Human-in-the-loop always — no auto-redaction, no auto-denial, no auto-release.

### 2.5 Current Product Scope
As of v1.1.0, the system implements:
Local deployment on a single-machine Docker stack (7 services)
Internal authentication with 6-role RBAC hierarchy
Department-level access controls with staff scoping
Document ingestion (PDF, DOCX, XLSX, CSV, email, HTML, text) with macro stripping
Hybrid search (semantic + keyword) with department filtering and CSV export
Request lifecycle management (10 statuses) with priority indicators
Exemption detection: 180 rules across 51 jurisdictions, Tier 1 PII detection, rule testing with ReDoS protection
Fee tracking with estimation, line items, and waiver workflows
Response letter generation with TipTap rich text editor
Notification service: 12 templates, SMTP delivery, dispatched via PATCH dynamic dispatch and 4 dedicated endpoints (see §8.3 for the audited matrix)
Operational analytics and dashboard with coverage gap indicators
Guided onboarding with LLM-powered adaptive interview
Municipal systems catalog (12 domains, 25+ vendors)
Connector framework (file system, IMAP email, manual drop)
Central LLM client with context manager, token budgeting, and prompt injection sanitization
Compliance templates (5 documents) and model registry
Hash-chained audit logging with CSV/JSON export
276 automated tests across 45 test modules (274 at v1.1.0; +2 post-v1.1.0)
Not yet implemented: public resident portal, public search/request tracking, full active network discovery engine, cross-instance federation workflows, liaison department-scoped UI (role exists, full scoping not complete), Tier 2/3 redaction.

## 3. User Groups & RBAC

### 3.1 Staff Users

| User Group | Primary Need | Design Response |
|---|---|---|
| City clerk / records officer | Triage, route, communicate, and complete requests. | Queue views, routing rules, templates, SLA timers, full event history. |
| Department liaison | Provide documents and answer scoped questions quickly. | Scoped assignment view, internal notes, due dates, one-click return to records team. |
| Legal / reviewer | Review exemptions, redactions, and sensitive material. | Review queue, exemption tags, redaction ledger, approval state. |
| City IT administrator | Install, configure, and maintain the system. | Docker Compose, admin panel, model management, audit export. |

### 3.2 Public Users [PLANNED]

| User Group | Primary Need | Design Response |
|---|---|---|
| Resident / first-time requester | Submit a request without knowing the exact record title. | Guided request flow, plain-language examples, estimated turnaround. |
| Journalist / researcher | Search existing records and request additional material. | Robust search, saved filters, exportable results, request history. |

### 3.3 RBAC Role Hierarchy [IMPLEMENTED]
All 6 roles are defined in UserRole enum with a numeric hierarchy. Role hierarchy enforced via check_department_access() and role-threshold checks on endpoints.

| Role | Level | Scope | Status |
|---|---|---|---|
| admin | 6 | Full system access, user management, configuration, model registry | [IMPLEMENTED] |
| reviewer | 5 | Everything staff can do + approve/reject responses and exemption flags | [IMPLEMENTED] |
| staff | 4 | Request management, search, ingestion, exemption review, fee management | [IMPLEMENTED] |
| liaison | 3 | Department-scoped via check_department_access(); can view department resources but cannot create requests or manage exemptions | [IMPLEMENTED] |
| read_only | 2 | View dashboards and reports only | [IMPLEMENTED] |
| public | 1 | Submit requests, track own requests, search published records | [IMPLEMENTED — role defined, no public endpoints yet] |

Service accounts with hashed API keys (SHA-256) enable instance-to-instance federation access.

## 4. Information Architecture

### 4.1 Staff Workbench — 13 Pages + Login
The frontend/src/pages/ directory contains 14 .tsx files:

| Page | Purpose | Status |
|---|---|---|
| Dashboard | System health, operational metrics, SLA overview, coverage gap warnings | [IMPLEMENTED] |
| Search | Hybrid RAG search with department filter, citation badges, CSV export | [IMPLEMENTED] |
| Requests | Request queue with triage, routing, SLA timers, priority badges | [IMPLEMENTED] |
| Request Detail | Single request: details, workflow, documents, timeline, fees, messages, response letter with rich text editor | [IMPLEMENTED] |
| Exemptions | Exemption rules management, flag review dashboard, rule test modal, audit history timeline | [IMPLEMENTED] |
| DataSources | Data source configuration with 3-step guided wizard and test connection | [IMPLEMENTED] |
| Ingestion | Document processing status, pipeline monitoring, retry failed documents | [IMPLEMENTED] |
| Users | User management, role assignment, department names, edit/deactivate with guards | [IMPLEMENTED] |
| Onboarding | 3-phase guided wizard with LLM-powered adaptive interview | [IMPLEMENTED] |
| City Profile | City configuration and metadata | [IMPLEMENTED] |
| Discovery | Network discovery preview page | [UI SHELL] |
| Settings | System settings | [IMPLEMENTED] |
| Audit Log | Audit event viewer with authenticated CSV/JSON export | [IMPLEMENTED] |
| Login | JWT authentication | [IMPLEMENTED] |

### 4.2 Public Portal [PLANNED]
No public-facing pages exist in the repository. Target design for future implementation:

| Page | Purpose | Status |
|---|---|---|
| Home | Search bar, common categories, response-time guidance | [PLANNED] |
| Search Records | Published records index with filters | [PLANNED] |
| Make a Request | Guided intake wizard with scope helper | [PLANNED] |
| Track a Request | Public timeline, messages, delivered files, fees | [PLANNED] |
| Help & Policy | Open records law summary, fee schedule, exemptions, contact | [PLANNED] |

### 4.3 Navigation Rules
Staff workbench: Sidebar navigation (240px fixed, 56px header). Grouped sections: Workflow / Setup / Administration. Active page highlighted with left border accent.
Public portal: Top navigation with no more than 6 top-level choices.
Every page identifiable from peripheral vision — unique page icon, header treatment, or accent color.

## 5. System Architecture

### 5.1 Docker Compose Stack [IMPLEMENTED]
The main docker-compose.yml defines a 7-service stack. Variant files exist for dev, GPU, and host-ollama configurations.

| # | Service | Role |
|---|---|---|
| 1 | postgres | PostgreSQL 17 + pgvector (data, vectors, audit) |
| 2 | redis | Redis 7.2 (BSD license, pinned <8.0) |
| 3 | api | FastAPI application server (port 8000) |
| 4 | worker | Celery worker(s) for async ingestion/embedding/notifications |
| 5 | beat | Celery Beat scheduler (60s notification dispatch interval) |
| 6 | ollama | Local LLM runtime (Gemma 4 26B + nomic-embed-text) |
| 7 | frontend | React/nginx (port 8080) |

### 5.2 Backend Modules (20 directories)
All modules listed with their implementation status:

| Module | Responsibility | Status |
|---|---|---|
| auth | fastapi-users, JWT, RBAC, 6-role hierarchy, service accounts | [IMPLEMENTED] |
| search | Hybrid RAG (semantic + keyword via RRF), department filter, CSV export, AI synthesis | [IMPLEMENTED] |
| requests | Request CRUD, 10 status transitions, timeline, messages, fees, response letters | [IMPLEMENTED] |
| audit | Hash-chained append-only logging, CSV/JSON export, chain verification | [IMPLEMENTED] |
| llm | Central LLM client (client.py), context manager (context_manager.py), prompt injection sanitization, model-registry budget scaling | [IMPLEMENTED] |
| exemptions | Rules engine (regex/keyword/statutory), LLM reviewer, Tier 1 PII patterns, rule test with ReDoS protection, audit history | [IMPLEMENTED] |
| notifications | 12 templates, SMTP delivery via smtp_delivery.py, queue_notification() via PATCH dynamic dispatch + 4 dedicated endpoints (see §8.3), Celery beat 60s tick | [IMPLEMENTED] |
| analytics | Operational metrics: response time, deadline compliance, overdue count, status breakdown | [IMPLEMENTED] |
| departments | Department CRUD, access control, staff scoping | [IMPLEMENTED] |
| datasources | Source CRUD, 3-step wizard, test-connection endpoint | [IMPLEMENTED] |
| documents | Document metadata, chunk management | [IMPLEMENTED] |
| ingestion | Two-track pipeline (parsers + multimodal OCR), retry endpoint, macro stripping | [IMPLEMENTED] |
| connectors | Universal protocol (authenticate/discover/fetch/health_check): file_system, imap_email, manual_drop | [IMPLEMENTED] |
| catalog | Municipal systems catalog (12 domains, 25+ vendors), auto-loader | [IMPLEMENTED] |
| city_profile | City configuration, gap map, template variable source | [IMPLEMENTED] |
| onboarding | 3-phase wizard, LLM-powered adaptive interview with fallback | [IMPLEMENTED] |
| admin | User edit/deactivate (self-demotion guard), model registry CRUD, fee schedules, coverage gaps, compliance template render | [IMPLEMENTED] |
| service_accounts | API key generation/hashing for federation | [IMPLEMENTED] |
| schemas | Pydantic request/response schemas | [IMPLEMENTED] |
| models | SQLAlchemy 2.0 models (15 model files) | [IMPLEMENTED] |

### 5.3 Central LLM Client [NEW in v1.1.0]
All LLM generation calls route through backend/app/llm/client.py, which enforces:
Context manager token budgeting on every call
Prompt injection sanitization
Model-registry context window scaling (reads context_window_size from model_registry table)
Refactored consumers: exemptions reviewer, search synthesizer, ingestion extractor, onboarding interview.

### 5.4 Context Manager [IMPLEMENTED]
backend/app/llm/context_manager.py implements priority-based context assembly for local LLM calls:
TokenBudget dataclass with configurable allocations: system_instruction (500), request_context (500), retrieved_chunks (5000), exemption_rules (500), output_reservation (1500), safety_margin (192)
estimate_tokens() function (~1 token per 4 chars)
assemble_context() — prioritizes system > request > top-k chunks > exemption rules within budget
ContextBlock data structure for organized prompt assembly
Model-aware budgeting: reads context_window_size from model_registry, auto-adjusts when admin switches models

## 6. Data Model
15 model files in backend/app/models/. The README states 29 database tables and ~30 API endpoints. All tables below are [IMPLEMENTED] unless noted.

### 6.1 Auth & Administration
users: id, email, hashed_password, display_name, role (6-value enum), department_id, is_active, is_verified, created_at
departments: id, name, code, contact_email, created_at
audit_log: id, user_id, action, resource_type, resource_id, details (JSON), ip_address, previous_hash, current_hash, created_at
service_accounts: id, name, api_key_hash (SHA-256), role, scopes (JSON), created_by, is_active

### 6.2 Documents & Ingestion
data_sources: id, name, type (file_share/database/email/upload/sharepoint/api), connection_config (encrypted JSON), schedule, status, created_by, department_id
documents: id, source_id, source_path, filename, display_name, file_type, file_hash (SHA-256), file_size, ingestion_status, ingested_at, metadata (JSON), department_id
document_chunks: id, document_id, chunk_index, content_text, embedding Vector(768), token_count

### 6.3 Search & RAG
search_sessions: id, user_id, created_at
search_queries: id, session_id, query_text, filters (JSON), results_count, ai_summary, created_at
search_results: id, query_id, chunk_id, similarity_score, rank, normalized_score (0–100)

### 6.4 Request Tracking
records_requests: id, requester_name, requester_email, requester_phone, requester_type, date_received, statutory_deadline, description, scope_assessment (narrow/moderate/broad), status, assigned_to, department_id, estimated_fee, fee_status, fee_waiver_requested, priority (urgent/expedited/normal/low), created_by, closed_at, closure_reason
Status ENUM (10 values): received, clarification_needed, assigned, searching, in_review, ready_for_release, drafted, approved, fulfilled, closed
request_documents: id, request_id, document_id, relevance_note, exemption_flags (JSON), inclusion_status
request_timeline: id, request_id, event_type, actor_id, actor_role, description, internal_note, created_at
request_messages: id, request_id, sender_type, sender_id, message_text, is_internal, created_at
response_letters: id, request_id, template_id, generated_content, edited_content (HTML via TipTap), status (draft/approved/sent), generated_by, approved_by, sent_at

### 6.5 Fees [IMPLEMENTED]
fee_schedules: id, jurisdiction, fee_type, amount, description, effective_date, created_by
fee_line_items: id, request_id, fee_schedule_id, description, quantity, unit_price, total, status
fee_waivers [NEW in v1.1.0]: id, request_id, waiver_type (indigency/public_interest/media/government/other), status (pending/approved/denied), automatic fee_status update on approval

### 6.6 Notifications [IMPLEMENTED]
notification_templates: id, event_type, channel, subject_template, body_template, is_active, created_by. 12 templates aligned with all router-dispatched event types.
notification_log: id, template_id, recipient_email, request_id, channel, subject, body, status, sent_at, error_message, created_at. (`subject` and `body` were added in migration 011 to fix model-vs-DB drift.)

### 6.7 Exemption Detection [IMPLEMENTED]
exemption_rules: id, state_code, category, rule_type (regex/keyword/statutory), rule_definition, description, enabled, version, created_by, created_at. 180 rules across 51 jurisdictions (50 states + DC). (`version` was added in migration 011 to fix model-vs-DB drift.)
exemption_flags: id, chunk_id, rule_id, request_id, category, confidence, status, reviewed_by, reviewed_at, review_note
redaction_ledger [PLANNED]: id, request_id, document_id, page_number, redaction_type, exemption_basis, redacted_by, created_at

### 6.8 Discovery & Connection
city_profile [IMPLEMENTED]: City metadata, gap map, template variable source
connectors [IMPLEMENTED]: Connector templates and framework
discovered_sources [PLANNED]: Active discovery results
discovery_runs [PLANNED]: Discovery execution log
source_health_log [PLANNED]: Connection health tracking
coverage_gaps [IMPLEMENTED]: Dashboard indicators for missing jurisdiction rules, unassigned departments, and inactive exemption categories

### 6.9 Other
prompts: Prompt template storage
model_registry: Admin-managed Ollama models with context_window_size for budget scaling

## 7. Visual Design System

### 7.1 Design Tokens

| Token | Value | Usage |
|---|---|---|
| brand.primary | #1F5A84 | Core actions, links, active navigation |
| brand.primaryDark | #163D59 | Page titles, hover states |
| brand.primaryLight | #E8F0F7 | Info backgrounds, selected states |
| text.default | #1F2933 | Body text, headings |
| text.muted | #5B6975 | Secondary text, labels, metadata |
| surface.default | #FFFFFF | Page background, card background |
| surface.subtle | #F6F9FB | Alternate row, section background |
| surface.border | #C8D3DC | Card borders, dividers |
| status.success | #2B6E4F | Completed, released, available |
| status.warning | #8A5A0A | Pending, clarification needed, approaching deadline |
| status.danger | #8B2E2E | Overdue, denied, failed |

### 7.2 Typography
Note: The frontend uses Geist Variable (@fontsource-variable/geist v5.2.8), imported in `main.tsx` and wired through `globals.css` body font-family and `tailwind.config.js` fontFamily.sans. Prior to commit `2663836` the dependency was declared but never imported, so the rendered font fell back to the system sans stack; the CHANGELOG v1.0.0 entry has also been corrected from "Inter typography scale" to "Geist Variable typography scale." Typography targets below are Geist metrics.

| Element | Current | Target |
|---|---|---|
| H1 (page title) | Not used | 36px / 700 weight |
| H2 (section head) | 20px / 600 weight | 28px / 600 weight |
| H3 (subsection) | 14px / 500 weight | 22px / 600 weight |
| Body | 16px / 400 weight | 16px / 400 weight |
| Labels | 14px / mixed | 13px / 500 weight / uppercase / 0.05em |
| Stat card numbers | Mixed | 36px / 700 weight for primary metrics |

### 7.3 Status Badges
Every badge includes an icon — never color-only. StatusBadge component maps color+icon across request, document, and exemption domains.

| Status | Color Role | Icon | Priority |
|---|---|---|---|
| Received | info (blue) | Inbox | — |
| Clarification needed | warning (amber) | MessageCircle | — |
| Assigned | info (blue) | UserCheck | — |
| Searching | info (blue) | Search | — |
| In review | warning (amber) | Eye | — |
| Ready for release | success (green) | CheckCircle | — |
| Drafted | info (blue) | FileText | — |
| Approved | success (green) | ShieldCheck | — |
| Fulfilled | success (green) | Send | — |
| Closed | neutral (gray) | Archive | — |

### 7.4 Priority Badges [NEW in v1.1.0]

| Priority | Color | Usage |
|---|---|---|
| Urgent | Red/danger badge | Legally mandated expedited processing |
| Expedited | Amber/warning badge | High-priority by policy or volume |
| Normal | Blue/info badge | Standard processing timeline |
| Low | Gray/neutral badge | Bulk or low-urgency requests |

### 7.5 Button Variants (3 only)

| Variant | Use | Style |
|---|---|---|
| Primary | Main page action (New Request, Submit for Review) | Filled brand.primary, white text |
| Secondary | Supporting actions (Search & Attach, Export) | Outlined brand.primary border, transparent bg |
| Ghost | Tertiary actions (Sign out, Cancel, Back) | Text-only, hover bg surface.subtle |

### 7.6 Reusable Components [IMPLEMENTED]
StatCard — metric display with loading, empty, and error states
PageHeader — consistent page titles
EmptyState — smart contextual guidance ("No flags reviewed yet" not "0.0%")
DataTable — sortable, filterable tables with loading states
StatusBadge — color+icon mapping across all domains

## 8. Workflow Patterns

### 8.1 Request Lifecycle [IMPLEMENTED]
10 statuses: [Received] → [Clarification Needed]? → [Assigned] → [Searching] → [In Review] → [Ready for Release] → [Drafted] → [Approved] → [Fulfilled] → [Closed]
Every status transition writes to request_timeline, writes to audit_log, triggers notification dispatch (if template exists), and updates records_requests.status.

The lifecycle has 10 statuses. The legacy `sent` value was removed in migration 010 — it was a leftover from the original v0.1.0 enum, marked in code as a "legacy alias for fulfilled" and orphaned by the broken Mark Fulfilled UX path (see section 8.3). Migration 010 collapses any historical `sent` rows into `fulfilled` and drops the enum value via the standard rename-recreate dance.
### 8.2 Response Letter Generation [IMPLEMENTED]
Clerk clicks [Generate Response Letter] on Request Detail.
Central LLM client assembles context within token budget via context manager.
LLM generates draft letter (labeled "AI-GENERATED DRAFT — REQUIRES HUMAN REVIEW").
Clerk edits in TipTap rich text editor (bold, italic, underline, bullet/ordered lists). Content stored as HTML.
Submit for Approval → Supervisor reviews → Approve → Send.

### 8.3 Notification Dispatch [IMPLEMENTED]
12 notification templates seeded. Dispatch is via the PATCH `/{request_id}` endpoint, which fires `queue_notification()` with a dynamically-built `event_type` of `request_{new_status}` for every reachable status transition. In addition, four dedicated POST endpoints (`submit_for_review`, `mark_ready_for_release`, `approve_request`, `reject_request`) call `queue_notification()` directly. `city_name` is sourced from `CityProfile` for template rendering. SMTP delivery is performed asynchronously by `smtp_delivery.py` driven by Celery beat (60s interval). Notification rows enter `notification_log` with `status='queued'` and are picked up on the next beat tick.

The Mark Fulfilled UX path was repaired in this release. The "Mark Fulfilled" button in `RequestDetail.tsx` had been pointing at `POST /requests/{id}/sent` — a route that does not exist — so every click 404'd and no notifications ever fired from that path. The button now PATCHes `status='fulfilled'`, which routes through the dynamic dispatch and produces the expected `request_fulfilled` notification. End-to-end manual verification (2026-04-14): a request walked through `searching → in_review → ready_for_release → approved → fulfilled` produces exactly five `notification_log` rows, one per transition, with rendered subjects.

#### Dispatch matrix (audited)

| Template event_type | Template seeded | Dispatch path | Status |
|---|---|---|---|
| `request_received` | yes | `create_request` (no call site) | OPEN — template-only; `create_request` does not yet call `queue_notification()` |
| `request_clarification_needed` | yes | PATCH dynamic | wired |
| `request_assigned` | yes | PATCH dynamic | wired |
| `request_searching` | yes | PATCH dynamic | wired |
| `request_in_review` | yes | PATCH dynamic + dedicated `submit_for_review` | wired |
| `request_ready_for_release` | yes | PATCH dynamic + dedicated `mark_ready_for_release` | wired |
| `request_drafted` | yes | PATCH dynamic + dedicated `reject_request` | wired |
| `request_approved` | yes | PATCH dynamic + dedicated `approve_request` | wired |
| `request_fulfilled` | yes | PATCH dynamic | wired (was unreachable until UI fix) |
| `request_closed` | yes | PATCH dynamic | wired |
| `request_deadline_approaching` | yes | Celery beat (no router call site) | OPEN — beat scheduler work, separate from router dispatch |
| `request_deadline_overdue` | yes | Celery beat (no router call site) | OPEN — beat scheduler work, separate from router dispatch |

The `sent` event type and the legacy `RequestStatus.SENT` enum value were removed in migration 010 (`010_remove_sent_status`). See section 8.1 for the lifecycle update.

#### Conceptual recipients (target design)

| Event | Recipient | Channel |
|---|---|---|
| Request received | Requester | Email |
| Clarification needed | Requester | Email |
| Request assigned | Liaison | In-app |
| Deadline approaching (3 days) | Assigned staff | In-app + Email |
| Deadline overdue | Assigned staff + Admin | In-app + Email |
| Records ready | Requester | Email |
| Request closed | Requester | Email |

### 8.4 Fee Workflow [IMPLEMENTED]
POST /requests/{id}/estimate-fees — staff enters page count, system calculates from fee schedule rates
Fee line items tracked per request with automatic total calculation
Fee waiver workflow: create waiver (indigency/public_interest/media/government/other) → approve/deny → automatic fee_status update on approval

### 8.5 Data Source Connection [NEW in v1.1.0]
3-step guided wizard replaces single-step add dialog
Step 1: Source type selection. Step 2: Connection config per type. Step 3: Review + test connection.
POST /datasources/test-connection validates connectivity without persisting credentials

### 8.6 Onboarding Interview [NEW in v1.1.0]
POST /onboarding/interview generates adaptive setup questions based on incomplete city profile fields
Chat-style UI with skip button
Profile updates via PATCH /city-profile
Falls back to default questions when LLM unavailable

## 9. Search & Ingestion [IMPLEMENTED]

### 9.1 Ingestion Pipeline
Two-track model:
Conventional parsers for structured/text-layer files (PDF, DOCX, XLSX, CSV, email, HTML, text)
Multimodal/OCR path for scanned/image-heavy material (Gemma 4 with Tesseract fallback)
[NEW] DOCX/XLSX macro stripping — VBA macros stripped at ZIP level before text extraction. Supports .docm and .xlsm. Stripping logged in metadata for audit.
[NEW] Legacy .xls blocklisted — BIFF8 binary format cannot be macro-stripped with ZIP approach
[NEW] Ingestion retry — POST /datasources/documents/{id}/re-ingest retries failed documents. Progress indicator for processing items, auto-refresh while active.
Sentence-aware text chunking with configurable overlap
Embeddings via nomic-embed-text through Ollama with batch support, stored in pgvector

### 9.2 Hybrid Search
Semantic search via pgvector embeddings
Keyword/full-text search via PostgreSQL tsvector
Combined via Reciprocal Rank Fusion (RRF)
Normalized relevance scoring (0–100 scale with visual progress bar)
Source attribution on every result
Optional AI-generated summaries (labeled as AI draft)
[NEW] Department filter — department dropdown filters via document-source-department join chain
[NEW] CSV export — GET /search/export with authenticated download
[NEW] Citation rendering — AI summary panel renders [Doc: filename, Page: N] as styled inline badges

## 10. Exemptions & Compliance

### 10.1 Exemption Rules [IMPLEMENTED]
180 rules across 51 jurisdictions (50 states + DC). Three rule types: regex, keyword, statutory.

### 10.2 Tier 1 PII Detection [IMPLEMENTED]
Built-in patterns: SSN, credit card (Luhn-validated), bank routing/account numbers, phone, email, DOB, state-specific driver's license patterns (CO, CA, TX, NY, FL).

### 10.3 Exemption Review Dashboard [IMPLEMENTED]
Acceptance/rejection rates
Export: /exemptions/dashboard/export?format=json|csv
[NEW] Rule test modal — POST /exemptions/rules/{id}/test tests regex or keyword rules against sample text with match positions. ReDoS protection via regex library with 2-second timeout. LLM-type rules rejected with 400.
[NEW] Audit history — GET /exemptions/rules/{id}/history returns audit log entries. Timeline UI in Exemptions page.

### 10.4 Tiered Redaction Engine [PLANNED]

| Tier | Method | What It Detects | Status |
|---|---|---|---|
| Tier 1 | RegEx pattern matching | SSNs, credit cards, phone, email, bank accounts, driver's licenses | [IMPLEMENTED — in exemption engine] |
| Tier 2 | NLP/NER (Ollama or spaCy) | Person names, medical info, juvenile IDs, attorney-client privilege | [PLANNED] |
| Tier 3 | Visual AI (GPU required) | Faces/plates in video, OCR for scanned docs, speech-to-text | [PLANNED] |

### 10.5 Compliance Architecture [IMPLEMENTED]

#### Human-in-the-Loop
No auto-redaction. Every exemption flag requires affirmative human action.
No auto-denial. No auto-release. All AI content labeled at API layer.

#### Audit Logging
Hash-chained (SHA-256), append-only. Every API call logged. CSV/JSON export. Chain verification endpoint.

#### Data Sovereignty
No outbound connections (verification script: scripts/verify-sovereignty.sh)
No telemetry, analytics beacons, or crash reporting. All LLM inference local via Ollama.
All dependencies permissive or weak-copyleft. No AGPL, SSPL, or BSL.

#### Compliance Templates (5 documents) [IMPLEMENTED]
AI governance policy, AI use disclosure, CAIA impact assessment, data residency attestation, response-letter disclosure
Template render endpoint with city profile variable substitution

#### Model Transparency [IMPLEMENTED]
Model registry CRUD in admin router. Context window tracking. Active model selection.

## 11. Universal Discovery & Connection Architecture

### 11.1 What Is Implemented
Guided onboarding wizard with LLM-powered adaptive interview [IMPLEMENTED]
City profile API with gap map [IMPLEMENTED]
Municipal systems catalog — 12 functional domains, 25+ vendor systems, bundled JSON with auto-loader [IMPLEMENTED]
Connector framework — universal protocol (authenticate/discover/fetch/health_check) [IMPLEMENTED]
Connectors: file_system.py, imap_email.py, manual_drop.py [IMPLEMENTED]
Dashboard coverage gaps — GET /admin/coverage-gaps [IMPLEMENTED]

### 11.2 What Is Not Yet Implemented
Active network scanning/discovery [UI SHELL — Discovery.tsx exists as preview page]
Automatic service fingerprinting [PLANNED]
REST API, ODBC/JDBC, GIS, Vendor SDK connectors [PLANNED]
Continuous discovery and self-healing [PLANNED]

### 11.3 Municipal Systems Catalog

| Domain | Typical Systems | Sensitivity |
|---|---|---|
| Finance & Budgeting | Tyler Munis, Caselle, OpenGov, SAP | Tax IDs, bank accounts, SSNs |
| Public Safety | Mark43, Spillman, Axon, Genetec | CJIS-protected, juvenile records |
| Land Use & Permitting | Accela, CityWorks, EnerGov | Homeowner PII, contractor data |
| Human Resources | NEOGOV, Workday, ADP, Paylocity | HIPAA, background checks, SSNs |
| Document Management | Laserfiche, OnBase, SharePoint | Varies |
| Email & Communication | Microsoft 365, Google Workspace | Personal emails, deliberations |
| Utilities & Public Works | CIS Infinity, Cartegraph, Lucity | Account numbers, payment info |
| Courts & Legal | Tyler Odyssey, Journal Technologies | Sealed records, juvenile cases |
| Parks & Recreation | RecTrac, CivicRec, ActiveNet | Minor personal info, payment data |
| Asset & Fleet Mgmt | Samsara, Asset Panda, FleetWave | Driver IDs, GPS patrol patterns |
| Legacy & Custom | AS/400, Access DBs, FoxPro, flat files | Often unknown |

### 11.4 Connector Protocol

| Protocol | Best For | Status |
|---|---|---|
| File System / SMB | Shared drives, document repos, scanned archives | [IMPLEMENTED] |
| SMTP / IMAP Journal | Email archives (#1 source for records requests) | [IMPLEMENTED] |
| Manual / Export Drop | Systems with no API — clerk uploads | [IMPLEMENTED] |
| REST API (Modern SaaS) | Tyler, Accela, NEOGOV, cloud platforms | [PLANNED] |
| ODBC / JDBC Bridge | On-prem databases, legacy SQL, AS/400 | [PLANNED] |
| GIS REST API | Esri ArcGIS, spatial data, property records | [PLANNED] |
| Vendor SDK | Evidence management (Axon), CAD systems | [PLANNED] |

### 11.5 Security for Connectors
Network discovery: disabled by default, explicit IT opt-in, audit-logged.
Every connection: admin must review, confirm, provide credentials, authorize.
Credentials: AES-256 encrypted at rest. Never logged, exported, or displayed after entry.
Test-connection endpoint: dedicated schema, never persists credentials, never logs connection strings.
Least-privilege: read-only accounts. System never writes to source systems.
CJIS Compliance: Architecture satisfies encryption (5.10.1), audit logging (5.4), access control (5.5), no cloud egress (5.10.3.2). City must satisfy fingerprint checks (5.12), signed addendum, and security training (5.2). Compliance gate blocks public safety connector activation until confirmed.

## 12. Security Hardening
Security measures implemented across the stack:
JWT authentication with configurable lifetime, minimum 32-char secret enforced at startup
Login rate limiting in main.py middleware
Role-based access control with 6-role numeric hierarchy
Self-demotion guard — admins cannot change their own role or deactivate their own account
Hash-chained audit log (SHA-256) — tamper-evident, append-only
Prompt injection sanitization in central LLM client
ReDoS protection — regex library with 2s timeout for admin-entered exemption patterns
VBA macro stripping from DOCX/XLSX at ZIP level before ingestion
Legacy .xls blocklisted (BIFF8 cannot be macro-stripped)
Test-connection credential safety — never persists, logs, or returns credentials
API keys hashed (SHA-256) before storage
No telemetry, no outbound connections, no crash reporting
SMTP credentials never logged or displayed after entry
All LLM outputs labeled as AI-generated drafts

## 13. Accessibility
Target: WCAG 2.2 AA. Session B (keyboard navigation audit) is complete as of this commit. **Session B also revealed that the Phase 1 hotfix claim in `b6627db` — that focus visibility was Met post-`2663836` — is incorrect.** The claim was based on CSS class-presence inspection, not on computed styles in a live browser. A real keyboard walk showed the intended 3px ring never renders on any shadcn primitive (see F1). Corrected below. Form error handling and full screen reader audit remain pending for Session C.

### 13.1 Scope of Session B
Session B is a keyboard navigation audit. It verified:
- Tab order, tab-stop completeness, skip-nav reachability, and `div onClick` / positive-tabindex hygiene on all 14 pages. Four pages were walked live via Chrome MCP + injected JS probes reading computed styles after a **real Tab keystroke** (Login, Dashboard, Requests, RequestDetail). The remaining ten pages were audited via static source read (Search, Exemptions, DataSources, Ingestion, Users, Onboarding, CityProfile, Discovery, Settings, AuditLog).
- Computed focus styles on **real** keyboard focus, not programmatic `el.focus()` — the latter does not trigger `:focus-visible` and would have silently passed the broken state reported in F1.

Session B did **not** verify and explicitly defers to **Session C**:
- Live screen reader announcements via NVDA or VoiceOver.
- Form error association and announcement on invalid submit (no validation states were triggered live).
- Dialog focus-trap behavior on live modals (shadcn / base-ui Dialog is structurally correct but unobserved in this audit).

### 13.2 WCAG 2.2 AA Requirements Summary

| Requirement | Current State | Status |
|---|---|---|
| Color contrast | Passes (text ~15:1, muted ~5.7:1) | Met |
| Touch targets | 44×44px enforced (min-width + min-height on all interactive elements, all icon button variants) | Met [v1.1.0] |
| Focus visibility | **Met (Session B.1).** `ring-3` → `ring-[3px]` fix shipped in this commit (see §13.4 F1). Post-rebuild computed-style verification after a real Tab keystroke: `--tw-ring-shadow` = `0 0 0 calc(3px + 0px) hsl(207 62% 32% / .5)` and `box-shadow` = `rgba(31, 87, 132, 0.5) 0px 0px 0px 3px` on keyboard-focused Button (Dashboard), Input (Onboarding "City Name"), and SelectTrigger (Requests filter bar); `focusVisible: true` on all three. The global `:focus-visible` outline fallback from `2663836` continues to render correctly on bare `<a>`, `[role="link"]`, and non-primitive `[tabindex]` elements. **Historical note:** Session B found that the Phase 1 hotfix (`b6627db`) incorrectly marked this "Met" — the 3px ring was never rendering on primitives because Tailwind v4 dropped the `ring-3` alias. Corrected to Partial in Session B, then fixed and confirmed Met in Session B.1. | Met (Session B.1) |
| Skip navigation | Skip-to-content link present and reachable as the first tab stop; verified live on Login, Dashboard, Requests, RequestDetail | Met [v1.0.0] |
| ARIA landmarks | `main`, `nav`, `header`, `h1` present on every page walked live | Met |
| Color-only indicators | StatusBadge uses icon+color across all domains | Met [v1.0.0] |
| Keyboard navigation | **Met — F2 resolved (Session B.1); F3–F6 resolved (Session B.2/C).** F2 resolved in Session B.1 — `data-table.tsx` TableRow `tabIndex={0}` + `role="button"` + `onKeyDown`; keyboard-only staff can open records requests. F3 resolved — DOM-confirmed: base-ui v1.3.0 already sets `tabindex="-1"` on its hidden form input; Requests filter bar reads 4 tab stops for 4 visible controls (was 10). F4 resolved — `aria-label` added to all 15 SelectTriggers across Exemptions, Onboarding, Requests, Search, Users. F5 resolved — `LoadingRegion` (`aria-live="polite"`, `aria-busy`) applied to Requests, AuditLog, Users, Exemptions, Search; Dashboard/DataSources early-return loading divs have `role="status"`. F6 resolved — 7 `<h2>` sections added to RequestDetail via CardTitle `as` prop. See §13.3 for per-page scoring and §13.4 for findings F2–F6. | Met — F2 resolved (B.1); F3–F6 resolved (B.2/C) |
| Form error handling | **Not tested in Session B.** No validation errors were triggered live. Source scan found 0 of 14 pages using `aria-describedby` / `aria-invalid` patterns in error UI, but the scan cannot confirm whether rendered error text is actually associated with its input. Full verification deferred to **Session C** (requires real invalid submits + screen reader listening). | Audit pending (Session C) |
| Screen reader | **Partial — F3–F6 fixes applied (Session B.2/C); full NVDA/VoiceOver audit deferred to Session C.** F3 (Select phantom inputs): DOM-confirmed already resolved in base-ui v1.3.0 — no code change needed. F4 (SelectTrigger `aria-label`): 15 instances fixed across Exemptions, Onboarding, Requests, Search, Users. F5 (`aria-live`/`aria-busy`): `LoadingRegion` component applied to Requests, AuditLog, Users, Exemptions, Search; Dashboard/DataSources early-return divs have `role="status"`. F6 (RequestDetail heading hierarchy): 7 `<h2>` sections — Request Details, Attached Documents, Timeline, Messages, Fees, Response Letter, Workflow. Form error handling (WCAG 3.3.1): Login "Login failed" error is `<p class="text-destructive">` with no `role="alert"`, no `aria-live`, no `aria-describedby` — NOT MET, flagged for Session C. Full SR verification (NVDA/VoiceOver) deferred to **Session C**. | Partial — fixes applied (B.2/C); full SR audit pending (Session C) |

### 13.3 Per-Page Audit Scorecard

"Not tested" in the form-error and screen-reader columns is deliberate — those are Session C scope and are carried forward without change. "N/A" means the page has no interactive surface of that type.

| Page | Focus visibility | Keyboard navigation | Form error handling | Screen reader |
|---|---|---|---|---|
| Login | Met (F1—B.1) | Met | Partial (no `role="alert"` on error — F8, Session C) | Partial (F5 — no async data load on this page; form error SR gap documented) |
| Dashboard | Met (F1—B.1) | Met | N/A | Met (F5—B.2/C; `role="status"` on loading div) |
| Search | Met (F1—B.1) | Met (F3—B.2/C) | Not tested | Met (F4, F5—B.2/C) |
| Requests | Met (F1—B.1) | Met (F3—B.2/C) | Not tested | Met (F4, F5—B.2/C) |
| RequestDetail | Met (F1—B.1) | Partial (scrollable regions not live-verified) | Not tested | Partial (F5 — LoadingRegion not yet applied); Met (F6—B.2/C) |
| Exemptions | Met (F1—B.1) | Met (F3—B.2/C) | Not tested | Met (F4, F5—B.2/C) |
| DataSources | Met (F1—B.1) | Met | Not tested | Met (F5—B.2/C; `role="status"` on loading div) |
| Ingestion | Met (F1—B.1) | Met | N/A | Partial (F5 — LoadingRegion not yet applied) |
| Users | Met (F1—B.1) | Met (F3—B.2/C) | Not tested | Met (F4, F5—B.2/C) |
| Onboarding | Met (F1—B.1) | Met (F3—B.2/C) | Not tested | Met (F4—B.2/C); Partial (F5 — no DataTable, loading state not covered) |
| CityProfile | Met (F1—B.1) | Met | Not tested | Partial (F5 — LoadingRegion not yet applied) |
| Discovery | Met (F1—B.1) | Met | N/A | Met (UI shell — nothing to announce) |
| Settings | N/A (no interactives) | N/A | N/A | N/A |
| AuditLog | Met (F1—B.1) | Met | N/A | Met (F5—B.2/C) |

### 13.4 Findings F1–F7

**F1 — Tailwind v4 `ring-3` utility silently missing. Systemic across every page using shadcn primitives.**
`frontend/src/components/ui/button.tsx:7`, `input.tsx:12`, and `select.tsx:44` all ship className strings containing `focus-visible:ring-3 focus-visible:ring-ring/50`. The Tailwind v3 `ring-3` alias was removed in Tailwind v4; this project runs Tailwind v4 without a shim or theme alias. CSS bundle scan via `document.styleSheets` returns zero rules matching `.focus-visible\:ring-3:focus-visible`. Computed `--tw-ring-shadow` resolves to `0 0 #0000` and `box-shadow` is `none` on a genuinely keyboard-focused primitive. Only `focus-visible:border-ring` actually renders, producing a 1px border color swap to brand `#1F5784` — which likely fails WCAG 2.2 AA 1.4.11 Non-text Contrast (3:1 required). The global `:focus-visible` fallback in `globals.css @layer base` renders correctly but intentionally excludes `[data-slot]`, so it does not backstop the primitives. **Severity: Partial system-wide.** Remediation: three one-line edits (`ring-3` → `ring-[3px]` on Button / Input / SelectTrigger), OR a Tailwind v4 theme config alias mapping `ring-3` to `3px`. Queued for **Session B.1**. **RESOLVED in Session B.1 (this commit).** Three edits: `button.tsx:7`, `input.tsx:12`, `select.tsx:44` — `ring-3` → `ring-[3px]` (and `aria-invalid:ring-3` → `aria-invalid:ring-[3px]` on each). Post-rebuild computed-style verification: `--tw-ring-shadow` = `0 0 0 calc(3px + 0px) hsl(207 62% 32% / .5)`, `box-shadow` = `rgba(31, 87, 132, 0.5) 0px 0px 0px 3px` on keyboard-focused Button (Dashboard), Input (Onboarding "City Name"), and SelectTrigger (Requests filter bar, index 0). `focusVisible: true` on all three.

**F2 — `data-table.tsx` rows are mouse-only clickable. WCAG 2.1.1 Keyboard hard fail on Requests.**
`frontend/src/components/data-table.tsx:89-91`:
```tsx
<TableRow
  className={cn(onRowClick && "cursor-pointer hover:bg-muted/50")}
  onClick={() => onRowClick?.(row)}
>
```
No `tabIndex`, `role="button"`, `onKeyDown`, inner anchor, or inner button. Live DOM confirmation on Requests: `rowTabindex: null, rowRole: null, anchors: [], buttons: [], hasOnclick: true`. **A keyboard-only staff member cannot open a records request from the list.** This is the most user-visible accessibility bug in the product — a hard functional blocker, not a cosmetic gap. Blast radius today is exactly 1 page: `grep onRowClick` confirms `Requests.tsx:400` is the sole consumer. But the fix is in the shared component so any future consumer inherits it automatically. **Severity: Not Met on Requests; Met elsewhere.** Remediation: add `tabIndex={0}`, `role="button"`, and `onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), onRowClick?.(row))}` to the TableRow in `data-table.tsx`. **One edit. Queued for Session B.1. Sequenced before F1 because severity is orders of magnitude higher.** **RESOLVED in Session B.1 (this commit).** `tabIndex={0}`, `role="button"`, and `onKeyDown` (Enter/Space with `e.preventDefault()`) added to `data-table.tsx:89`. Post-fix verification on Requests page: `<tr>` has `role="button"`, `tabIndex=0`, `focusVisible: true`; Enter key navigated to `/requests/ee112475-788d-49dc-8830-6ea8a66bb9d5`; Space key confirmed same (back-nav + re-test). Both activation keys working.

**F3 — base-ui Select hidden form-input leaks into tab order. Inferred system-wide; confirmed live on Requests.**
base-ui's `@base-ui/react/select` renders a hidden native `<input>` alongside the SelectTrigger for form integration and does not set `tabindex="-1"` on it. On the Requests filter bar (4 SelectTriggers), live tab order reads `select-trigger → phantom-input → select-trigger → phantom-input → select-trigger → phantom-input → select-trigger → phantom-input → date → date` — 10 tab stops for 6 visible controls. Inferred from shared-primitive usage to apply to every page with `<Select>`: Search, Exemptions, DataSources, Users, Onboarding, CityProfile, Requests. **Severity: Partial keyboard-nav + Partial screen-reader** on every affected page — controls are eventually reachable, just disorientingly, and an SR user hears a content-less listbox/input pair per filter. Remediation: global CSS selector to set `tabindex="-1"` on the pattern, OR an upstream fix to base-ui Select. Queued for **Session B.2 or Session C**. **RESOLVED (Session B.2/C — no code change required).** DOM inspection of Requests filter bar in base-ui v1.3.0 confirmed: hidden inputs already carry `tabindex="-1"`. Requests filter bar now reads exactly 4 tab stops for 4 visible controls. No upstream fix needed; base-ui already resolved this in v1.3.0.

**F4 — SelectTrigger missing `aria-label`. Inferred system-wide; confirmed live on Requests filter bar.**
All 4 SelectTriggers on the Requests filter bar have `aria-haspopup="listbox"` and `aria-expanded="false"` correctly, but `aria-label` is `null`. Visual labels are rendered as adjacent text, not associated via `<label for>` or `aria-labelledby`. A screen-reader user tabs onto four consecutive unlabeled listboxes and cannot disambiguate them. Inferred to affect every SelectTrigger in the app. **Severity: Partial screen-reader.** Remediation: add explicit `aria-label` prop to every SelectTrigger, or wrap each in a `<Label>` with `htmlFor`. Queued for **Session B.2 or Session C**. **RESOLVED (Session B.2/C).** `aria-label` added to all 15 SelectTriggers across 5 pages: `Exemptions.tsx` (1 — "Exemption category"), `Onboarding.tsx` (5 — "State", "Population band", "Email platform", "Dedicated IT department", "Monthly records request volume"), `Requests.tsx` (4 — "Status filter", "Department filter", "Priority filter", "Assigned to filter"), `Search.tsx` (2 — "File type filter", "Department filter"), `Users.tsx` (3 — "User role" ×2, "Department"). Verified via DOM on Requests filter bar: all 4 SelectTriggers show non-null `aria-label` attributes.

**F5 — Data-loading pages lack `aria-live` / `aria-busy` regions. Every page with async data.**
Confirmed in static source audit (7 of 10 non-live-walked pages) and live DOM on Dashboard and Requests (`ariaLiveRegions: 0, ariaBusyElements: 0`). Loading spinners do not announce state transitions to screen readers, and when data arrives the UI change is silent. **Severity: Partial screen-reader** on every page with async data. Remediation: a shared `<LoadingRegion aria-live="polite" aria-busy={isLoading}>` helper, applied to the standard `isLoading` patterns in each page. Queued for **Session B.2 or Session C**. **RESOLVED on 6 pages + 2 early-return divs (Session B.2/C).** Created `frontend/src/components/loading-region.tsx` — a thin wrapper with `aria-live="polite"` and `aria-busy={loading}`. Applied as a DataTable wrapper in: `Requests.tsx`, `AuditLog.tsx`, `Users.tsx`, `Exemptions.tsx`; and as a results wrapper in `Search.tsx`. Early-return loading `<div>` elements upgraded with `role="status"` + `aria-label` in: `Dashboard.tsx` ("Loading dashboard data"), `DataSources.tsx` ("Loading data sources"). Remaining pages with loading states (RequestDetail, Ingestion, CityProfile, Onboarding, Login) carry the partial forward to Session C.

**F6 — RequestDetail heading hierarchy is flat.**
Live walk: `<h1> = 1, <h2> = 0`. The page has at least 5 logical sections (Overview / Status, Actions, Messages, Fees, Timeline) but screen-reader heading navigation surfaces a single landmark. **Severity: Partial screen-reader** on RequestDetail. Remediation: add `<h2>` per section in `RequestDetail.tsx`. Queued for **Session B.2 or Session C**. **RESOLVED (Session B.2/C).** Added polymorphic `as` prop to `CardTitle` in `frontend/src/components/ui/card.tsx` (`as?: React.ElementType`, defaults to `"div"`). Applied `as="h2"` to 7 sections in `RequestDetail.tsx`: Request Details, Attached Documents, Timeline, Messages, Fees, Response Letter, Workflow. Note: `@radix-ui/react-slot` is not installed (project uses base-ui, not radix); the `as` pattern achieves identical semantic result without adding a dependency. Post-edit: `<h1>=1, <h2>=7` in RequestDetail.

**F7 — Non-WCAG observation: sidebar nav order buries Dashboard 9th.**
Live walk: sidebar nav order is `Search, Requests, Exemptions, Onboarding, City Profile, Sources, Ingestion, Discovery, Dashboard, Users, Settings, Audit Log`. `/` resolves to Dashboard but a keyboard user Tabs past 8 unrelated items before reaching the "home" destination. Not a WCAG failure — an information architecture choice — but it compounds with F1 (weak focus indicator makes the long Tab walk more disorienting). **Severity: observation only, not scored.** Flagged for product decision, not engineering remediation.

### 13.5 Remediation sequencing

**Session B.1** — **DONE (this commit).** Single commit, single frontend rebuild:
- **F2 first.** `data-table.tsx` TableRow `tabIndex={0}` + `role="button"` + `onKeyDown` (Enter/Space) — keyboard-only staff can now open records requests. Highest user-visible severity in the whole audit. Verified: Enter and Space both navigated to `/requests/<uuid>` from keyboard focus.
- **F1 second.** `ring-3` → `ring-[3px]` on Button, Input, SelectTrigger — 3px brand-color ring restored across every primitive system-wide. Verified: `--tw-ring-shadow` = `0 0 0 calc(3px + 0px) hsl(207 62% 32% / .5)` and `box-shadow` = `rgba(31, 87, 132, 0.5) 0px 0px 0px 3px` on all three primitives after a real Tab keystroke.

**Session B.2/C** — **DONE (this commit).** F3–F6 all resolved:
- **F3**: DOM-confirmed resolved in base-ui v1.3.0 — no code change needed. Requests filter bar: 4 tab stops for 4 controls.
- **F4**: `aria-label` on all 15 SelectTriggers across 5 pages. DOM-verified on Requests.
- **F5**: `LoadingRegion` (`aria-live="polite"`, `aria-busy`) component; applied to Requests, AuditLog, Users, Exemptions, Search; `role="status"` on Dashboard + DataSources early-return divs.
- **F6**: CardTitle `as` prop; 7 `<h2>` sections in RequestDetail. `<h1>=1, <h2>=7` verified.
- **Dialog focus trap**: Verified on Exemptions new-exemption modal. `focusInsideDialog=true` on open; Tab cycles within dialog; Escape is a pre-existing controlled-dialog behavior (not introduced by our changes).
- **Form error handling (1d)**: Login "Login failed" rendered as `<p class="text-destructive">` — no `role="alert"`, no `aria-live`, no `aria-describedby`. **NOT MET** — flagged for Session C.

**Session C** — live screen reader audit (NVDA + VoiceOver), covering: form error handling (WCAG 3.3.1) — add `role="alert"` / `aria-describedby` to Login and other forms; SR announcement verification of F4/F5/F6 fixes; complete LoadingRegion coverage for RequestDetail, Ingestion, CityProfile, Onboarding; Dialog Escape behavior (controlled-dialog gap); and a final pass on the per-page scoring table to replace every "Not tested" cell.

### 13.6 Content Design Rules
Lead with action: "Tell us what records you need" not "Records Request Submission Form"
Explain why data is requested when not obvious.
Never hide important policy terms only in tooltips.
Every closed/denied request shows reason in human language plus formal basis.
Replace jargon: "responsive documents" → "records found for release"
Every error state explains: what happened, how to fix it, how to get help.
[v1.0.0] Smart empty states provide contextual guidance.

## 14. Documentation Suite
The docs/ directory contains a comprehensive documentation set:

| File | Purpose |
|---|---|
| docs/UNIFIED-SPEC.md (.docx) | This document — single source of truth (in-repo version is now v3.1) |
| docs/RECONCILIATION-2026-04-13.md | Gap analysis: spec vs. codebase with 16 Built / 0 Missing |
| docs/CANONICAL-SPEC-GAP-LIST.md | Gap list derived from canonical spec |
| docs/GAP-LIST-ACCURACY-REVIEW.md | Accuracy review of gap list |
| docs/QA-REPORT-2026-04-13.md | QA verification report |
| docs/SESSION-REPORT-2026-04-13.md | Development session report |
| docs/CHANGE-CONTROL.md | Change control process |
| docs/DESIGN-CRITIQUE.md | Design audit of v0.1.0 UI |
| docs/civicrecords-ai-manual.pdf/.docx/.html | Complete system manual (unified staff + IT admin) |
| docs/user-manual-staff.html | Staff user manual (non-technical) |
| docs/admin-manual-it.html | IT administrator manual |
| docs/architecture/system-architecture.html | Interactive component and data flow diagrams |
| docs/architecture/decomposition.html | Project phases and build sequence |
| docs/compliance-regulatory-analysis.md | 50-state regulatory analysis |
| docs/product-description.md | Product description |
| docs/github-discussions-seed.md | GitHub Discussions seed content |
| CONTRIBUTING.md | Development setup, coding standards, contribution guide |
| USER-MANUAL.md | User manual (root-level) |
| CLAUDE.md | Claude Code system prompt for development |

## 15. Release History

| Version | Date | Headline | Tests |
|---|---|---|---|
| 0.1.0 | April 12 | Foundation: Docker stack, auth, ingestion, search, requests, exemptions, 8 pages | 80 |
| 1.0.0 | April 12 | Design system (shadcn/ui), 11 pages, request lifecycle, fees, analytics, notifications, connectors, context manager | 104 |
| 1.1.0 | April 13 | Departments, 50-state exemptions, compliance templates, central LLM client, notification dispatch, user mgmt, search enhancements, fee waivers, rich text, macro stripping, coverage gaps, version alignment | 274 |
| _unreleased_ | April 14 | `request_received` dispatch on create, Mark Fulfilled 404 fix, SENT status removal (migration 010), schema drift fix (migration 011), spec v3.1 import, Session A accessibility (global `:focus-visible` fallback + Geist Variable font wiring), Session B accessibility audit (14-page keyboard walk, findings F1–F7, Phase 1 focus-visibility claim corrected from Met to Partial), Session B.1 accessibility fixes (F2: `data-table.tsx` keyboard row activation; F1: `ring-[3px]` on Button/Input/SelectTrigger), Session B.2/C accessibility fixes (F3: DOM-confirmed resolved in base-ui v1.3.0; F4: 15 SelectTrigger `aria-label`s; F5: `LoadingRegion` component + `role="status"` on Dashboard/DataSources; F6: CardTitle `as` prop + 7 `<h2>` in RequestDetail; dialog focus trap verified; form error handling flagged for Session C) | 276 |

## 16. Capability Summary

| Capability | Status |
|---|---|
| Core internal staff platform (13 pages + login) | [IMPLEMENTED] |
| Department scoping and access controls | [IMPLEMENTED] |
| 6-role RBAC hierarchy with numeric levels | [IMPLEMENTED] |
| Onboarding / city profile / systems catalog / LLM interview | [IMPLEMENTED] |
| Connector framework (file system, IMAP, manual drop) | [IMPLEMENTED] |
| Hybrid search with department filter, CSV export, citation rendering | [IMPLEMENTED] |
| Request lifecycle (10 statuses) with priority indicators | [IMPLEMENTED] |
| Fee tracking with estimation, line items, waiver workflows | [IMPLEMENTED] |
| Response letter generation with TipTap rich text editor | [IMPLEMENTED] |
| Notification service: 12 templates, SMTP delivery, PATCH-dynamic + 4 dedicated dispatch (see §8.3) | [IMPLEMENTED] |
| 50-state + DC exemption rules (180 rules), Tier 1 PII, rule testing | [IMPLEMENTED] |
| Context manager with token budgeting and model-aware scaling | [IMPLEMENTED] |
| Central LLM client with prompt injection sanitization | [IMPLEMENTED] |
| Operational analytics and coverage gap dashboard | [IMPLEMENTED] |
| Compliance templates (5 docs) and model registry | [IMPLEMENTED] |
| Hash-chained audit logging with export | [IMPLEMENTED] |
| 276 automated tests across 45 modules (274 at v1.1.0; +2 post-v1.1.0) | [IMPLEMENTED] |
| Version alignment across all files | [IMPLEMENTED] |
| WCAG: 44px touch targets, skip nav, icon+color badges | [IMPLEMENTED] |
| Full active discovery engine | [UI SHELL / PLANNED] |
| REST API / ODBC / GIS connectors | [PLANNED] |
| Public resident portal (5 pages) | [PLANNED] |
| Federation as a full product surface | [PLANNED] |
| Tier 2/3 redaction (NER, visual AI) | [PLANNED] |
| Redaction ledger | [PLANNED] |
| Saved searches | [PLANNED] |
| WCAG: focus visibility — global `:focus-visible` fallback (bare `<a>`, `[role="link"]`, non-primitive `[tabindex]`) | [IMPLEMENTED — post-v1.1.0 in `2663836`] |
| WCAG: focus visibility — shadcn Button / Input / SelectTrigger primitives | [IMPLEMENTED — Session B.1 (this commit). `ring-[3px]` fix on button.tsx, input.tsx, select.tsx; 3px brand-color ring verified post-rebuild on all three primitives.] |
| WCAG: keyboard navigation audit | [IMPLEMENTED — Session B, 14-page walk, 7 findings F1–F7 in §13.4] |
| WCAG: keyboard navigation — `data-table.tsx` row accessibility | [IMPLEMENTED — Session B.1. TableRow `tabIndex={0}` + `role="button"` + `onKeyDown`; Enter and Space key activation verified on Requests page.] |
| WCAG: keyboard navigation — F3 Select phantom tab stops | [IMPLEMENTED — Session B.2/C. DOM-confirmed: base-ui v1.3.0 already sets `tabindex="-1"` on hidden form inputs. No code change required. Requests filter bar: 4 tab stops for 4 controls.] |
| WCAG: screen reader — F4 SelectTrigger aria-labels | [IMPLEMENTED — Session B.2/C. `aria-label` on all 15 SelectTriggers across Exemptions, Onboarding, Requests, Search, Users.] |
| WCAG: screen reader — F5 aria-live loading regions | [IMPLEMENTED (partial) — Session B.2/C. `LoadingRegion` component (`aria-live="polite"`, `aria-busy`) wraps DataTable in Requests, AuditLog, Users, Exemptions, Search. `role="status"` on Dashboard + DataSources early-return divs. RequestDetail, Ingestion, CityProfile, Onboarding carry forward to Session C.] |
| WCAG: screen reader — F6 RequestDetail heading hierarchy | [IMPLEMENTED — Session B.2/C. CardTitle `as` prop added to card.tsx. 7 `<h2>` sections in RequestDetail: Request Details, Attached Documents, Timeline, Messages, Fees, Response Letter, Workflow.] |
| WCAG: form error handling | [NOT MET — Session C. Login "Login failed" error has no `role="alert"`, `aria-live`, or `aria-describedby`. Flagged for Session C fix.] |
| WCAG: screen reader testing | [AUDIT PENDING — Session C. SR fixes applied (B.2/C); full NVDA/VoiceOver verification deferred.] |

## 17. Next Priorities
Based on the repository as it exists now:
1. Accessibility audit — in progress.
   1a. Focus visibility — **DONE (Session B.1, this commit).** The global `:focus-visible` outline fallback from `2663836` (Session A) is Met on bare `<a>`, `[role="link"]`, and non-primitive `[tabindex]` elements. The shadcn primitive `ring-3` omission (F1) is now resolved — `ring-[3px]` ships on button.tsx, input.tsx, select.tsx; 3px brand-color ring confirmed via computed-style probe post-rebuild. See §13.4 F1 and §13.2.
   1b. Keyboard navigation audit — **DONE** in Session B (this commit). 14-page walk (4 live via Chrome MCP, 10 via source audit) with per-page WCAG 2.2 AA scoring in §13.3 and 7 findings F1–F7 in §13.4. Session B.1 handles the two blocking remediations; F3–F6 queued for Session B.2 or Session C.
   1c. **Session B.1 — F2 + F1 remediation — DONE (this commit).** F2 first (WCAG 2.1.1 hard fail): `data-table.tsx` TableRow `tabIndex={0}` + `role="button"` + `onKeyDown` for Enter/Space — keyboard-only staff can now open records requests. F1 second: `ring-3` → `ring-[3px]` on button.tsx, input.tsx, select.tsx — 3px brand-color ring restored on all shadcn primitives. Both fixes verified via Chrome MCP computed-style probe after rebuild. See §13.4 F1, F2 for verification evidence.
   1d. Form error handling — **PARTIAL.** Session B.2/C verified: Login "Login failed" error is visual-only (`<p class="text-destructive">`) with no `role="alert"`, `aria-live`, or `aria-describedby`. NOT MET — fix queued for Session C (add `role="alert"` to error containers; link inputs via `aria-describedby`).
   1e. Screen reader audit — **PARTIAL — fixes applied (Session B.2/C); full verification pending Session C.** F3–F6 code changes landed this commit. Remaining Session C scope: NVDA/VoiceOver verification of F4/F5/F6 fixes, form error ARIA (1d), Dialog Escape behavior (controlled-dialog gap on Exemptions), and complete LoadingRegion coverage for RequestDetail, Ingestion, CityProfile, Onboarding.
2. Liaison scoping completion — role constants and hierarchy are in place; build department-scoped UI views (hide Users/Audit Log/Onboarding nav items, filter Requests/Search to the liaison's department) and endpoint restrictions for liaison-level users. Backend `check_department_access()` already enforces the authoritative boundary; this is ~50 LOC frontend plus a handful of list-query filter params. Auditor's explicit pull-forward — do not let it keep sliding.
3. Deadline notifications — wire `request_deadline_approaching` and `request_deadline_overdue` into Celery beat. Templates already exist and are seeded; §8.3 matrix has both rows marked open. Self-contained subsystem session.
4. Discovery implementation — Discovery.tsx is a shell. Either implement active discovery or mark it explicitly as v1.1+ throughout all documentation (decision pending).
5. Connector expansion — REST API, ODBC/JDBC, and SharePoint connectors for broader municipal system coverage.
6. Spec alignment — **DONE**. The in-repo `docs/UNIFIED-SPEC.md` is now this v3.1 document, kept current through commit `2663836` + this hotfix. (Completed alongside the SENT removal and notification_log/exemption_rules drift fixes; see migrations 010 and 011.)
7. Public portal buildout — implement the requester-facing surface only after internal staff workflows are stable and fully documented.
8. CHANGELOG font correction — **DONE** in `2663836`. The v1.0.0 entry and the actual wiring now both reflect Geist Variable.

## 18. Engineering Acceptance Criteria
Every component must support loading, empty, error, and disabled states.
Every workflow must support keyboard-only completion.
Role-based permissions change available actions, not layout or naming.
All status transitions write to audit log automatically.
All status transitions dispatch notifications (if template exists).
Public status pages understandable without staff login.
Onboarding completable by clerk alone without IT involvement.
Network discovery requires explicit IT opt-in.
Every connector authorization is audit-logged.
Health checks surfaced on Dashboard.
Credentials encrypted AES-256 at rest. Never logged, exported, or returned.
Coverage gap map auto-updates.
Zero false negatives for Tier 1 regex PII detection.
All redaction is proposal-only; humans approve.
CJIS compliance gate enforced for public safety connectors.
All LLM calls route through central client with prompt injection sanitization.
ReDoS protection on all admin-entered regex patterns.
VBA macros stripped from all ingested DOCX/XLSX files.

## 19. Canonical Guidance for Future Spec Work
For future documentation, use this precedence order:
1. Repository code and route surface
2. Repository tests
3. CHANGELOG entries
4. Repository README
5. Design/spec prose
When those disagree, do not preserve the older narrative claim just because it sounds cleaner.

## Appendix A: Repository Structure
Top-level contents of github.com/scottconverse/civicrecords-ai (master branch):
backend/ — Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, Celery
frontend/ — React 18, Vite, shadcn/ui, Tailwind CSS, Geist Variable font
docs/ — 20+ documentation files including manuals, specs, QA reports, architecture diagrams
scripts/ — install scripts, verification scripts
test-data/ — test fixtures
docker-compose.yml + 3 variant files (dev, gpu, host-ollama)
install.ps1 (Windows), install.sh (macOS/Linux)
CHANGELOG.md, CONTRIBUTING.md, CLAUDE.md, USER-MANUAL.md, LICENSE (Apache 2.0)
Backend modules (20): admin, analytics, audit, auth, catalog, city_profile, connectors, datasources, departments, documents, exemptions, ingestion, llm, models, notifications, onboarding, requests, schemas, search, service_accounts
Backend model files (15): audit.py, city_profile.py, connectors.py, departments.py, document.py, exemption.py, fees.py, notifications.py, prompts.py, request.py, request_workflow.py, search.py, service_account.py, user.py
Frontend pages (14): AuditLog, CityProfile, Dashboard, DataSources, Discovery, Exemptions, Ingestion, Login, Onboarding, RequestDetail, Requests, Search, Settings, Users
Test modules (45): test_admin, test_analytics, test_audit, test_auth, test_catalog, test_chunker, test_city_profile, test_compliance_templates, test_coverage_gaps, test_datasource_connection, test_datasources, test_department_scoping, test_departments, test_documents, test_embedder, test_exemption_dashboard, test_exemption_features, test_exemption_rules_seed, test_exemptions, test_fee_lifecycle, test_fee_schedules, test_fees, test_health, test_imap_connector, test_ingestion_retry, test_llm_client, test_manual_drop, test_messages, test_model_registry, test_notification_dispatch, test_notifications, test_onboarding_interview, test_parsers, test_pipeline, test_prompt_injection, test_requests, test_response_letter, test_roles, test_search_api, test_search_engine, test_search_features, test_service_accounts, test_smtp_delivery, test_timeline, test_user_management

## Appendix B: Bottom-Line Summary
CivicRecords AI at v1.1.0 is a substantially complete internal staff platform. In three releases over two days, the codebase grew from an 80-test foundation to a 274-test system with department-level access control, 50-state exemption coverage, a complete notification pipeline, a central LLM client with prompt injection sanitization, fee waiver workflows, a rich text editor, macro stripping, search enhancements, coverage gap monitoring, and user management improvements.
The system is well beyond a simple MVP: it has professional security hardening (ReDoS protection, self-demotion guards, credential safety, macro stripping), operational polish (retry, priority indicators, citation rendering, empty states), and accessibility foundations (44px touch targets, skip navigation, icon+color badges).
What remains: public-facing portal, full active network discovery, expanded connector suite (REST API, ODBC, GIS), liaison-scoped UI completion, Tier 2/3 redaction, and a full accessibility audit (focus styles, keyboard navigation, screen reader testing).
This document (v3.1) is the single source of truth and is now the in-repo `docs/UNIFIED-SPEC.md`.