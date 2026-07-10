> **RETRACTED — DO NOT USE**
>
> This document was created on 2026-04-13 based on the superseded Master Design Spec v1.0,
> NOT the canonical Unified Design Specification. It contains known inaccuracies:
> features removed from the roadmap that the canonical spec requires (Liaison role, public portal,
> NER/Tier 2 redaction, active discovery engine, RPA bridge, open records library),
> an invented phase-to-version mapping that contradicts the canonical spec's phasing,
> and "SHIPPED" tags on items that were never fully verified.
>
> **The canonical spec is:** `docs/UNIFIED-SPEC.md` (Unified Design Specification v2.0, April 12, 2026)
>
> This file is preserved for audit trail purposes only.

# CivicRecords AI — Master Design Specification (RETRACTED)

**Version:** 2.0
**Date:** 2026-04-13
**Status:** RETRACTED
**Previous Version:** [v1.0 (2026-04-11)](2026-04-11-civicrecords-ai-master-design-v1-SUPERSEDED.md)
**Source Documents:**
- [Product Description](../../product-description.md)
- [Compliance & Regulatory Analysis](../../compliance-regulatory-analysis.md)

**Change Log (v1.0 → v2.0):**
- Phase 2 delivered: department access controls, 50-state exemption rules, compliance templates, model registry, auditability dashboard
- Docker services updated from 6 to 7 (added Celery beat)
- Phase-to-version mapping added (v1.0.x → v1.1.0 → v1.2.0 → v2.0.0)
- Test count updated (104 → 144)
- Endpoint count updated (~25 → ~30)
- Exemption rules expanded from pilot (5 states) to full coverage (50 states + DC, 180 rules)
- Compliance templates marked as shipped (5 documents)
- Model registry CRUD endpoints marked as implemented
- Auditability dashboard marked as implemented

---

## 1. Product Summary

CivicRecords AI is a fully open-source, locally-hosted AI system that helps municipal staff respond to open records requests (FOIA/CORA and state equivalents). It runs entirely on commodity hardware — a single Ryzen-based desktop with 32-64 GB of RAM — inside a city's existing network perimeter. No cloud subscriptions. No vendor lock-in. No resident data leaving the building.

The system ingests a city's documents into a searchable knowledge base, then helps staff locate responsive records, flag exemptions, draft response language, and track request status.

### What It Is Not

- Not a records management system — it indexes and searches what already exists.
- Not a legal advisor — it surfaces suggestions, staff make all decisions.
- Not a public-facing portal (v1.x is internal staff tool only).
- Not a cloud service — every deployment is a sovereign instance.

### Target Users

- **Primary:** Municipal records staff (clerks, paralegals, records officers). Non-technical. The interface must be as approachable as a search engine.
- **Secondary:** Department heads and city attorneys who review responses before release.
- **Enabling:** City IT staff who install, configure, and maintain the system.

---

## 2. Competitive Landscape

No existing open-source tool combines AI-assisted search, local-first architecture, municipal workflow management, and state-specific exemption law for the responder side of open records.

| Project | Relevance | Gap |
|---|---|---|
| MITRE FOIA Assistant | Validated exemption detection approach (BERT on deliberative process). Modular exemption framework. Human-in-the-loop. | Federal-only, closed-source, no workflow, single exemption type. |
| OpenFOIA | Local-first, encrypted, entity extraction, relationship graphs. | Requester-side tool (journalists), not responder-side. CLI-only. AGPL. |
| AnythingLLM | MIT-licensed local RAG platform. Workspace isolation, LLM abstraction, Docker deployment. | Generic tool — no FOIA workflow, no exemption detection, no compliance features. |
| RecordTrac (Code for America) | Proven municipal records request workflow used by City of Oakland. Python/Flask. | No AI capabilities whatsoever. |
| GovPilot, OPEXUS | Commercial FOIA management SaaS. | Cloud-based, subscription-priced, vendor lock-in. |

### Architectural Lessons Learned

- **From MITRE:** Treat each exemption category as a separate classification problem, not one monolithic model.
- **From AnythingLLM:** Workspace isolation pattern maps to per-request or per-department document collections. LLM provider abstraction layer enables model swapping without code changes. Collector service pattern for ingestion.
- **From RecordTrac:** Battle-tested municipal workflow patterns for intake, assignment, tracking, and status.

