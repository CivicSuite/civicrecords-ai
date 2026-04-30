CivicRecords AI
Unified Design Specification
Version 3.1 â€” Repo-Verified Canonical
April 13, 2026

| Field | Value |
|---|---|
| Status | Canonical â€” verified against repository at commit head |
| Supersedes | All prior spec versions (v2.0, v2.2, v3.0, v3.0.1) |
| Repository | github.com/CivicSuite/civicrecords-ai |
| Current release | v1.4.3 (April 29, 2026) â€” versions aligned across all files |
| Test suite | ~620 automated backend tests + ~30 frontend tests â€” all passing |
| Method | GitHub API crawl of repo structure, README, CHANGELOG, config files, module directories, and in-repo RECONCILIATION doc |

Status Legend: [IMPLEMENTED] evidenced in code, tests, and routes. [PARTIAL] present but incomplete. [UI SHELL] interface exists without full backend capability. [PLANNED] not implemented. [NEW in v1.1.0] / [NEW in v1.2.0] / [NEW in v1.3.0] / [NEW in v1.4.0] / [UPDATED in v1.4.3] indicate which release introduced or updated a feature.

## 1. Purpose of This Document
This is the single source of truth for CivicRecords AI. It merges comprehensive design detail with implementation status verified directly against the repository at commit head. Every feature is tagged with its actual implementation state.
When narrative claims and repository evidence disagree, repository evidence wins. This document replaces all prior spec versions.

### 1.1 Version Alignment (Resolved)
As of v1.4.3, version numbers are aligned across all four authoritative files:
backend/app/config.py: APP_VERSION = "1.4.3"
backend/pyproject.toml: version = "1.4.3"
frontend/package.json: version = "1.4.3"
CHANGELOG.md: [1.4.3] - 2026-04-29
The version drift documented in prior spec versions has been resolved and remains resolved. The CHANGELOG now covers releases through v1.4.3: 0.1.0 (foundation), 1.0.0 (design system + core features), 1.1.0 (department scoping, compliance, and feature sprint), 1.2.0 (Tier 5 installer/onboarding/seeding/model-picker/portal-mode + Tier 6 at-rest encryption ENG-001 closure), 1.3.0 (release-mechanics pass + civiccore v0.1.x integration), 1.4.0 (Phase 2 LLM integration via civiccore v0.2.0 dependency), 1.4.1 (suite-wide civiccore v0.3.0 dependency alignment), and 1.4.3 (shared connector-security extraction aligned to civiccore v0.13.0).

## 2. Product Summary

### 2.1 What It Is
Open-source, locally-hosted AI system for municipal open records request processing. Runs on commodity hardware via Docker. No cloud, no vendor lock-in, no telemetry.

### 2.2 North-Star Statement
Any resident should be able to search for public records, request what is missing, and understand the status of their request without needing insider knowledge of city government.
Staff corollary: Any records clerk should be able to triage, search, review, redact, and respond to records requests from a single calm interface without falling back to email, spreadsheets, or paper.

### 2.3 What It Is Not
Not a records management system â€” it indexes and searches what already exists.
Not a legal advisor â€” it surfaces suggestions, staff make all decisions.
Not a cloud service â€” every deployment is a sovereign instance owned by the city.
Not a full public-facing portal. A minimal public surface ships in T5D behind the `PORTAL_MODE=public` install-time switch (landing page + resident-registration + records-request submission form, Option A authenticated-submission only). Broader public features â€” resident dashboard, published-records search, track-my-request â€” remain [PLANNED]. See Â§4.2 and Â§8.9.

### 2.4 Design Stance & Principles
Transparent, calm, accessible, and government-appropriate. Trust through clarity, not visual excitement.
Clarity over bureaucracy â€” residents should not need to understand government structure.
Transparency over mystery â€” statuses, timelines, costs, and next actions always visible.
Consistency over one-off screens â€” shared patterns reduce confusion and cost.
Accessibility over compliance theater â€” forms must be usable, not merely valid.
Operational calm over case chaos â€” staff views aid triage, not add clutter.
Human-in-the-loop always â€” no auto-redaction, no auto-denial, no auto-release.

### 2.5 Current Product Scope
As of v1.4.3, the system implements:
Local deployment on a single-machine Docker stack (7 services)
Internal authentication with 6-role RBAC hierarchy
Department-level access controls with staff scoping
Document ingestion (PDF, DOCX, XLSX, CSV, email, HTML, text) with macro stripping
Hybrid search (semantic + keyword) with department filtering and CSV export
Request lifecycle management (10 statuses) with priority indicators
Exemption detection: 175 state-scoped rules across 50 states + DC (plus universal PII regex rules defined in `scripts/seed_rules.py::UNIVERSAL_PII_RULES` but not yet seeded â€” deferred until `ExemptionRule.state_code` is expanded beyond `VARCHAR(2)`), Tier 1 PII detection, rule testing with ReDoS protection
Fee tracking with estimation, line items, and waiver workflows
Response letter generation with TipTap rich text editor
Notification service: 12 templates, SMTP delivery, dispatched via PATCH dynamic dispatch and 4 dedicated endpoints (see Â§8.3 for the audited matrix)
Operational analytics and dashboard with coverage gap indicators
Guided onboarding â€” two modes operators can switch between: a 3-phase form wizard (City Profile â†’ Systems â†’ Gap Map), and a single-phase LLM-powered adaptive interview that persists each answer to the CityProfile singleton and transitions `onboarding_status` (not_started â†’ in_progress â†’ complete) as the walk progresses
Municipal systems catalog (12 domains, 25+ vendors)
Connector framework (4 shipped: file_system, manual_drop, rest_api, odbc; imap_email class exists as roadmap groundwork, not registered)
Central LLM client with context manager, token budgeting, and prompt injection sanitization (Phase 2 LLM integration introduced via civiccore v0.2.0 in v1.4.0; latest published release aligned to civiccore v0.3.0 in v1.4.1; current development line now targets civiccore v0.13.0 for shared search, onboarding, connector host-validation, and encrypted-config helpers)
Compliance templates (5 documents) and model registry
Hash-chained audit logging with CSV/JSON export
~620 automated backend tests + ~30 frontend tests (all passing)
Post-v1.1.0 Tier 5 additions (2026-04-22/23): onboarding interview persistence with `has_dedicated_it` + `onboarding_status` lifecycle (T5A `1782573`); first-boot baseline seeding of 175 state-scoped exemption rules across 51 jurisdictions + 5 compliance templates + 12 notification templates, idempotent (T5B `61449c5`); 4-model Gemma 4 installer picker (`gemma4:e2b`, `gemma4:e4b` default, `gemma4:26b`, `gemma4:31b`) purging fake `gemma4:12b` / `gemma4:27b` tags (T5C `7721cf0`); `PORTAL_MODE=public|private` install-time switch + minimal public surface â€” landing, resident-registration, authenticated records-request submission (T5D `a57a897`); Windows unsigned double-click installer via Inno Setup 6.x with Start-vs-Install flow split and tag-derived version sourcing (T5E `1d5429d`).
Not yet implemented: published-records search, resident dashboard, track-my-request suite, full active network discovery engine, cross-instance federation workflows, macOS/Linux native installer (script path only), Tier 2/3 redaction, signed Windows installer (Î± posture locked).

## 3. User Groups & RBAC

### 3.1 Staff Users

| User Group | Primary Need | Design Response |
|---|---|---|
| City clerk / records officer | Triage, route, communicate, and complete requests. | Queue views, routing rules, templates, SLA timers, full event history. |
| Department liaison | Provide documents and answer scoped questions quickly. | Scoped assignment view, internal notes, due dates, one-click return to records team. |
| Legal / reviewer | Review exemptions, redactions, and sensitive material. | Review queue, exemption tags, redaction ledger, approval state. |
| City IT administrator | Install, configure, and maintain the system. | Docker Compose, admin panel, model management, audit export. |

### 3.2 Public Users [PARTIAL â€” T5D minimal surface shipped 2026-04-23]

Public-mode deployments (`PORTAL_MODE=public`) expose the minimum-viable resident surface shipped in T5D. Broader journalist/research workflows remain [PLANNED] and are not implied by the minimal surface.

| User Group | Primary Need | Design Response | Status |
|---|---|---|---|
| Resident / first-time requester | Submit a request without knowing the exact record title. | Guided request flow, plain-language examples, estimated turnaround. | [PARTIAL â€” T5D ships authenticated submission (register â†’ sign in â†’ submit). Guided scope helper and plain-language category picker remain [PLANNED].] |
| Journalist / researcher | Search existing records and request additional material. | Robust search, saved filters, exportable results, request history. | [PLANNED â€” no published-records search or public search filters shipped in T5D.] |

### 3.3 RBAC Role Hierarchy [IMPLEMENTED]
All 6 roles are defined in UserRole enum with a numeric hierarchy. Role hierarchy enforced via `require_department_scope`, `require_department_or_404`, `require_department_filter`, and role-threshold checks on endpoints. (`check_department_access` was removed in T2A-cleanup â€” all callers migrated to the fail-closed helpers.)

| Role | Level | Scope | Status |
|---|---|---|---|
| admin | 6 | Full system access, user management, configuration, model registry | [IMPLEMENTED] |
| reviewer | 5 | Everything staff can do + approve/reject responses and exemption flags | [IMPLEMENTED] |
| staff | 4 | Request management, search, ingestion, exemption review, fee management | [IMPLEMENTED] |
| liaison | 3 | Department-scoped via check_department_access(); can view department resources but cannot create requests or manage exemptions | [IMPLEMENTED] |
| read_only | 2 | View dashboards and reports only | [IMPLEMENTED] |
| public | 1 | Submit requests (T5D), track own requests [PLANNED], search published records [PLANNED] | [IMPLEMENTED (partial) â€” T5D (`a57a897`) adds authenticated `POST /public/requests` (`UserRole.PUBLIC` only) + `GET /config/portal-mode`. Resident dashboard + track-my-request UI + published-records search are not shipped.] |

Service accounts with hashed API keys (SHA-256) enable instance-to-instance federation access.

## 4. Information Architecture

### 4.1 Staff Workbench â€” 13 Pages + Login
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
| Onboarding | Two modes: 3-phase form wizard (City Profile / Systems / Gap Map) AND a single-phase LLM-powered adaptive interview that persists answers in-endpoint and drives the `onboarding_status` lifecycle | [IMPLEMENTED] |
| City Profile | City configuration and metadata | [IMPLEMENTED] |
| Discovery | Network discovery preview page | [UI SHELL] |
| Settings | System settings | [IMPLEMENTED] |
| Audit Log | Audit event viewer with authenticated CSV/JSON export | [IMPLEMENTED] |
| Login | JWT authentication | [IMPLEMENTED] |

### 4.2 Public Portal [PARTIAL â€” T5D minimal surface shipped 2026-04-23]

T5D ships the minimal public surface (3 pages) under Scott-locked B4=(b) + Option A (register-first, authenticated submission). Broader public-portal pages remain [PLANNED] and are not implied by the T5D scope. When `PORTAL_MODE=private` (the default), none of these pages are reachable â€” the login screen is the only externally reachable surface.

| Page | Purpose | Status |
|---|---|---|
| Public Landing (`/public`) | Minimal calm landing page explaining the public surface and routing residents to register/submit | [IMPLEMENTED â€” T5D (`a57a897`). `frontend/src/pages/PublicLanding.tsx`.] |
| Resident Registration (`/public/register`) | Self-service account creation. `UserCreate.force_public_role` guarantees `UserRole.PUBLIC` assignment regardless of client-supplied role. | [IMPLEMENTED â€” T5D (`a57a897`). `frontend/src/pages/PublicRegister.tsx`.] |
| Records-Request Submission (`/public/submit`) | Authenticated submission form posting to `POST /public/requests`. Staff roles receive 403 here. | [IMPLEMENTED â€” T5D (`a57a897`). `frontend/src/pages/PublicSubmit.tsx`.] |
| Home / published records landing | Search bar, common categories, response-time guidance | [PLANNED â€” out of T5D scope.] |
| Search Records | Published records index with filters | [PLANNED â€” out of T5D scope.] |
| Track a Request | Public timeline, messages, delivered files, fees | [PLANNED â€” out of T5D scope.] |
| Help & Policy | Open records law summary, fee schedule, exemptions, contact | [PLANNED â€” out of T5D scope.] |

### 4.3 Navigation Rules
Staff workbench: Sidebar navigation (240px fixed, 56px header). Grouped sections: Workflow / Setup / Administration. Active page highlighted with left border accent.
Public portal: Top navigation with no more than 6 top-level choices.
Every page identifiable from peripheral vision â€” unique page icon, header treatment, or accent color.

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
| 6 | ollama | Local LLM runtime (Gemma 4 â€” e4b default; e2b/26b/31b supported via installer picker â€” plus nomic-embed-text) |
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
| notifications | 12 templates, SMTP delivery via smtp_delivery.py, queue_notification() via PATCH dynamic dispatch + 4 dedicated endpoints (see Â§8.3), Celery beat 60s tick | [IMPLEMENTED] |
| analytics | Operational metrics: response time, deadline compliance, overdue count, status breakdown | [IMPLEMENTED] |
| departments | Department CRUD, access control, staff scoping | [IMPLEMENTED] |
| datasources | Source CRUD, 3-step wizard, test-connection endpoint | [IMPLEMENTED] |
| documents | Document metadata, chunk management | [IMPLEMENTED] |
| ingestion | Two-track pipeline (parsers + multimodal OCR), retry endpoint, macro stripping | [IMPLEMENTED] |
| connectors | Universal protocol (authenticate/discover/fetch/health_check): file_system, manual_drop, rest_api, odbc | [IMPLEMENTED] |
| catalog | Municipal systems catalog (12 domains, 25+ vendors), auto-loader | [IMPLEMENTED] |
| city_profile | City configuration, gap map, template variable source | [IMPLEMENTED] |
| onboarding | Frontend offers two modes â€” a 3-phase form wizard (form mode) and a single-phase LLM-powered adaptive interview. The interview endpoint (`POST /onboarding/interview`) persists each answer onto the CityProfile singleton (creating the row on the first answer), normalizes yes/no â†’ bool for `has_dedicated_it`, and transitions `onboarding_status` (not_started â†’ in_progress â†’ complete). LLM failure falls back to the default question text. | [IMPLEMENTED] |
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
assemble_context() â€” prioritizes system > request > top-k chunks > exemption rules within budget
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
data_sources: id, name, source_type (file_system/manual_drop/rest_api/odbc), connection_config (JSONB â€” encrypted at rest as a Fernet envelope `{"v":1,"ct":...}` via the `EncryptedJSONB` TypeDecorator; see Â§8.10 / ENG-001 closed 2026-04-23), schedule, status, created_by, department_id
documents: id, source_id, source_path, filename, display_name, file_type, file_hash (SHA-256), file_size, ingestion_status, ingested_at, metadata (JSON), department_id
document_chunks: id, document_id, chunk_index, content_text, embedding Vector(768), token_count

