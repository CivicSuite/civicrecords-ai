# CivicRecords AI — Development Standards

## Project

Open-source, locally-hosted AI system for municipal open records request processing.
Apache 2.0 licensed. Python/FastAPI backend, React/shadcn/ui frontend, PostgreSQL+pgvector, Ollama.

## Testing Requirements

Every sub-project must pass ALL verification gates before merge:

### Unit Tests
- Run with `cd backend && python -m pytest tests/ -v` (no Docker required for pure unit tests)
- Parser, chunker, embedder tests must pass without a database
- Integration tests (auth, audit, admin, datasources, documents) require PostgreSQL

### Integration Tests
- Require Docker: `docker compose up -d postgres redis`
- Create test database: `docker compose exec postgres createdb -U civicrecords civicrecords_test`
- Run: `DATABASE_URL=postgresql+asyncpg://civicrecords:civicrecords@localhost:5432/civicrecords_test python -m pytest tests/ -v`

### Docker Verification
- `docker compose build` must succeed with no errors
- `docker compose up -d` must start all services healthy
- `curl http://localhost:8000/health` must return `{"status": "ok"}`
- `curl http://localhost:8000/docs` must serve OpenAPI docs

### Frontend Verification
- `cd frontend && npm install && npm run build` must succeed
- No TypeScript errors
- Login page renders, dashboard loads, navigation works

### QA Checklist (before merge)
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Docker Compose starts all services
- [ ] API health endpoint responds
- [ ] Frontend builds without errors
- [ ] Spec/docs match implemented code (feature counts, endpoint names, etc.)
- [ ] No hardcoded secrets or credentials in code
- [ ] Audit logging verified (actions create log entries)

## Code Standards

- Python: Follow existing patterns. Use async/await consistently. Type hints on all public functions.
- TypeScript: Strict mode. No `any` types except in catch blocks.
- Tests: Unit tests for pure logic, integration tests for API endpoints, mocked external services (Ollama).
- Commits: Conventional commits (`feat:`, `fix:`, `chore:`, `docs:`).

## Architecture

See `docs/UNIFIED-SPEC.md` for the canonical spec (single source of truth).

### Key Constraints
- All dependencies must be permissive or weak-copyleft licensed (MIT, Apache 2.0, BSD, LGPL, MPL)
- Redis pinned to <8.0.0 (BSD licensed; 8.x changed licensing)
- No telemetry, analytics, or outbound data transmission
- Human-in-the-loop enforced at API layer (no auto-redaction, no auto-denial)
- Audit logging is a legal compliance requirement, not optional

## Docker Services

1. `postgres` — PostgreSQL 17 + pgvector
2. `redis` — Redis 7.2 (BSD)
3. `ollama` — Local LLM runtime
4. `api` — FastAPI backend (port 8000)
5. `worker` — Celery async tasks
6. `beat` — Celery beat scheduler
7. `frontend` — React admin panel (port 8080)
