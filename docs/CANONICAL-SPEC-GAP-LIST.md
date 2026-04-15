# CivicRecords AI -- Canonical Spec Gap List

**Generated:** 2026-04-13
**Source:** `docs/UNIFIED-SPEC.md` v2.0 (April 12, 2026)
**Method:** Spec section-by-section comparison against codebase at HEAD

---

## How to Read This Document

Each item lists:
- **Spec reference** (section number, phase tag)
- **Code status** (exists / partial / missing)
- **What's missing** (specific deliverable gap)

Items completed during the current session are noted but NOT re-listed unless they have remaining sub-gaps.

---

## Phase 0: Design Foundation [MVP-NOW] -- COMPLETE

Spec Section 11 marks Phase 0 as COMPLETE. Verified in codebase:
- shadcn/ui installed (`frontend/src/components/ui/`)
- Design tokens mapped to CSS variables (`globals.css`)
- Sidebar layout shell (`app-shell.tsx`, `sidebar-nav.tsx`)
- Component variants: buttons, badges, cards, tables, stat-cards, empty-states
- Typography scale implementation

**No gaps in Phase 0.**

---

## Phase 1: Staff Workbench Redesign [MVP-NOW] -- 11 Pages

### 1.1 Dashboard (Section 7.2) [REDESIGN]

| Item | Spec Says | Code Status | Missing |
|------|-----------|-------------|---------|
| Priority stat cards (4) | Open Requests, Overdue, Avg Response, Deadline Compliance | Partial -- `Dashboard.tsx` exists | Verify operational metrics cards match spec (Overdue count, Avg Response days, Compliance %) |
| Service health row | Compact inline: Database, LLM Engine, Task Queue | Partial | Verify service health indicators match spec format |
| Recent activity timeline | Last 10 events across all requests | Unknown | Verify timeline component pulling from `request_timeline` |
| Requests by status | Mini bar chart or stacked badges | Unknown | Verify chart/badge visualization |
| Approaching deadlines | Next 5 with days remaining | Unknown | Verify deadline widget |
| Quick actions | New Request, Search Records, Export Audit Log | Unknown | Verify action buttons |
| Coverage gap indicators | Section 12, gap map on dashboard | Missing | No coverage gap display on Dashboard |

### 1.2 Search (Section 7.3) [REDESIGN]

| Item | Spec Says | Code Status | Missing |
|------|-----------|-------------|---------|
| Empty state guidance | Example searches, prominent search bar | Partial -- `Search.tsx` exists | Verify empty state matches spec |
| Normalized scores | 0-100% scale with progress bar | Partial (1 grep hit) | Verify visual rendering as percentage bar |
| Department filter | Filter by department | Unknown | Verify department filter dropdown |
| Export results | Export button on results | Unknown | Verify export functionality |
| AI Summary panel | "Generate AI summary" checkbox, bordered card with citations | Unknown | Verify AI summary panel with source citations |
| Saved searches | v1.1 feature | N/A for MVP | -- |

### 1.3 Requests (Section 7.4) [REDESIGN]

| Item | Spec Says | Code Status | Missing |
|------|-----------|-------------|---------|
| Priority stat cards | Overdue, Due This Week, In Review, Total Open | Partial -- `Requests.tsx` exists | Verify priority-focused stat cards |
| Filter bar | Status, Assigned To, Department, Priority, Date Range | Partial (8 grep hits for filter/priority) | Verify all 5 filter dropdowns implemented |
| Priority indicators | Red urgent, normal, expedited | Unknown | Verify priority column and icons |
| Pagination | Previous/Next with page count | Unknown | Verify pagination controls |
| "No deadline set" | Replace "None" display | Unknown | Verify empty deadline text |

### 1.4 Request Detail (Section 7.5) [REDESIGN]

| Item | Spec Says | Code Status | Missing |
|------|-----------|-------------|---------|
| Timeline panel | Chronological event history from `request_timeline` | Partial (1 grep hit) | Verify timeline rendering |
| Messages panel | Internal notes + requester messages, toggle | Partial (98 grep hits for fee/message) | Verify message send/toggle UI |
| Fee tracking panel | Estimated fee, status, Update Fee Estimate button | Partial | Verify fee panel in right column |
| Workflow panel | Status transitions, Submit for Review, Request Clarification, Generate Response Letter | Unknown | Verify workflow action buttons |
| Search & Attach panel | Quick search within request context | Unknown | Verify inline search-and-attach |
| Response letter generation | Generate Response Letter button triggering LLM | Unknown | Verify button + LLM integration |
| Document filenames | Original filenames not UUIDs | Unknown | Verify display_name rendering |
| Two-column layout | 65%/35% split per spec wireframe | Unknown | Verify layout proportions |