---

## 3. Architecture Decisions

All decisions documented below were evaluated against the constraint: 1-2 person team building and maintaining the system, deployed on commodity hardware, maintained by municipal IT generalists.

| Decision | Choice | Rationale |
|---|---|---|
| Backend | Python / FastAPI | AI/ML ecosystem is Python-native. RAG, embeddings, OCR, document parsing — all strongest in Python. |
| LLM Runtime | Ollama | Simple, well-documented, good model library. Model management UX suitable for municipal IT. |
| LLM Model | Gemma 4 (recommended default) | Apache 2.0. 26B MoE (~4B active params) runs on target hardware. Native multimodal (OCR, document parsing). 256K context. Architecture is model-agnostic — works with any Ollama-compatible model. |
| Embedding Model | nomic-embed-text via Ollama | Apache 2.0. Runs natively in Ollama (one less dependency). Swappable via admin panel. |
| Database | PostgreSQL 17 + pgvector | Single database for everything: app data, vector embeddings, audit logs, user accounts. One backup, one restore, one connection pool. Eliminates separate vector DB dependency. |
| Frontend | React + shadcn/ui + Tailwind | 50+ pre-built components. Admin dashboard templates exist. Professional UX out of the box. ~70-80% of needed UI available as copy-paste components. |
| Auth | Built-in (fastapi-users + JWT + RBAC in Postgres) | No separate auth service. Covers 4 roles (Admin, Staff, Reviewer, Read-Only) + service accounts for federation. LDAP/AD can be added as a connector. |
| Task Queue | Celery + Redis | Async ingestion, embedding, and LLM jobs. Well-proven Python ecosystem. |
| Outbound/Federation | Federation-ready REST API (no proxy server) | API designed from day one to support external callers. Service accounts for instance-to-instance auth. No Squid/mitmproxy dependency. |
| Document Storage | Hybrid | Index (extracted text + embeddings) always stored. Original document cached only when attached to an active records request (legal defensibility). |
| Exemption Detection | Rules-primary, LLM-secondary | Deterministic pattern matching (PII regex, statutory phrases) as primary layer. LLM as secondary "did I miss anything?" suggestion layer. All flags require human confirmation. |
| Ingestion | Two-track pipeline | Fast track: lightweight Python parsers for structured docs (DOCX, CSV, email, text). LLM track: Gemma 4 multimodal for scanned PDFs, images, handwriting. Tesseract fallback for non-multimodal models. |
| Licensing | Apache 2.0 (project) | All dependencies must be permissive (MIT, Apache 2.0, BSD) or weak-copyleft (LGPL, MPL, EPL). No AGPL, SSPL, or BSL dependencies. |
| Multi-tenancy | Department-scoped access controls | **[SHIPPED v1.1.0]** Staff scoped to assigned department. Admins retain org-wide access. Shared resources (null department) visible to all. |
| Deployment | Docker Compose (Windows, macOS, Linux) | 7 services: postgres, redis, api, worker, beat, ollama, frontend. Cross-platform via Docker Desktop. |

---

## 4. System Architecture

### Docker Compose Stack

```
Services:
  1. postgres    — PostgreSQL 17 + pgvector (data, vectors, audit)
  2. redis       — Task queue broker (BSD, pinned <8.0)
  3. api         — FastAPI application server (~30 endpoints)
  4. worker      — Celery worker(s) for async ingestion/embedding
  5. beat        — Celery beat scheduler for periodic tasks
  6. ollama      — Local LLM runtime (Gemma 4 + nomic-embed-text)
  7. frontend    — React build served by nginx (port 8080)
```

### Application Layer (FastAPI)

The API server contains these modules:

