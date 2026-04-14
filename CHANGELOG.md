# Changelog

All notable changes to CivicRecords AI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-04-13

### Added
- **Department Scoping:** Department model with CRUD API, department assignment on users and data sources, department-based access control on requests
- **50-State Exemption Rules:** 180 exemption rules across 51 jurisdictions (50 states + DC), seeded from canonical state public records law database
- **Compliance Templates:** 5 seeded compliance documents (AI use disclosure, response letter disclosure, CAIA impact assessment, AI governance policy, data residency attestation)
- **Model Registry:** Admin-managed Ollama model registry with context window tracking, active model selection, and automatic budget scaling in context manager
- **Central LLM Client:** All LLM generation calls route through `app/llm/client.py` — enforces context manager budgeting, prompt injection sanitization, and model-registry context window scaling on every call. Refactored exemptions reviewer, search synthesizer, and ingestion extractor to use it
- **Notification System:** 12 notification templates aligned with all router-dispatched event types, city_name sourced from city profile for email templates, queue_notification wired into 5 status transitions
- **Users Edit/Deactivate:** PATCH /admin/users/{id} endpoint with self-demotion lockout and self-deactivation guard. Frontend edit dialog and deactivate button with confirmation
- **Search Department Filter:** Department filtering on both semantic and keyword search engines via document-source-department join chain. Department dropdown in search UI
- **Search CSV Export:** GET /search/export endpoint with authenticated download. Export button in search results
- **Fee Estimation:** POST /requests/{id}/estimate-fees — staff enters page count, system calculates from fee schedule rates
- **Fee Waivers:** FeeWaiver model with Alembic migration, create/approve/deny workflow, automatic fee_status update on approval. Waiver types: indigency, public interest, media, government, other
- **Exemption Audit History:** GET /exemptions/rules/{id}/history returns audit log entries for any rule. Timeline UI in Exemptions page
- **Exemption Rule Test Modal:** POST /exemptions/rules/{id}/test — tests regex or keyword rules against sample text with match positions. ReDoS protection via `regex` library with 2-second timeout. LLM-type rules rejected with 400
- **Sources 3-Step Wizard:** Replaced single-step add dialog with guided wizard (source type selection, connection config per type, review + test connection). POST /datasources/test-connection validates connectivity without persisting credentials
- **Dashboard Coverage Gaps:** GET /admin/coverage-gaps identifies jurisdictions without exemption rules, departments without assigned staff, and exemption categories without active rules. Warning card on dashboard when gaps > 0
- **Search Citation Rendering:** AI summary panel renders [Doc: filename, Page: N] citations as styled inline badges instead of plain text
- **Request Priority Indicators:** Priority column with colored badges (urgent/expedited/normal/low) on Requests table
- **Ingestion Retry:** POST /datasources/documents/{id}/re-ingest retries failed documents (resets to pending, queues Celery task). Progress indicator for processing items, auto-refresh while active
- **Rich Text Editor:** TipTap editor replaces plain textarea for response letter editing. Toolbar with bold, italic, underline, bullet list, ordered list. Content stored as HTML in edited_content field
- **Onboarding LLM Interview:** POST /onboarding/interview generates adaptive setup questions based on incomplete city profile fields. Chat-style UI with skip button, profile updates via PATCH /city-profile. Falls back to default questions when LLM unavailable
- **DOCX/XLSX Macro Stripping:** Parsers strip VBA macros at ZIP level before text extraction. Supports .docm and .xlsm. Stripping logged in metadata for audit
- **WCAG 44x44px Touch Targets:** min-width: 44px added alongside min-height for all interactive elements. All icon button variants enforce minimum touch target

### Changed
- **Department Names on Users Page:** UUID column replaced with human-readable department names via /departments/ API lookup
- **Legacy .xls Blocklisted:** Removed .xls from XlsxParser supported extensions — BIFF8 binary format cannot be macro-stripped with ZIP approach
- **Dead CSS Selector Removed:** `a.nav-link` in globals.css was unreachable (WCAG 44px applied via Tailwind inline on sidebar NavLinks)
- **Version Alignment:** config.py, pyproject.toml, package.json, and CHANGELOG all at 1.1.0