### 1.5 Exemptions (Section 7.6) [REDESIGN]

| Item | Spec Says | Code Status | Missing |
|------|-----------|-------------|---------|
| Tab bar | Flags for Review, Rules, Audit History | Unknown -- `Exemptions.tsx` exists | Verify 3-tab layout |
| Flag review table | Document, Category, Confidence, Matched Text, Rule, Accept/Reject/View Context | Unknown | Verify flag review workflow on this page |
| "No flags reviewed yet" | Replace misleading "Acceptance Rate: 0.0%" | Unknown | Verify empty state text |
| Rule test input | Modal with test input for rule validation | Unknown | Verify rule test modal |

### 1.6 Sources (Section 7.7) [REDESIGN]

| Item | Spec Says | Code Status | Missing |
|------|-----------|-------------|---------|
| Card grid layout | Cards not table for connected sources | Unknown -- `DataSources.tsx` exists | Verify card grid vs. table |
| Guided setup modal | 3-step wizard: path, schedule, department | Unknown | Verify guided Add Source flow |
| Connection testing | Test Connection button per source | Unknown | Verify test connection UI |
| Integration placeholders | SharePoint, Database, API coming soon cards | Unknown | Verify placeholder cards |
| Connector management | Section 12.4 connector UI | Unknown | Verify connector config UI |

### 1.7 Ingestion (Section 7.8) [REDESIGN]

| Item | Spec Says | Code Status | Missing |
|------|-----------|-------------|---------|
| Clean filenames | Original filenames, not UUID prefixes | Unknown -- `Ingestion.tsx` exists | Verify filename display |
| Progress indicators | Progress bar with step indicator during active processing | Unknown | Verify progress bar UI |
| Retry for failed | Re-ingest button on failed documents | Unknown | Verify retry action |
| Relative timestamps | "3 hours ago" alongside absolute dates | Unknown | Verify timestamp format |

### 1.8 Users (Section 7.9) [REDESIGN]

| Item | Spec Says | Code Status | Missing |
|------|-----------|-------------|---------|
| Department column | Department assignment visible in table | Unknown -- `Users.tsx` exists | Verify department column |
| User edit view | Edit modal/page for user details | Unknown | Verify edit user UI |
| Deactivate button | Per-user deactivate action | Unknown | Verify deactivate action |
| "Never logged in" | Replace unhelpful "Never" text | Unknown | Verify last active display |

### 1.9 Onboarding Interview (Section 7.10, 12.2) [MVP-NOW] -- NEW PAGE

| Item | Spec Says | Code Status | Missing |
|------|-----------|-------------|---------|
| Three-phase wizard | City Profile, System Identification, Gap Map | Partial -- `Onboarding.tsx` exists | Verify 3-phase wizard with progress indicator |
| Chat-style interface | Conversational with structured inputs | Unknown | Verify chat UI pattern |
| LLM-guided adaptive interview | Questions adapt based on answers | Unknown | Verify LLM integration in interview flow |
| Save-and-resume | `onboarding_status` tracks progress | Unknown | Verify save/resume capability |
| Skip buttons | For unknown answers | Unknown | Verify skip functionality |

### 1.10 City Profile & Settings (Section 7.11, 12.2.2) [MVP-NOW] -- NEW PAGE

| Item | Spec Says | Code Status | Missing |
|------|-----------|-------------|---------|
| City details card | Name, state, population, email platform, IT staffing, request volume | Partial -- `CityProfile.tsx` exists | Verify all fields rendered |
| Connected Systems table | Domain, System, Vendor, Protocol, Status, Last Sync, Actions | Unknown | Verify systems table |
| Gap Map display | Warning icons for unconnected domains, checkmarks for connected | Unknown | Verify gap map visualization |
| Re-run Onboarding button | Link back to onboarding wizard | Unknown | Verify re-run action |

### 1.11 Discovery Dashboard (Section 7.12, 12.3.3) [v1.2+] -- DEFERRED