- **Auth Module** — fastapi-users, JWT tokens, 4 roles (Admin, Staff, Reviewer, Read-Only), service accounts for federation. Login rate limiting (5/minute per IP).
- **Department Module** — **[SHIPPED v1.1.0]** Department CRUD with audit logging. `check_department_access()` middleware scopes all request/document/exemption endpoints by user department.
- **Search API** — RAG queries, hybrid retrieval (semantic + keyword via Reciprocal Rank Fusion), source attribution, session context for iterative refinement. Results scoped by department.
- **Workflow API** — Request CRUD, status transitions (11 statuses), document association, deadline management. Department auto-set from creating user.
- **Audit Logger** — Middleware that logs every API call. Hash-chained (SHA-256), append-only, SELECT FOR UPDATE on chain writes. Exportable as CSV/JSON. 3-year default retention with archival.
- **LLM Abstraction** — Model-agnostic interface wrapping Ollama. Swap models without touching application code. Supports both chat completion and embedding endpoints.
- **Exemption Engine** — Rules engine (regex, keyword, statutory phrases) + LLM suggestion layer. **[SHIPPED v1.1.0]** 180 rules across 50 states + DC. Auditability dashboard with acceptance/rejection rates and CSV/JSON export.
- **Compliance Module** — **[SHIPPED v1.1.0]** 5 compliance template documents with variable substitution from city profile. Template render endpoint. Model registry CRUD for compliance metadata (name, license, version, capabilities).
- **Federation API** — REST endpoints accessible via service account API keys. Another CivicRecords AI instance can query this one with scoped access.

### Ingestion Pipeline (Two-Track)

**Fast Track (structured documents):**
- python-docx (MIT) for DOCX
- openpyxl (MIT) for XLSX
- pdfplumber (MIT) for text-layer PDFs
- email/mailbox (stdlib) for EML/MBOX
- csv (stdlib) for CSV
- beautifulsoup4 (MIT) for HTML
- Flow: parse → extract text → chunk → embed via nomic-embed-text → store in pgvector

**LLM Track (scanned/image documents):**
- Scanned PDFs (image-only), JPEG, PNG, TIFF, handwritten documents, charts
- Flow: image → Gemma 4 multimodal → extracted text → chunk → embed → pgvector
- Fallback: Tesseract OCR if running a non-multimodal model

**Ingestion behavior:**
- Incremental: new/modified documents indexed on configurable schedule
- Auditable: every ingested document logged with source, timestamp, hash, status
- Non-destructive: system never modifies source documents
- Chunking configurable per source type
- Upload size limit: 100 MB per file

### Data Sources

| Phase | Sources | Status |
|-------|---------|--------|
| Phase 1 (v1.0.x) | Uploaded files, configured file directories | **SHIPPED** |
| Phase 3 (v1.2.0) | SQL databases (PostgreSQL, MySQL, MSSQL, SQLite), IMAP email, SMB/NFS file shares, SharePoint, REST APIs | Planned |

---

## 5. Data Model

### Users & Auth

```
users
  id, email, full_name, role (admin/staff/reviewer/read_only),
  hashed_password, department_id (FK), created_at, last_login

departments                                    [SHIPPED v1.1.0]
  id, name, code (unique), contact_email, created_at

service_accounts
  id, name, api_key_hash, role, created_by, created_at
```

### Documents & Ingestion

```
data_sources
  id, name, type (file_share/database/email/upload), connection_config (encrypted JSON),
  schedule, status, created_by

documents
  id, source_id, source_path, filename, file_type, file_hash (SHA-256),
  ingestion_status, department_id, ingested_at, metadata (JSON)

document_chunks
  id, document_id, chunk_index, content_text, embedding (vector 768),
  token_count, page_number

document_cache
  id, document_id, cached_file_path (local filesystem path), file_size,
  cached_at
  (only populated when document is attached to a records request;
   original file stored on local filesystem, not in database)
```

### Search & RAG

```
search_sessions
  id, user_id, created_at

search_queries
  id, session_id, query_text, filters (JSON), results_count, created_at

search_results
  id, query_id, chunk_id, similarity_score, rank
```

### Request Tracking

