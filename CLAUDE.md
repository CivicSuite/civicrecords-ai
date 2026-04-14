# CivicRecords AI — Development Standards

## Hard Rule 10 — CONTEXT-MODE HARD GATE (active in every session)

**Context-mode is a hard gate — not a suggestion.** When the context-mode plugin is loaded, every operation MUST follow the 4-Stage Context-Mode Protocol below. This is non-negotiable. If you catch yourself about to use Bash for a command that produces output, STOP and use context-mode instead. If you catch yourself using Read to analyze a file you won't edit, STOP and use ctx_execute_file instead.

**THE 4-STAGE CONTEXT-MODE PROTOCOL:**

**Stage 1 — GATHER:** All research, exploration, multi-command operations → `ctx_batch_execute(commands, queries)`. This is the PRIMARY tool. One call replaces many individual steps. Use it FIRST for any new investigation.

**Stage 2 — FOLLOW-UP:** All follow-up questions on previously gathered data → `ctx_search(queries: ["q1", "q2", ...])`. One call, multiple queries. Never make separate ctx_search calls when you can batch them.

**Stage 3 — PROCESS:** All data processing, log analysis, file analysis, API calls → `ctx_execute(language, code)` or `ctx_execute_file(files, language, code)`. Raw data stays in the sandbox. Only your printed summary enters context.

**Stage 4 — WRITE:** All file creation and modification → Native `Write` and `Edit` tools ONLY. Never use ctx_execute to create, modify, or overwrite files. ctx_execute is for reading and analysis; Write/Edit are for mutations.

**WHAT IS FORBIDDEN:**
- Bash for ANY command producing >20 lines of output
- Read for file analysis (use ctx_execute_file) — Read is ONLY for files you are about to Edit
- WebFetch (use ctx_fetch_and_index instead)
- ctx_execute or ctx_execute_file to create/modify/overwrite files
- Dumping test output into context via Bash — ALWAYS use ctx_execute
- Running git log, git diff, npm test, pytest, or any CLI that returns data via Bash

**WHAT IS ALLOWED via native Bash:**
- git add, git commit, git push, git checkout, git branch, git merge (write operations)
- mkdir, rm, mv, cp, touch, chmod (file mutations)
- cd, pwd, which, echo, printf (navigation and simple output)
- npm install, pip install (package management)

**REFUSAL TEMPLATE — use this exact language when tempted to skip:**
"I need to use context-mode for this operation. Running [command] via Bash would dump [estimated size] into the context window. Using [ctx tool] instead keeps only the summary in context."

**If context-mode tools are unavailable:** State clearly "Context-mode tools are not responding. I cannot proceed with large-output operations until the plugin is restored." Do NOT fall back to Bash as a workaround.

**NEVER dismiss context-mode hook reminders.** They exist because the default reflex is wrong. Every reminder is a signal that the wrong tool was about to be used.

**Enforcement:** A PreToolUse hook at `~/.claude/hooks/context-mode-gate.sh` matches `Bash` commands against a forbidden-verb list (git log, git diff, pytest, grep, find, cat, head, tail, ls -la, docker logs, etc.). Matches exit with code 2 and return the `[HARD-RULE-10]` message above. This is a Level 3 blocking gate, not advisory — the tool call physically does not complete when the forbidden pattern is detected.

**Override phrase:** To bypass this gate for a single operation, the human must say the literal phrase `"override hard rule 10"`. The model should never self-authorize a bypass.

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

## Post-Push Verification

After every `git push`, verify the remote state matches what you expect — not the git output, the actual result:
- `git log origin/master --oneline -3` to confirm commits landed
- `git diff HEAD origin/master` to confirm nothing diverged
- If a specific file matters, verify it exists on remote

Same principle applies to all deployment actions: verify the outcome, not the action. Seed scripts must be run against the production database and verified in the running UI. Connectors must be wired into the pipeline with integration tests. Code that exists but has no caller is not shipped.

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
