# CivicCore Extraction Inventory

- **Branch:** `civiccore-extraction-inventory`
- **Authored:** 2026-04-23
- **Author:** Claude (Day 3 of CivicSuite Phase 1 prep)
- **Status:** Draft for Scott Converse review
- **Spec source of truth:** `github.com/CivicSuite/civicsuite` → `specs/02_CivicCore.md`, sections **§8 (moves table)**, **§9 (stays table)**, **§10 (database schema ownership)**
- **Branch base:** `origin/master` at `3cf7719` (clean push baseline; deliberately *not* branched from local `master` at `073b58e`, which contains Scott's unfinished resident-tracking spec)

---

## Purpose

This document is the Phase-1 checklist for the CivicCore extraction. It walks every Python module under `backend/app/`, every Alembic revision under `backend/alembic/versions/`, every relevant frontend file under `frontend/src/`, and every seed/script under `backend/data/` and `backend/scripts/`, then classifies each item against the moves/stays rules in CivicCore Extraction Spec v0.1 §8–§10.

Every entry below is an auditable target for the Phase-1 work: a contributor executing the extraction will translate this inventory into concrete `git mv` operations plus import-rewrite shims (per spec §13). Phase 0 (repo skeletons) is already shipped at `github.com/CivicSuite/{civicsuite, civiccore}`. Phase 1 lifts the User / Role / Department / audit_log subsystem into civiccore and replaces the current in-tree models with shim re-exports. Subsequent phases extract LLM, ingestion, search, connectors, notifications, onboarding, admin shell.

This is **not** an approval to start moving code. It is a map of the territory and a list of decisions Scott needs to make before Phase 1 can begin. Section F enumerates those decisions.

---

## Methodology

The inventory was produced as a research-only walk against `origin/master` (`3cf7719`). No code was modified.

1. **Filesystem walk.** Enumerated every directory and `.py`/`.yaml`/`.json`/`.tsx` file under `backend/app/`, `backend/alembic/versions/`, `backend/tests/`, `backend/scripts/`, `backend/data/`, `frontend/src/`, `scripts/`, and `data/`.
2. **Symbol inspection.** Read the top-of-file docstring and import block of every backend subsystem to confirm its purpose.
3. **Cross-reference grep.** For each subsystem, searched the codebase for `from app.<modulename>` imports to count blast radius. (Aggregate result: **320 import-lines across 132 files** referencing `app.<module>` paths — the shim layer must cover all of them.)
4. **Spec mapping.** Each module was classified MOVES, STAYS, or INVESTIGATE per spec §8 / §9.
5. **DB ownership cross-check.** Cross-referenced models against §10 (CivicCore-owned tables vs module-owned tables). Where a model file maps to a table named in §10.1 it MOVES; §10.2 it STAYS.
6. **Test triage.** Test modules were attached to their subject under test; tests for shared subsystems are listed for copy/move into civiccore per spec §15.

The INVESTIGATE bucket exists because §8 and §9 do not name every directory currently in the tree. For those, this document records what the module does, why it isn't unambiguously named in either table, and a recommended classification — explicitly flagged as a recommendation, not a decision.

**Corrections to spec naming.** The spec §8 names some paths that don't exist verbatim in this repo. Where there's a mismatch the actual current path is listed:

| Spec §8 path | Actual current path | Note |
|---|---|---|
| `backend/app/ingest/*` | `backend/app/ingestion/*` | Singular vs. plural; same subsystem. |
| `backend/app/tasks/ingest_*.py` | `backend/app/ingestion/tasks.py` + `sync_runner.py` + `scheduler.py` | Tasks live inside `ingestion/`, not in a separate `tasks/` package. |
| `backend/app/connectors/protocol.py` | (does not exist; `backend/app/connectors/base.py` defines the ABC) | One file, not two. |
| `backend/app/llm/ollama_client.py` + `model_registry.py` + `context_budget.py` | `backend/app/llm/client.py` + `backend/app/llm/context_manager.py` + `backend/app/models/document.py::ModelRegistry` | Model registry is a SQLAlchemy model under `models/document.py`, not a stand-alone `llm/model_registry.py`. Verify before extraction. |
| `data/seeds/exemption_rules/*.yaml` | `backend/scripts/seed_rules.py::STATE_RULES_REGISTRY` (Python literal, no YAML files) | Seed data is in-source Python, not YAML files. |
| `data/seeds/systems_catalog.yaml` | `backend/data/systems_catalog.json` | JSON not YAML; under `backend/data/`. |
| `scripts/verify_no_egress.sh` + `verify_no_telemetry.py` + `tests/sovereignty/*` | `scripts/verify-sovereignty.sh` + `scripts/verify-sovereignty.ps1` (no `tests/sovereignty/` dir) | Single combined script, both shell + PowerShell. |
| `frontend/src/layouts/AdminShell.tsx` | `frontend/src/components/app-shell.tsx` | Naming differs; same role. No `layouts/` directory. |
| `frontend/src/design-tokens/*` | (does not exist; tokens are inline in `frontend/src/components/ui/*` shadcn-ui style) | No design-tokens package today. |

These deltas are flagged so the Phase-1 executor doesn't `git mv` files that aren't there.

---

## Summary counts

| Bucket | Subsystems | Backend `.py` files (approx) | Notes |
|---|---|---|---|
| **MOVES → civiccore** | 13 | ~75 | All §8 subsystems plus the shared models, schemas, and tests. |
| **STAYS in civicrecords-ai** | 9 | ~12 | Records-specific lifecycle, fees, response letters, public portal, dashboards. |
| **INVESTIGATE — needs Scott's call** | 8 | ~15 | Modules not named verbatim in §8 or §9. See Section C. |

(The `.py` file count excludes `__pycache__`, test files, and frontend code, and treats `__init__.py` as 1 per package.)

---

## Section A — MOVES → civiccore

Per spec §8. Each entry below is auditable: open `backend/app/<path>` in the current tree, confirm the row matches, then plan the `git mv` + shim.

### A.1 Auth / RBAC

- **Spec target:** `civiccore/auth/*`, `civiccore/models/user.py`, `civiccore/models/role.py`
- **Current paths in civicrecords-ai:**
  - `backend/app/auth/__init__.py`, `backend.py`, `dependencies.py`, `manager.py`, `router.py`
  - `backend/app/models/user.py` (defines `Base`, `User`, `UserRole` — note `Base` lives here and is imported by every other model)
  - `backend/app/schemas/user.py`
- **Cross-references found:** `app.auth.dependencies` is imported by every router (admin, analytics, audit, catalog, city_profile, datasources, departments, documents, exemptions, notifications, onboarding, public, requests, search, service_accounts) — at least 16 router files. `app.models.user.User`/`UserRole` is imported by ~25 files. **This is the highest-fanout subsystem in the codebase.**
- **Tests to copy:** `backend/tests/test_auth.py`, `test_roles.py`, `test_user_management.py`, `test_department_scoping.py` (shared dependency on RBAC).
- **Phase-1 inclusion:** YES (Phase 1 scope per spec §12 row 1).
- **Special note:** `Base = declarative_base()` is defined in `models/user.py` and imported by every other model file. The Phase-1 move must keep `Base` re-exported at `app.models.user.Base` via shim, otherwise every other model breaks.

### A.2 Audit chain

- **Spec target:** `civiccore/audit/*`, `civiccore/models/audit_log.py`
- **Current paths in civicrecords-ai:**
  - `backend/app/audit/__init__.py`, `logger.py`, `middleware.py`, `router.py`
  - `backend/app/models/audit.py` (`AuditLog`)
  - `backend/app/schemas/audit.py`
- **Cross-references found:** `app.audit.logger.write_audit_log` is called from at least 9 routers (admin, auth, city_profile, datasources, departments, exemptions, notifications, requests, service_accounts). `app.audit.middleware.AuditMiddleware` is mounted in `main.py`.
- **Tests to copy:** `backend/tests/test_audit.py`, `test_info_leak_hardening.py` (audit-leakage hardening).
- **Phase-1 inclusion:** YES (Phase 1 scope per spec §12 row 1).

### A.3 LLM abstraction

- **Spec target:** `civiccore/llm/*`
- **Current paths in civicrecords-ai:**
  - `backend/app/llm/__init__.py`, `client.py`, `context_manager.py`
  - `backend/app/models/document.py::ModelRegistry` (the model_registry table) — see Section C.7 for whether this co-moves
  - `backend/app/schemas/model_registry.py`
- **Cross-references found:** `app.llm.client` is imported by `ingestion/llm_extractor.py`, `exemptions/llm_reviewer.py`, `search/synthesizer.py`. ModelRegistry is referenced by the admin router and by `llm/context_manager.py`.
- **Tests to copy:** `backend/tests/test_llm_client.py`, `test_model_registry.py`.
- **Phase-1 inclusion:** NO — Phase 2 per spec §12.
- **Special note:** Spec §8 lists `llm/model_registry.py` and `llm/context_budget.py` as separate files. In this repo, `context_manager.py` performs the budget logic and the model registry is a SQLAlchemy model in `models/document.py`. The Phase-2 executor needs to either split `models/document.py` (separating ModelRegistry from Document/DocumentChunk) or co-move ModelRegistry as part of the LLM phase.

### A.4 Document ingestion

- **Spec target:** `civiccore/ingest/*`
- **Current paths in civicrecords-ai:**
  - `backend/app/ingestion/*` (all 8 top-level files: `__init__.py`, `chunker.py`, `cron_utils.py`, `embedder.py`, `llm_extractor.py`, `pipeline.py`, `scheduler.py`, `sync_runner.py`, `tasks.py`)
  - `backend/app/ingestion/parsers/*` (8 parser files: base, csv, docx, email, html, pdf, text, xlsx)
- **Cross-references found:** `app.ingestion.pipeline.run_pipeline` is called from `datasources/router.py` and `connectors/*`. `app.ingestion.sync_runner` is called from `scheduler.py`.
- **Tests to copy:** `test_chunker.py`, `test_embedder.py`, `test_ingestion_retry.py`, `test_ingestion_tasks.py`, `test_parsers.py`, `test_pipeline.py`, `test_pipeline_idempotency.py`, `test_scheduler.py`, `test_sync_runner_*` (4 files), `test_sync_failures.py`, `test_sync_failures_router.py`.
- **Phase-1 inclusion:** NO — Phase 2 per spec §12.

### A.5 Hybrid search

- **Spec target:** `civiccore/search/*`, `civiccore/models/document*.py`
- **Current paths in civicrecords-ai:**
  - `backend/app/search/__init__.py`, `engine.py`, `router.py`, `synthesizer.py`
  - `backend/app/models/document.py` (`Document`, `DocumentChunk`, `DataSource`, `IngestionStatus`, `ModelRegistry`, `SourceType` — all in one file)
  - `backend/app/models/search.py` (`SearchQuery`, `SearchResult`, `SearchSession`)
  - `backend/app/schemas/document.py`, `backend/app/schemas/search.py`
- **Cross-references found:** `app.search.engine` is called from `search/router.py` and `requests/router.py` (records workflow uses search to find candidate docs). This is a **module → core dependency**: the records workflow consumes the core search API, which is exactly the pattern §8 anticipates.
- **Tests to copy:** `test_search_api.py`, `test_search_engine.py`, `test_search_features.py`, `test_documents.py`.
- **Phase-1 inclusion:** NO — Phase 2 per spec §12.

### A.6 Connector framework

- **Spec target:** `civiccore/connectors/*`
- **Current paths in civicrecords-ai:**
  - `backend/app/connectors/__init__.py`, `base.py`, `file_system.py`, `imap_email.py`, `manual_drop.py`, `odbc.py`, `rest_api.py`, `retry.py`
  - `backend/app/models/connectors.py` (`SystemCatalog`, `ConnectorTemplate`)
  - `backend/app/schemas/connectors/__init__.py`, `odbc.py`, `rest_api.py`
- **Cross-references found:** Connectors are loaded by `datasources/router.py` and `ingestion/sync_runner.py`. `connectors/base.py::BaseConnector` is the ABC the spec calls `Connector`.
- **Tests to copy:** `test_base_connector.py`, `test_circuit_breaker.py`, `test_connector_schemas.py`, `test_connector_taxonomy.py`, `test_imap_connector.py`, `test_manual_drop.py`, `test_odbc_connector.py`, `test_rest_connector.py`, `test_retry.py`, `test_datasource_connection.py`.
- **Phase-1 inclusion:** NO — Phase 3 per spec §12.
- **Special note:** Spec §9 says "records-specific connectors (Laserfiche records adapter, etc.) stay module-side." None of the current `backend/app/connectors/*` files are records-specific — they are generic protocol implementations (SMB/file-system, IMAP, ODBC, REST, manual-drop). So **all of them move**. A future Laserfiche-specific connector would stay in records.

### A.7 Notifications

- **Spec target:** `civiccore/notifications/*`
- **Current paths in civicrecords-ai:**
  - `backend/app/notifications/__init__.py`, `router.py`, `service.py`, `smtp_delivery.py`, `sync_notifications.py`
  - `backend/app/models/notifications.py` (`NotificationTemplate`, `NotificationLog`)
  - `backend/app/schemas/notifications.py`
- **Cross-references found:** `app.notifications.service.queue_notification` is called from `requests/router.py`, `requests/deadline_check.py`, `notifications/sync_notifications.py`.
- **Tests to copy:** `test_notifications.py`, `test_notification_dispatch.py`, `test_smtp_delivery.py`, `test_compliance_templates.py`, `test_sync_notifications.py`, `test_messages.py`, `test_deadline_notifications.py` (records-specific deadline triggers may need shim).
- **Phase-1 inclusion:** NO — Phase 3 per spec §12.
- **Special note:** `sync_notifications.py` is connector-failure notification logic (circuit-breaker + recovery digests). It moves with notifications since both the connector framework and the notification engine are core.

### A.8 Onboarding + city profile

- **Spec target:** `civiccore/onboarding/*`, `civiccore-ui/onboarding/*`
- **Current paths in civicrecords-ai:**
  - `backend/app/onboarding/__init__.py`, `router.py`
  - `backend/app/city_profile/__init__.py`, `router.py`
  - `backend/app/models/city_profile.py` (`CityProfile`)
  - `backend/app/schemas/city_profile.py`
  - `frontend/src/pages/Onboarding.tsx`, `frontend/src/pages/CityProfile.tsx`
- **Cross-references found:** `CityProfile` is read by `requests/router.py` (deadline calculation depends on jurisdiction defaults) and `exemptions/router.py` (exemption rules vary by state). Module → core consumption, expected.
- **Tests to copy:** `test_city_profile.py`, `test_onboarding_interview.py`, `test_bootstrap_integration.py`.
- **Phase-1 inclusion:** NO — Phase 4 per spec §12.

### A.9 Municipal systems catalog

- **Spec target:** `civiccore/catalog/*`
- **Current paths in civicrecords-ai:**
  - `backend/app/catalog/__init__.py`, `loader.py`, `router.py`
  - `backend/data/systems_catalog.json` (the seed file — see "Corrections to spec naming" above)
  - `backend/app/models/connectors.py::SystemCatalog`, `ConnectorTemplate` (catalog tables — though physically housed in `models/connectors.py`)
- **Cross-references found:** Loader is called from `app.main` lifespan; router serves `/catalog` to the onboarding wizard.
- **Tests to copy:** `test_catalog.py`.
- **Phase-1 inclusion:** NO — Phase 4 per spec §12.

### A.10 Exemption engine (50-state)

- **Spec target:** `civiccore/exemptions/*`
- **Current paths in civicrecords-ai:**
  - `backend/app/exemptions/__init__.py`, `engine.py`, `llm_reviewer.py`, `patterns.py`, `router.py`
  - `backend/app/models/exemption.py` (`ExemptionRule`, `ExemptionFlag`, `DisclosureTemplate`, `FlagStatus`, `RuleType`)
  - `backend/app/schemas/exemption.py`
  - `backend/scripts/seed_rules.py` (contains `STATE_RULES_REGISTRY` — 175 rules across 50 states + DC, plus `UNIVERSAL_PII_RULES`)
  - `backend/scripts/seed_templates.py` (5 disclosure templates)
  - `backend/compliance_templates/*.md` (template content; not yet enumerated — verify exists before Phase 3)
- **Cross-references found:** `exemptions.engine.scan_request_documents` is called from `requests/router.py` workflow; `exemptions.router` serves both the engine API and the dashboard.
- **Tests to copy:** `test_exemptions.py`, `test_exemption_features.py`, `test_exemption_rules_seed.py`.
- **Phase-1 inclusion:** NO — Phase 3 per spec §12.
- **Special note:** Spec §9 says "exemption dashboard stays" but `exemptions/router.py` currently mixes engine endpoints (rule CRUD, flag scan) with dashboard endpoints (accuracy metrics). The Phase-3 executor must split this router: engine endpoints move to civiccore, dashboard endpoints stay in records. `test_exemption_dashboard.py` stays. See Section C.5.

### A.11 Sovereignty verification

- **Spec target:** `civiccore/verification/*`, `scripts/verify/*`
- **Current paths in civicrecords-ai:**
  - `scripts/verify-sovereignty.sh`
  - `scripts/verify-sovereignty.ps1`
  - `scripts/detect_hardware.sh`, `detect_hardware.ps1` (hardware-tier detection — pairs with sovereignty verification)
  - `backend/scripts/verify_at_rest.py` (at-rest encryption verifier, ENG-001)
- **Cross-references found:** Standalone scripts; not imported.
- **Tests to copy:** `test_at_rest_encryption.py` covers the encryption primitives.
- **Phase-1 inclusion:** NO — Phase 4 per spec §12.
- **Special note:** Spec calls out separate `verify_no_egress.sh` and `verify_no_telemetry.py`; current repo has them combined into `verify-sovereignty.sh`/`.ps1`. Confirm with Scott whether to split during extraction or keep combined. **Recommendation: keep combined** — the consolidated form has been the verified shape since v1.2.0.

### A.12 Admin shell (UI)

- **Spec target:** `civiccore-ui/shell/*`, `civiccore-ui/tokens/*`
- **Current paths in civicrecords-ai:**
  - `frontend/src/components/app-shell.tsx` (the AdminShell equivalent)
  - `frontend/src/components/app-shell.test.tsx`
  - `frontend/src/components/sidebar-nav.tsx`, `page-header.tsx`, `data-table.tsx`, `empty-state.tsx`, `loading-region.tsx`, `stat-card.tsx`, `status-badge.tsx`
  - `frontend/src/components/ui/*` — 13 shadcn-ui primitives (`badge`, `button`, `card`, `checkbox`, `dialog`, `dropdown-menu`, `input`, `select`, `separator`, `skeleton`, `table`, `tabs`, `tooltip`)
  - `frontend/src/lib/utils.ts` (the shadcn `cn()` utility)
- **Cross-references found:** `app-shell` is imported by `App.tsx` and wraps every records page. `sidebar-nav` is imported by `app-shell`. Every records page imports from `components/ui/*`.
- **Tests to copy:** `app-shell.test.tsx` and the `*.test.tsx` for shared components.
- **Phase-1 inclusion:** NO — Phase 4 per spec §12.
- **Special note:** No standalone `frontend/src/design-tokens/*` directory exists. Tokens are baked into the shadcn-ui components. Confirm with Scott: extract tokens-as-CSS-vars during Phase 4, or leave them inline in the shadcn primitives that move with the shell. **Recommendation: leave tokens inline** for v0.1; the design-token abstraction can land in CivicCore v0.2 once a second module's UI demands it.

### A.13 Shared tables / migrations

- **Spec target:** `civiccore/migrations/*`
- **Current paths in civicrecords-ai:**
  - `backend/alembic/env.py` and `script.mako` / `script.py.mako`
  - `backend/alembic/versions/001_initial.py` (creates users + roles)
  - `backend/alembic/versions/002_documents.py` (creates documents + chunks)
  - `backend/alembic/versions/003_model_registry.py` (creates model_registry)
  - `backend/alembic/versions/004_search.py` (creates search tables)
  - `backend/alembic/versions/006_exemptions.py` (creates exemption_rules + flags)
  - `backend/alembic/versions/011_fix_schema_drift.py` (cross-cutting; analyze before split)
  - `backend/alembic/versions/012_add_liaison_public_roles.py` (extends UserRole enum)
  - `backend/alembic/versions/013_add_connector_types.py` (connector taxonomy)
  - `backend/alembic/versions/014_p6a_idempotency.py` (ingestion idempotency)
  - `backend/alembic/versions/015_p6b_scheduler.py` (ingestion scheduler tables)
  - `backend/alembic/versions/016_p7_sync_failures.py` (connector failure tracking)
  - `backend/alembic/versions/017_rename_connector_enum_values.py`
  - `backend/alembic/versions/018_city_profile_state_nullable.py`
  - `backend/alembic/versions/019_encrypt_connection_config.py` (T6/ENG-001 — at-rest encryption for connector creds)
  - `backend/alembic/versions/787207afc66a_phase2_extensions_12_new_tables_and_.py` (Phase-2 multi-table — must be split)
- **Cross-references found:** Migrations are not imported; they are run by alembic.
- **Tests to copy:** `test_migration_014.py`, `test_migration_015.py`.
- **Phase-1 inclusion:** Partial — Phase 1 moves only the User/Role/Department/audit_log migrations (`001_initial.py` plus the audit-log half of any cross-cutting migration). Other shared-table migrations move in their respective phases. See Section D for the Phase-1 critical path.
- **Special note:** The Phase-2 extensions migration (`787207afc66a_phase2_extensions_12_new_tables_and_.py`) creates 12 tables in one revision spanning records-specific (fees, request_workflow, prompts) and shared (city_profile, departments, notifications). **This is the hardest single migration to split.** Recommendation: do not attempt to split it in-place; instead, in Phase 1 mark it as "stays in records" and have CivicCore baseline its history at 020+. The shared tables it creates already exist in any deployed DB; CivicCore's models reference them without a migration of its own. This requires an explicit ADR.

---

## Section B — STAYS in civicrecords-ai

Per spec §9. Each entry below confirms the listed item is records-specific and notes any cross-references that will need a shim.

### B.1 Request lifecycle

- **Path:** `backend/app/requests/__init__.py`, `router.py`, `deadline_check.py`
- **Why stays:** Records-module-specific FOIA/ORR workflow (state machine, timeline, deadline triggers). No other module has a request of this shape.
- **Cross-references that need shims:** Imports `app.audit.logger`, `app.auth.dependencies`, `app.exemptions.engine`, `app.notifications.service`, `app.search.engine`, `app.llm.client` — every one of these imports goes through the shim layer during Phases 1–4 and rewrites to `civiccore.*` in Phase 5.

### B.2 Letter generation

- **Spec §9 path:** `backend/app/letters/*` — **does not exist as a standalone subsystem in this repo.** Response-letter logic lives inside `backend/app/models/request_workflow.py::ResponseLetter` and is rendered by code in `requests/router.py`.
- **Why stays:** Records-specific output format (FOIA response letters with redaction summaries, fee tables, exemption disclosures).
- **Recommendation:** When Phase 1+ separates module from core, factor letter rendering into `backend/app/letters/render.py` to match the spec layout. Do not ship the spec promising a `backend/app/letters/*` directory that doesn't exist. Flag for Scott (Section F.5).

### B.3 Fee schedules

- **Spec §9 path:** `backend/app/fees/*` — **does not exist as a standalone subsystem in this repo.** Fee data lives in `backend/app/models/fees.py` (`FeeSchedule`, `FeeLineItem`, `FeeWaiver`) and `backend/app/schemas/fee_schedule.py`. Fee-CRUD endpoints are in `backend/app/admin/router.py` (fee-schedule management is part of the admin surface).
- **Why stays:** ORR/FOIA-specific fee rules. CivicPermit/CivicCode would need different fee schemas.
- **Cross-references:** `app.models.fees` is imported by `admin/router.py` and `requests/router.py`.
- **Recommendation:** During Phase 5, extract fee endpoints out of `admin/router.py` into a new `backend/app/fees/router.py` so the spec/code align. Flag for Scott (Section F.5).

### B.4 Exemption dashboard

- **Path:** Endpoints currently inside `backend/app/exemptions/router.py` (mixed with engine endpoints).
- **Why stays:** The dashboard surfaces records-specific accuracy metrics (false-positive rates, reviewer agreement, state-by-state hit rates for this city's actual records workflow). The 50-state engine + rules MOVE; the dashboard reads them through the public engine API and renders module-specific aggregations.
- **Cross-references:** `test_exemption_dashboard.py` stays in records.
- **Recommendation:** Phase 3 must split `exemptions/router.py` into `civiccore/exemptions/router.py` (rule CRUD, flag scan) and `backend/app/exemptions/dashboard.py` (records-specific dashboard endpoints). See Section C.5.

### B.5 Public request portal

- **Path:** `backend/app/public/__init__.py`, `router.py` (already shipped in T5D — see file's own docstring).
- **Why stays:** Records-specific resident UX. Spec §9 says "shared resident portal shell lives in CivicCore; portal content is module-specific" — the current `public/router.py` is portal *content*, not the shell.
- **Cross-references:** Mounted under `/public` only when `settings.portal_mode == "public"`. Imports `app.auth.dependencies`, `app.audit.logger`, `app.models.request`, `app.models.user` (PUBLIC role).
- **Frontend:** `frontend/src/pages/PublicLanding.tsx`, `PublicRegister.tsx`, `PublicSubmit.tsx` — all stay.

### B.6 Records-specific UI pages

- **Paths:** `frontend/src/pages/AuditLog.tsx`, `Dashboard.tsx`, `DataSources.tsx`, `Discovery.tsx`, `Exemptions.tsx`, `Ingestion.tsx`, `Login.tsx`, `Onboarding.tsx`, `RequestDetail.tsx`, `Requests.tsx`, `Search.tsx`, `Settings.tsx`, `Users.tsx`, `CityProfile.tsx`, `PublicLanding.tsx`, `PublicRegister.tsx`, `PublicSubmit.tsx` — all stay.
- **Special case:** `Login.tsx`, `Users.tsx`, `Onboarding.tsx`, `CityProfile.tsx` render core subsystems (auth, RBAC, onboarding, city profile). They consume the AdminShell + tokens from civiccore-ui but the pages themselves are module code per §9 row 6.
- **Hooks:** `frontend/src/hooks/useSyncNow.ts` is records-specific (datasources sync trigger) — stays.
- **Generated:** `frontend/src/generated/api.ts` is the OpenAPI-generated client — stays in records (regenerated against records' own OpenAPI spec).

### B.7 Records-schema migrations

- **Paths in `backend/alembic/versions/`:**
  - `005_requests.py` — creates `records_requests` and related
  - `008_extend_request_status_enum.py`
  - `009_fee_waivers.py`
  - `010_remove_sent_status.py`
  - The records-specific tables created by `787207afc66a_phase2_extensions...py` (see A.13 special note)
- **Why stays:** Tables in `§10.2` (records_requests, records_request_events, response_letters, fee_schedules, fee_line_items, waivers).

### B.8 Module-specific prompts

- **Spec §9 path:** `data/prompts/*.yaml` — **does not exist in this repo.** Prompt strings are inlined in `app.exemptions.llm_reviewer`, `app.search.synthesizer`, `app.ingestion.llm_extractor`, plus stored in DB via `app.models.prompts.PromptTemplate`.
- **Why stays:** Records-specific prompt copy (FOIA exemption review prompts, response-letter drafting prompts).
- **Recommendation:** The `PromptTemplate` *table* is shared infrastructure (any module would want a template store). The *records-specific seed rows* stay in records. So `models/prompts.py` itself is INVESTIGATE — see C.6. The prompt copy stays regardless.

### B.9 Records-specific connectors

- **Path:** None today — there is no Laserfiche/records-specific connector in the current tree. All current connectors (file_system, imap_email, manual_drop, odbc, rest_api) are generic and MOVE per A.6.
- **Why stays:** Future records-specific adapters (Laserfiche records adapter, NextRequest export, etc.) would stay module-side.

### B.10 Records behavior tests

- **Tests that stay:**
  - `test_requests.py`, `test_response_letter.py`, `test_timeline.py`, `test_deadline_notifications.py`
  - `test_fees.py`, `test_fee_lifecycle.py`, `test_fee_schedules.py`
  - `test_exemption_dashboard.py`
  - `test_portal_mode.py`, `test_admin.py` (admin endpoints that are records-specific)
  - `test_analytics.py` (operational metrics for the records workflow)
  - `test_datasources.py`, `test_datasources_router_tc.py` (datasource UX, not connector mechanics)
  - `test_compliance_templates.py` (records compliance template seeding)
  - `test_first_boot_seeding.py` (seeds records-specific data — see C.4)
  - `test_prompt_injection.py` (records LLM prompt hardening)
  - `test_tier2a_hardening.py` (records workflow hardening)
  - `test_health.py`, `test_config_validation.py` (records-app boot tests)
  - `test_coverage_gaps.py`, `test_messages.py` (records workflow messages)
- **Tests that move with their subject:** see each Section A entry.

---

## Section C — INVESTIGATE — needs Scott's call

Each entry below is a directory or file that is **not unambiguously named in spec §8 or §9**. Each gets a recommendation, but the recommendation is not a decision.

### C.1 `backend/app/admin/`

- **What it does:** Admin-shell HTTP endpoints — system status (`/admin/status`), fee-schedule CRUD (`POST /admin/fees`), model-registry CRUD (`POST /admin/models`), user-management endpoints. Mixes core admin (model registry) with records admin (fee schedules).
- **Why ambiguous:** Spec §8 row "Admin shell (UI)" covers the *frontend* `AdminShell.tsx`. The *backend* `/admin/*` endpoints are not named in either §8 or §9.
- **Recommendation:** **SPLIT.** Move model-registry endpoints + system-status endpoint to `civiccore/admin/router.py`. Keep fee-schedule + records-specific user-management views in `backend/app/admin/router.py`. The split should happen during Phase 4 (admin shell phase) at the same time the frontend AdminShell moves.

### C.2 `backend/app/analytics/`

- **What it does:** Operational metrics for the records workflow — counts of `RecordsRequest` rows by status, by department, by month. Department-scoped (admin sees all, others see own dept).
- **Why ambiguous:** Spec §8 has no "analytics" row. §9 doesn't list it either.
- **Recommendation:** **STAYS in records.** It only queries `RecordsRequest` and `Department`; it has no general-purpose metric framework. A future module would need its own analytics router. If a generic "records-by-status pivot table" is needed in CivicCore later (v0.2), it can be extracted then.

### C.3 `backend/app/datasources/`

- **What it does:** Admin UX for connector instance management (`/datasources` CRUD, `/datasources/{id}/sync`, `/datasources/{id}/sync-failures`). Hosts the `BaseConnector` integration plumbing for HTTP — uses `app.connectors.*` to actually run connectors, but presents the admin-facing API.
- **Why ambiguous:** Spec §8 lists "Connector framework" as moving (`backend/app/connectors/*`). The `datasources/` router is *consumer of* the connector framework, not the framework itself. Splitting hairs: is the admin UX for managing connector instances "core" (every module wants connector management) or "module" (every module manages its own connectors)?
- **Recommendation:** **MOVES → civiccore.** Connector instance management is a generic admin concern — every module that uses connectors needs CRUD on its own connector instances, and the table (`data_sources`) is in `§10.1`. Move `datasources/router.py` and `datasources/sync_failures_router.py` to `civiccore/datasources/`. Move with the connector framework in Phase 3.

### C.4 `backend/app/seed/first_boot.py`

- **What it does:** Runs from `app.main` lifespan after first admin user is created. Seeds 175 exemption rules, 5 disclosure templates, 12 notification templates. Calls `scripts/seed_rules.py::STATE_RULES_REGISTRY`, `scripts/seed_templates.py::TEMPLATES`, `scripts/seed_notification_templates.py::NOTIFICATION_TEMPLATES`.
- **Why ambiguous:** First-boot seeding spans both core (notification templates, exemption rules) and records (compliance disclosure templates are records-specific). Currently a single function runs all three.
- **Recommendation:** **SPLIT.** Move exemption-rule + notification-template seeding into `civiccore/seed/first_boot.py` (called from civiccore's bootstrap). Keep records-specific compliance-template seeding in `backend/app/seed/first_boot.py`. The records `first_boot` will call core's `first_boot` first, then seed its own data. This preserves the current "manual-step-free fresh install" behavior across the split.

### C.5 `backend/app/exemptions/router.py` — split required

- **What it does:** Hosts both engine endpoints (`/exemptions/rules` CRUD, `/exemptions/scan/{request_id}`) and dashboard endpoints (`/exemptions/dashboard/accuracy`, `/exemptions/dashboard/by-state`).
- **Why ambiguous:** §8 says "Exemption engine moves"; §9 says "exemption dashboard stays." This file currently mixes both.
- **Recommendation:** **SPLIT** during Phase 3. Engine endpoints + rule CRUD → `civiccore/exemptions/router.py`. Dashboard endpoints → new `backend/app/exemptions/dashboard.py` router. Same model file, two routers consuming it.

### C.6 `backend/app/models/prompts.py` — table is core, content is records

- **What it does:** `PromptTemplate` SQLAlchemy model — a generic prompt-storage table (name, purpose, system_prompt, user_prompt_template, token_budget, model_id).
- **Why ambiguous:** The *table* is generic infrastructure (any module would want a versioned prompt store). The *seed rows* are records-specific.
- **Recommendation:** **MOVES → civiccore** as part of A.3 (LLM abstraction) in Phase 2. Records-specific prompt seed rows stay in `backend/scripts/seed_*` and are inserted by records' own bootstrap.

### C.7 `backend/app/models/document.py` — co-located shared models

- **What it does:** Single file containing `Document`, `DocumentChunk`, `DataSource`, `IngestionStatus`, `ModelRegistry`, `SourceType`. Six classes covering 4 spec subsystems (search, ingestion, connectors, llm).
- **Why ambiguous:** Every class in this file MOVES, but they move in different phases (Phase 2 for ModelRegistry/Document/DocumentChunk, Phase 3 for DataSource).
- **Recommendation:** **SPLIT before extraction.** During Phase 2, factor `models/document.py` into `models/document.py` (Document, DocumentChunk, IngestionStatus, SourceType), `models/model_registry.py` (ModelRegistry), and `models/data_source.py` (DataSource). Then move each in its target phase. Note: this is a precursor refactor — see Section E.

### C.8 `backend/app/security/`

- **What it does:** `at_rest.py` (Fernet envelope for `data_sources.connection_config` — ENG-001 / T6 closure) and `host_validator.py` (SSRF protection blocking internal/loopback/RFC1918 destinations in connector URLs).
- **Why ambiguous:** Spec §8 doesn't have a "security" row. Both modules are generic infrastructure (any module with connectors needs SSRF protection; any module storing connector creds needs at-rest encryption), but they ride alongside the connector framework.
- **Recommendation:** **MOVES → civiccore** as part of A.6 (connector framework) in Phase 3. They are the security primitives the connector framework depends on. `test_at_rest_encryption.py` and `test_host_validator.py` move with them.

---

## Section D — Phase 1 critical path

Per spec §12 row 1: Phase 1 extracts ONLY the User / Role / Department / audit_log models + their migrations + supporting code.

### D.1 Files moving in Phase 1

**Backend modules:**
- `backend/app/auth/__init__.py` → `civiccore/auth/__init__.py`
- `backend/app/auth/backend.py` → `civiccore/auth/backend.py`
- `backend/app/auth/dependencies.py` → `civiccore/auth/dependencies.py`
- `backend/app/auth/manager.py` → `civiccore/auth/manager.py`
- `backend/app/auth/router.py` → `civiccore/auth/router.py`
- `backend/app/audit/__init__.py` → `civiccore/audit/__init__.py`
- `backend/app/audit/logger.py` → `civiccore/audit/logger.py`
- `backend/app/audit/middleware.py` → `civiccore/audit/middleware.py`
- `backend/app/audit/router.py` → `civiccore/audit/router.py`
- `backend/app/departments/__init__.py` → `civiccore/departments/__init__.py`
- `backend/app/departments/router.py` → `civiccore/departments/router.py`
- `backend/app/service_accounts/__init__.py` → `civiccore/service_accounts/__init__.py`
- `backend/app/service_accounts/router.py` → `civiccore/service_accounts/router.py`

**Backend models:**
- `backend/app/models/user.py` (`Base`, `User`, `UserRole`) → `civiccore/models/user.py`
- `backend/app/models/audit.py` (`AuditLog`) → `civiccore/models/audit_log.py`
- `backend/app/models/departments.py` (`Department`) → `civiccore/models/department.py`
- `backend/app/models/service_account.py` (`ServiceAccount`) → `civiccore/models/service_account.py`

**Backend schemas:**
- `backend/app/schemas/user.py` → `civiccore/schemas/user.py`
- `backend/app/schemas/audit.py` → `civiccore/schemas/audit.py`
- `backend/app/schemas/department.py` → `civiccore/schemas/department.py`
- `backend/app/schemas/service_account.py` → `civiccore/schemas/service_account.py`

**Migrations:**
- `backend/alembic/versions/001_initial.py` → `civiccore/migrations/versions/001_initial.py`
- `backend/alembic/versions/012_add_liaison_public_roles.py` → `civiccore/migrations/versions/002_add_liaison_public_roles.py` (renumber per civiccore baseline)
- The `audit_log` and `departments` portions of `787207afc66a_phase2_extensions_...py` → see A.13 special note (likely deferred to a follow-on civiccore baseline migration that creates these tables fresh against an empty DB; the existing deployed DB already has them).

**Tests:**
- `backend/tests/test_auth.py` → `civiccore/tests/test_auth.py`
- `backend/tests/test_roles.py` → `civiccore/tests/test_roles.py`
- `backend/tests/test_user_management.py` → `civiccore/tests/test_user_management.py`
- `backend/tests/test_departments.py` → `civiccore/tests/test_departments.py`
- `backend/tests/test_department_scoping.py` → `civiccore/tests/test_department_scoping.py`
- `backend/tests/test_service_accounts.py` → `civiccore/tests/test_service_accounts.py`
- `backend/tests/test_audit.py` → `civiccore/tests/test_audit.py`
- `backend/tests/test_info_leak_hardening.py` → `civiccore/tests/test_info_leak_hardening.py`

### D.2 Shims required after Phase 1

Per spec §13, every moved symbol gets a 3-line shim file. Records keeps its current import paths working.

```python
# backend/app/models/user.py (shim — Phases 1–4)
from civiccore.models.user import Base, User, UserRole  # noqa: F401
```

Equivalent shims for `app.models.audit`, `app.models.departments`, `app.models.service_account`, `app.auth.*`, `app.audit.*`, `app.departments.*`, `app.service_accounts.*`, and the schemas.

**Special shim for `app.models.user.Base`:** Every other model file imports `Base` from `app.models.user`. The shim must re-export `Base` exactly so this line keeps working unchanged in `models/document.py`, `models/request.py`, etc.:
```python
from app.models.user import Base  # this becomes a shim → civiccore.models.user.Base
```

### D.3 Pre-Phase-1 precursor work

1. **`models/__init__.py` re-export audit.** The current `__init__.py` re-exports every model. After Phase 1 it must continue to re-export `User`, `UserRole`, `AuditLog`, `Department`, `ServiceAccount` (now from civiccore) so `from app.models import User` keeps working. Trivial change but must land in the same PR.
2. **Confirm `Base` ownership.** Spec §10 doesn't address the SQLAlchemy `Base` declarative base. Decision needed (Section F.1): does `Base` live in civiccore (every module imports it from `civiccore.models.user`) or does each module declare its own `Base` (with a CivicCore-provided convention for naming consistency)? **Recommendation: civiccore owns `Base`.** Single declarative_base across the suite, simpler migrations, consistent with §10.
3. **Audit migration history.** Spec §14 says CivicCore baselines its alembic history at the latest CivicRecords migration that touched a shared table. Pre-Phase-1, identify that revision (currently `019_encrypt_connection_config.py`, since it touched `data_sources` which is shared). Document the baseline in an ADR.

---

## Section E — Phase ordering implications

### E.1 Clean moves (no precursor refactor)

- Auth, audit, departments, service_accounts, schemas — Phase 1 lifts cleanly.
- Connectors framework (the `connectors/` directory itself, minus Laserfiche-style records adapters which don't exist yet) — Phase 3 lifts cleanly.
- Notifications, onboarding, city_profile, catalog — clean lifts in their target phases.

### E.2 Moves requiring precursor refactor

- **`models/document.py` split** (C.7) — must split into 3 files before Phase 2 extracts ModelRegistry and Phase 3 extracts DataSource. Otherwise Phase 2 has to drag DataSource into civiccore prematurely.
- **`exemptions/router.py` split** (C.5) — must split engine vs dashboard endpoints before Phase 3 ships.
- **`admin/router.py` split** (C.1) — must split core admin (model registry, system status) vs records admin (fees, records-specific user views) before Phase 4 ships.
- **`seed/first_boot.py` split** (C.4) — must split core seeders (exemption rules, notification templates) from records seeders (compliance templates) before Phase 3 ships.
- **`backend/app/letters/` and `backend/app/fees/` directory creation** (B.2, B.3) — recommended for Phase 5 alignment; not blocking earlier phases.

### E.3 Moves that cluster (must move together)

- **A.1 (Auth) + A.2 (Audit) + Department + ServiceAccount must move together in Phase 1.** Splitting auth and audit across phases breaks the audit middleware, which depends on the user identity from auth.
- **A.4 (Ingestion) + A.5 (Search) + ModelRegistry must move together in Phase 2.** Search depends on DocumentChunk; ingestion writes DocumentChunk; both consume the LLM client and ModelRegistry.
- **A.6 (Connectors) + A.7 (Notifications, specifically `sync_notifications.py`) + DataSource model + `security/at_rest.py` + `security/host_validator.py` must move together in Phase 3.** Connector framework consumes notification dispatch on circuit-open; both consume the at-rest encryption + SSRF protection primitives.
- **A.8 (Onboarding + city_profile) + A.9 (Catalog) must move together in Phase 4.** Onboarding wizard reads the catalog to populate connector setup steps.

---

## Section F — Open questions for Scott

Each of these needs a Scott decision before Phase 1 starts.

### F.1 `Base = declarative_base()` ownership

**Question:** Where does the SQLAlchemy declarative base live?
- **Option A (recommended):** `civiccore.models.base.Base` — one declarative_base across the suite. Every module imports it. Simpler migrations, single MetaData object.
- **Option B:** Each module declares its own `Base` with a shared naming convention. Independent MetaData per module. Cleaner module isolation, more complex Alembic setup.
- **Spec section:** §10 (table ownership) doesn't address Base.
- **Consequence:** Affects every model file in every module forever. Decide once.

### F.2 Phase-2 extensions migration (`787207afc66a_phase2_extensions_...py`)

**Question:** How is the multi-table Phase-2 extensions migration handled across the split?
- **Option A (recommended):** Leave the migration file in records' alembic history. Have CivicCore baseline its history at a later revision. Existing deployments continue with the records-side history; fresh deployments run records' migrations after civiccore's, which already created the shared tables (or will, in CivicCore's baseline).
- **Option B:** Hand-split the migration into a civiccore migration + a records migration. High risk of breaking existing deployments.
- **Spec section:** §14 (database migration strategy) — silent on cross-cutting historical migrations.
- **Consequence:** Get this wrong and existing deployments fail to upgrade.

### F.3 Combined sovereignty verification scripts

**Question:** Keep `scripts/verify-sovereignty.sh`/`.ps1` combined, or split into `verify_no_egress.sh` + `verify_no_telemetry.py` per spec §8 row 11?
- **Recommendation:** Keep combined. The current consolidated form has been verified through v1.2.0; splitting it adds risk for no benefit.
- **Consequence:** Spec §8 must be updated to reflect the actual filenames being moved.

### F.4 Design tokens

**Question:** Extract `frontend/src/components/ui/*` shadcn primitives' design tokens into a separate `civiccore-ui/tokens/` package, or leave them inline in the shadcn primitives moving with the AdminShell?
- **Recommendation:** Leave inline for civiccore v0.1. Extract tokens as a separate package in v0.2 once a second module's UI demands shared tokens.
- **Consequence:** Affects civiccore-ui package shape and the @civicsuite/core-ui import surface.

### F.5 Pre-Phase-5 directory restructuring (letters, fees)

**Question:** Spec §9 promises `backend/app/letters/*` and `backend/app/fees/*` directories that don't exist in this repo. Do we (a) update the spec to match reality (letters are inside `models/request_workflow.py`; fees endpoints are inside `admin/router.py`) or (b) restructure records during Phase 5 to match the spec?
- **Recommendation:** **(b) restructure records during Phase 5** — extract `letters/render.py` from `requests/router.py` rendering code, and `fees/router.py` from `admin/router.py` fee endpoints. Aligning the layout with the published spec is worth the modest refactor cost. Do this in the same PR that removes the import shims.
- **Consequence:** Phase 5 grows by ~2 files of focused refactor.

### F.6 ModelRegistry table location

**Question:** `ModelRegistry` is currently in `backend/app/models/document.py`. Spec §10.1 lists `model_registry` as a CivicCore-owned table. Pre-Phase-2, factor it into its own `backend/app/models/model_registry.py` to enable a clean Phase-2 move?
- **Recommendation:** Yes — see C.7. Land the split in a precursor PR before Phase 2 begins.
- **Consequence:** One additional pre-Phase-2 PR; reduces Phase-2 PR complexity.

### F.7 Datasources router classification

**Question:** Confirm Section C.3's recommendation that `backend/app/datasources/*` MOVES with the connector framework in Phase 3 (it manages the shared `data_sources` table), not stays as a records-admin surface.
- **Recommendation:** MOVES. The `data_sources` table is in §10.1, and connector instance management is a generic admin concern.
- **Consequence:** Phase 3 grows by 2 files; records keeps a thin shim.

### F.8 Frontend tests in scope

**Question:** Does Phase 1 also move the frontend test files for the AdminShell + shadcn-ui primitives, or do those wait until Phase 4 (when the AdminShell moves)?
- **Recommendation:** Wait until Phase 4. Phase 1 is backend-only. The frontend AdminShell stays in records throughout Phases 1–3 and consumes core via the OpenAPI-generated client.
- **Consequence:** Phase 1 PR stays focused on backend; no frontend churn.

---

## Appendix — Out-of-scope observations (do not fix in this branch)

Per Hard Rule 8 these are noted but not acted on:

- **`test-write.txt`** — empty 6-byte scratch file at repo root, untracked. Leftover from prior session.
- **`backend/scripts/__pycache__/`** under `backend/scripts/` — should be in `.gitignore` if not already covered.
- **`models/__init__.py` ordering** — Phase 2 models are imported after baseline models with a `# Phase 2 models` comment header. After the Phase 1 split, the comment will be stale (Phase 1 also touches the baseline section). Worth a comment refresh in the Phase 1 PR.
- **No `frontend/src/__tests__/` or top-level `tests/`** — test files live alongside source (`*.test.tsx`) and in `backend/tests/`. This is consistent and correct, just worth noting for the spec author.

These observations are reported, not fixed. Decisions on whether to address belong to a separate task per Hard Rule 8.
