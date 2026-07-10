# CivicSunshine — Product Description

**Local AI-Powered Open Records Support for American Cities**

*Version 0.1 — Draft for Product Team*

---

## Executive Summary

CivicSunshine is a fully open-source, locally-hosted AI system that helps municipal staff respond to open records requests (FOIA/CORA and state equivalents). It runs entirely on commodity hardware — a single $1,000 Ryzen-based desktop with 32–64 GB of RAM — inside a city's existing network perimeter. No cloud subscriptions. No vendor lock-in. No resident data leaving the building.

The system ingests a city's documents, databases, images, and digital records into a searchable knowledge base, then helps staff locate responsive records, flag exemptions, draft response language, and track request status — cutting response times from weeks to days while reducing legal exposure from missed or mishandled requests.

---

## The Problem

Every city in America is legally required to respond to open records requests. The operational reality is brutal:

- **Volume is rising.** Requests have increased steadily as citizens, journalists, and advocacy groups become more sophisticated. Many cities report 20–50% year-over-year growth.
- **Staff are overwhelmed.** Most cities assign open records duties to clerks, paralegals, or department heads who carry the work on top of their primary jobs. There is rarely a dedicated records officer below the county level.
- **Records are scattered.** Responsive documents may live in email archives, shared drives, paper filing cabinets, proprietary database systems, body camera footage, council meeting minutes, financial systems, and permitting software — often with no unified index.
- **Mistakes are expensive.** An incomplete search, a missed exemption, or a blown deadline can trigger litigation, sanctions, or public embarrassment. Over-redaction erodes public trust; under-redaction exposes private information.
- **Commercial AI is a non-starter for most cities.** Cloud-based AI tools raise immediate concerns: resident data flowing to third-party servers, recurring SaaS costs that small-city budgets can't absorb, and vendor dependency that conflicts with public stewardship obligations.

Cities need AI that works *for* them, runs *inside* their walls, and costs less than a single part-time employee.

---

## The Product

### What It Is

CivicSunshine is a self-contained software system that a city's IT staff can install on a single desktop-class machine, connect to the city's document stores and databases, and hand to records staff as a browser-based tool. It combines:

1. **A local large language model** (running via Ollama or compatible runtime) that never sends data off the machine.
2. **A document ingestion pipeline** that can consume PDFs, images (via OCR), Word documents, spreadsheets, emails, structured database exports, API feeds, and plain text — normalizing everything into a searchable knowledge base.
3. **A retrieval-augmented generation (RAG) engine** that lets staff ask natural-language questions against the full corpus of ingested records.
4. **A request management interface** where staff can log incoming requests, track deadlines, associate responsive documents, flag exemptions, and generate response drafts.
5. **A controlled outbound research module** that can — when explicitly authorized by staff — reach out through a secured proxy to check external public records databases, state archives, and legal reference sources to support a response.

### What It Is Not

- It is **not a records management system.** It does not replace a city's existing document management, email archiving, or database infrastructure. It indexes and searches what already exists.
- It is **not a legal advisor.** It can surface relevant exemption language and flag potential issues, but all decisions remain with authorized staff. Every AI-generated suggestion is clearly labeled as a draft requiring human review.
- It is **not a public-facing portal.** Version 1 is an internal staff tool only. A future public request submission interface is on the roadmap but out of initial scope.
- It is **not a cloud service.** There is no hosted version. Every deployment is a sovereign instance owned and operated by the city.

---

## Target Users

### Primary: Municipal Records Staff

City clerks, paralegals, records officers, and administrative staff who receive and process open records requests. They need to search across scattered document stores, identify responsive records, apply exemptions correctly, and respond within legally mandated timelines. Typical skill level: comfortable with web browsers and office software, not technical. The interface must be as approachable as a search engine.

### Secondary: Department Heads and City Attorneys

Supervisors who review responses before release, especially for sensitive or complex requests. They need confidence that the search was thorough, exemptions were correctly applied, and response language is defensible. They interact with the review/approval workflow, not the search interface directly.

### Enabling: City IT Staff

The people who install, configure, and maintain the system. They need clear documentation, a reproducible installation process, and straightforward integration points for connecting city data sources. They are the gatekeepers for the outbound research module's network access rules.

