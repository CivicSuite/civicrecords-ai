# CivicRecords AI — Canonical Spec Reconciliation

**Date:** 2026-04-13
**Canonical Spec:** docs/UNIFIED-SPEC.md (Unified Design Specification v2.0, April 12, 2026)
**Codebase Audited:** backend/ and frontend/ directories

## Summary

| Status | Count |
|--------|-------|
| Built | 8 |
| Partial | 8 |
| Missing | 0 |

## Detailed Findings

### 1. Roles

| Spec Requires | Code Reality | Status |
|---------------|-------------|--------|
| admin | `ADMIN = "admin"` | Built |
| staff | `STAFF = "staff"` | Built |
| reviewer | `REVIEWER = "reviewer"` | Built |
| read_only | `READ_ONLY = "read_only"` | Built |
| liaison | `LIAISON = "liaison"` | Built (2026-04-13) |
| public | `PUBLIC = "public"` | Built (2026-04-13) |

**Status: Built** (completed 2026-04-13)
**Files:** `backend/app/models/user.py`, `backend/app/auth/dependencies.py`
**Tests:** `backend/tests/test_roles.py` (6 tests)
**Notes:** All 6 roles now in UserRole enum. Role hierarchy updated: admin(6) > reviewer(5) > staff(4) > liaison(3) > read_only(2) > public(1). Liaison is department-scoped via existing `check_department_access()` — can view department resources but cannot create requests or manage exemptions (below STAFF threshold). Public role exists in enum for future Phase 3 portal auth; no public endpoints yet.

---

### 2. Staff Workbench Pages (8 required by spec)

| Spec Requires | Code Reality | Status |
|---------------|-------------|--------|
| Dashboard | `frontend/src/pages/Dashboard.tsx` | Built |
| Search | `frontend/src/pages/Search.tsx` | Built |
| Requests | `frontend/src/pages/Requests.tsx` | Built |
| RequestDetail | `frontend/src/pages/RequestDetail.tsx` | Built |
| Exemptions | `frontend/src/pages/Exemptions.tsx` | Built |
| Sources | `frontend/src/pages/DataSources.tsx` | Built |
| Ingestion | `frontend/src/pages/Ingestion.tsx` | Built |
| Users | `frontend/src/pages/Users.tsx` | Built |

**Status: Built**
**Notes:** All 8 required pages exist. Additionally, 4 bonus pages beyond spec minimum: `Onboarding.tsx`, `CityProfile.tsx`, `Discovery.tsx`, `Login.tsx`. All are routed in `App.tsx`.

---

### 3. Application Modules

| Module | Spec Requires | Code Reality | Status |
|--------|--------------|-------------|--------|
| Auth Module | `app/auth/` | `backend/app/auth/` exists with `router.py`, `dependencies.py` | Built |
| Search API | `app/search/` | `backend/app/search/router.py` exists | Built |
| Workflow API | `app/requests/` | `backend/app/requests/router.py` exists with full CRUD, timeline, messages, fees, response letters | Built |
| Audit Logger | `app/audit/` | `backend/app/audit/` exists, `write_audit_log` used throughout | Built |
| LLM Abstraction | `app/llm/` | `backend/app/llm/` exists with `context_manager.py` | Built |
| Exemption Engine | `app/exemptions/` | `backend/app/exemptions/` exists with `engine.py`, `patterns.py`, `llm_reviewer.py`, `router.py` | Partial (see notes) |
| Context Manager | Token budgeting | `backend/app/llm/context_manager.py` with `TokenBudget` dataclass and `assemble_context()` | Built |
| Notification Service | `app/notifications/` | `backend/app/notifications/` exists with `router.py` (template CRUD) and `service.py` (queue only) | Partial |
| Fee Tracking | Fee endpoints | Fee line item endpoints exist on requests router (`/{request_id}/fees`) | Partial |
| Response Generator | Response letter generation | Full implementation: template-based + Ollama LLM generation, CRUD for letters, approval workflow | Built |
| Analytics API | `app/analytics/` | `backend/app/analytics/router.py` exists | Built |
| Federation API | `app/service_accounts/` | `backend/app/service_accounts/` exists with router | Built |
| Public API | Public-facing endpoints without auth | No unauthenticated endpoints found; no public portal API | Missing |