### 6.3 Search & RAG
search_sessions: id, user_id, created_at
search_queries: id, session_id, query_text, filters (JSON), results_count, ai_summary, created_at
search_results: id, query_id, chunk_id, similarity_score, rank, normalized_score (0â€“100)

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
exemption_rules: id, state_code, category, rule_type (regex/keyword/statutory), rule_definition, description, enabled, version, created_by, created_at. 175 state-scoped rules across 50 states + DC seeded at first boot by `app/seed/first_boot.py`. (`version` was added in migration 011 to fix model-vs-DB drift.)
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
Every badge includes an icon â€” never color-only. StatusBadge component maps color+icon across request, document, and exemption domains.

| Status | Color Role | Icon | Priority |
|---|---|---|---|
| Received | info (blue) | Inbox | â€” |
| Clarification needed | warning (amber) | MessageCircle | â€” |
| Assigned | info (blue) | UserCheck | â€” |
| Searching | info (blue) | Search | â€” |
| In review | warning (amber) | Eye | â€” |
| Ready for release | success (green) | CheckCircle | â€” |
| Drafted | info (blue) | FileText | â€” |
| Approved | success (green) | ShieldCheck | â€” |
| Fulfilled | success (green) | Send | â€” |
| Closed | neutral (gray) | Archive | â€” |

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
StatCard â€” metric display with loading, empty, and error states
PageHeader â€” consistent page titles
EmptyState â€” smart contextual guidance ("No flags reviewed yet" not "0.0%")
DataTable â€” sortable, filterable tables with loading states
StatusBadge â€” color+icon mapping across all domains

## 8. Workflow Patterns

### 8.1 Request Lifecycle [IMPLEMENTED]
10 statuses: [Received] â†’ [Clarification Needed]? â†’ [Assigned] â†’ [Searching] â†’ [In Review] â†’ [Ready for Release] â†’ [Drafted] â†’ [Approved] â†’ [Fulfilled] â†’ [Closed]
Every status transition writes to request_timeline, writes to audit_log, triggers notification dispatch (if template exists), and updates records_requests.status.

The lifecycle has 10 statuses. The legacy `sent` value was removed in migration 010 â€” it was a leftover from the original v0.1.0 enum, marked in code as a "legacy alias for fulfilled" and orphaned by the broken Mark Fulfilled UX path (see section 8.3). Migration 010 collapses any historical `sent` rows into `fulfilled` and drops the enum value via the standard rename-recreate dance.
### 8.2 Response Letter Generation [IMPLEMENTED]
Clerk clicks [Generate Response Letter] on Request Detail.
Central LLM client assembles context within token budget via context manager.
LLM generates draft letter (labeled "AI-GENERATED DRAFT â€” REQUIRES HUMAN REVIEW").
Clerk edits in TipTap rich text editor (bold, italic, underline, bullet/ordered lists). Content stored as HTML.
Submit for Approval â†’ Supervisor reviews â†’ Approve â†’ Send.

### 8.3 Notification Dispatch [IMPLEMENTED]
12 notification templates seeded. Dispatch is via the PATCH `/{request_id}` endpoint, which fires `queue_notification()` with a dynamically-built `event_type` of `request_{new_status}` for every reachable status transition. In addition, four dedicated POST endpoints (`submit_for_review`, `mark_ready_for_release`, `approve_request`, `reject_request`) call `queue_notification()` directly. `city_name` is sourced from `CityProfile` for template rendering. SMTP delivery is performed asynchronously by `smtp_delivery.py` driven by Celery beat (60s interval). Notification rows enter `notification_log` with `status='queued'` and are picked up on the next beat tick.

The Mark Fulfilled UX path was repaired in this release. The "Mark Fulfilled" button in `RequestDetail.tsx` had been pointing at `POST /requests/{id}/sent` â€” a route that does not exist â€” so every click 404'd and no notifications ever fired from that path. The button now PATCHes `status='fulfilled'`, which routes through the dynamic dispatch and produces the expected `request_fulfilled` notification. End-to-end manual verification (2026-04-14): a request walked through `searching â†’ in_review â†’ ready_for_release â†’ approved â†’ fulfilled` produces exactly five `notification_log` rows, one per transition, with rendered subjects.

#### Dispatch matrix (audited)

| Template event_type | Template seeded | Dispatch path | Status |
|---|---|---|---|
| `request_received` | yes | `create_request` (no call site) | OPEN â€” template-only; `create_request` does not yet call `queue_notification()` |
| `request_clarification_needed` | yes | PATCH dynamic | wired |
| `request_assigned` | yes | PATCH dynamic | wired |
| `request_searching` | yes | PATCH dynamic | wired |
| `request_in_review` | yes | PATCH dynamic + dedicated `submit_for_review` | wired |
| `request_ready_for_release` | yes | PATCH dynamic + dedicated `mark_ready_for_release` | wired |
| `request_drafted` | yes | PATCH dynamic + dedicated `reject_request` | wired |
| `request_approved` | yes | PATCH dynamic + dedicated `approve_request` | wired |
| `request_fulfilled` | yes | PATCH dynamic | wired (was unreachable until UI fix) |
| `request_closed` | yes | PATCH dynamic | wired |
| `request_deadline_approaching` | yes | Celery beat daily (no router call site) | IMPLEMENTED â€” `check_deadline_approaching()` in `deadline_check.py` |
| `request_deadline_overdue` | yes | Celery beat daily (no router call site) | IMPLEMENTED â€” `check_deadline_overdue()` in `deadline_check.py` |

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
POST /requests/{id}/estimate-fees â€” staff enters page count, system calculates from fee schedule rates
Fee line items tracked per request with automatic total calculation
Fee waiver workflow: create waiver (indigency/public_interest/media/government/other) â†’ approve/deny â†’ automatic fee_status update on approval

### 8.5 Data Source Connection [NEW in v1.1.0]
3-step guided wizard replaces single-step add dialog
Step 1: Source type selection. Step 2: Connection config per type. Step 3: Review + test connection.
POST /datasources/test-connection validates connectivity without persisting credentials

### 8.6 Onboarding Interview [NEW in v1.1.0; updated T5A 2026-04-22]
POST /onboarding/interview walks a fixed list of CityProfile fields in priority order:
city_name â†’ state â†’ county â†’ population_band â†’ email_platform â†’ has_dedicated_it â†’
monthly_request_volume. Each call:
- Generates the next question for the first remaining empty field (LLM-powered; falls back to a hardcoded default when the LLM is unavailable).
- **Persists the previous answer in-endpoint** â€” creates the CityProfile singleton on the first answer (requires `city_name` first) and updates it on subsequent calls. Normalizes yes/no â†’ bool for `has_dedicated_it`.
- **Transitions `onboarding_status`** (`not_started` â†’ `in_progress` â†’ `complete`) based on how many tracked fields are populated; the computed state is returned on every response.
Chat-style UI (`frontend/src/pages/Onboarding.tsx`) with a Skip button that actually advances the walk â€” the client tracks skipped fields and sends them as `skipped_fields` on every request so the server walks past them instead of re-asking. DB truth is anchored to populated-in-DB: skipped fields stay null, onboarding_status stays `in_progress` until they are answered, and when every non-skipped field is populated the closure message lists the skipped set so the operator knows what is still missing. Errors and lifecycle state are surfaced in the UI rather than silently swallowed. The prior split where the frontend called a separate `PATCH /city-profile` to persist answers was removed in T5A because it 404-ed silently when no profile existed yet.

### 8.8 Windows Installer [NEW in T5E, 2026-04-22; corrected 2026-04-22]

**UNSIGNED BY DESIGN.** Scott locked T5E signing posture = Î± on 2026-04-22. This installer ships unsigned. Every operator-facing truth surface (the installer README, the top-level README, release notes) states this plainly and walks operators through the Windows SmartScreen "More info â†’ Run anyway" flow. Checksum verification (SHA-256) is published alongside each release asset as an independent trust surface.

**Two shortcuts, two flows (Start is not Install).** The installer creates distinct Start Menu entries wired to distinct launcher scripts, so a daily double-click on "Start" never re-runs the installer or re-pulls a model:

| Shortcut | Script | Behavior |
|---|---|---|
| **Start CivicRecords AI** (also Desktop shortcut, if opted in) | `installer/windows/launch-start.ps1` | Daily start. Verifies Docker is reachable; runs `docker compose up -d` (idempotent); opens `http://localhost:8080/`. **Does NOT** run the prereq check, **does NOT** invoke `install.ps1`, **does NOT** pull any model, **does NOT** re-seed data. On failure, points the operator at "Install or Repair CivicRecords AI". |
| **Install or Repair CivicRecords AI** | `installer/windows/launch-install.ps1` | Full bootstrap / repair. Prereq check â†’ `install.ps1` (T5C 4-model Gemma 4 picker + `ollama pull` of selected model + `ollama pull nomic-embed-text` + T5B baseline seeding) â†’ open browser. Also triggered automatically from the installer wizard's post-install `[Run]` step on first-run. |

The model-pull behavior of `install.ps1` is *always* present on the install/repair path (not optional, not manual) and *never* present on the daily-start path. The installer README, the top-level README, and the launcher banner say this plainly; there is no "Does not auto-pull the Gemma 4 LLM" language anywhere (the previous line by that name in the installer README was contradicted by `install.ps1` L284 and has been removed).

**Version sourcing â€” single authoritative source, no hardcoded drift.** `civicrecords-ai.iss` does not carry a hardcoded `MyAppVersion`. ISCC is invoked with `/DMyAppVersion=<semver>`; the `.iss` declares `#ifndef MyAppVersion / #error` so a version-less ISCC invocation fails fast instead of shipping a stale value. `build-installer.sh` resolves the version in this order:
1. `$CIVICRECORDS_VERSION` environment variable (CI sets this from the git tag with any leading `v` stripped).
2. `backend/pyproject.toml` `[project] version = "..."` (authoritative for untagged local dev builds).

`.github/workflows/release.yml` extracts the version from `github.ref_name`, exports `CIVICRECORDS_VERSION` to the build step, and the "Locate installer artifact" step expects exactly `build/CivicRecordsAI-${CIVICRECORDS_VERSION}-Setup.exe`. Local bash build and CI build produce the same artifact filename for the same version.

**Toolchain / pipeline inherited from PatentForgeLocal (verified direct read 2026-04-21):**
- `installer/windows/civicrecords-ai.iss` â€” Inno Setup 6.x script. Admin elevation required, MinVersion=10.0, x64compatible, lzma2/max compression. AppId is a fresh GUID. `[Dirs]` marks `{app}\data|logs|config` with `uninsneveruninstall`. `[Code]` `CurUninstallStepChanged` prompts twice with truthful copy: step 1 stops the Compose stack (`docker compose down` â€” containers only, Docker-managed volumes preserved); step 2 deletes **local app files under the install dir only** (`{app}\data|logs|config`) and **explicitly preserves the Postgres database and Ollama models** (both in Docker-managed volumes). The full-wipe path (`docker compose down -v`) is called out in the dialog text for operators who want to remove the volumes too. The word "database" was removed from the file-system-deletion prompt where it was previously misleading.
- `installer/windows/build-installer.sh` â€” bash build driver. Locates `ISCC.exe`, verifies bundle sources, resolves the version per the precedence above, passes it to ISCC via `/DMyAppVersion=`, compiles, reports output path + SHA-256. The PatentForgeLocal output-name typo (`PatentForgeLocalLocal-`) was intentionally not carried forward.
- `.github/workflows/release.yml` â€” release-on-tag (`v*`). Single `windows-latest` job installs Inno Setup via `choco install innosetup -y`, resolves the version from the tag, runs the bash driver with `CIVICRECORDS_VERSION` set, uploads the `.exe` + `.sha256` file, and creates+publishes a draft GitHub release with both assets attached.

**CivicRecords-specific adaptations (not in PFL):**
- `installer/windows/prereq-check.ps1` â€” reports on Docker Desktop, WSL 2 + Virtual Machine Platform, 32 GB RAM target-profile floor (Tier 5 Blocker 2), and host Ollama (preferred when present per the target profile). Prints concrete remediation commands for each miss. Does NOT auto-install Docker Desktop or silently enable WSL features â€” the elevation/reboot cost is too high to hide. Exits non-zero on required-prereq miss.
- `installer/windows/launch-install.ps1` â€” install/repair orchestrator (prereq-check â†’ `install.ps1` â†’ open browser). Invoked from the installer wizard's post-install `[Run]` step and from the "Install or Repair CivicRecords AI" shortcut.
- `installer/windows/launch-start.ps1` â€” daily-start script (Docker reachability check â†’ `docker compose up -d` â†’ open browser). Invoked from the "Start CivicRecords AI" Start Menu entry and the Desktop shortcut. Surfaces actionable errors if Docker is unreachable or the bring-up fails and points the operator at "Install or Repair CivicRecords AI" for rebuilds.
- Bundles the CivicRecords repo snapshot (backend source, frontend source, docs, scripts, Dockerfiles, `install.ps1`, `docker-compose.yml` + overlays, `.env.example`, LICENSE, README.md). No portable Python / Ollama binaries â€” CivicRecords runs in Docker, not native processes.

**Out of scope for T5E:**
- No macOS / Linux native installer â€” cross-platform parity is documented as follow-on, not shipped.
- No code signing â€” Scott-locked Î± (unsigned).
- No auto-install of Docker Desktop, no silent WSL feature-enable.