| Item | Spec Says | Code Status | Decision |
|------|-----------|-------------|---------|
| Discovery nav + route | v1.1 full implementation | Removed from nav and routing in v1.1 | Deferred to v1.2+. No backend exists. Shipping a dead nav item is worse than honest scoping. `Discovery.tsx` preserved as starting point. See CC-004. |

---

## Phase 2: New Backend Features [MVP-NOW]

### Completed During This Session

The following items were built during the current session. They are listed here only if remaining sub-gaps exist.

| Item | Spec Section | Status | Remaining Gaps |
|------|-------------|--------|----------------|
| Database migrations (12 new tables + extended columns) | 5, 12.9, Appendix A | DONE | Migration file exists: `787207afc66a_phase2_extensions...` |
| Prompt injection defenses | 10.1 | DONE | `test_prompt_injection.py` exists |
| RBAC roles (liaison) | 2 | DONE | `user.py` has liaison enum + department_id |
| SMTP / notification service | 8.4 | DONE | `notifications/` module with `smtp_delivery.py`, `service.py`, `router.py` |
| Fee schedules + tracking | 5 (Fees), 7.5 | DONE | `models/fees.py` exists |
| Connector framework | 12.4 | DONE | `connectors/` with `base.py`, `file_system.py`, `imap_email.py`, `manual_drop.py` |
| Dashboard filtering | 7.4 | DONE | Filter support in Requests page |
| Rule versioning | 5 (Exemptions) | DONE | Extended exemption_flags model |
| Scope assessment | 5 (Requests) | DONE | `scope_assessment` field in request model |
| WCAG foundations | 9 | DONE | Focus rings in shadcn/ui components (6 files) |
| Departments | 5 | DONE | `departments/` module with router |
| City profile model + router | 12.2.2 | DONE | `city_profile/` module with router |
| Systems catalog | 12.1 | DONE | `catalog/` module with loader + router |
| Analytics API | 5 (Analytics) | DONE | `analytics/router.py` with operational metrics |
| Response letter model | 8.3 | DONE | `models/request_workflow.py` + `test_response_letter.py` |
| Prompt templates | 5 (Prompts) | DONE | `models/prompts.py` |

### Phase 2 Items NOT Yet Complete

| # | Item | Spec Section | Code Status | What's Missing |
|---|------|-------------|-------------|----------------|
| 2.1 | **Context Manager (token budgeting)** | 4 (Context Management) | MISSING | No dedicated context manager module. Spec requires: token budget system, smart context assembly, chunked processing, model-aware budgeting. Only grep hits are in `requests/router.py` (basic prompt assembly) and `models/prompts.py` (schema only). Need `backend/app/llm/context_manager.py` implementing the full budget system from Section 4. |
| 2.2 | **Response letter generation (LLM integration)** | 8.3 | PARTIAL | Model + test exist, but no evidence of actual LLM-powered generation endpoint. Need: context assembly within token budget, LLM draft generation, rich text editor integration, approval workflow API (draft -> approved -> sent status transitions). |
| 2.3 | **Onboarding service (LLM-guided interview)** | 12.2 | PARTIAL | `city_profile/` router exists but no LLM-guided adaptive interview service. Need: interview state machine, LLM prompt integration for adaptive questions, catalog cross-referencing, gap map generation logic. |
| 2.4 | **Tier 1 regex expansion** | 12.7.1 | UNKNOWN | Spec requires: credit cards (Luhn-validated), bank account/routing numbers, driver's license (state-specific patterns). Existing exemption rules may only cover SSN, phone, email. Need to verify existing regex rules cover ALL Tier 1 patterns and add seed data for missing ones. |
| 2.5 | **Fee tracking API** | 5 (Fees) | PARTIAL | `models/fees.py` exists. Need to verify: fee estimation endpoint, fee line item CRUD, waiver management API, invoice/payment status transitions. May need `backend/app/fees/router.py`. |
| 2.6 | **Audit retention cleanup task** | 10.2 | PARTIAL | `ingestion/scheduler.py` and `config.py` reference retention. Need to verify: Celery Beat periodic task that purges audit entries older than configurable retention period. |
| 2.7 | **Notification templates seed data** | 8.4 | UNKNOWN | `scripts/seed_templates.py` exists. Need to verify it seeds all 7 notification templates from Section 8.4 (received, clarification, assigned, deadline approaching, deadline overdue, records ready, request closed). |
| 2.8 | **Request status transitions with side effects** | 8.1 | UNKNOWN | Spec requires every status transition to: write to `request_timeline`, write to `audit_log`, trigger notification (if template exists), update status. Need to verify the workflow engine implements all side effects. |