```
records_requests
  id, requester_name, requester_email, date_received, statutory_deadline,
  description, status (11 statuses), assigned_to, department_id (FK),
  created_by, estimated_fee, fee_status, closed_at

request_documents
  id, request_id, document_id, relevance_note, exemption_flags (JSON),
  inclusion_status (included/excluded/pending)

request_timeline
  id, request_id, event_type, actor_id, actor_role, description,
  internal_note, created_at

request_messages
  id, request_id, sender_type, sender_id, message_text, is_internal,
  created_at

response_letters
  id, request_id, template_id, generated_content, edited_content,
  status (draft/approved/sent), generated_by, approved_by, sent_at

fee_line_items
  id, request_id, description, quantity, unit_price, total, created_at
```

### Exemption Detection

```
exemption_rules
  id, state_code, category, rule_type (regex/keyword/llm_prompt),
  rule_definition, description, enabled, created_by
  [180 rules across 50 states + DC — SHIPPED v1.1.0]

exemption_flags
  id, chunk_id, rule_id, request_id, category, confidence,
  status (flagged/reviewed/accepted/rejected), reviewed_by, reviewed_at,
  review_reason, detection_tier, detection_method, auto_detected
```

### Audit Log (append-only, hash-chained)

```
audit_log
  id, prev_hash, entry_hash, timestamp, user_id, action,
  resource_type, resource_id, details (JSON), ai_generated (boolean)
```

### Compliance & Configuration

```
disclosure_templates                            [5 TEMPLATES SHIPPED v1.1.0]
  id, template_type, state_code, content, version, updated_by, updated_at
  Shipped types: ai_use_disclosure, response_letter_disclosure,
                 caia_impact_assessment, ai_governance_policy,
                 data_residency_attestation

model_registry                                  [CRUD SHIPPED v1.1.0]
  id, model_name, model_version, parameter_count, license,
  model_card_url, is_active, context_window_size, supports_ner,
  supports_vision
```

---

## 6. Compliance Architecture

Based on the 50-state regulatory analysis, these features are hard requirements enforced at the API layer.

### 6.1 Human-in-the-Loop (Architectural Enforcement)

- No API endpoint produces a final, releasable document without a human approval step.
- Exemption flags stored as recommendations with status (flagged/reviewed/accepted/rejected) — system cannot proceed past "flagged" without human action.
- Response letters generated as drafts in a review queue. "Send" or "finalize" requires authenticated human authorization.
- No "batch approve" or "auto-process" mode for exemption decisions or response generation.

### 6.2 Audit Logging

- Every search query, AI-generated result, exemption flag, draft response, and user action logged with timestamp, user identity, and session context.
- Append-only, hash-chained (each entry includes hash of previous entry). SELECT FOR UPDATE prevents concurrent write race conditions.
- Exportable as CSV and JSON for production in response to records requests or attorney general inquiries.
- Retention period configurable per city (default: 3 years, aligns with CAIA).
- Automatic archival before retention cleanup.
- Logs distinguish between AI-generated content and human-authored content.

### 6.3 AI Content Labeling

- All LLM outputs visually distinct and labeled as "AI-generated draft requiring human review."
- Labels enforced at the API response layer, not just the UI.

### 6.4 Data Sovereignty

- Installation verification script confirms no outbound network connections (or only allowlisted).
- No telemetry, analytics, or crash reporting that transmits data off the machine.
- **[SHIPPED v1.1.0]** Data Residency Attestation document template for city IT directors — ships as `data_residency_attestation` in compliance templates.
- Verifiable in source code (open source).

### 6.5 Transparency Templates — SHIPPED v1.1.0

All 5 required compliance templates ship with the product and are seeded into the `disclosure_templates` table:

| Template | Type Key | Description |
|----------|----------|-------------|
| Public AI Use Disclosure | `ai_use_disclosure` | Statement cities post publicly disclosing AI use in records processing |
| Response Letter Disclosure Language | `response_letter_disclosure` | Boilerplate paragraph for inclusion in response letters |
| CAIA Impact Assessment | `caia_impact_assessment` | Pre-filled Colorado AI Act assessment (NOT high-risk classification) |
| AI Governance Policy | `ai_governance_policy` | Policy template based on GovAI Coalition, Boston, San Jose, Bellevue, Garfield County CO |
| Data Residency Attestation | `data_residency_attestation` | IT director attestation that all data remains on local hardware |

All templates use `{{VARIABLE_NAME}}` placeholder syntax. The `/exemptions/templates/{id}/render` endpoint substitutes variables from the city profile automatically.