**Status: Partial (11 Built, 2 Partial, 1 Missing)**

---

### 4. Context Manager (spec says MVP-NOW)

**Status: Built**
**File:** `backend/app/llm/context_manager.py`
**Notes:** Fully implemented with:
- `TokenBudget` dataclass with configurable allocations: system_instruction (500), request_context (500), retrieved_chunks (5000), exemption_rules (500), output_reservation (1500), safety_margin (192)
- `estimate_tokens()` function (rough 1 token ~ 4 chars)
- `assemble_context()` function that prioritizes system > request > top-k chunks > exemption rules within budget
- `ContextBlock` data structure for organized prompt assembly

---

### 5. Database Tables

| Spec Requires | Model File | Status |
|---------------|-----------|--------|
| users | `user.py` | Built |
| departments | `departments.py` | Built |
| audit_log | `audit.py` | Built |
| service_accounts | `service_account.py` | Built |
| data_sources | `document.py` | Built |
| documents | `document.py` | Built |
| document_chunks | `document.py` | Built |
| search_sessions | `search.py` | Built |
| search_queries | `search.py` | Built |
| search_results | `search.py` | Built |
| records_requests | `request.py` | Built |
| request_documents | `request.py` | Built |
| request_timeline | `request_workflow.py` | Built |
| request_messages | `request_workflow.py` | Built |
| response_letters | `request_workflow.py` | Built |
| fee_schedules | `fees.py` | Built |
| fee_line_items | `fees.py` | Built |
| notification_templates | `notifications.py` | Built |
| notification_log | `notifications.py` | Built |
| prompt_templates | `prompts.py` | Built |
| exemption_rules | `exemption.py` | Built |
| exemption_flags | `exemption.py` | Built |
| disclosure_templates | `exemption.py` | Built |
| model_registry | `document.py` | Built |
| city_profile | `city_profile.py` | Built |
| system_catalog | `connectors.py` | Built |
| connector_templates | `connectors.py` | Built |
| redaction_ledger (v1.1) | Not found | Missing (expected v1.1) |
| saved_searches (v1.1) | Not found | Missing (expected v1.1) |
| discovered_sources (v1.1) | Not found | Missing (expected v1.1) |
| discovery_runs (v1.1) | Not found | Missing (expected v1.1) |
| source_health_log (v1.1) | Not found | Missing (expected v1.1) |
| coverage_gaps (v1.1) | Not found | Missing (expected v1.1) |

**Status: Built (for MVP scope)**
**Notes:** All 27 MVP tables exist. The 6 v1.1 tables are correctly deferred. One additional table `document_cache` exists in `request.py` beyond spec requirements.

---

### 6. FEE_SCHEDULES Table

**Status: Partial**
**File:** `backend/app/models/fees.py`
**Notes:** The `FeeSchedule` model exists with proper fields (jurisdiction, fee_type, amount, description, effective_date, created_by). The `FeeLineItem` model references it via `fee_schedule_id` FK. However, there are NO dedicated CRUD endpoints for `fee_schedules`. The only fee endpoints are on the requests router (`/{request_id}/fees`) which manage `FeeLineItem` records. An admin needs CRUD endpoints to manage the fee schedule catalog itself (create/list/update/delete fee schedule entries).

---

### 7. Notification — Actual Email

**Status: Partial**
**File:** `backend/app/notifications/service.py`
**Notes:** The notification service (`queue_notification()`) renders templates and creates `NotificationLog` entries with status "queued", but does NOT actually send email. The code explicitly comments: "Actual delivery (SMTP, etc.) will be handled by a Celery task once configured." No SMTP, smtplib, aiosmtplib, or sendmail code exists anywhere in the codebase. Email delivery is stubbed out.

---

### 8. Prompt Injection Defense