---

## Phase 3: Public Portal [v1.1] -- NOT STARTED

All Phase 3 items are future work. No code exists for any of these.

| # | Item | Spec Section | What's Missing |
|---|------|-------------|----------------|
| 3.1 | **Public API with rate limiting** | 4 (Public API) | No `public/` API module. Need read-only endpoints, rate limiting middleware, public auth (token or anonymous). |
| 3.2 | **Public homepage** | 7 (Public Portal), 3 | No public frontend app. Need: search bar, common categories, response-time guidance, top tasks. |
| 3.3 | **Public search** | 3 (Search Records) | Published records index with filters. Requires `published_records` table (migration exists but table is v1.1). |
| 3.4 | **Guided request wizard** | 3 (Make a Request) | Multi-step intake wizard with scope helper for public users. |
| 3.5 | **Public request tracker** | 3 (Track a Request) | Public timeline, messages, delivered files, fees -- all visible without staff login. |
| 3.6 | **Help and policy pages** | 3 (Help & Policy) | Open records law summary, fee schedule, exemptions, contact info. |
| 3.7 | **Published records index** | 5 (published_records) | CRUD for publishing records, collection management. |
| 3.8 | **Saved searches** | 5 (saved_searches) | User-saved search queries with filters. |
| 3.9 | **Redaction ledger with originals vs. derivatives** | 5 (redaction_ledger), 12.8.3 | Full redaction tracking: page-level redactions, exemption basis, derivative file management. |
| 3.10 | **Network discovery engine** | 12.3 | Active network scanning, IT opt-in, fingerprinting. Requires `discovered_sources`, `discovery_runs` tables. |
| 3.11 | **Confidence scoring and auto-identification** | 12.3.2 | Score 0-100%, vendor matching against catalog. |
| 3.12 | **Connection health monitoring and self-healing** | 12.5 | Heartbeat scheduler, exponential backoff, auto-refresh OAuth, schema drift detection. Requires `source_health_log` table. |
| 3.13 | **REST API connectors (Tyler, Accela)** | 12.4.2 | Vendor-specific REST connectors implementing authenticate/discover/fetch/health_check. |
| 3.14 | **ODBC/JDBC bridge connector** | 12.4.2 | Database bridge connector for legacy on-prem databases. |
| 3.15 | **Coverage gap analysis** | 12.5.3 | Cross-reference requests vs. connected sources. Requires `coverage_gaps` table. Monthly Celery task. |
| 3.16 | **Discovery Dashboard (full)** | 7.12, 12.3.3 | Full implementation replacing MVP shell. Scan results, confidence, confirm/reject/connect actions. |
| 3.17 | **Tier 2 NER redaction** | 12.7.2 | AI-powered: person names, medical info, juvenile identifiers, attorney-client privilege. Requires NER model (spaCy or Ollama). |
| 3.18 | **`public` RBAC role** | 2 | Public user role: submit requests, track own requests, search published records. |

---

## Phase 4: Transparency Layer [v2.0] -- NOT STARTED

All Phase 4 items are future work. No code exists for any of these.

| # | Item | Spec Section | What's Missing |
|---|------|-------------|----------------|
| 4.1 | **Open records library with curated collections** | 5 (record_collections) | Collection CRUD, featured collections, freshness labels. |
| 4.2 | **Reporting dashboards and trend analytics** | 13 | Advanced analytics beyond operational metrics. |
| 4.3 | **Public request archive** | 13 | Closed requests visible to public (opt-in per request). |
| 4.4 | **Federation between instances** | 4 (Federation API) | Inter-instance REST queries via service accounts. Federation API exists as [BUILT] but needs cross-instance search. |
| 4.5 | **API endpoint probing** | 12.3.1 (Method 3) | Vendor auto-detection by probing standard API endpoints. |
| 4.6 | **Schema drift detection and alerting** | 12.5.2 | Detect schema hash changes, pause ingestion, alert admin. |
| 4.7 | **LLM-assisted database characterization** | 12.6.1 | Enumerate unknown DB schemas, feed to LLM for classification. Encrypted storage. |
| 4.8 | **RPA bridge** | 12.6.3 | Screen-scraping connector with self-diagnostics. Last resort per suitability criteria. |
| 4.9 | **Community catalog contributions** | 12.1 | Open-source contribution workflow for Municipal Systems Catalog updates. |
| 4.10 | **GIS connector** | 12.4.2 | Esri ArcGIS REST API connector for spatial/property data. |
| 4.11 | **Vendor SDK connectors** | 12.4.2 | Axon, CAD systems, evidence management integrations. |
| 4.12 | **Tier 3 visual AI** | 12.7.3 | Face/plate blurring in video, OCR for scanned docs, speech-to-text for audio. GPU required. |
| 4.13 | **Webhook/event stream connectors** | 12.4.2 | Real-time IoT, fleet telematics, sensors via shared secret or mTLS. |