### 6.6 Exemption Detection Auditability — SHIPPED v1.1.0

- **[SHIPPED]** Dashboard showing flag acceptance/rejection rates by category, department, and time period (`GET /exemptions/dashboard/accuracy`).
- **[SHIPPED]** Export flag accuracy data for external review (`GET /exemptions/dashboard/export` — CSV and JSON formats).
- Configuration interface for adjusting exemption rules without code changes, with all changes logged.
- Documentation of exemption rule sources with version tracking.

### 6.7 Model Transparency — SHIPPED v1.1.0

- **[SHIPPED]** Admin panel displays current model name, version, parameter count, license, model card URL via Model Registry CRUD (`GET/POST/PATCH/DELETE /admin/models/registry`).
- Live Ollama model status available at `GET /admin/models`.
- No fine-tuning on city data unless explicitly configured by IT. Default: RAG only.
- No proprietary or closed-source models by default.

---

## 7. Hardware Target

| Component | Minimum Spec | Recommended Spec |
|---|---|---|
| CPU | 8-core x86_64 (Intel or AMD) | 12-16 core (Ryzen 9, Core i9, Apple M3 Pro+) |
| RAM | 32 GB | 64 GB |
| Storage | 1 TB NVMe SSD | 2 TB NVMe SSD |
| GPU | Integrated (CPU inference) | Discrete with 8+ GB VRAM |
| Network | Gigabit Ethernet | Gigabit Ethernet |
| OS | Windows 10/11, macOS 13+, Ubuntu 22.04+ | Any with Docker Desktop |
| Total Cost | ~$800 | ~$1,200 |

**Supported Platforms:** Windows 10/11 (Docker Desktop), macOS 13+ (Docker Desktop), Linux (Docker Engine or Docker Desktop). All platforms use identical Docker containers — the application runs in Linux containers regardless of host OS.

**GPU Acceleration:** Auto-detected by install scripts. AMD ROCm on Linux, DirectML via host Ollama on Windows, NVIDIA CUDA via Ollama built-in support.

**Performance target:** Under 30 seconds for a typical query-and-retrieve cycle on minimum spec without discrete GPU.

---

## 8. Security Model

### Network

- Binds to localhost or city-designated internal IP only. Never exposed to public internet.
- HTTPS with self-signed or city-provided TLS certificates.
- All outbound traffic disabled by default.

### Application

- Role-based access control: Admin, Staff, Reviewer, Read-Only.
- **[SHIPPED v1.1.0]** Department-level access controls — staff scoped to assigned department.
- Service accounts with API keys (hashed before storage) for federation.
- Session management with configurable timeout.
- No default passwords. First-run setup requires creating admin account.
- All API endpoints require authentication.
- Login rate limiting: 5 requests per minute per IP (OrderedDict with eviction cap).
- Public registration disabled — users created by admin only.

### Data

- Filesystem-level encryption (LUKS, configured at OS level by IT).
- No plaintext credential storage — secrets via environment variables or local vault.
- Audit logs append-only and tamper-evident (hash-chained with SHA-256).

### AI Safety

- All LLM outputs labeled as AI-generated drafts.
- Prompt injection defense layer sanitizes document content before LLM context.
- Model outputs constrained to retrieval context — cite sources, don't hallucinate.
- Configurable confidence threshold for surfacing low-confidence results.

---

## 9. Project Decomposition

The system was decomposed into 5 sub-projects built in hybrid sequence. Phase 2 adds department access, compliance, and state coverage on top.

### Build Sequence

```
Sub-Project 1: Foundation            [SHIPPED v1.0.0]
    ↓
Sub-Project 2: Ingestion Pipeline    [SHIPPED v1.0.0]
    ↓
Sub-Project 3: RAG Search + UI       [SHIPPED v1.0.0]
    ↓
Sub-Project 4: Request Tracking      [SHIPPED v1.0.0]
    ↓
Sub-Project 5: Exemption & Compliance [SHIPPED v1.0.0]
    ↓
Phase 2: Departments, 50-State Rules, Compliance Templates [SHIPPED v1.1.0]
```

