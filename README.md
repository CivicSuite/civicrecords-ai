# CivicRecords AI

**Open-source, locally-hosted AI that helps American cities respond to open records requests.**

CivicRecords AI runs entirely on a single machine inside your city's network — no cloud subscriptions, no vendor lock-in, no resident data leaving the building. It ingests your city's documents, makes them searchable with AI-powered natural language queries, detects potential exemptions, and manages the full request lifecycle from intake to response.

## Why This Exists

Every city in America processes open records requests (FOIA, CORA, and state equivalents). Staff manually search file shares, email archives, and databases — then review every document for exemptions before release. It's slow, error-prone, and a growing burden as request volumes increase.

No open-source tool exists for the **responder side** of open records at the municipal level. CivicRecords AI fills that gap.

## Key Features

- **AI-Powered Search** — Natural language hybrid search (semantic + keyword) across all ingested city documents with source attribution and confidence scores
- **Document Ingestion** — Automatic parsing of PDF, DOCX, XLSX, CSV, email, HTML, and text files. Scanned documents processed via multimodal AI (Gemma 4) with Tesseract OCR fallback
- **Exemption Detection** — Rules-based PII detection (SSN, phone, email, credit card) plus per-state statutory keyword matching. Optional LLM secondary review. All flags require human confirmation
- **Request Management** — Full lifecycle tracking: intake, search, document attachment, review, approval, response. Deadline alerts for approaching and overdue requests
- **Compliance by Design** — Hash-chained audit logs, human-in-the-loop enforcement, AI content labeling, data sovereignty verification. Designed for Colorado CAIA and 50-state regulatory compliance
- **Federation-Ready** — REST API with service accounts enables future cross-jurisdiction record discovery between CivicRecords AI instances

## Quick Start

### Requirements

- **Docker Desktop** (Windows 10/11, macOS 13+) or **Docker Engine** (Linux)
- **8+ CPU cores**, **32 GB RAM**, **50 GB free disk space**
- No internet connection required after initial setup

### Install

**Windows:**
```powershell
git clone https://github.com/scottconverse/civicrecords-ai.git
cd civicrecords-ai
.\install.ps1
```

**macOS / Linux:**
```bash
git clone https://github.com/scottconverse/civicrecords-ai.git
cd civicrecords-ai
bash install.sh
```

### First Use

1. Open **http://localhost:8080** in your browser
2. Sign in with the admin credentials you configured in `.env`
3. Go to **Sources** → **Add Source** → enter a directory path to your documents
4. Click **Ingest Now** — documents are parsed, chunked, and indexed automatically
5. Go to **Search** — type a natural language query and get cited results

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Browser    │────▶│   nginx     │────▶│   FastAPI    │
│  (React UI) │     │  (frontend) │     │   (API)      │
└─────────────┘     └─────────────┘     └──────┬───────┘
                                               │
                    ┌──────────────────────────┤
                    │              │            │
              ┌─────▼─────┐ ┌────▼────┐ ┌─────▼─────┐
              │ PostgreSQL │ │  Redis  │ │  Ollama   │
              │ + pgvector │ │ (queue) │ │  (LLM)    │
              └───────────┘ └─────────┘ └───────────┘
                                  │
                            ┌─────▼─────┐
                            │  Celery   │
                            │ (worker)  │
                            └───────────┘
```

**7 Docker services:** PostgreSQL 17 + pgvector, Redis 7.2, Ollama, FastAPI, Celery worker, Celery beat, nginx frontend.

**Tech stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, React 18, Tailwind CSS, Alembic, Celery, pgvector, nomic-embed-text, Gemma 4 (recommended).

## Configuration

All configuration is via environment variables in `.env`:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://civicrecords:civicrecords@postgres:5432/civicrecords` |
| `JWT_SECRET` | Secret key for JWT tokens | (must be set) |
| `FIRST_ADMIN_EMAIL` | Initial admin account email | `admin@example.gov` |
| `FIRST_ADMIN_PASSWORD` | Initial admin account password | (must be set) |
| `OLLAMA_BASE_URL` | Ollama API endpoint | `http://ollama:11434` |
| `REDIS_URL` | Redis connection string | `redis://redis:6379/0` |
| `AUDIT_RETENTION_DAYS` | Audit log retention period | `1095` (3 years) |

## User Roles

| Role | Permissions |
|------|-------------|
| **Admin** | Full access: user management, system config, rule management, audit logs |
| **Staff** | Search, create requests, attach documents, scan for exemptions, review flags |
| **Reviewer** | Everything Staff can do + approve/reject responses |
| **Read-Only** | View search results and request status only |

## Supported Platforms

- Windows 10/11 (Docker Desktop)
- macOS 13+ (Docker Desktop)
- Ubuntu 22.04+ / Debian 12+ (Docker Engine)

All platforms use identical Docker containers — the application runs in Linux containers regardless of host OS.

## Data Sovereignty

CivicRecords AI is designed for environments where resident data must never leave the network:

- Runs entirely on local hardware — no cloud dependencies
- No telemetry, analytics, or crash reporting
- All LLM inference runs locally via Ollama
- Verification script confirms no outbound connections: `bash scripts/verify-sovereignty.sh`

## License

Apache License 2.0 — see [LICENSE](LICENSE).

All dependencies use permissive (MIT, Apache 2.0, BSD) or weak-copyleft (LGPL, MPL) licenses. No AGPL, SSPL, or BSL dependencies.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, coding standards, and how to submit changes.

## Status

**v0.1.0** — Feature-complete initial release. All 5 sub-projects implemented:

1. Foundation (Docker, auth, audit logging)
2. Ingestion Pipeline (7 parsers, chunking, embeddings)
3. RAG Search Engine (hybrid search, LLM synthesis)
4. Request Tracking (workflow, deadlines, document caching)
5. Exemption Detection (rules engine, LLM suggestions, compliance templates)

80 automated tests passing. Tested on Windows 11 with Docker Desktop.