### Fixed
- **Notification Event-Type Mismatch:** Aligned 12 seed templates with router dispatch strings — all 5 dispatch paths now deliver notifications instead of silently no-oping on 3 of 5
- **Notification Seed Production Run:** Confirmed execution against production DB (5 created, 7 skipped)
- **Audit Log CSV Export:** Frontend export button now uses authenticated fetch with ?format=csv and blob download instead of bare anchor tag (was returning 401)
- **Dockerfile:** Added compliance_templates/, scripts/, and tests/ to COPY directives — compliance template test was failing on clean builds
- **city_name in Notifications:** All 5 queue_notification call sites now include city_name from CityProfile — 8 templates were silently failing at render time due to missing template variable
- **GitHub Pages Build:** Added .nojekyll to docs/ — Jekyll was failing on spec markdown files, causing 59 consecutive failed pages-build-deployment runs

### Security
- **ReDoS Protection:** Exemption rule test endpoint uses `regex` library with timeout=2s for admin-entered patterns — prevents catastrophic backtracking
- **Test-Connection Credential Safety:** POST /datasources/test-connection uses dedicated schema, never persists credentials, never logs connection strings, never returns credentials in response
- **Self-Demotion Guard:** Admins cannot change their own role or deactivate their own account via the PATCH endpoint
- **Macro Stripping:** VBA macros stripped from DOCX/XLSX before ingestion — defense-in-depth for document pipeline security

### Tests
- 274 automated tests (up from 80 in v0.1.0, 104 at v1.0.0 release)
- +36 tests in debt sprint: LLM client wiring (3), user management (7), search features (3), fee lifecycle (5), exemption features (6), datasource connection (4), coverage gaps (2), ingestion retry (2), onboarding interview (4)
- Template render mismatch test catches any notification template referencing variables not provided by the router
- Seed coverage test ensures every router-dispatched event_type has a matching template
- .xls blocklist test prevents accidental re-addition of legacy format

## [1.0.0] - 2026-04-12