**Verification surfaces operators should trust:**
- The GitHub release page publishes both the `.exe` and a matching `CivicRecordsAI-<version>-Setup.exe.sha256` file. Operators can compare `Get-FileHash -Algorithm SHA256 <file>` against the checksum to verify the binary is byte-identical to the CI-produced artifact at the tagged commit.

### 8.7 First-Boot Seeding [NEW in T5B, 2026-04-22]
`app/main.lifespan` auto-seeds the three baseline datasets CivicRecords AI needs on first boot, immediately after the first admin user is created and the systems catalog is auto-loaded:

| Dataset | Source | Natural key | Row count |
|---|---|---|---|
| Exemption rules (state-scoped) | `scripts/seed_rules.py::STATE_RULES_REGISTRY` | `(state_code, category)` | 175 rules across 50 states + DC |
| Disclosure / compliance templates | `scripts/seed_templates.py::TEMPLATES` + `backend/compliance_templates/*.md` | `template_type` | 5 templates |
| Notification event templates | `scripts/seed_notification_templates.py::NOTIFICATION_TEMPLATES` | `event_type` | 12 templates |

**Upsert policy â€” skip-if-exists.** Every row is written only if a row with the same natural key does not already exist. **Existing admin-customized rows are preserved on restart** (an operator who disables a rule or edits a template's body text keeps their change; the seeder never overwrites). Re-running the lifespan is idempotent; every restart reports `created=0, skipped=N` once the dataset is present.

**Logging.** Every run emits a start line (`T5B first-boot seeding â€” starting`), per-dataset start + result lines with `created` / `skipped` counts, and a completion line with totals. One summary line is additionally `print()`-ed so operators watching Docker stdout see the outcome even if LOG_LEVEL filters INFO.

**Universal PII rules** (`UNIVERSAL_PII_RULES` in `scripts/seed_rules.py`) are intentionally **NOT seeded by T5B** because `ExemptionRule.state_code` is `VARCHAR(2)` and the `"ALL"` sentinel those rules use cannot fit. A follow-on slice that expands the column (or models universality as a nullable) will close this gap.

**Test coverage:** `backend/tests/test_first_boot_seeding.py` â€” 3 tests pin (a) fresh-DB seeding populates all three datasets with full state coverage, (b) rerunning the seeder produces zero new rows, and (c) a customized exemption rule + notification template survive a re-seed.

### 8.9 Install-time Portal Switch (T5D) [NEW 2026-04-22]

**Two modes, locked at install time, changeable post-install by editing `.env` and restarting the stack.** Scott locked B4 = (b) on 2026-04-22 and selected Option A (authenticated public submission only, no anonymous walk-up) on the same day. T5D implements exactly that â€” no more, no less.

**Private mode (default).** Staff-only. No public routes are mounted. `/auth/register` returns 404 (not 403 â€” the route does not exist in private mode). `UserRole.PUBLIC` is not assignable via self-registration. The login screen is the only externally reachable page. This matches the pre-T5D behavior of every CivicRecords AI deployment; existing deployments that do nothing will keep working exactly as they did.

**Public mode â€” minimal surface (exact, locked).** Three user-visible surfaces, no more:
1. **Public landing page** (`/public/`) â€” explains what the city lets residents do online and routes them to register or sign in.
2. **Resident registration path** (`/public/register`) â€” creates a `UserRole.PUBLIC` account. The existing pre-T5D `UserCreate` bug that silently forced self-registered users to `UserRole.STAFF` is corrected in this slice; self-register now correctly forces `UserRole.PUBLIC`.
3. **Authenticated records-request submission form** (`/public/submit`) â€” `UserRole.PUBLIC`-only. Requires the resident to be signed in. Populates `created_by` from the authenticated account.

**Explicitly NOT in this slice and NOT implied by any copy:** anonymous walk-up submission, published-records search, a full resident dashboard, a track-my-request suite, or any other public-portal feature. Section 4.2 ("Public Portal [PLANNED]") remains the forward-looking scope; T5D does not advance it beyond the three surfaces above.

**Config surface.**
- Env var: `PORTAL_MODE=private|public` (default `private`).
- Backend model: `backend/app/config.py` adds `portal_mode: Literal["public","private"] = "private"` with a Pydantic `field_validator` that lowercases and strips whitespace â€” `"public"`, `"Public"`, `" PUBLIC "` all resolve to `"public"`.
- **Failure mode:** any value other than the two canonical strings (after normalization) fails fast at startup rather than silently defaulting to private. The operator gets a loud error instead of a quietly misconfigured deployment.
- Installer integration: `install.ps1` / `install.sh` prompt interactively with `private` as the default; non-interactive installs accept `$CIVICRECORDS_PORTAL_MODE` as a pre-set. `.env.example` documents both modes with a comment block.

**Backend endpoints.**
| Endpoint | Mount condition | Auth | Roles | Notes |
|---|---|---|---|---|
| `POST /public/requests` | `portal_mode == "public"` | Required | `UserRole.PUBLIC` only | Staff roles (ADMIN, STAFF, REVIEWER, READ_ONLY, LIAISON) get 403 here and use `/requests/`. `created_by` FK is populated from the authenticated resident. **Not anonymous â€” submission requires a signed-in `UserRole.PUBLIC` account.** |
| `POST /auth/register` | `portal_mode == "public"` | None | â€” | Returns 404 in private mode (route not mounted). In public mode, forces `UserRole.PUBLIC` on the created account. |
| `GET /config/portal-mode` | Always mounted | None | â€” | Returns `{"mode": "private" \| "public"}`. Unauthenticated so the frontend can branch its routing on boot before any user-identity lookup. |

**Frontend routing branches** (`frontend/src/App.tsx`).
1. Boot: fetch `GET /config/portal-mode`.
2. If `private`: behavior matches pre-T5D â€” login screen â†’ staff workbench.
3. If `public`:
   - Unauthenticated visitors â†’ `/public/*` routes (landing, register, sign-in).
   - Authenticated `UserRole.PUBLIC` â†’ `/public/*` only; cannot reach the staff dashboard.
   - Authenticated staff roles â†’ existing workbench; the public landing is not used.

New frontend pages â€” `PublicLanding.tsx`, `PublicRegister.tsx`, `PublicSubmit.tsx` â€” each render loading / success / empty / error / partial states with actionable error copy (every error message names a specific fix path, not a dead end).

**Test coverage.**
- Backend: `backend/tests/test_portal_mode.py` â€” 15 pytest cases covering config normalization, the fail-fast path on invalid values, register gating (mounted in public / 404 in private), `UserCreate` role forcing, public-submit role gating (PUBLIC allowed, staff 403), and the always-on `/config/portal-mode` endpoint in both modes.
- Frontend: `PublicLanding.test.tsx`, `PublicRegister.test.tsx`, `PublicSubmit.test.tsx` â€” 12 vitest cases total across the three pages, pinning state rendering and error copy.

**Standing caveat (historical â€” closed by Tier 6 / Â§8.10 on 2026-04-23):** T2B closed the runtime exposure in an earlier sprint; Tier 6 closes the at-rest exposure. As of 2026-04-23 ENG-001 is fully closed. The phrase "T2B closed; Tier 6 open" is preserved here for traceability with prior sprint notes and memory/state files but no longer describes the live system.

### 8.10 At-rest Encryption for `data_sources.connection_config` [IMPLEMENTED â€” Tier 6 / ENG-001, 2026-04-23]

**Closes ENG-001.** T2B previously closed the runtime API-response exposure of `connection_config`; Tier 6 closes the remaining at-rest exposure (plaintext JSONB visible to DB superusers, `pg_dump` output, and restored backups). Together, T2B + Tier 6 = ENG-001 fully closed.

**Scott-locked design decisions (2026-04-22/23):**
1. **Single key.** One `ENCRYPTION_KEY`. No rotation program in v1. The versioned envelope (`"v": 1`) leaves rotation as a future slice; rotation is **not** a deferred Tier 6 item, it is explicitly out of this slice.
2. **Reversible migration.** Both `up` and `down` require the key. `down` decrypts envelope rows back to plaintext for operators who need to roll back.
3. **Concise operator docs.** No KMS/vault integration, no rotation runbook, no HSM story. Operators are told what the key protects, that they must back it up separately from the database, how to generate one, and how to verify post-deploy. That is the full operator surface.
4. **Closure criterion.** At-rest encryption of this column closes the at-rest gap for ENG-001. No audit-log scrub or adjacent data-at-rest scope is part of this slice.
5. **OpenAPI regenerated per the T3D gate.** Zero semantic change expected â€” `DataSourceAdminRead` still returns the dict because encryption is transparent at the ORM layer.

**Envelope shape.** `{"v": 1, "ct": "<fernet-token>"}`. Version tag reserves room for a future rotation/migration story without breaking existing rows.

**Crypto.** `cryptography.fernet.Fernet` â€” AES-128-CBC for confidentiality plus HMAC-SHA256 for integrity. Tampered ciphertext fails authentication at decryption time and raises `AtRestDecryptionError` rather than returning corrupted JSON.

**Helper module (`backend/app/security/at_rest.py`).** Exposes `encrypt_json(obj, key)`, `decrypt_json(envelope, key)`, `is_encrypted(value)`, and `AtRestDecryptionError`. Version dispatch is based on the `"v"` field; unknown versions raise a specific error rather than attempting a best-effort decode.

**ORM integration (`backend/app/models/document.py`).** A new `EncryptedJSONB(TypeDecorator)` class transparently encrypts on `process_bind_param` and decrypts on `process_result_value`. `DataSource.connection_config` now uses `EncryptedJSONB`; every existing caller continues to see a plain dict. No admin UI or API changes are required â€” the change is invisible above the ORM layer, which is why the OpenAPI schema does not move.

**Config (`backend/app/config.py`).** New `encryption_key: str` setting (env: `ENCRYPTION_KEY`) with a `check_encryption_key` validator that:
- Rejects insecure defaults (the `.env.example` placeholder `CHANGE-ME-generate-with-fernet-generate-key`, empty strings, and other obvious placeholders).
- Calls `Fernet(key)` to catch malformed keys at startup rather than at first write.
- Short-circuits in `testing=True` mode so the unit-test suite does not need a real Fernet key to run.

**Migration (`backend/alembic/versions/019_encrypt_connection_config.py`).** Reversible and idempotent in both directions:
- `up`: for each row where `connection_config` does not match the envelope shape, encrypt the plaintext JSONB and overwrite. Skip rows already in envelope shape. Requires the key.
- `down`: for each row where `connection_config` is envelope-shaped, decrypt and overwrite with plaintext JSONB. Skip rows already in plaintext. Requires the key.
- Re-running either direction is safe â€” the skip-if-shape-matches check makes both idempotent.

**Operator verification (`backend/scripts/verify_at_rest.py`).** Post-deploy sanity check. Connects to the database, scans every `data_sources.connection_config` row, and exits `0` if every row is envelope-shaped (encrypted) or `1` if any row is still plaintext. Intended use: `docker compose run --rm --no-deps api python scripts/verify_at_rest.py` after running the migration.

**Installer integration.** `install.ps1` and `install.sh` generate a Fernet-shape key on fresh install (PowerShell uses .NET `RandomNumberGenerator` + URL-safe base64 substitution; bash uses `openssl rand -base64 32 | tr '+/' '-_'`). Both print a loud red "BACK THIS UP SEPARATELY FROM YOUR DATABASE" banner so the operator sees the backup responsibility before the stack comes up.

**`.env.example`** documents `ENCRYPTION_KEY=CHANGE-ME-generate-with-fernet-generate-key` with a comment block explaining key generation (`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`) and the backup responsibility.

**Test coverage (`backend/tests/test_at_rest_encryption.py`).** Covers: helper round-trip (encrypt â†’ decrypt returns original dict), envelope shape validation, tampered-ciphertext rejection (HMAC failure raises `AtRestDecryptionError`), version dispatch (unknown `"v"` value raises a specific error), startup validator behavior (insecure defaults rejected, malformed key rejected, testing mode short-circuit), end-to-end admin create â†’ raw DB row is envelope-shaped â†’ admin GET decrypts back to the original dict, and migration idempotency on both `up` and `down`.

**What this slice does NOT do:**
- No key rotation. One key per deployment, for the lifetime of that deployment in v1.
- No KMS/HSM/vault integration. Key comes from `ENCRYPTION_KEY` only.
- No encryption of other columns (audit log, documents, search indexes, request body). That is not part of ENG-001.
- No change to the API surface, the admin UI, or the generated TypeScript types.

## 9. Search & Ingestion [IMPLEMENTED]

### 9.1 Ingestion Pipeline
Two-track model:
Conventional parsers for structured/text-layer files (PDF, DOCX, XLSX, CSV, email, HTML, text)
Multimodal/OCR path for scanned/image-heavy material (Gemma 4 with Tesseract fallback)
[NEW] DOCX/XLSX macro stripping â€” VBA macros stripped at ZIP level before text extraction. Supports .docm and .xlsm. Stripping logged in metadata for audit.
[NEW] Legacy .xls blocklisted â€” BIFF8 binary format cannot be macro-stripped with ZIP approach
[NEW] Ingestion retry â€” POST /datasources/documents/{id}/re-ingest retries failed documents. Progress indicator for processing items, auto-refresh while active.
Sentence-aware text chunking with configurable overlap
Embeddings via nomic-embed-text through Ollama with batch support, stored in pgvector

### 9.2 Hybrid Search
Semantic search via pgvector embeddings
Keyword/full-text search via PostgreSQL tsvector
Combined via Reciprocal Rank Fusion (RRF)
Normalized relevance scoring (0â€“100 scale with visual progress bar)
Source attribution on every result
Optional AI-generated summaries (labeled as AI draft)
[NEW] Department filter â€” department dropdown filters via document-source-department join chain
[NEW] CSV export â€” GET /search/export with authenticated download
[NEW] Citation rendering â€” AI summary panel renders [Doc: filename, Page: N] as styled inline badges

## 10. Exemptions & Compliance

### 10.1 Exemption Rules [IMPLEMENTED]
175 state-scoped rules across 50 states + DC. Three rule types: regex, keyword, statutory.

### 10.2 Tier 1 PII Detection [IMPLEMENTED]
Built-in patterns: SSN, credit card (Luhn-validated), bank routing/account numbers, phone, email, DOB, state-specific driver's license patterns (CO, CA, TX, NY, FL).

### 10.3 Exemption Review Dashboard [IMPLEMENTED]
Acceptance/rejection rates
Export: /exemptions/dashboard/export?format=json|csv
[NEW] Rule test modal â€” POST /exemptions/rules/{id}/test tests regex or keyword rules against sample text with match positions. ReDoS protection via regex library with 2-second timeout. LLM-type rules rejected with 400.
[NEW] Audit history â€” GET /exemptions/rules/{id}/history returns audit log entries. Timeline UI in Exemptions page.

### 10.4 Tiered Redaction Engine [PLANNED]

| Tier | Method | What It Detects | Status |
|---|---|---|---|
| Tier 1 | RegEx pattern matching | SSNs, credit cards, phone, email, bank accounts, driver's licenses | [IMPLEMENTED â€” in exemption engine] |
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
Municipal systems catalog â€” 12 functional domains, 25+ vendor systems, bundled JSON with auto-loader [IMPLEMENTED]
Connector framework â€” universal protocol (authenticate/discover/fetch/health_check) [IMPLEMENTED]
Connectors (4 shipped): file_system, manual_drop, rest_api, odbc [IMPLEMENTED] â€” imap_email class exists on disk as roadmap groundwork but is not registered or reachable from shipping flows
Dashboard coverage gaps â€” GET /admin/coverage-gaps [IMPLEMENTED]

### 11.2 What Is Not Yet Implemented
Active network scanning/discovery [UI SHELL â€” Discovery.tsx exists as preview page]
Automatic service fingerprinting [PLANNED]
GIS, Vendor SDK, IMAP email connectors [PLANNED] (REST API and ODBC shipped in T3B)
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
| SMTP / IMAP Journal | Email archives (#1 source for records requests) | [PLANNED] |
| Manual / Export Drop | Systems with no API â€” clerk uploads | [IMPLEMENTED] |
| REST API (Modern SaaS) | Tyler, Accela, NEOGOV, cloud platforms | [IMPLEMENTED] |
| ODBC / JDBC Bridge | On-prem databases, legacy SQL, AS/400 | [IMPLEMENTED] |
| GIS REST API | Esri ArcGIS, spatial data, property records | [PLANNED] |
| Vendor SDK | Evidence management (Axon), CAD systems | [PLANNED] |

### 11.5 Security for Connectors
Network discovery: disabled by default, explicit IT opt-in, audit-logged.
Every connection: admin must review, confirm, provide credentials, authorize.
Credentials (API): `connection_config` fields are redacted from non-admin API responses (T2B); admin write endpoints return the full config. At-rest storage is **encrypted** as a versioned Fernet envelope (`{"v":1,"ct":"<fernet-token>"}`, AES-128-CBC + HMAC-SHA256) via the `EncryptedJSONB` SQLAlchemy TypeDecorator, keyed off `ENCRYPTION_KEY` (T6 / ENG-001, 2026-04-23). `pg_dump` output and raw backups contain ciphertext only; decryption happens transparently at the ORM layer. Credentials are never logged, returned on GET, or displayed after initial admin entry. See Â§8.10 for the full design. Key rotation is intentionally not supported in this release; the `"v": 1` tag leaves rotation as a future slice.
Test-connection endpoint: dedicated schema, never persists credentials, never logs connection strings.
Least-privilege: read-only accounts. System never writes to source systems.
CJIS Compliance: Architecture satisfies encryption (5.10.1), audit logging (5.4), access control (5.5), no cloud egress (5.10.3.2). City must satisfy fingerprint checks (5.12), signed addendum, and security training (5.2). Compliance gate blocks public safety connector activation until confirmed.

## 12. Security Hardening
Security measures implemented across the stack:
JWT authentication with configurable lifetime, minimum 32-char secret enforced at startup
Login rate limiting in main.py middleware
Role-based access control with 6-role numeric hierarchy
Self-demotion guard â€” admins cannot change their own role or deactivate their own account
Hash-chained audit log (SHA-256) â€” tamper-evident, append-only
Prompt injection sanitization in central LLM client
ReDoS protection â€” regex library with 2s timeout for admin-entered exemption patterns
VBA macro stripping from DOCX/XLSX at ZIP level before ingestion
Legacy .xls blocklisted (BIFF8 cannot be macro-stripped)
Test-connection credential safety â€” never persists, logs, or returns credentials
API keys hashed (SHA-256) before storage
No telemetry, no outbound connections, no crash reporting
SMTP credentials never logged or displayed after entry
All LLM outputs labeled as AI-generated drafts
T2A â€” Department scope enforcement: role self-escalation via `PATCH /users/me` closed (`UserSelfUpdate` schema); all 24 department-scoped request handlers use `require_department_scope` (fail-closed); 404/403 status-code info-leak unified via `require_department_or_404` across 21 handler call sites; Pattern D list-endpoint fail-open closed on `GET /requests/`, `/requests/stats`, `POST /search/query`, `GET /search/export` via `require_department_filter`; parameterized cross-endpoint enforcement test covers 25 routes; `review_fee_waiver` gap found by auditor during review and fixed in same PR
T2B â€” Connection credential redaction: `connection_config` removed from `DataSourceRead`; `DataSourceAdminRead` (full config) returned only by admin write endpoints (`POST /datasources/`, `PATCH /datasources/{id}`). Runtime credential exposure to non-admin users: **closed**.

Tier 6 / ENG-001 â€” At-rest encryption of `data_sources.connection_config` (2026-04-23): Fernet envelope (`{"v":1,"ct":"<fernet-token>"}`, AES-128-CBC + HMAC-SHA256) via `backend/app/security/at_rest.py` (`encrypt_json` / `decrypt_json` / `is_encrypted` / `AtRestDecryptionError`) and the `EncryptedJSONB(TypeDecorator)` in `backend/app/models/document.py` â€” transparent to caller code, which still sees a plain dict. Driven by a new `encryption_key` config setting (env: `ENCRYPTION_KEY`) with a `check_encryption_key` validator that rejects insecure defaults, calls `Fernet(...)` to catch malformed keys, and short-circuits in `testing=True` mode. Reversible + idempotent Alembic data migration `019_encrypt_connection_config` â€” `up` encrypts plaintext rows, `down` decrypts envelope rows, both require the key, both skip rows already in the target shape. Operator post-deploy check: `backend/scripts/verify_at_rest.py` exits 0 if every row is envelope-shaped, 1 otherwise. Tests: `backend/tests/test_at_rest_encryption.py` covers helper round-trip, envelope shape, tampered-ciphertext rejection, version dispatch, startup validator behavior, end-to-end admin create â†’ raw DB is envelope â†’ admin GET decrypts, and migration idempotency. **ENG-001 fully closed.** Key rotation intentionally out of scope for this release; the `"v": 1` tag reserves room for a future rotation slice. OpenAPI schema is unchanged â€” `DataSourceAdminRead` still returns the dict because encryption is transparent at the ORM layer.
T2C â€” Bootstrap hardening: `Settings.check_first_admin_password` model-validator rejects `.env.example` placeholder, empty value, <12 chars, and an embedded blocklist of common defaults; installers generate a 32-hex-char password and substitute it into `.env`; bootstrap-failure CI job confirms non-zero exit with placeholder
T2C â€” SSRF protection: `backend/app/security/host_validator.py` rejects connector URLs targeting loopback (127.0.0.0/8, ::1), link-local/IMDS (169.254.0.0/16), RFC1918 (10/8, 172.16/12, 192.168/16), and 0.0.0.0 at Pydantic schema-validation time; `CONNECTOR_HOST_ALLOWLIST` env var for on-prem overrides (exact-match only, no wildcards); ODBC fail-closed on unparseable host field
T3A â€” Admin user creation: `frontend/src/pages/Users.tsx` create-user form POSTs to `/api/admin/users` (was `/api/auth/register`, which routed through `UserCreate.force_staff_role` and silently downgraded any submitted role to STAFF); three create-form labels received `htmlFor`/`id` associations

T3B/T3C â€” Connector taxonomy unified (four canonical types: `file_system`, `manual_drop`, `rest_api`, `odbc`) across PostgreSQL enum, Python registry, ingestion dispatch, test-connection, and frontend chooser; migration `017_rename_connector_enum_values` renames `upload â†’ manual_drop` / `directory â†’ file_system` in place; `test-connection` and `handleSubmit` rewritten to send/persist type-correct payloads for rest_api and odbc; 14 new tests under `TestCanonicalVocabulary` and `TestConnectionActionableErrors`

T3D â€” OpenAPI typegen: `backend/scripts/generate_openapi.py` emits `docs/openapi.json`; `frontend/src/generated/api.ts` generated via `openapi-typescript`; `SourceCard.tsx`, `Users.tsx`, and `DataSources.tsx` migrated off hand-maintained interfaces; CI stale-artifact enforcement on both backend and frontend jobs

T4A â€” Responsive AppShell: desktop `<aside>` hidden below `md:` (768px); mobile hamburger in header opens a Base UI Dialog-backed slide-in drawer (`aria-label="Primary navigation"`, focus trap via `FloatingFocusManager`, ESC close, overlay dim, `aria-expanded`/`aria-controls` wired to the drawer id, `useEffect` on `location.pathname` auto-closes on route change); `SidebarContents` extracted so desktop and mobile render the same nav contents; `app-shell.test.tsx` covers hamburger, open/close, and complementary landmark

T4B â€” Dashboard and Settings service-health: hand-maintained `SystemStatus` interface with nested `{status: string}` shape (always read as `undefined` against the flat-string `/admin/status` backend response, producing red X icons on healthy services) replaced with the generated `components["schemas"]["SystemStatus"]`; `isServiceHealthy(status)` helper extracted in Settings; `Dashboard.test.tsx` adds 3 regression tests (healthy flat, degraded flat, nested-shape regression guard)

T4C â€” Add Data Source wizard accessibility and validation: every input received a stable `id`; `<label>` elements wired with `htmlFor`; hint text received `id` and is linked via `aria-describedby`; `validateStep(step, data)` centralizes required-field validation with field-specific actionable messages and `http(s)://` / cron-expression checks; errors render as `<p role="alert">` with `aria-invalid="true"` on the input and clear field-by-field on edit; source-type buttons became `role="radiogroup"` with `role="radio"`/`aria-checked`/roving `tabindex`; `testResult` and `submitError` both announce via `role="alert"`; 5 new wizard tests in `DataSources.test.tsx`

Button `forwardRef` migration (T4A/T4C cleanup): `components/ui/button.tsx` wrapped in `React.forwardRef<HTMLButtonElement, ButtonProps>` so Base UI's `DialogTrigger`/`DialogClose` `render={<Button/>}` pattern no longer triggers the `"Function components cannot be given refs"` warning; verified zero occurrences of that warning string in the full `vitest run` stderr post-fix

T4 post-audit â€” UX-001: the Source Type radiogroup shipped with `role="radiogroup"`, `role="radio"`, `aria-checked`, and roving `tabindex` but no `onKeyDown` â€” keyboard users couldn't arrow between source types. Hoisted `SOURCE_TYPES` to module scope, added per-radio ids, and wired a WAI-ARIA keyboard handler: ArrowRight/ArrowDown advance, ArrowLeft/ArrowUp retreat (both wrap), Home/End jump to first/last, selection-and-focus move together; non-navigation keys ignored. Two new tests in `DataSources.test.tsx` drive the keyboard interaction and assert the aria-checked + roving-tabindex state transitions

T4 post-audit â€” QA-001: `Settings.tsx` was rendering four rows (SMTP Configuration, Audit Retention, Data Sovereignty, Current Model) whose values were derived from fields the `/admin/status` endpoint never returns â€” guessed state presented as sourced compliance fact on an admin truth surface. Removed the `SystemStatus` intersection-type extension and the three fake cards; Settings now renders a single System Info card with four rows, every row backed by a real backend field. New `Settings.test.tsx` (3 tests) pins: the four legitimate rows render with verbatim backend values; none of the removed labels or synthesized strings appear; exactly one `CardTitle` ("System Info") is rendered

## 13. Accessibility
Target: WCAG 2.2 AA. Session B (keyboard navigation audit) is complete as of this commit. **Session B also revealed that the Phase 1 hotfix claim in `b6627db` â€” that focus visibility was Met post-`2663836` â€” is incorrect.** The claim was based on CSS class-presence inspection, not on computed styles in a live browser. A real keyboard walk showed the intended 3px ring never renders on any shadcn primitive (see F1). Corrected below. Form error handling and full screen reader audit remain pending for Session C.

### 13.1 Scope of Session B
Session B is a keyboard navigation audit. It verified:
- Tab order, tab-stop completeness, skip-nav reachability, and `div onClick` / positive-tabindex hygiene on all 14 pages. Four pages were walked live via Chrome MCP + injected JS probes reading computed styles after a **real Tab keystroke** (Login, Dashboard, Requests, RequestDetail). The remaining ten pages were audited via static source read (Search, Exemptions, DataSources, Ingestion, Users, Onboarding, CityProfile, Discovery, Settings, AuditLog).
- Computed focus styles on **real** keyboard focus, not programmatic `el.focus()` â€” the latter does not trigger `:focus-visible` and would have silently passed the broken state reported in F1.

Session B did **not** verify and explicitly defers to **Session C**:
- Live screen reader announcements via NVDA or VoiceOver.
- Form error association and announcement on invalid submit (no validation states were triggered live).
- Dialog focus-trap behavior on live modals (shadcn / base-ui Dialog is structurally correct but unobserved in this audit).

### 13.2 WCAG 2.2 AA Requirements Summary

| Requirement | Current State | Status |
|---|---|---|
| Color contrast | Passes (text ~15:1, muted ~5.7:1) | Met |
| Touch targets | 44Ã—44px enforced (min-width + min-height on all interactive elements, all icon button variants) | Met [v1.1.0] |
| Focus visibility | **Met (Session B.1).** `ring-3` â†’ `ring-[3px]` fix shipped in this commit (see Â§13.4 F1). Post-rebuild computed-style verification after a real Tab keystroke: `--tw-ring-shadow` = `0 0 0 calc(3px + 0px) hsl(207 62% 32% / .5)` and `box-shadow` = `rgba(31, 87, 132, 0.5) 0px 0px 0px 3px` on keyboard-focused Button (Dashboard), Input (Onboarding "City Name"), and SelectTrigger (Requests filter bar); `focusVisible: true` on all three. The global `:focus-visible` outline fallback from `2663836` continues to render correctly on bare `<a>`, `[role="link"]`, and non-primitive `[tabindex]` elements. **Historical note:** Session B found that the Phase 1 hotfix (`b6627db`) incorrectly marked this "Met" â€” the 3px ring was never rendering on primitives because Tailwind v4 dropped the `ring-3` alias. Corrected to Partial in Session B, then fixed and confirmed Met in Session B.1. | Met (Session B.1) |
| Skip navigation | Skip-to-content link present and reachable as the first tab stop; verified live on Login, Dashboard, Requests, RequestDetail | Met [v1.0.0] |
| ARIA landmarks | `main`, `nav`, `header`, `h1` present on every page walked live | Met |
| Color-only indicators | StatusBadge uses icon+color across all domains | Met [v1.0.0] |
| Keyboard navigation | **Met â€” F2 resolved (Session B.1); F3â€“F6 resolved (Session B.2/C).** F2 resolved in Session B.1 â€” `data-table.tsx` TableRow `tabIndex={0}` + `role="button"` + `onKeyDown`; keyboard-only staff can open records requests. F3 resolved â€” DOM-confirmed: base-ui v1.3.0 already sets `tabindex="-1"` on its hidden form input; Requests filter bar reads 4 tab stops for 4 visible controls (was 10). F4 resolved â€” `aria-label` added to all 15 SelectTriggers across Exemptions, Onboarding, Requests, Search, Users. F5 resolved â€” `LoadingRegion` (`aria-live="polite"`, `aria-busy`) applied to Requests, AuditLog, Users, Exemptions, Search; Dashboard/DataSources early-return loading divs have `role="status"`. F6 resolved â€” 7 `<h2>` sections added to RequestDetail via CardTitle `as` prop. See Â§13.3 for per-page scoring and Â§13.4 for findings F2â€“F6. | Met â€” F2 resolved (B.1); F3â€“F6 resolved (B.2/C) |
| Form error handling | **Not tested in Session B.** No validation errors were triggered live. Source scan found 0 of 14 pages using `aria-describedby` / `aria-invalid` patterns in error UI, but the scan cannot confirm whether rendered error text is actually associated with its input. Full verification deferred to **Session C** (requires real invalid submits + screen reader listening). | Audit pending (Session C) |
| Screen reader | **Partial â€” F3â€“F6 fixes applied (Session B.2/C); full NVDA/VoiceOver audit deferred to Session C.** F3 (Select phantom inputs): DOM-confirmed already resolved in base-ui v1.3.0 â€” no code change needed. F4 (SelectTrigger `aria-label`): 15 instances fixed across Exemptions, Onboarding, Requests, Search, Users. F5 (`aria-live`/`aria-busy`): `LoadingRegion` component applied to Requests, AuditLog, Users, Exemptions, Search; Dashboard/DataSources early-return divs have `role="status"`. F6 (RequestDetail heading hierarchy): 7 `<h2>` sections â€” Request Details, Attached Documents, Timeline, Messages, Fees, Response Letter, Workflow. Form error handling (WCAG 3.3.1): Login "Login failed" error is `<p class="text-destructive">` with no `role="alert"`, no `aria-live`, no `aria-describedby` â€” NOT MET, flagged for Session C. Full SR verification (NVDA/VoiceOver) deferred to **Session C**. | Partial â€” fixes applied (B.2/C); full SR audit pending (Session C) |

### 13.3 Per-Page Audit Scorecard

"Not tested" in the form-error and screen-reader columns is deliberate â€” those are Session C scope and are carried forward without change. "N/A" means the page has no interactive surface of that type.

| Page | Focus visibility | Keyboard navigation | Form error handling | Screen reader |
|---|---|---|---|---|
| Login | Met (F1â€”B.1) | Met | Partial (no `role="alert"` on error â€” F8, Session C) | Partial (F5 â€” no async data load on this page; form error SR gap documented) |
| Dashboard | Met (F1â€”B.1) | Met | N/A | Met (F5â€”B.2/C; `role="status"` on loading div) |
| Search | Met (F1â€”B.1) | Met (F3â€”B.2/C) | Not tested | Met (F4, F5â€”B.2/C) |
| Requests | Met (F1â€”B.1) | Met (F3â€”B.2/C) | Not tested | Met (F4, F5â€”B.2/C) |
| RequestDetail | Met (F1â€”B.1) | Partial (scrollable regions not live-verified) | Not tested | Partial (F5 â€” LoadingRegion not yet applied); Met (F6â€”B.2/C) |
| Exemptions | Met (F1â€”B.1) | Met (F3â€”B.2/C) | Not tested | Met (F4, F5â€”B.2/C) |
| DataSources | Met (F1â€”B.1) | Met | Not tested | Met (F5â€”B.2/C; `role="status"` on loading div) |
| Ingestion | Met (F1â€”B.1) | Met | N/A | Partial (F5 â€” LoadingRegion not yet applied) |
| Users | Met (F1â€”B.1) | Met (F3â€”B.2/C) | Not tested | Met (F4, F5â€”B.2/C) |
| Onboarding | Met (F1â€”B.1) | Met (F3â€”B.2/C) | Not tested | Met (F4â€”B.2/C); Partial (F5 â€” no DataTable, loading state not covered) |
| CityProfile | Met (F1â€”B.1) | Met | Not tested | Partial (F5 â€” LoadingRegion not yet applied) |
| Discovery | Met (F1â€”B.1) | Met | N/A | Met (UI shell â€” nothing to announce) |
| Settings | N/A (no interactives) | N/A | N/A | N/A |
| AuditLog | Met (F1â€”B.1) | Met | N/A | Met (F5â€”B.2/C) |

### 13.4 Findings F1â€“F7

**F1 â€” Tailwind v4 `ring-3` utility silently missing. Systemic across every page using shadcn primitives.**
`frontend/src/components/ui/button.tsx:7`, `input.tsx:12`, and `select.tsx:44` all ship className strings containing `focus-visible:ring-3 focus-visible:ring-ring/50`. The Tailwind v3 `ring-3` alias was removed in Tailwind v4; this project runs Tailwind v4 without a shim or theme alias. CSS bundle scan via `document.styleSheets` returns zero rules matching `.focus-visible\:ring-3:focus-visible`. Computed `--tw-ring-shadow` resolves to `0 0 #0000` and `box-shadow` is `none` on a genuinely keyboard-focused primitive. Only `focus-visible:border-ring` actually renders, producing a 1px border color swap to brand `#1F5784` â€” which likely fails WCAG 2.2 AA 1.4.11 Non-text Contrast (3:1 required). The global `:focus-visible` fallback in `globals.css @layer base` renders correctly but intentionally excludes `[data-slot]`, so it does not backstop the primitives. **Severity: Partial system-wide.** Remediation: three one-line edits (`ring-3` â†’ `ring-[3px]` on Button / Input / SelectTrigger), OR a Tailwind v4 theme config alias mapping `ring-3` to `3px`. Queued for **Session B.1**. **RESOLVED in Session B.1 (this commit).** Three edits: `button.tsx:7`, `input.tsx:12`, `select.tsx:44` â€” `ring-3` â†’ `ring-[3px]` (and `aria-invalid:ring-3` â†’ `aria-invalid:ring-[3px]` on each). Post-rebuild computed-style verification: `--tw-ring-shadow` = `0 0 0 calc(3px + 0px) hsl(207 62% 32% / .5)`, `box-shadow` = `rgba(31, 87, 132, 0.5) 0px 0px 0px 3px` on keyboard-focused Button (Dashboard), Input (Onboarding "City Name"), and SelectTrigger (Requests filter bar, index 0). `focusVisible: true` on all three.

**F2 â€” `data-table.tsx` rows are mouse-only clickable. WCAG 2.1.1 Keyboard hard fail on Requests.**
`frontend/src/components/data-table.tsx:89-91`:
```tsx
<TableRow
  className={cn(onRowClick && "cursor-pointer hover:bg-muted/50")}
  onClick={() => onRowClick?.(row)}
>
```
No `tabIndex`, `role="button"`, `onKeyDown`, inner anchor, or inner button. Live DOM confirmation on Requests: `rowTabindex: null, rowRole: null, anchors: [], buttons: [], hasOnclick: true`. **A keyboard-only staff member cannot open a records request from the list.** This is the most user-visible accessibility bug in the product â€” a hard functional blocker, not a cosmetic gap. Blast radius today is exactly 1 page: `grep onRowClick` confirms `Requests.tsx:400` is the sole consumer. But the fix is in the shared component so any future consumer inherits it automatically. **Severity: Not Met on Requests; Met elsewhere.** Remediation: add `tabIndex={0}`, `role="button"`, and `onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), onRowClick?.(row))}` to the TableRow in `data-table.tsx`. **One edit. Queued for Session B.1. Sequenced before F1 because severity is orders of magnitude higher.** **RESOLVED in Session B.1 (this commit).** `tabIndex={0}`, `role="button"`, and `onKeyDown` (Enter/Space with `e.preventDefault()`) added to `data-table.tsx:89`. Post-fix verification on Requests page: `<tr>` has `role="button"`, `tabIndex=0`, `focusVisible: true`; Enter key navigated to `/requests/ee112475-788d-49dc-8830-6ea8a66bb9d5`; Space key confirmed same (back-nav + re-test). Both activation keys working.

**F3 â€” base-ui Select hidden form-input leaks into tab order. Inferred system-wide; confirmed live on Requests.**
base-ui's `@base-ui/react/select` renders a hidden native `<input>` alongside the SelectTrigger for form integration and does not set `tabindex="-1"` on it. On the Requests filter bar (4 SelectTriggers), live tab order reads `select-trigger â†’ phantom-input â†’ select-trigger â†’ phantom-input â†’ select-trigger â†’ phantom-input â†’ select-trigger â†’ phantom-input â†’ date â†’ date` â€” 10 tab stops for 6 visible controls. Inferred from shared-primitive usage to apply to every page with `<Select>`: Search, Exemptions, DataSources, Users, Onboarding, CityProfile, Requests. **Severity: Partial keyboard-nav + Partial screen-reader** on every affected page â€” controls are eventually reachable, just disorientingly, and an SR user hears a content-less listbox/input pair per filter. Remediation: global CSS selector to set `tabindex="-1"` on the pattern, OR an upstream fix to base-ui Select. Queued for **Session B.2 or Session C**. **RESOLVED (Session B.2/C â€” no code change required).** DOM inspection of Requests filter bar in base-ui v1.3.0 confirmed: hidden inputs already carry `tabindex="-1"`. Requests filter bar now reads exactly 4 tab stops for 4 visible controls. No upstream fix needed; base-ui already resolved this in v1.3.0.

**F4 â€” SelectTrigger missing `aria-label`. Inferred system-wide; confirmed live on Requests filter bar.**
All 4 SelectTriggers on the Requests filter bar have `aria-haspopup="listbox"` and `aria-expanded="false"` correctly, but `aria-label` is `null`. Visual labels are rendered as adjacent text, not associated via `<label for>` or `aria-labelledby`. A screen-reader user tabs onto four consecutive unlabeled listboxes and cannot disambiguate them. Inferred to affect every SelectTrigger in the app. **Severity: Partial screen-reader.** Remediation: add explicit `aria-label` prop to every SelectTrigger, or wrap each in a `<Label>` with `htmlFor`. Queued for **Session B.2 or Session C**. **RESOLVED (Session B.2/C).** `aria-label` added to all 15 SelectTriggers across 5 pages: `Exemptions.tsx` (1 â€” "Exemption category"), `Onboarding.tsx` (5 â€” "State", "Population band", "Email platform", "Dedicated IT department", "Monthly records request volume"), `Requests.tsx` (4 â€” "Status filter", "Department filter", "Priority filter", "Assigned to filter"), `Search.tsx` (2 â€” "File type filter", "Department filter"), `Users.tsx` (3 â€” "User role" Ã—2, "Department"). Verified via DOM on Requests filter bar: all 4 SelectTriggers show non-null `aria-label` attributes.

**F5 â€” Data-loading pages lack `aria-live` / `aria-busy` regions. Every page with async data.**
Confirmed in static source audit (7 of 10 non-live-walked pages) and live DOM on Dashboard and Requests (`ariaLiveRegions: 0, ariaBusyElements: 0`). Loading spinners do not announce state transitions to screen readers, and when data arrives the UI change is silent. **Severity: Partial screen-reader** on every page with async data. Remediation: a shared `<LoadingRegion aria-live="polite" aria-busy={isLoading}>` helper, applied to the standard `isLoading` patterns in each page. Queued for **Session B.2 or Session C**. **RESOLVED on 6 pages + 2 early-return divs (Session B.2/C).** Created `frontend/src/components/loading-region.tsx` â€” a thin wrapper with `aria-live="polite"` and `aria-busy={loading}`. Applied as a DataTable wrapper in: `Requests.tsx`, `AuditLog.tsx`, `Users.tsx`, `Exemptions.tsx`; and as a results wrapper in `Search.tsx`. Early-return loading `<div>` elements upgraded with `role="status"` + `aria-label` in: `Dashboard.tsx` ("Loading dashboard data"), `DataSources.tsx` ("Loading data sources"). Remaining pages with loading states (RequestDetail, Ingestion, CityProfile, Onboarding, Login) carry the partial forward to Session C.

**F6 â€” RequestDetail heading hierarchy is flat.**
Live walk: `<h1> = 1, <h2> = 0`. The page has at least 5 logical sections (Overview / Status, Actions, Messages, Fees, Timeline) but screen-reader heading navigation surfaces a single landmark. **Severity: Partial screen-reader** on RequestDetail. Remediation: add `<h2>` per section in `RequestDetail.tsx`. Queued for **Session B.2 or Session C**. **RESOLVED (Session B.2/C).** Added polymorphic `as` prop to `CardTitle` in `frontend/src/components/ui/card.tsx` (`as?: React.ElementType`, defaults to `"div"`). Applied `as="h2"` to 7 sections in `RequestDetail.tsx`: Request Details, Attached Documents, Timeline, Messages, Fees, Response Letter, Workflow. Note: `@radix-ui/react-slot` is not installed (project uses base-ui, not radix); the `as` pattern achieves identical semantic result without adding a dependency. Post-edit: `<h1>=1, <h2>=7` in RequestDetail.

**F7 â€” Non-WCAG observation: sidebar nav order buries Dashboard 9th.**
Live walk: sidebar nav order is `Search, Requests, Exemptions, Onboarding, City Profile, Sources, Ingestion, Discovery, Dashboard, Users, Settings, Audit Log`. `/` resolves to Dashboard but a keyboard user Tabs past 8 unrelated items before reaching the "home" destination. Not a WCAG failure â€” an information architecture choice â€” but it compounds with F1 (weak focus indicator makes the long Tab walk more disorienting). **Severity: observation only, not scored.** Flagged for product decision, not engineering remediation.

### 13.5 Remediation sequencing

**Session B.1** â€” **DONE (this commit).** Single commit, single frontend rebuild:
- **F2 first.** `data-table.tsx` TableRow `tabIndex={0}` + `role="button"` + `onKeyDown` (Enter/Space) â€” keyboard-only staff can now open records requests. Highest user-visible severity in the whole audit. Verified: Enter and Space both navigated to `/requests/<uuid>` from keyboard focus.
- **F1 second.** `ring-3` â†’ `ring-[3px]` on Button, Input, SelectTrigger â€” 3px brand-color ring restored across every primitive system-wide. Verified: `--tw-ring-shadow` = `0 0 0 calc(3px + 0px) hsl(207 62% 32% / .5)` and `box-shadow` = `rgba(31, 87, 132, 0.5) 0px 0px 0px 3px` on all three primitives after a real Tab keystroke.

**Session B.2/C** â€” **DONE (this commit).** F3â€“F6 all resolved:
- **F3**: DOM-confirmed resolved in base-ui v1.3.0 â€” no code change needed. Requests filter bar: 4 tab stops for 4 controls.
- **F4**: `aria-label` on all 15 SelectTriggers across 5 pages. DOM-verified on Requests.
- **F5**: `LoadingRegion` (`aria-live="polite"`, `aria-busy`) component; applied to Requests, AuditLog, Users, Exemptions, Search; `role="status"` on Dashboard + DataSources early-return divs.
- **F6**: CardTitle `as` prop; 7 `<h2>` sections in RequestDetail. `<h1>=1, <h2>=7` verified.
- **Dialog focus trap**: Verified on Exemptions new-exemption modal. `focusInsideDialog=true` on open; Tab cycles within dialog; Escape is a pre-existing controlled-dialog behavior (not introduced by our changes).
- **Form error handling (1d)**: **DONE â€” Session C.** `role="alert"` added to error containers in Login, Users (Ã—3), Exemptions, DataSources, Onboarding, Requests (8 locations / 6 pages). `setError("")` clears before each submit â€” unmount/remount pattern guarantees re-announcement on repeated errors. Commits `226453c`, `98791d6`, `47b92a3`.
- **F5 completion**: **DONE â€” Session C.** `role="status"` + `aria-label` added to loading skeleton `<div>` in RequestDetail, Ingestion, CityProfile. All 7 affected pages now covered. Commit `b8d60ae`.
- **Search `aria-live` restructure**: **DONE â€” Session C.** Persistent `<div aria-live="polite" aria-busy={loading} aria-label="Search results">` wrapper gated on `(loading || hasSearched)`. Replaces `LoadingRegion` inside `{results && !loading}` â€” `aria-busy` now transitions `true â†’ false` when results arrive. Commit `bdfc230`.

**Session C â€” COMPLETE.** All code changes landed. Source-level verification: 13 ARIA attribute placements confirmed via grep; TypeScript build EXIT:0. Live Chrome MCP DOM checks blocked by backend not running in this session.

### 13.6 Content Design Rules
Lead with action: "Tell us what records you need" not "Records Request Submission Form"
Explain why data is requested when not obvious.
Never hide important policy terms only in tooltips.
Every closed/denied request shows reason in human language plus formal basis.
Replace jargon: "responsive documents" â†’ "records found for release"
Every error state explains: what happened, how to fix it, how to get help.
[v1.0.0] Smart empty states provide contextual guidance.

## 14. Documentation Suite
The docs/ directory contains a comprehensive documentation set:

| File | Purpose |
|---|---|
| docs/UNIFIED-SPEC.md (.docx) | This document â€” single source of truth (in-repo version is now v3.1) |
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
| 1.2.0 | April 23 | **Tier 6 / ENG-001 at-rest encryption closed** (Fernet envelope on `data_sources.connection_config`, reversible migration 019, required `ENCRYPTION_KEY`). **Tier 5 complete:** T5A onboarding persistence + lifecycle; T5B first-boot baseline seeding (175 state rules + 5 compliance templates + 12 notification templates, idempotent); T5C 4-model Gemma 4 installer picker (`gemma4:e4b` default, fake tags purged); T5D install-time `PORTAL_MODE` switch with minimal public surface (landing + resident-registration + authenticated submission); T5E unsigned Windows `.exe` installer via Inno Setup 6.x + GH Actions `windows-latest`. **Earlier unreleased work folded in:** April 14 accessibility Sessions A/B/B.1/B.2/C (Geist Variable font, `ring-[3px]` focus, data-table keyboard activation, 15 SelectTrigger `aria-label`s, `LoadingRegion`, CardTitle `as` prop); April 19â€“21 security remediation T2Aâ€“T3D (CI ratchet, dept-scope hardening, info-leak unified, Pattern D closed, T2B `connection_config` redaction, `FIRST_ADMIN_PASSWORD` validator, SSRF host validator, admin-create path fix, OpenAPI typegen + stale-check gate); April 21â€“22 T4A responsive AppShell + T4B Dashboard/Settings service-health truth + T4C Add-Source wizard a11y + Button `forwardRef` + UX-001/QA-001. CI green on `d556904` (run 24853147133). | 617 |

## 16. Capability Summary

| Capability | Status |
|---|---|
| Core internal staff platform (13 pages + login) | [IMPLEMENTED] |
| Department scoping and access controls | [IMPLEMENTED] |
| 6-role RBAC hierarchy with numeric levels | [IMPLEMENTED] |
| Onboarding / city profile / systems catalog / LLM interview | [IMPLEMENTED] |
| Connector framework (4 shipped: file_system, manual_drop, rest_api, odbc) | [IMPLEMENTED] |
| Hybrid search with department filter, CSV export, citation rendering | [IMPLEMENTED] |
| Request lifecycle (10 statuses) with priority indicators | [IMPLEMENTED] |
| Fee tracking with estimation, line items, waiver workflows | [IMPLEMENTED] |
| Response letter generation with TipTap rich text editor | [IMPLEMENTED] |
| Notification service: 12 templates, SMTP delivery, PATCH-dynamic + 4 dedicated dispatch (see Â§8.3) | [IMPLEMENTED] |
| 50-state + DC exemption rules (175 rules), Tier 1 PII, rule testing | [IMPLEMENTED] |
| Context manager with token budgeting and model-aware scaling | [IMPLEMENTED] |
| Central LLM client with prompt injection sanitization | [IMPLEMENTED] |
| Operational analytics and coverage gap dashboard | [IMPLEMENTED] |
| Compliance templates (5 docs) and model registry | [IMPLEMENTED] |
| Hash-chained audit logging with export | [IMPLEMENTED] |
| ~620 automated backend tests + ~30 frontend tests (all passing) | [IMPLEMENTED] |
| Version alignment across all files | [IMPLEMENTED] |
| WCAG: 44px touch targets, skip nav, icon+color badges | [IMPLEMENTED] |
| Onboarding interview persists answers + `has_dedicated_it` + `onboarding_status` lifecycle + skip-truth | [IMPLEMENTED â€” T5A, 2026-04-22 at `1782573`. See Â§5.2 `onboarding`.] |
| First-boot baseline seeding: 175 state-scoped exemption rules across 51 jurisdictions + 5 compliance templates + 12 notification templates, idempotent, visibly logged | [IMPLEMENTED â€” T5B, 2026-04-22 at `61449c5`. See Â§8.7.] |
| 4-model Gemma 4 installer picker (`gemma4:e2b`, `gemma4:e4b` default, `gemma4:26b`, `gemma4:31b`) with per-model disk/RAM advisories and `supportable_against_target` boolean; fake `gemma4:12b` and `gemma4:27b` tags purged repo-wide | [IMPLEMENTED â€” T5C, 2026-04-22 at `7721cf0`.] |
| `PORTAL_MODE=public\|private` install-time switch with conditional `/auth/register` and `/public/*` route mounting + typed `GET /config/portal-mode` | [IMPLEMENTED â€” T5D, 2026-04-23 at `a57a897`. See Â§8.9.] |
| At-rest encryption for `data_sources.connection_config` (Fernet envelope, `EncryptedJSONB` TypeDecorator, reversible Alembic migration, operator verification script) | [IMPLEMENTED â€” Tier 6 / ENG-001, 2026-04-23. See Â§8.10.] |
| Full active discovery engine | [UI SHELL / PLANNED] |
| Full-spectrum guided installer: Windows unsigned double-click installer (Inno Setup 6.x) with prerequisite detection (Docker Desktop, WSL 2, 32 GB RAM floor, optional host Ollama), split Start-vs-Install shortcuts, tag-derived version sourcing, T5C 4-model Gemma 4 picker + auto-pull, and T5B first-boot baseline seeding | [IMPLEMENTED â€” T5E, 2026-04-22. Windows only; macOS/Linux remain on script-based install (`install.sh`). Unsigned by design per Scott-locked B3=Î± posture. See Â§8.8 and `installer/windows/README.md`.] |
| GIS connector | [PLANNED] |
| Public resident portal â€” minimal surface (landing + resident-registration + records-request submission form) behind `PORTAL_MODE=public` install-time switch (Option A register-first; authenticated `UserRole.PUBLIC` only) | [IMPLEMENTED â€” T5D, 2026-04-23 at `a57a897`. Scope is minimal (3 public pages); resident dashboard, published-records search, and track-my-request remain PLANNED. See Â§8.9.] |
| Federation as a full product surface | [PLANNED] |
| Tier 2/3 redaction (NER, visual AI) | [PLANNED] |
| Redaction ledger | [PLANNED] |
| Saved searches | [PLANNED] |
| WCAG: focus visibility â€” global `:focus-visible` fallback (bare `<a>`, `[role="link"]`, non-primitive `[tabindex]`) | [IMPLEMENTED â€” post-v1.1.0 in `2663836`] |
| WCAG: focus visibility â€” shadcn Button / Input / SelectTrigger primitives | [IMPLEMENTED â€” Session B.1 (this commit). `ring-[3px]` fix on button.tsx, input.tsx, select.tsx; 3px brand-color ring verified post-rebuild on all three primitives.] |
| WCAG: keyboard navigation audit | [IMPLEMENTED â€” Session B, 14-page walk, 7 findings F1â€“F7 in Â§13.4] |
| WCAG: keyboard navigation â€” `data-table.tsx` row accessibility | [IMPLEMENTED â€” Session B.1. TableRow `tabIndex={0}` + `role="button"` + `onKeyDown`; Enter and Space key activation verified on Requests page.] |
| WCAG: keyboard navigation â€” F3 Select phantom tab stops | [IMPLEMENTED â€” Session B.2/C. DOM-confirmed: base-ui v1.3.0 already sets `tabindex="-1"` on hidden form inputs. No code change required. Requests filter bar: 4 tab stops for 4 controls.] |
| WCAG: screen reader â€” F4 SelectTrigger aria-labels | [IMPLEMENTED â€” Session B.2/C. `aria-label` on all 15 SelectTriggers across Exemptions, Onboarding, Requests, Search, Users.] |
| WCAG: screen reader â€” F5 aria-live loading regions | [IMPLEMENTED â€” Session C. `LoadingRegion` component wraps DataTable in Requests, AuditLog, Users, Exemptions. Search replaced with persistent `aria-live="polite" aria-busy={loading}` wrapper. `role="status"` on Dashboard, DataSources (B.2/C) + RequestDetail, Ingestion, CityProfile (Session C). All 7 affected pages covered.] |
| WCAG: screen reader â€” F6 RequestDetail heading hierarchy | [IMPLEMENTED â€” Session B.2/C. CardTitle `as` prop added to card.tsx. 7 `<h2>` sections in RequestDetail: Request Details, Attached Documents, Timeline, Messages, Fees, Response Letter, Workflow.] |
| WCAG: form error handling | [IMPLEMENTED â€” Session C. `role="alert"` on error containers in Login, Users Ã—3, Exemptions, DataSources, Onboarding, Requests (8 locations / 6 pages). Unmount/remount on `setError("")` guarantees re-announcement.] |
| WCAG: screen reader testing | [IMPLEMENTED (code) â€” Session C. All ARIA code changes landed. Full NVDA/VoiceOver verification deferred pending backend availability.] |

## 17. Next Priorities
Based on the repository as it exists now:
1. Accessibility audit â€” in progress.
   1a. Focus visibility â€” **DONE (Session B.1, this commit).** The global `:focus-visible` outline fallback from `2663836` (Session A) is Met on bare `<a>`, `[role="link"]`, and non-primitive `[tabindex]` elements. The shadcn primitive `ring-3` omission (F1) is now resolved â€” `ring-[3px]` ships on button.tsx, input.tsx, select.tsx; 3px brand-color ring confirmed via computed-style probe post-rebuild. See Â§13.4 F1 and Â§13.2.
   1b. Keyboard navigation audit â€” **DONE** in Session B (this commit). 14-page walk (4 live via Chrome MCP, 10 via source audit) with per-page WCAG 2.2 AA scoring in Â§13.3 and 7 findings F1â€“F7 in Â§13.4. Session B.1 handles the two blocking remediations; F3â€“F6 queued for Session B.2 or Session C.
   1c. **Session B.1 â€” F2 + F1 remediation â€” DONE (this commit).** F2 first (WCAG 2.1.1 hard fail): `data-table.tsx` TableRow `tabIndex={0}` + `role="button"` + `onKeyDown` for Enter/Space â€” keyboard-only staff can now open records requests. F1 second: `ring-3` â†’ `ring-[3px]` on button.tsx, input.tsx, select.tsx â€” 3px brand-color ring restored on all shadcn primitives. Both fixes verified via Chrome MCP computed-style probe after rebuild. See Â§13.4 F1, F2 for verification evidence.
   1d. Form error handling â€” **DONE (Session C).** `role="alert"` added to error containers across 8 locations in 6 pages. Unmount/remount pattern via `setError("")` ensures re-announcement. Commits `226453c`, `98791d6`, `47b92a3`.
   1e. Screen reader audit â€” **DONE (code â€” Session C).** All F3â€“F6 ARIA code changes landed. F5 complete across all 7 pages. Search `aria-live` restructured with persistent `aria-busy` transitions. Source-level verification: 13 ARIA attributes confirmed; TypeScript build EXIT:0. Full NVDA/VoiceOver listening verification deferred pending backend availability.
2. **Liaison scoping â€” DONE (this commit).** `require_role` lowered to LIAISON on read endpoints (`GET /requests/`, `GET /requests/stats`, `GET /requests/{id}`, `POST /search/query`); search dept filter injected automatically for all non-admin users with a department; nav items (Users/Audit Log/Onboarding) hidden + route-guarded for LIAISON role. 278 tests pass.
3. **Deadline notifications â€” DONE (this commit).** `check_deadline_approaching` fires for requests due within 3 days; `check_deadline_overdue` fires for past-deadline requests. Both run daily via Celery beat. Assigned staff is the recipient; unassigned requests skipped. 23-hour deduplication. 278â†’287 tests.
4. Discovery implementation â€” **DEFERRED to v1.2+.** Discovery.tsx shell removed from nav and routing (`8fe19ba`). Active discovery is out of scope for v1.1.
5. Connector expansion â€” **DONE (d335c5b).** `RestApiConnector` + `OdbcConnector` shipped. 61 connector tests passing. See `CHANGELOG.md`.
   5a. **P6a â€” Idempotency contract split** â€” **DONE (`e462c7e`, 2026-04-16).** Dedup contract split by connector type: binary sources use `(source_id, file_hash)`, structured REST/ODBC use `(source_id, source_path)`. Canonical JSON serialization + envelope-pollution detection at test-connection. `SELECT â€¦ FOR UPDATE` + partial UNIQUE indexes (`uq_documents_binary_hash`, `uq_documents_structured_path`) prevent concurrent-update races. Atomic chunk/embedding replacement on content UPDATE. Migration 014. 382+19 tests passing. See `docs/superpowers/specs/2026-04-16-p6a-idempotency-design.md`.
   5b. **P6b â€” Cron scheduler rewrite** â€” **DONE (`c670ef1`, 2026-04-17).** `schedule_minutes` interval replaced with 5-field cron `sync_schedule` via croniter (Apache 2.0). `schedule_enabled` toggle preserves expression when paused. Trigger logic: `get_next(datetime) <= now`. Rolling 7-day (2016-tick) min-interval validation rejects adversarial crons; 5-min floor. UTC evaluation with UI disclosure. Allowlist migration (13 entries) converts legacy intervals; non-allowlist values null + recorded in `_migration_015_report`. Migration 015 also drops `schedule_minutes` and adds 8 P7 stub columns. 395/397 tests passing (+13 new). D-SCHED-5 three-state card display deferred to P7. See `docs/superpowers/specs/2026-04-16-p6b-scheduler-design.md`.
   5c. **P7 â€” Sync failures, circuit breaker, UI polish** â€” **DONE (`32ceb9c`, 2026-04-17).** Per-record failure tracking (`sync_failures` table), two-layer retry (task-level 3Ã—30sâ†’90sâ†’270s + record-level 5Ã—/7-day), circuit breaker (5 full-run failures â†’ `sync_paused`, unpause grace threshold=2), `health_status` computed at response time via LEFT JOIN (circuit_open > degraded > healthy). Option B SourceCard layout with `FailedRecordsPanel` (5 states: loading/empty/populated/error + circuit-open banner), Sync Now button with exponential backoff polling (5sâ†’10sâ†’20sâ†’30s, 15-min timeout, elapsed display). 429/Retry-After honored at connector layer (capped 600s, D-FAIL-12). IntegrityError â†’ `permanently_failed` (D-FAIL-10). `sync_run_log` one row per run. Bulk retry/dismiss actions. `formatNextRun()` UTC+local display in wizard Step 3. `conftest` migrated to `alembic upgrade head` subprocess (true migration parity). **P7 QA pass (`301c4f3`, 2026-04-17):** Retry-After crash fix (ValueError on malformed headers â†’ backoff); grace period activation fix (DB-persisted `sync_paused_reason` sentinel replaces transient Python attribute); SourceCard + FailedRecordsPanel ARIA accessibility (role/img, aria-label, aria-live, aria-hidden, role/region, role/alert); `âš ï¸` copy fix. 4 adversarial Retry-After tests + 2 grace-period integration tests added. **432 backend tests passing (full Docker suite, 0 failures, 0 errors); 5 frontend tests passing** at time of this P7 entry. Test suite hardened in v1.1.0 post-audit: per-test DB recreation via `DROP DATABASE WITH FORCE`, per-test async engine, `_SessionProxy` pattern, `db_session_factory` engine disposal, `ingest_file` connector_type + SELECT FOR UPDATE to close binary-ingest race. (Current count is 556 backend + 7 frontend following T2Aâ€“T3A remediation.) *(5aâ€“5c shipped prior to Rule 9 enforcement. Rule 9 deliverables produced separately in `c433beb`.)* See `docs/superpowers/specs/2026-04-16-p7-sync-failures-design.md`.
6. Spec alignment â€” **DONE**. The in-repo `docs/UNIFIED-SPEC.md` is now this v3.1 document, kept current through commit `2663836` + this hotfix. (Completed alongside the SENT removal and notification_log/exemption_rules drift fixes; see migrations 010 and 011.)
7. Public portal buildout â€” implement the requester-facing surface only after internal staff workflows are stable and fully documented.
8. CHANGELOG font correction â€” **DONE** in `2663836`. The v1.0.0 entry and the actual wiring now both reflect Geist Variable.
9. **v1.1.0 release readiness â€” Rule 9 mandatory deliverables** â€” **DONE (`c433beb`, `9c1d98b`, `23f0655`, 2026-04-17).** `coder-ui-qa-test` skill (Hard Rule 9) requires five artifact classes before any push: (a) professional UML diagrams, (b) README in four formats, (c) three-section User Manual in three formats, (d) landing page with required action buttons, (e) GitHub Discussions seed. All five produced and committed. `docs/diagrams/` contains 6 Mermaid `.mmd` sources + 6 SVG renders (Class, Component, Sequence, Deployment, Activity). README.md/.txt/.docx/.pdf all in repo root. USER-MANUAL.md/.docx/.pdf with Sections A (end-user), B (technical), C (architectural). `docs/index.html` redesigned with 5 action buttons. `docs/github-discussions-seed.md` contains 9 seeded posts across Announcements/Q&A/Ideas/Show and Tell/General. Landing page User Manual link corrected in `23f0655`. Download Installer buttons currently point to `/raw/master/` branch files; will update to `/releases/download/` assets when v1.1.0 GitHub Release is tagged. See D-PROC-1.

## 17.x Decision Log (P6a / P6b / P7)

Decisions that constrain implementation. Each links to the specific test function that proves it. Future devs: if you want to change a decision, update the test first.

| ID | Decision | Why | Proof Test (file::function) |
|---|---|---|---|
| D-IDEM-1 | Split idempotency contract: binary connectors dedup by `(source_id, file_hash)`; structured connectors (REST/ODBC) dedup by `(source_id, source_path)`. file_hash = change detector for structured. | REST/ODBC hash non-determinism confirmed in code audit â€” raw response bytes include rotating envelope fields. Same CDC/ETL pattern as Airbyte/Fivetran. | `test_pipeline_idempotency.py::test_rest_envelope_timestamp_same_document` |
| D-IDEM-2 | `data_key` optional (null = hash root). Dotted-path only (no JSONPath). Pollution detection at test-connection time is the enforcement guardrail. | sort_keys fixes key order, not envelope values. Double-fetch warning converts silent bug to test-time signal. | `test_rest_connector.py::test_data_key_nested_extraction` |
| D-IDEM-3 | Test-connection calls fetch() twice (500ms apart), warns on hash mismatch with differing key list. | Admin finds misconfiguration during config, not 3 weeks post-GA. | `test_datasources_router.py::test_test_connection_pollution_warning` |
| D-IDEM-4 | source_path frozen at GA. ODBC: `{table}/{url_encoded_pk}`, unquoted in fetch() before SQL. REST: `{base_url}{endpoint_path}/{url_encoded_id}`. Max 2048 chars. | Format changes after GA = silent duplicates. Decode gap in ODBC fetch() would lose records with special-char PKs. | `test_odbc_connector.py::test_source_path_encode_decode_special_chars` |
| D-IDEM-5 | source_path change upstream = new document, orphaned old row. No fuzzy matching. | Fuzzy matching introduces its own failure modes. | `test_pipeline_idempotency.py::test_structured_record_content_change_updates_document` |
| D-IDEM-6 | Deletion detection is a Known Gap in v1. | Out of scope; flag for v1.2. | N/A |
| D-IDEM-7 | On UPDATE (content change): DELETE existing Chunk rows and pgvector embeddings in same transaction before re-generating. Atomic: no stale search results. | Stale embeddings after content update = incorrect search results. This is a correctness bug for a civic records search product. | `test_pipeline_idempotency.py::test_update_deletes_old_chunks_before_reembed` |
| D-IDEM-8 | ingest_structured_record uses SELECT â€¦ FOR UPDATE before comparing hashes. | Without lock: two concurrent workers both detect content change, race to update, produce non-deterministic chunk counts. | `test_pipeline_idempotency.py::test_concurrent_update_select_for_update` |
| D-IDEM-9 | Downstream consumers of documents table must watch updated_at, not just created_at. Audit of known consumers required before P6a ships. Current known: ingestion pipeline only. | With source-path identity, content-changed re-fetches are UPDATEs not INSERTs. Insert-only watchers miss updates silently. | N/A â€” action item, not testable |
| D-IDEM-10 | Existing structured-source documents (if any) deduped by MAX(ingested_at) per (source_id, source_path) before UNIQUE constraint lands. State explicitly in migration if no rows exist. | UNIQUE migration that silently fails on existing duplicates is a Friday-night incident. | `test_migration_014.py::test_connector_type_backfill` |
| D-SCHED-1 | `sync_schedule` (cron, croniter Apache 2.0) replaces `schedule_minutes`. `schedule_enabled` boolean preserves expression on toggle-off. Correct trigger logic: `get_next(datetime) <= now()`. | Interval scheduling drifts. get_prev() > anchor is almost never true â€” original spec had inverted logic that would never trigger. | `test_scheduler.py::test_overdue_source_triggers` |
| D-SCHED-2 | Min interval validated via rolling 7-day sample (2016 intervals). Floor: 5 minutes. | Adversarial cron `*/1 0 * * *` fires 60Ã—/hour in hour 0. Single get_next() check misses this. | `test_scheduler.py::test_min_interval_adversarial_cron` |
| D-SCHED-3 | Cron evaluated in UTC. UI shows both UTC and local time ("2:00 AM UTC / 8:00 PM MDT"). Wizard discloses "All schedules run in UTC." | Admin typing `0 2 * * *` intends 2am local; gets 2am UTC without disclosure. Compliance audit trail discrepancy. | `test_scheduler.py::test_cron_evaluated_in_utc` |
| D-SCHED-4 | schedule_minutes migration uses explicit allowlist. Non-allowlist values (e.g., 45) â†’ sync_schedule=NULL + migration report entry. No silent incorrect cron (*/45 is not a 45-min interval). | `*/45 * * * *` fires at :00 and :45 only, leaving a 15-min gap. Silent wrong schedule is worse than no schedule. | `test_migration_015.py::test_schedule_minutes_non_allowlist_nulled_with_report` |
| D-SCHED-5 | Three-state card display: Manual (`sync_schedule NULL or disabled`), Scheduled ("Next: Apr 17 at 2:00 AM UTC"), Paused ("Paused â€” check failed records"). | Admin must know at a glance whether source is running, waiting, or broken. Missing paused state = silent compliance gap. | `test_datasources_router.py::test_next_sync_at_returned_in_list` |
| D-FAIL-1 | Two retry layers: task-level (3 retries, 30sâ†’90sâ†’270s, 10-min cap) for transient errors; record-level (5 retries OR 7 days, one per tick, N=100/T=90s cap) for persistent failures. Handoff: task exhaustion â†’ sync_failures row. | Task-level absorbs VPN hiccups without polluting failures table. Without it, every county firewall blip trips circuit breaker via noise. | `test_sync_runner_retry_layers.py::test_task_retry_exhaustion_creates_sync_failure` |
| D-FAIL-2 | Partial failure: cursor advances past successful records. Failed records in sync_failures. | All-or-nothing cursor = one poisoned record re-fetches 50k records nightly forever. | `test_sync_runner_cursor.py::test_partial_failure_cursor_advances_past_successes` |
| D-FAIL-3 | Retry ordering: retrying rows first, then discover(). Per-run cap: N=100 OR T=90s. | Resolving existing failures > expanding backlog. Cap prevents worker pile-up on large queues. | `test_sync_runner_retry_cap.py::test_retry_cap_by_count` |
| D-FAIL-4 | Circuit breaker: full-run failure = authenticate() throws OR discover() throws OR all fetches fail. Zero-work (discover=0, no retries) does NOT move counter. Any success resets counter to 0. Zero new + retry-only successes = NOT a full-run failure. | Explicit rule prevents false positives (0 records = fail) and false negatives (partial success = fail). | `test_circuit_breaker.py::test_retry_success_with_zero_new_records_resets_counter` |
| D-FAIL-5 | Unpause grace: threshold=2 for first post-unpause window, returns to 5 after success. | Admin gets immediate feedback if creds still wrong, not 5-cycle wait. "Unpause didn't work" confusion prevented. | `test_circuit_breaker.py::test_unpause_grace_period_threshold_is_2` |
| D-FAIL-6 | Dismiss = soft delete (status=dismissed + dismissed_at + dismissed_by). Hard delete prohibited. | "We chose not to ingest this record" is a compliance artifact. Audit trail must be preserved. | `test_sync_failures.py::test_dismiss_sets_dismissed_status_not_deletes` |
| D-FAIL-7 | 404 during task-level retry = tombstone, not retrying. | Chasing deleted upstream records forever wastes workers. Tombstone = explicit "not our data anymore." | `test_sync_failures.py::test_404_response_creates_tombstone` |
| D-FAIL-8 | health_status computed at response time: sync_paused=circuit_open; consecutive_failure_count>0 OR active sync_failures=degraded; else healthy. Single LEFT JOIN, not stored field. | Avoids cache staleness. Stored field would require sync runner to update on every failure â€” adds complexity. | `test_datasources_router.py::test_health_status_degraded_on_failure_count` |
| D-FAIL-9 | sync_run_log: one row per run, no coupling to retry logic. Minimal fields. | "Why did this sync run at 2:13 not 2:00" is unanswerable without it. Conflating with sync_failures complicates both. | `test_sync_run_log.py::test_each_sync_creates_one_run_log_row` |
| D-FAIL-10 | Pipeline error classification: IntegrityError â†’ immediately permanently_failed (no task retry); IOError/Ollama timeout â†’ task retry. | IntegrityError is a code bug; retrying wastes workers and produces misleading metrics. Transient infra errors self-resolve. | `test_sync_runner_pipeline_failures.py::test_integrity_error_skips_task_retry` |
| D-FAIL-11 | Bulk actions: retry-all and dismiss-all on sync_failures. | Admin with 50 stuck records will not click Retry 50 times. Hotfix later is worse. | `test_sync_failures_router.py::test_retry_all_permanently_failed` |
| D-UI-1 | Sync Now button stays "Syncingâ€¦" + disabled until last_sync_at advances (exponential backoff polling: 5sâ†’10sâ†’20sâ†’30s). Timeout 15min. Shows elapsed time. **Required automated test (not manual QA).** | Button that lies about completion = shipped broken feature. Polling refactors silently break it without test. | `DataSourceCard.test.tsx::test_sync_now_button_stays_disabled_until_completion` |
| D-UI-2 | Notifications: created_by recipient, fallback to ADMIN-role users. Triggers: circuit-open + recovery. Rate-limit: batch within 5-min window â†’ digest. | First-failure is noisy. Circuit-open is the signal. 10-source simultaneous outage â†’ 1 digest not 10 emails. | `test_sync_notifications.py::test_circuit_open_fires_notification` |
| D-FAIL-12 | 429 with `Retry-After` header honored at task-level (not enqueued as sync_failures). Capped at 600s to prevent worker starvation. | 429 is transient and expected on rate-limited municipal APIs. Task-level is the right layer â€” polluting sync_failures with rate-limit events would trip circuit breaker on noise. | `test_rest_connector.py::test_429_retry_after_header_honored` |
| D-FAIL-13 | sync_failures and sync_run_log both CASCADE on DataSource delete. | Orphaned failure rows for a deleted source are noise. Admin deleting a source intends to remove all associated state. | `test_sync_failures.py::test_cascade_delete_removes_failures_and_run_log` |
| D-TENANT-1 | CivicRecords is single-tenant per install (one city per deployment). No org-level isolation within a deployment. All admin-role users within the installation share access to all sources. | Architecture is per-city SaaS/self-hosted. Multi-tenant within a single install is not a v1 requirement. | `test_datasources_router.py` â€” admin-role access tests (existing) |
| D-PROC-1 | Every Claude Code / Cowork session touching this repo MUST load the `coder-ui-qa-test` skill as its first action. The skill defines the Principal Engineer / Senior UI Designer / Senior QA Engineer standards and enforces Hard Rule 9 (mandatory deliverables gate). No push is permitted until all five Rule 9 artifact classes exist on disk. Override phrase: `"override rule 9"` (literal, from human in chat only). | The five Rule 9 deliverables (UML diagrams, README Ã—4 formats, USER-MANUAL Ã—3 formats/sections, landing page with 4 action buttons, GitHub Discussions seed) were absent from the initial v1.1.0 development because the skill was not loaded. Retroactive production required three commits after the fact. This decision ensures the gap cannot recur. | Verified via `CLAUDE.md` Hard Rule 0 (project-level) and the `coder-ui-qa-test` skill `Â§ HARD RULES Â§9`. |

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
Credentials encrypted at rest (Fernet envelope: AES-128-CBC + HMAC-SHA256) via the `EncryptedJSONB` TypeDecorator on `data_sources.connection_config`, keyed off `ENCRYPTION_KEY`. Never logged, exported, or returned. See Â§8.10.
Coverage gap map auto-updates.
Zero false negatives for Tier 1 regex PII detection.
All redaction is proposal-only; humans approve.
CJIS compliance gate enforced for public safety connectors.
All LLM calls route through central client with prompt injection sanitization.
ReDoS protection on all admin-entered regex patterns.
VBA macros stripped from all ingested DOCX/XLSX files.
**Process criteria (coder-ui-qa-test skill enforcement):**
- `coder-ui-qa-test` skill MUST be loaded as the first action of every session touching code, tests, documentation, or deployment â€” no exceptions.
- All five Rule 9 mandatory deliverables (UML diagrams, README Ã—4, USER-MANUAL Ã—3 sections/formats, landing page with action buttons, GitHub Discussions seed) MUST exist on disk and be verified before any `git push` or release.
- Every coding task MUST close with a Verification Log containing evidence of what was verified â€” terminal output unedited, files read listed, tests run with counts, runtime behavior described, documentation artifacts accounted for. "It should work" is not evidence.

## 19. Canonical Guidance for Future Spec Work
For future documentation, use this precedence order:
0. **Verification Log** â€” terminal output, DOM inspection results, and runtime evidence from the session that produced the change. This is the ground truth. It supersedes everything below.
1. Repository code and route surface
2. Repository tests
3. CHANGELOG entries
4. Repository README
5. Design/spec prose
When those disagree, do not preserve the older narrative claim just because it sounds cleaner.

## Appendix A: Repository Structure
Top-level contents of github.com/CivicSuite/civicrecords-ai (master branch):
backend/ â€” Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, Celery
frontend/ â€” React 18, Vite, shadcn/ui, Tailwind CSS, Geist Variable font
docs/ â€” 20+ documentation files including manuals, specs, QA reports, architecture diagrams
scripts/ â€” install scripts, verification scripts
test-data/ â€” test fixtures
docker-compose.yml + 3 variant files (dev, gpu, host-ollama)
install.ps1 (Windows), install.sh (macOS/Linux) â€” **install paths as of 2026-04-22 (post-T5E):**
- **Windows:** double-click unsigned installer (Inno Setup 6.x) produced by `.github/workflows/release.yml` on every `v*` tag â€” `installer/windows/civicrecords-ai.iss` + `build-installer.sh`. Installs to `C:\Program Files\CivicRecords AI\`, runs `installer/windows/prereq-check.ps1` (Docker Desktop, WSL 2 + Virtual Machine Platform, 32 GB RAM floor, optional host Ollama), then `install.ps1` for the T5C Gemma 4 picker + auto-pull + T5B first-boot baseline seeding. Start Menu ships two separate shortcuts: **Start CivicRecords AI** (daily start via `launch-start.ps1` â€” `docker compose up -d` only, no install, no model pull) and **Install or Repair CivicRecords AI** (full bootstrap via `launch-install.ps1`). Operators must install Docker Desktop separately; the prereq check detects absence and prints remediation. See Â§8.8 and `installer/windows/README.md`.
- **macOS / Linux:** script-based (`install.sh`) â€” configures and starts the Docker Compose stack; requires Docker Desktop (macOS) or Docker Engine (Linux) to already be installed and running. No platform-native installer ships in this slice; cross-platform installer parity is documented as follow-on, not implemented.
CHANGELOG.md, CONTRIBUTING.md, CLAUDE.md, USER-MANUAL.md, LICENSE (Apache 2.0)
Backend modules (20): admin, analytics, audit, auth, catalog, city_profile, connectors, datasources, departments, documents, exemptions, ingestion, llm, models, notifications, onboarding, requests, schemas, search, service_accounts
Backend model files (15): audit.py, city_profile.py, connectors.py, departments.py, document.py, exemption.py, fees.py, notifications.py, prompts.py, request.py, request_workflow.py, search.py, service_account.py, user.py
Frontend pages (14): AuditLog, CityProfile, Dashboard, DataSources, Discovery, Exemptions, Ingestion, Login, Onboarding, RequestDetail, Requests, Search, Settings, Users
Test modules (45): test_admin, test_analytics, test_audit, test_auth, test_catalog, test_chunker, test_city_profile, test_compliance_templates, test_coverage_gaps, test_datasource_connection, test_datasources, test_department_scoping, test_departments, test_documents, test_embedder, test_exemption_dashboard, test_exemption_features, test_exemption_rules_seed, test_exemptions, test_fee_lifecycle, test_fee_schedules, test_fees, test_health, test_imap_connector, test_ingestion_retry, test_llm_client, test_manual_drop, test_messages, test_model_registry, test_notification_dispatch, test_notifications, test_onboarding_interview, test_parsers, test_pipeline, test_prompt_injection, test_requests, test_response_letter, test_roles, test_search_api, test_search_engine, test_search_features, test_service_accounts, test_smtp_delivery, test_timeline, test_user_management

## Appendix B: Bottom-Line Summary
CivicRecords AI at v1.4.3 is a substantially complete internal staff platform with a minimal public surface, at-rest-encrypted connector credentials, a real Windows double-click installer, and Phase 2 LLM integration aligned to the civiccore dependency line. From an 80-test foundation at v0.1.0 the codebase has grown to **~620 automated backend tests + ~30 frontend tests** (all passing) with department-level access control, 50-state exemption coverage, a complete notification pipeline, a central LLM client with prompt injection sanitization, fee waiver workflows, a rich text editor, macro stripping, search enhancements, coverage gap monitoring, user management improvements, Tier 2 auth/authz hardening across 24 department-scoped handlers, credential redaction, bootstrap hardening, SSRF protection, and Tier 6 at-rest encryption (Fernet envelope on `data_sources.connection_config`), and the first shared connector-security extraction onto civiccore v0.13.0.

The system is well beyond a simple MVP: it has professional security hardening (ReDoS protection, self-demotion guards, credential redaction, SSRF host validation, FIRST_ADMIN_PASSWORD validation, macro stripping), operational polish (retry, priority indicators, citation rendering, empty states), and accessibility foundations (44px touch targets, skip navigation, icon+color badges, full F1â€“F6 keyboard/SR audit complete).

**Tier 5 status â€” FULLY SHIPPED (2026-04-22/23):** all five slices pushed to `origin/master` and individually CI-verified. T5C Gemma 4 tag purge + 4-model installer picker (`7721cf0`). T5A onboarding persistence + `has_dedicated_it` + `onboarding_status` lifecycle + skip-truth (`1782573`). T5B first-boot baseline seeding â€” 175 state-scoped exemption rules + 5 compliance templates + 12 notification templates, idempotent, visibly logged (`61449c5`). T5D `PORTAL_MODE=public|private` install-time switch + minimal public surface under Scott-locked B4=(b) + Option A register-first (`a57a897`). T5E Windows unsigned double-click installer via Inno Setup 6.x with Start-vs-Install flow split and tag-derived version sourcing (`1d5429d`; CI-flake fix `e898319`). T3D regen after T5A schema change (`bf3c9c3`). CI workflow Node 20 runtime bump (`5dbeed7`). All slices shipped under Hard Rule 9 (six-artifact doc gate) with matching CHANGELOG + README + USER-MANUAL + docs/index.html updates in the same commit.

**What remains (not in Tier 5 scope, intentionally deferred):**
- **Tier 6 â€” at-rest encryption for `data_sources.connection_config` (ENG-001).** CLOSED 2026-04-23. Fernet envelope + `EncryptedJSONB` TypeDecorator + reversible Alembic migration `019_encrypt_connection_config` + operator `verify_at_rest.py` script. T2B runtime exposure + Tier 6 at-rest exposure both closed â†’ ENG-001 fully closed. See Â§8.10. (Historical entry retained so prior sprint notes and memory/state files that refer to "Tier 6 still open" can be reconciled with the live repo. Key rotation is intentionally not in scope for this release and is available as a future slice â€” not a deferred Tier 6 item.)
- **Cross-platform native installer parity for macOS/Linux.** Follow-on to T5E; not scheduled. macOS/Linux remain on the script path (`install.sh`).
- **Signed Windows installer.** Scott-locked B3=Î± (unsigned by design for this slice). Signing is not a deferred Tier 5 item; it is explicitly out of the T5E slice. Any future signing work would be a new decision.
- **Public-portal expansion beyond B4=(b).** Published-records search, resident dashboard, track-my-request suite are all PLANNED and explicitly out of the T5D minimal surface. Expansion requires explicit Scott re-scoping.
- **Full active network discovery engine.**
- **GIS connector.**
- **Cross-instance federation workflows** (role + service-account primitives exist; full product surface PLANNED).
- **Tier 2/3 redaction** (NER, visual AI).
- **CI hygiene â€” GitHub Actions Node 20 deprecation follow-through.** `5dbeed7` landed the workflow action bumps; the runner-side Node 20 â†’ Node 24 default flip on 2026-06-02 must be clean by that date.

**Release state:** Current release is **v1.4.3** (April 29, 2026), which moves connector host validation and encrypted-config primitives onto the shared civiccore v0.13.0 line on top of the v1.4.0 Phase 2 LLM integration release. The `[Unreleased]` CHANGELOG block above `[1.4.3]` is the collection point for post-v1.4.3 work.

This document (v3.1) is the single source of truth and is now the in-repo `docs/UNIFIED-SPEC.md`.