**Status: Built** (completed 2026-04-13)
**File:** `backend/app/llm/context_manager.py`
**Tests:** `backend/tests/test_prompt_injection.py` (19 tests)
**Notes:** `sanitize_for_llm()` function added. Strips three categories of injection patterns before document content enters LLM prompts:
- Role override phrases ("ignore previous instructions", "you are now", "pretend you are", "disregard", "act as if", "from now on you")
- Delimiter injection (`<|system|>`, `[INST]`, `<<SYS>>`, `<system>`, `` ```system ``)
- Excessive repetition (common jailbreak technique — collapsed to single instance)

Applied to all document chunks and exemption rules in `assemble_context()`. System prompts are NOT sanitized (trusted content). Normal document text, legal language, and technical content pass through unchanged. 19 tests verify both filtering and preservation behavior.

---

### 9. Connectors

| Spec Requires (MVP-NOW) | Code Reality | Status |
|--------------------------|-------------|--------|
| File System/SMB | `backend/app/connectors/file_system.py` | Built |
| SMTP/IMAP | Not implemented | Missing |
| Manual/Export Drop | Not implemented | Missing |
| Base class | `backend/app/connectors/base.py` | Built |

**Status: Partial**
**Files:** `backend/app/connectors/base.py`, `backend/app/connectors/file_system.py`
**Notes:** Only the File System connector is implemented. The base class defines the connector interface (abstract methods for `connector_type`, `test_connection`, `list_files`, `read_file`). SMTP/IMAP and Manual/Export Drop connectors are missing. The base class mentions `smtp` as a type identifier in its docstring but no implementation exists.

---

### 9a. Exemption Dashboard Time-Period Filtering

**Status: Partial**
**File:** `backend/app/exemptions/router.py`
**Notes:** The canonical spec (Section 9, Compliance) requires the exemption auditability dashboard to show "flag acceptance/rejection rates by category, department, and time period." The `GET /exemptions/dashboard/accuracy` endpoint supports filtering by `category` (via aggregation) and `department_id` (via query parameter), but has NO time period filtering. There are no `date_from`, `date_to`, `time_period`, or date range parameters on the accuracy or export endpoints. This was identified during development and marked [SHIPPED] anyway.

---

### 9b. Exemption Rule Version Tracking

**Status: Partial**
**File:** `backend/app/models/exemption.py`
**Notes:** The canonical spec (Section 9, Compliance) requires "documentation of exemption rule sources with version tracking." The `ExemptionRule` model has no `version` field — changes are tracked only via audit log entries (which record old and new values when a rule is updated). The `version` field exists on `DisclosureTemplate` but NOT on `ExemptionRule`. True version tracking would require a version column that increments on each rule definition change, enabling rollback and historical comparison. Currently only audit log provides change history, with no structured versioning.

---

### 9c. scope_assessment Field

**Status: Partial**
**File:** `backend/app/models/request.py`
**Notes:** The canonical spec marks `scope_assessment` as [MVP-NOW] on `records_requests` with values narrow/moderate/broad. The field EXISTS on the `RecordsRequest` model. However, API endpoint coverage for setting and reading this field has not been verified — the `RequestCreate` and `RequestUpdate` schemas may or may not expose it. Field exists in database; endpoint access status unknown.

---

### 10. Tier 1 Redaction

| PII Type (Spec Requires) | Code Reality | Status |
|---------------------------|-------------|--------|
| SSN | `SSN_PATTERN` in `UNIVERSAL_PATTERNS` | Built |
| Credit Cards | `CREDIT_CARD_PATTERN` with Luhn validation | Built |
| Phone | `PHONE_PATTERN` in `UNIVERSAL_PATTERNS` | Built |
| Email | `EMAIL_PATTERN` in `UNIVERSAL_PATTERNS` | Built |
| Bank Accounts | `BANK_ROUTING_PATTERN` + `BANK_ACCOUNT_PATTERN` | Built |
| Driver's Licenses | `DRIVERS_LICENSE_PATTERNS` (state-specific, keyed by state code) | Built |

**Status: Built**
**File:** `backend/app/exemptions/patterns.py`
**Notes:** All 6 required PII types are implemented. Credit card detection includes Luhn algorithm validation for reduced false positives. Driver's license patterns are state-specific (looked up by `state_code` parameter). The `scan_text()` function applies universal patterns plus optional state-specific DL patterns.

---

### 11. WCAG Compliance

**Status: Partial**

| Requirement | Found | Location |
|-------------|-------|----------|
| Skip-to-content link | Yes — "Skip to main content" | `app-shell.tsx` |
| Focus-visible styles | Yes — `focus-visible` classes found in 8 files | UI components, sidebar-nav, app-shell |
| Aria labels | Yes — `aria-label="Main navigation"`, `aria-current`, `role="navigation"`, `role="main"` | `sidebar-nav.tsx`, `app-shell.tsx` |
| 44px touch targets | Not verified | No explicit `min-h-[44px]` or `min-w-[44px]` classes found |

**Notes:** Core WCAG elements are present (skip link, focus-visible, aria-labels, semantic roles). Touch target sizing was not explicitly enforced via CSS classes, though button components may achieve this through padding. A full WCAG audit was not performed.

---

### 12. Content Design Rules

**Status: Built**

| Check | Result |
|-------|--------|
| "responsive documents" (wrong term) | Not found in frontend code |
| "records found for release" (correct term) | Not found either, but also not using the wrong term |
| Error/empty states with what/how/help | `EmptyState` component exists with icon, title, description, and optional action button pattern |

**File:** `frontend/src/components/empty-state.tsx`
**Notes:** The codebase does not use the problematic "responsive documents" phrasing. The `EmptyState` component provides a structured pattern (icon + title + description + action) that supports the what/how/help error state pattern from the spec.

---

### 13. Frontend Navigation

**Status: Built**
**Files:** `frontend/src/components/sidebar-nav.tsx`, `frontend/src/components/app-shell.tsx`
**Notes:** The frontend uses sidebar navigation via `SidebarNav` component rendered inside `AppShell`. The sidebar includes:
- Grouped navigation sections: Workflow items, Setup items, Admin items
- `NavLink` component with active state (`aria-current="page"`)
- Semantic `<nav>` element with `role="navigation"` and `aria-label`
- Sidebar width controlled via CSS custom property `--sidebar-width`

---

## Critical Gaps (items that block canonical spec compliance)

1. **Prompt Injection Defense (Section 8)** — No sanitization of document content before LLM context injection. Security risk for any deployment processing untrusted documents.

2. **Public API (Section 3)** — No unauthenticated endpoints for citizen-facing portal. Blocks the public records request submission workflow entirely.

3. **Notification Email Delivery (Section 7)** — Notification service is template CRUD + queue logging only. No actual email sending. Blocks all automated stakeholder notifications.

4. **Missing Roles: liaison, public (Section 1)** — Without `public` role, citizen portal auth is impossible. Without `liaison`, department contact workflow is incomplete.

5. **SMTP/IMAP Connector (Section 9)** — Email-based document ingestion not implemented. Required for MVP-NOW per spec.

## Reconciliation Backlog (prioritized)

1. ~~**P0 — Prompt Injection Defense:** COMPLETED 2026-04-13. `sanitize_for_llm()` in `context_manager.py`, 19 tests.~~

2. ~~**P0 — Add `liaison` and `public` roles:** COMPLETED 2026-04-13. Both roles in enum, hierarchy updated, 6 tests.~~

3. **P0 — Public API endpoints:** Create unauthenticated API routes for citizen records request submission and status lookup.

4. **P1 — Email delivery (SMTP):** Implement a Celery task in `app/notifications/` that reads queued `NotificationLog` entries and sends via SMTP (aiosmtplib or smtplib). Add SMTP configuration to settings.

5. **P1 — Fee Schedules CRUD:** Add admin endpoints for managing `fee_schedules` records (list, create, update, delete). Currently only `fee_line_items` have endpoints.

6. **P1 — SMTP/IMAP Connector:** Implement `app/connectors/smtp_imap.py` for email-based document ingestion.

7. **P1 — Exemption dashboard time-period filtering:** Add `date_from` and `date_to` query parameters to `GET /exemptions/dashboard/accuracy` and `GET /exemptions/dashboard/export` endpoints. Canonical spec requires filtering by category, department, AND time period.

8. **P1 — Exemption rule version tracking:** Add `version` integer column to `ExemptionRule` model. Increment on each rule_definition change. Enables rollback and historical comparison beyond audit log.

9. **P1 — scope_assessment endpoint coverage:** Verify `scope_assessment` field is exposed in `RequestCreate` and `RequestUpdate` schemas. If not, add it. Field exists in DB model but API access unconfirmed.

10. **P2 — Manual/Export Drop Connector:** Implement `app/connectors/manual_drop.py` for manual file upload ingestion pathway.

11. **P2 — WCAG touch targets:** Audit and enforce minimum 44px touch targets on interactive elements.
