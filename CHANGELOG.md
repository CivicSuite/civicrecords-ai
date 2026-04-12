# Changelog

All notable changes to CivicRecords AI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