### Added
- **Design System:** shadcn/ui component library with civic design tokens (#1F5A84 primary), Geist Variable typography scale, sidebar layout shell
- **Sidebar Navigation:** Grouped navigation (Workflow / Setup / Administration) replacing top nav bar, 44px touch targets, active page indicator
- **11 Pages:** Dashboard, Search, Requests, Request Detail, Exemptions, Sources, Ingestion, Users, Onboarding Interview, City Profile, Discovery Dashboard
- **Onboarding Interview:** 3-phase wizard (City Profile, System Identification, Gap Map) for first-time city deployment
- **City Profile API:** GET/POST/PATCH /city-profile for persistent city configuration with gap map
- **Municipal Systems Catalog:** 12 functional domains, 25+ vendor systems in bundled JSON with auto-loader on startup
- **Request Timeline:** Event history on every request with automatic logging on status transitions
- **Request Messages:** Internal/external messaging thread on each request
- **Fee Tracking:** Fee line items per request with automatic total calculation
- **Response Letter Generation:** LLM-assisted draft letters with template fallback, labeled as AI-generated draft
- **Notification Service:** Template-based notification system with queue_notification() helper, template CRUD API
- **Operational Analytics:** GET /analytics/operational with response time, deadline compliance, overdue count, status breakdown
- **Connector Framework:** Universal connector protocol (authenticate/discover/fetch/health_check) with file system implementation
- **Tier 1 PII Expansion:** Credit card (Luhn-validated), bank routing/account numbers, state-specific driver's license patterns (CO, CA, TX, NY, FL)
- **Context Manager:** Token budgeting for local LLM calls with priority-based context assembly
- **11 Request Statuses:** received, clarification_needed, assigned, searching, in_review, ready_for_release, drafted, approved, fulfilled, closed
- **StatusBadge Component:** Color+icon mapping for all statuses across request, document, and exemption domains (colorblind accessible)
- **StatCard, PageHeader, EmptyState, DataTable:** Reusable design system components with loading, empty, and error states
- **Skip-to-content Link:** Screen reader accessibility (WCAG 2.4.1)
- **Discovery Dashboard Shell:** v1.1 preview page with feature explanation

### Changed
- **UI Redesign:** All pages migrated from raw Tailwind to shadcn/ui design system with civic color tokens
- **Ingestion Filenames:** UUID prefixes stripped from display — original filenames shown
- **Timestamps:** Relative display ("3 hours ago") alongside absolute dates
- **Search Scores:** RRF scores normalized to 0-100% with visual progress bar
- **Empty States:** Smart contextual guidance instead of blank screens ("No flags reviewed yet" instead of "0.0%")
- **Request Forms:** Collapsible inline forms replaced with Dialog modals
- **Status Badges:** Color-only badges replaced with icon+color badges for accessibility
- **Navigation:** Top nav bar replaced with sidebar layout (240px fixed, 56px header)

### Fixed
- **Dockerfile.backend:** Added missing `data/` directory copy for systems catalog
- **Catalog Loader:** Graceful handling when systems_catalog.json not found (no crash on startup)
- **Sidebar Footer:** Shows user email instead of UUID (via /users/me endpoint)

### Security
- All new endpoints require role-based authentication
- All mutations audit-logged
- Notification credentials never logged or displayed after entry
- Response letters labeled as "AI-GENERATED DRAFT — REQUIRES HUMAN REVIEW"
- CJIS compliance gate designed for public safety connectors (Section 12)

## [0.1.0] - 2026-04-12

### Added
- **Foundation:** Docker Compose stack with PostgreSQL+pgvector, Redis 7.2, Ollama, FastAPI, Celery, React frontend
- **Authentication:** JWT-based auth with 4 roles (Admin, Staff, Reviewer, Read-Only) via fastapi-users
- **Service Accounts:** API key generation for federation between CivicRecords AI instances
- **Audit Logging:** Hash-chained, append-only audit log with CSV/JSON export and chain verification
- **Document Ingestion:** Two-track pipeline — 7 file type parsers (PDF, DOCX, XLSX, CSV, email, HTML, text) + Gemma 4 multimodal OCR with Tesseract fallback
- **Chunking:** Sentence-aware text chunking with configurable overlap
- **Embeddings:** nomic-embed-text via Ollama with batch support, stored in pgvector
- **Hybrid Search:** pgvector semantic similarity + PostgreSQL full-text search combined via Reciprocal Rank Fusion
- **LLM Synthesis:** Optional AI-generated answer summaries from search results (labeled as AI draft)
- **Search Sessions:** Query history tracking with iterative refinement
- **Request Tracking:** Records request lifecycle management with status workflow (received → searching → in_review → drafted → approved → sent)
- **Document Attachment:** Link search results to requests with automatic document caching for legal defensibility
- **Deadline Management:** Approaching deadline and overdue alerts on request dashboard
- **Exemption Detection:** Rules-primary engine with built-in PII patterns (SSN, phone, email, credit card, DOB) + per-state keyword rules
- **LLM Exemption Suggestions:** Optional secondary exemption detection via Ollama, confidence capped at 0.7
- **Colorado CORA Pilot:** Pre-configured exemption rules for Colorado Open Records Act categories
- **Exemption Review Workflow:** Accept/reject flags with audit trail and acceptance rate dashboard
- **Disclosure Templates:** Configurable compliance document templates (AI disclosure, response letters)
- **Model Transparency:** Admin panel showing Ollama model info (name, size, details)
- **Data Sovereignty:** Verification script confirming no outbound data transmission
- **Cross-Platform:** Windows (Docker Desktop), macOS, and Linux support with platform-specific install scripts
- **React Admin Panel:** 8 pages — Login, Dashboard, Search, Requests, Request Detail, Exemptions, Data Sources, Ingestion, Users
- **80 automated tests** covering auth, audit, search, requests, exemptions, parsers, chunking, embeddings

### Security
- All audit logs hash-chained with SHA-256 for tamper evidence
- Human-in-the-loop enforced at API layer (no auto-redaction, no auto-approval)
- All LLM outputs labeled as AI-generated drafts
- No telemetry, analytics, or outbound data transmission
- JWT secrets from environment configuration (not hardcoded)
- API keys hashed before storage (SHA-256)