### Sub-Project 1: Foundation — SHIPPED

**Delivered:** Docker Compose stack (7 services), user auth (JWT, 4 roles, service accounts), hash-chained audit logging, Alembic migrations, admin panel, install scripts (Windows + Linux/macOS), data sovereignty verification, GPU auto-detection.

### Sub-Project 2: Ingestion Pipeline — SHIPPED

**Delivered:** Data source configuration, fast track parsers (PDF, DOCX, XLSX, CSV, email, HTML, text), LLM track (Gemma 4 multimodal, Tesseract fallback), sentence-aware chunking, nomic-embed-text embedding, Celery async workers, ingestion dashboard. Upload size limit: 100 MB.

### Sub-Project 3: RAG Search Engine + UI — SHIPPED

**Delivered:** Natural language search (React + shadcn/ui), hybrid search (pgvector semantic + PostgreSQL full-text via RRF), source attribution with page numbers, confidence scores, filters, iterative refinement, AI output labeling.

### Sub-Project 4: Request Tracking — SHIPPED

**Delivered:** Request intake, 11-status workflow (received → clarification → assigned → searching → in_review → ready_for_release → drafted → approved → fulfilled → sent → closed), document caching on attachment, deadline dashboard, response letter generation (LLM + template fallback), review/approval workflow, timeline, messaging, fee tracking.

### Sub-Project 5: Exemption Detection & Compliance — SHIPPED

**Delivered:** PII regex rules (SSN, phone, email, credit card, DOB), statutory keyword rules (5 pilot states: CO, TX, CA, NY, FL), LLM secondary suggestion layer, exemption flag workflow, basic dashboard.

### Phase 2: Department Access & Full Compliance — SHIPPED v1.1.0

**Delivered:**
- Department CRUD API (5 endpoints) with audit logging
- `check_department_access()` scoping middleware on all request/document/exemption endpoints
- 50-state + DC exemption rule coverage (180 rules across 51 jurisdictions, 5 universal PII regex)
- 5 compliance template documents with seed script
- Template render endpoint with city profile variable substitution
- Exemption auditability dashboard (acceptance/rejection rates by category/department, CSV/JSON export)
- Model registry CRUD (4 endpoints) for compliance metadata

---

## 10. Phase-to-Version Mapping

| Phase | Version | Focus | Status |
|-------|---------|-------|--------|
| Phase 1 | v1.0.x | MVP — search, requests, exemptions, audit, onboarding | **SHIPPED** |
| Phase 2 | v1.1.0 | Department access controls, 50-state rules, compliance templates | **SHIPPED** |
| Phase 3 | v1.2.0 | Data source connectors (SQL, IMAP, SMB/NFS, SharePoint, REST APIs) | Planned |
| Phase 3+ | v2.0.0 | Federation (instance discovery, cross-instance search, federated audit, trust management) | Planned |

### Current Metrics (v1.1.0)

| Metric | Value |
|--------|-------|
| Automated tests | 144 |
| Database tables | 29 |
| API endpoints | ~30 |
| Docker services | 7 |
| Exemption rules | 180 |
| Jurisdictions covered | 51 (50 states + DC) |
| Compliance templates | 5 |
| Supported platforms | 3 (Windows, macOS, Linux) |

---

## 11. Federation (Phase 3+)

The API is designed from day one to support federation between CivicRecords AI instances across jurisdictions.

### Federation Model

- Each instance can act as both client (querying other instances) and server (responding to queries).
- Trust relationships: City A authorizes County B's instance as a trusted peer with scoped access via service accounts.
- Cross-boundary audit trail: "County requested these records from us on [date], authorized by [person]."
- Allowlist/approval model applied to instance-to-instance traffic.

### Day-One API Decisions That Enable Federation

- REST API with proper auth (JWT for humans, API keys for service accounts).
- Service accounts have role-based scoping (what data they can access).
- All API responses include provenance metadata (which instance produced the result).
- No dependency on shared state between instances.

### Deferred to Phase 3+ (v2.0.0)

- Instance discovery and registration.
- Cross-instance search (query multiple instances from one UI).
- Federated audit log aggregation.
- Trust relationship management UI.

---