---

## Section 12: Universal Discovery & Connection (Cross-Phase)

| Component | MVP-NOW Status | v1.1 Status | v2.0 Status |
|-----------|---------------|-------------|-------------|
| 12.1 Municipal Systems Catalog | DONE (catalog/ module, loader, router) | -- | Community contributions NOT STARTED |
| 12.2 Guided Onboarding Interview | PARTIAL (city_profile model/router exist, LLM interview logic MISSING) | -- | -- |
| 12.3 Active Discovery Engine | N/A for MVP | NOT STARTED | API probing NOT STARTED |
| 12.4 Universal Connector Protocol | DONE (base + 3 connectors) | REST API / ODBC NOT STARTED | GIS/SDK/webhook NOT STARTED |
| 12.5 Continuous Discovery & Self-Healing | N/A for MVP | NOT STARTED | Schema drift NOT STARTED |
| 12.6 Unknown/Legacy Systems | Manual fallback (upload) DONE | -- | LLM characterization + RPA NOT STARTED |
| 12.7 Tiered Redaction Engine | Tier 1 PARTIAL (regex exists, full pattern set UNVERIFIED) | Tier 2 NER NOT STARTED | Tier 3 visual NOT STARTED |
| 12.8 Security & Compliance | Credential encryption DONE, CJIS checklist UNKNOWN | -- | -- |
| 12.9 Data Model Additions | MVP tables DONE in migration | v1.1 tables in migration but UNUSED | v2.0 tables NOT STARTED |

---

## WCAG 2.2 AA Compliance (Section 9) -- Cross-Cutting

| Requirement | Spec Section | Status | Gap |
|-------------|-------------|--------|-----|
| Color contrast | 9 | PASSES | Maintain |
| Touch targets (44x44px minimum) | 9 | UNKNOWN | Need to verify all interactive elements meet 44px minimum |
| Focus visibility | 9 | PARTIAL | Focus rings in shadcn/ui components; need to verify custom components |
| Skip-to-content link | 9 | MISSING | No `skip-to-content` link found in layout shell |
| ARIA landmarks | 9 | PARTIAL | Nav role exists; need to verify new components |
| Status badge icons | 9 | UNKNOWN | Spec requires icon on every badge, never color-only |
| Keyboard navigation | 9 | UNTESTED | Full keyboard completion for all workflows not verified |
| Form error handling | 9 | UNTESTED | Preserve data on validation error, focus first error |
| Screen reader testing | 9 | NOT DONE | Test with NVDA/VoiceOver before v1.0 |

---

## Summary Counts

| Phase | Total Items | Complete | Partial | Not Started |
|-------|------------|----------|---------|-------------|
| Phase 0 | 5 | 5 | 0 | 0 |
| Phase 1 (UI pages) | 11 pages | 0 verified | 11 need verification | 0 (all pages exist as files) |
| Phase 2 (Backend) | ~20 items | 12 | 5 | 3 |
| Phase 3 (v1.1) | 18 | 0 | 0 | 18 |
| Phase 4 (v2.0) | 13 | 0 | 0 | 13 |
| WCAG | 9 requirements | 1 | 2 | 6 |

### Critical Path for v1.0 Release

The following Phase 2 items are **blocking** and must be completed before the staff workbench is functional end-to-end:

1. **Context Manager** (Section 4) -- all LLM features depend on this
2. **Response letter generation** (Section 8.3) -- core workflow feature
3. **Onboarding service LLM logic** (Section 12.2) -- first-run experience
4. **Tier 1 regex verification/expansion** (Section 12.7.1) -- compliance requirement
5. **Fee tracking API router** (Section 5) -- needed for request detail page
6. **Skip-to-content link** (Section 9) -- WCAG 2.2 AA hard requirement

Phase 1 pages all exist as files but need **visual verification** against the spec wireframes to confirm they match the redesign requirements. This verification should be done with a running frontend.