---

## Hardware Target

The system must run acceptably on a single machine with the following baseline specification:

| Component | Minimum Spec | Recommended Spec |
|---|---|---|
| CPU | AMD Ryzen 7 (8-core) | AMD Ryzen 9 (12–16 core) |
| RAM | 32 GB DDR4/DDR5 | 64 GB DDR5 |
| Storage | 1 TB NVMe SSD | 2 TB NVMe SSD |
| GPU | Integrated (CPU inference) | Discrete AMD or NVIDIA with 8+ GB VRAM |
| Network | Gigabit Ethernet | Gigabit Ethernet |
| OS | Ubuntu 24.04 LTS | Ubuntu 24.04 LTS |
| Total Cost | ~$800 | ~$1,200 |

**Design constraint:** The system must deliver usable response times (under 30 seconds for a typical query-and-retrieve cycle) on the minimum spec without a discrete GPU. GPU acceleration is a performance bonus, not a requirement.

---

## Core Capabilities

### 1. Document Ingestion Pipeline

The system must be able to consume, normalize, and index documents from the following source types:

**File Formats:**
- PDF (text-layer and scanned/image-only via OCR)
- Microsoft Office (DOCX, XLSX, PPTX)
- Plain text and Markdown
- Email archives (MBOX, EML, PST via conversion)
- Images (JPEG, PNG, TIFF — OCR to text)
- CSV and structured data exports
- HTML and web archives

**Live Data Sources (via IT-configured connectors):**
- SQL databases (PostgreSQL, MySQL, SQLite, MS SQL Server)
- REST APIs with configurable authentication
- File shares (SMB/CIFS, NFS)
- IMAP email servers
- SharePoint document libraries (via API)

**Ingestion Behavior:**
- Incremental: once a source is connected, new and modified documents are indexed automatically on a configurable schedule.
- Auditable: every ingested document is logged with source, timestamp, hash, and processing status.
- Non-destructive: the system never modifies source documents. It creates its own index and vector embeddings from copies.
- Chunking and embedding are configurable per source type to optimize retrieval quality.

### 2. Search and Retrieval (RAG Engine)

Staff interact with the knowledge base through a natural-language search interface:

- **Semantic search:** "Find all communications between the planning department and Acme Construction about the downtown rezoning in 2024."
- **Keyword + semantic hybrid:** Combines traditional keyword matching with vector similarity for higher recall.
- **Source attribution:** Every retrieved chunk links back to its source document with page/section reference and a confidence score.
- **Filters:** Staff can scope searches by date range, department, document type, and source system.
- **Iterative refinement:** Staff can follow up with clarifying questions in the same session context.

### 3. Exemption and Sensitivity Detection

The system includes a configurable rules engine for flagging potentially exempt content:

- Pre-loaded with common exemption categories from all 50 state open records statutes (personnel records, law enforcement investigations, attorney-client privilege, trade secrets, personal privacy, deliberative process, etc.).
- City-specific exemption rules can be added or modified by authorized staff without code changes.
- Flagged content is highlighted in retrieved documents with the applicable exemption category and confidence level.
- The system never auto-redacts. It flags and recommends; staff decide.

### 4. Request Tracking and Workflow

A lightweight case management interface for open records requests:

- Log incoming requests with requester info, date received, statutory deadline, and description.
- Associate responsive documents discovered through search.
- Track status: received → in search → in review → response drafted → approved → sent.
- Generate response letters from templates with auto-populated fields (request details, responsive document list, exemption citations).
- Dashboard showing open requests, approaching deadlines, and workload distribution.
- Export request history for reporting and compliance audits.

### 5. Controlled Outbound Research Module

For requests that require checking external public records or legal references:

- **Whitelist-only architecture:** Outbound network access is disabled by default. IT staff configure an explicit allowlist of approved external domains (e.g., state archives, court records databases, legal reference sites).
- **Proxy-mediated:** All outbound traffic routes through a local proxy server that logs every request and response, enforces the allowlist, and can be monitored or disabled at any time.
- **Staff-initiated only:** The system never reaches out to the internet autonomously. A staff member must explicitly trigger an external search and approve the query before it leaves the network.
- **Air-gap compatible:** The system is fully functional without any outbound internet access. The research module is an optional enhancement, not a dependency.
- **No data exfiltration path:** Outbound queries contain only the search terms staff enter — never raw document content, resident data, or internal records.