## 12. Open Source Strategy

### License

Apache License 2.0 for all project code.

### Acceptable Dependency Licenses

**Permissive (preferred):** MIT, Apache 2.0, BSD 2/3-Clause, ISC, PostgreSQL License, Public Domain/Unlicense/CC0.

**Weak Copyleft (acceptable):** LGPL v2.1/v3, MPL 2.0, EPL 2.0.

**Not Acceptable:** AGPL, SSPL, BSL, or any "source available" license restricting commercial/government use.

**Note:** Redis pinned to <8.0.0 (BSD licensed). Redis 8.x changed to a non-permissive license.

### Repository

- **Name:** `civicrecords-ai`
- **Domain target:** civicrecords.ai
- Public GitHub repository with issue tracker, discussions, and contribution guidelines.

---

## 13. Success Metrics

| Metric | Target |
|---|---|
| Time from bare metal to first successful search | < 2 hours |
| Average query-to-response time (minimum hardware) | < 30 seconds |
| Records clerk time-to-competence | < 1 hour of training |
| Responsive document recall vs. manual search | >= 90% |
| System cost (hardware + zero software licensing) | < $1,500 total |
| Annual operating cost (electricity + maintenance) | < $500/year |
| Uptime target (during business hours) | 99.5% |

---

## 14. Gemma 4 Assessment

Gemma 4 (released April 2, 2026) is the recommended default model. Key findings from evaluation:

### Strengths

- Apache 2.0 license — no friction for municipal deployment.
- 26B MoE variant (~4B active parameters) runs on target hardware.
- Native multimodal: OCR, document parsing, handwriting recognition, chart comprehension.
- 256K token context window.
- Strong general reasoning (85% MMLU Pro, 84% GPQA Diamond).

### Limitations

- No published LegalBench scores. Legal reasoning capability is extrapolated from general benchmarks.
- No production deployments for FOIA/legal sensitivity review documented.
- Google's own model card states it is not suitable for autonomous legal decision-making.
- 26B MoE has 22-point gap vs 31B dense on long-context retrieval (44% vs 66%).
- Known failure modes: hallucination, multi-step reasoning degradation, legal terms of art.

### Architecture Implications

- Gemma 4's multimodal capabilities simplify the ingestion pipeline (two-track instead of 5-tool OCR stack).
- LLM is used for search/retrieval and draft generation (strong use case) but NOT as the primary exemption detection engine (unproven use case).
- Exemption detection uses rules-primary approach with LLM as secondary suggestion layer.
- Architecture is model-agnostic. Gemma 4 is recommended, not required.

---

## 15. Documentation

| Document | Location | Audience |
|----------|----------|----------|
| Master Design Spec (this document) | `docs/superpowers/specs/` | Architects, reviewers |
| Phase 2 Spec | `docs/superpowers/specs/2026-04-12-phase2-spec.md` | Developers |
| Phase 2 Implementation Plan | `docs/superpowers/specs/2026-04-12-phase2-implementation-plan.md` | Developers |
| System Architecture Diagram | `docs/architecture/system-architecture.html` | All |
| Phase Decomposition Diagram | `docs/architecture/decomposition.html` | All |
| City Clerk User Manual | `docs/user-manual-staff.html` | Records staff |
| IT Administrator Manual | `docs/admin-manual-it.html` | IT staff |
| Landing Page | `docs/index.html` | Public |
| Contributing Guide | `CONTRIBUTING.md` | Developers |
| README | `README.md` | All |

---

## Appendix A: Regulatory Summary

CivicRecords AI is deployable in all 50 states. The system sits in the "staff productivity tool" category, not the "automated decision-making" category. Maintaining that classification requires:

1. No auto-redaction.
2. No auto-denial.
3. No auto-release.
4. Clear AI content labeling.

See [Compliance & Regulatory Analysis](../../compliance-regulatory-analysis.md) for full 50-state assessment including Colorado CAIA deep analysis.

## Appendix B: Architecture Diagrams

Interactive architecture diagrams are available in [docs/architecture/](../../architecture/):
- `system-architecture.html` — Full system component diagram with data flows
- `decomposition.html` — Phase timeline and sub-project build sequence