### 6. Administration and Configuration

- **Web-based admin panel** for IT staff to manage data source connections, user accounts, system settings, and the outbound allowlist.
- **Role-based access control:** Admin, Records Staff, Reviewer, Read-Only.
- **Audit logging:** All user actions, searches, document access, and AI interactions are logged with timestamps and user identity.
- **Model management:** IT staff can select, download, and swap LLM models (via Ollama's model library) without rebuilding the system. Recommended default models will be documented for different hardware tiers.
- **Backup and restore:** Configuration and index data can be backed up and restored. Source document access is via live connections, not stored copies (except for the vector index).

---

## Technical Architecture (High Level)

```
┌─────────────────────────────────────────────────────────────┐
│                    City Network Perimeter                    │
│                                                             │
│  ┌─────────────┐    ┌──────────────────────────────────┐   │
│  │  Staff       │    │  CivicSunshine Server          │   │
│  │  Workstation │◄──►│                                  │   │
│  │  (Browser)   │    │  ┌────────────┐  ┌───────────┐  │   │
│  └─────────────┘    │  │ Web UI     │  │ Admin UI  │  │   │
│                      │  │ (React)    │  │ (React)   │  │   │
│                      │  └─────┬──────┘  └─────┬─────┘  │   │
│                      │        │               │         │   │
│                      │  ┌─────▼───────────────▼─────┐  │   │
│                      │  │     API Gateway            │  │   │
│                      │  │     (FastAPI / Node)       │  │   │
│                      │  └─────┬──────────────────┬───┘  │   │
│                      │        │                  │       │   │
│                      │  ┌─────▼──────┐   ┌──────▼────┐  │   │
│                      │  │ RAG Engine │   │ Workflow  │  │   │
│                      │  │            │   │ Engine    │  │   │
│                      │  └─────┬──────┘   └──────────┘  │   │
│                      │        │                         │   │
│                      │  ┌─────▼──────┐  ┌───────────┐  │   │
│                      │  │ Vector DB  │  │ Ollama    │  │   │
│                      │  │ (Chroma /  │  │ (Local    │  │   │
│                      │  │  Qdrant)   │  │  LLM)     │  │   │
│                      │  └────────────┘  └───────────┘  │   │
│                      │                                  │   │
│                      │  ┌────────────────────────────┐  │   │
│                      │  │  Ingestion Pipeline         │  │   │
│                      │  │  (Parsers, OCR, Embedders)  │  │   │
│                      │  └─────────────┬──────────────┘  │   │
│                      └────────────────┼────────────────┘   │
│                                       │                     │
│  ┌──────────┐  ┌──────────┐  ┌───────▼──────┐             │
│  │ File     │  │ Email    │  │ City         │             │
│  │ Shares   │  │ Server   │  │ Databases    │             │
│  └──────────┘  └──────────┘  └──────────────┘             │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Outbound Research Proxy (optional, allowlist-only) │──►│── Internet
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Component Stack (All Open Source)

| Layer | Component | License | Purpose |
|---|---|---|---|
| LLM Runtime | Ollama | MIT | Local model serving and management |
| LLM Models | Llama 3.x, Mistral, Phi-3, Qwen 2.5 | Various (Apache 2.0, MIT, community) | Language understanding and generation |
| Embedding Model | nomic-embed-text / all-MiniLM | Apache 2.0 | Document vectorization for RAG |
| Vector Database | ChromaDB or Qdrant | Apache 2.0 | Semantic search index |
| OCR Engine | Tesseract + PaddleOCR | Apache 2.0 | Image and scanned PDF text extraction |
| PDF Processing | PyMuPDF (fitz) or pdfplumber | AGPL (PyMuPDF) / MIT (pdfplumber) | PDF text and structure extraction |
| Document Parsing | Apache Tika or Unstructured.io | Apache 2.0 | Multi-format document parsing |
| Backend API | FastAPI (Python) or NestJS (Node) | MIT (FastAPI) / MIT (NestJS) | Application server and API layer |
| Frontend | React + Tailwind CSS | MIT | Staff-facing web interface |
| Database | PostgreSQL + SQLite | PostgreSQL License / Public Domain | Application data and metadata |
| Task Queue | Celery + Redis or BullMQ + Redis | BSD (Celery) / MIT (BullMQ) / BSD (Redis) | Async ingestion and processing jobs |
| Outbound Proxy | Squid or mitmproxy | GPL (Squid) / MIT (mitmproxy) | Controlled, logged internet access |
| Containerization | Docker + Docker Compose | Apache 2.0 | Deployment and isolation |
| Auth | Keycloak or Authelia | Apache 2.0 (Keycloak) / Apache 2.0 (Authelia) | User authentication and RBAC |

**License note on PyMuPDF:** PyMuPDF's AGPL license requires that if the software is distributed or made available over a network, the complete source code of the application must also be made available. Since CivicSunshine is fully open source, this is compatible. However, the product team should evaluate pdfplumber (MIT) as the default to simplify licensing for cities that may want to make local modifications without open-sourcing them. Both should be supported as swappable backends.

**License note on Squid (GPL):** Squid is used as an isolated network proxy, not linked into the application code. Under standard GPL interpretation, this constitutes "mere aggregation" and does not require the rest of the system to be GPL. If the product team prefers a more permissive option, mitmproxy (MIT) is the alternative, though Squid is the more battle-tested choice for municipal network environments.

---

## Deployment Model

### Installation

The system ships as a Docker Compose stack with an automated install script:

1. IT staff provision a Ryzen-based machine with Ubuntu 24.04 LTS.
2. Run the install script, which installs Docker, pulls the compose stack, downloads a recommended LLM model, and starts all services.
3. Access the admin panel at `https://[machine-ip]:8443` to configure data sources, create user accounts, and set network policies.
4. Records staff access the search interface at `https://[machine-ip]:8080` from their workstations via browser.

**Target: a competent IT generalist should be able to go from bare metal to a working system in under 2 hours, following the documentation, with no prior AI or Docker experience.**

### Updates

- The system includes a self-updater that checks a public GitHub release feed (the only mandatory outbound connection, and even this can be done manually on air-gapped systems).
- Updates are delivered as new Docker image tags. `docker compose pull && docker compose up -d` applies an update.
- Database migrations are handled automatically on startup.
- LLM model updates are independent of application updates and managed through Ollama's CLI.

### Data Residency

- All data — ingested documents, vector embeddings, user accounts, audit logs, request records — lives on the local machine's storage.
- No telemetry, analytics, or usage data is collected or transmitted.
- The system has no "phone home" capability.
- Cities own their data completely and can export or destroy it at any time.

---

## Security Model

### Network Security

- The system binds to `localhost` or a city-designated internal IP only. It is never exposed to the public internet.
- HTTPS with self-signed or city-provided TLS certificates for all web interfaces.
- The outbound research proxy is disabled by default and requires explicit IT configuration to enable.
- All outbound traffic is logged, allowlisted, and auditable.

### Application Security

- Role-based access control with four tiers: Admin, Records Staff, Reviewer, Read-Only.
- Session management with configurable timeout.
- All AI interactions are logged per-user for accountability.
- No default passwords. First-run setup requires creating an admin account.
- API endpoints require authentication; no anonymous access.

### Data Security

- Ingested data is stored in local PostgreSQL and vector databases with filesystem-level encryption (LUKS or equivalent, configured at OS level by IT).
- The system does not store credentials for connected data sources in plaintext — secrets management via environment variables or a local vault.
- Audit logs are append-only and tamper-evident.

### AI Safety

- All LLM outputs are clearly labeled as AI-generated drafts requiring human review.
- The system includes a prompt injection defense layer that sanitizes document content before it enters the LLM context.
- Model outputs are constrained to the retrieval context — the system is designed to cite sources, not hallucinate answers.
- A "confidence threshold" setting lets staff control how aggressively the system surfaces low-confidence results.

---

## Open Source Strategy

### Project License

The CivicSunshine application code is released under the **Apache License 2.0**, providing:

- Freedom for any city to use, modify, and deploy without restriction.
- Patent protection for contributors and users.
- Compatibility with all dependency licenses in the stack.
- No obligation for cities to share local modifications (though contributions are welcomed and encouraged).

### Acceptable Dependency Licenses

All dependencies must carry one of the following license types:

**Permissive (preferred):**
- MIT License
- Apache License 2.0
- BSD 2-Clause or 3-Clause
- ISC License
- PostgreSQL License
- Public Domain / Unlicense / CC0

**Weak Copyleft (acceptable with documentation):**
- GNU Lesser General Public License (LGPL) v2.1 or v3
- Mozilla Public License 2.0 (MPL)
- Eclipse Public License 2.0 (EPL)

**Strong Copyleft (acceptable only for isolated/non-linked components):**
- GPL v2 or v3 — only for standalone tools (e.g., Squid proxy) that are not linked into the application code.

**Not Acceptable:**
- AGPL — unless the entire CivicSunshine codebase is itself open source (which it is, so AGPL dependencies are technically compatible, but should be avoided or flagged for review to keep the licensing story simple for municipal legal departments).
- SSPL, BSL, or any "source available" license that restricts commercial or government use.
- Any license requiring attribution beyond what is standard (e.g., "you must display our logo").

### Community Model

- Public GitHub repository with issue tracker, discussion board, and contribution guidelines.
- A municipal advisory group (city clerks, IT directors, records officers) provides input on priorities and validates releases against real-world needs.
- A "City Implementer" certification program (documentation-based, free) helps IT staff demonstrate readiness to deploy and maintain the system.

---

## Roadmap (Suggested Phases)

### Phase 1: Foundation (MVP)

**Goal:** A working system that ingests documents and answers natural-language questions against them.

- Ollama integration with recommended model selection per hardware tier.
- Document ingestion for PDF, DOCX, TXT, CSV, and images (OCR).
- ChromaDB or Qdrant vector store with hybrid search.
- React-based search interface with source attribution.
- Docker Compose deployment with install script.
- Admin panel for data source configuration and user management.
- Installation and user documentation.

**Exit criteria:** A city IT staffer can install the system, point it at a shared drive of PDFs, and a records clerk can search those documents from their browser and get useful, cited results — in one afternoon.

### Phase 2: Workflow and Compliance

**Goal:** Turn search results into managed open records responses.

- Request tracking and case management interface.
- Exemption detection engine with 50-state statute library.
- Response letter generation from templates.
- Deadline tracking and notification system.
- Review/approval workflow for supervisors.
- Audit logging for all actions.

**Exit criteria:** A records clerk can receive a request, search for responsive documents, flag exemptions, draft a response letter, route it for review, and close the case — entirely within the system.

### Phase 3: Data Integration and Outbound Research

**Goal:** Connect to live city data sources and external reference materials.

- Database connectors (PostgreSQL, MySQL, MSSQL, SQLite).
- Email server integration (IMAP).
- File share monitoring (SMB/NFS).
- SharePoint connector.
- REST API connector framework.
- Outbound research proxy with allowlist management.
- External public records database search.

**Exit criteria:** The system indexes records from multiple city departments automatically and can supplement internal search with controlled external lookups.

### Phase 4: Scale and Polish

**Goal:** Production hardening for sustained municipal use.

- Performance optimization for large document corpora (100K+ documents).
- Multi-model support with automatic fallback (smaller model for simple queries, larger model for complex analysis).
- Advanced analytics dashboard (request volume trends, response time metrics, departmental workload).
- Accessibility compliance (WCAG 2.1 AA).
- Internationalization framework (for cities with multilingual populations).
- Automated testing suite and CI/CD pipeline.
- Security audit and penetration testing documentation.

---

## Success Metrics

| Metric | Target |
|---|---|
| Time from bare metal to first successful search | < 2 hours |
| Average query-to-response time (minimum hardware) | < 30 seconds |
| Records clerk time-to-competence | < 1 hour of training |
| Responsive document recall vs. manual search | ≥ 90% |
| System cost (hardware + zero software licensing) | < $1,500 total |
| Annual operating cost (electricity + maintenance) | < $500/year |
| Uptime target (during business hours) | 99.5% |

---

## Competitive Positioning

| Dimension | CivicSunshine | Cloud-Based FOIA Tools | Manual Process |
|---|---|---|---|
| Data residency | 100% local | Vendor servers | Local but unsearchable |
| Recurring cost | $0 software | $500–$5,000/mo | Staff time |
| Setup complexity | 2 hours | Weeks (procurement + onboarding) | N/A |
| AI search capability | Full RAG | Varies | None |
| Vendor dependency | None | High | None |
| Scalability | Hardware-limited | Elastic | Staff-limited |
| Public trust | High (auditable, local) | Low (data leaves city) | Moderate |

---

## Open Questions for Product Team

1. **Model selection:** Should the MVP ship with a single recommended model (e.g., Llama 3.1 8B for minimum hardware, Llama 3.1 70B-Q4 for recommended) or support model selection from day one? Recommendation: ship with a tested default, allow swapping in admin panel.

2. **Multi-tenancy:** Should a single installation support multiple departments with isolated data? Or is a flat, city-wide knowledge base the right starting point? Recommendation: flat to start, with department-level access controls in Phase 2.

3. **Embedding model:** nomic-embed-text (via Ollama, fully local) vs. all-MiniLM-L6-v2 (via sentence-transformers, fully local). Both are Apache 2.0. Performance testing needed.

4. **Backend language:** FastAPI (Python) gives access to the richest AI/ML ecosystem. NestJS (TypeScript) offers stronger typing and may be more familiar to municipal IT contractors. Recommendation: FastAPI for Phase 1, evaluate based on contributor community.

5. **PyMuPDF vs. pdfplumber:** AGPL vs. MIT licensing trade-off. PyMuPDF is significantly faster and more capable. pdfplumber is simpler and license-clean. Recommendation: support both, default to pdfplumber, document PyMuPDF as an opt-in upgrade.

6. **Outbound proxy implementation:** Squid (GPL, battle-tested, familiar to IT) vs. mitmproxy (MIT, more flexible, better logging UI). Recommendation: Squid for v1, evaluate mitmproxy for v2.

7. **State statute library:** Building exemption rules for all 50 states is a massive undertaking. Should Phase 2 ship with a configurable framework + 5 pilot states, or attempt full coverage? Recommendation: framework + pilot states, with community contributions for the rest.

8. **Name:** "CivicSunshine" is a working title. The product team should validate naming with municipal stakeholders. Considerations: should it sound governmental, approachable, or technical?

---

## Appendix A: Relevant Legal Frameworks

Every U.S. state has its own open records statute. The system must be designed to accommodate variation across:

- **Naming:** Freedom of Information (federal + some states), Open Records, Public Records, Right to Know, Sunshine Laws.
- **Timelines:** Response deadlines range from 3 business days (some states) to 30+ days.
- **Exemption categories:** While there is substantial overlap (personnel, law enforcement, attorney-client, trade secrets, personal privacy), specific categories and their scope vary significantly.
- **Fee structures:** Some states allow cost recovery for search and copying; others do not.
- **Appeal processes:** Varies from informal to administrative to judicial.

The exemption detection engine must be state-configurable, not hardcoded to any single state's framework.

## Appendix B: Hardware Procurement Guidance

For cities that need to purchase hardware, the documentation should include:

- A specific parts list with current pricing from mainstream retailers (Amazon, Newegg, etc.).
- Pre-built system recommendations (e.g., Minisforum, Beelink, AZW mini PCs) as alternatives to custom builds.
- Network integration guidance (static IP, firewall rules, DNS).
- Physical security recommendations (locked office/closet, UPS).
- A one-page "request for purchase" template that a city IT director can hand to their purchasing department.

## Appendix C: Accessibility and Equity Considerations

- The web interface must meet WCAG 2.1 AA standards.
- The system should support multilingual search where city populations require it.
- Documentation should be written at a reading level accessible to non-technical municipal staff.
- The hardware cost target ($800–$1,200) is deliberately chosen to be within the small-purchase threshold that most cities can approve without a formal procurement process.
