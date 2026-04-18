# CivicRecords AI — Development Standards

## Hard Rule 0 — CODER-UI-QA-TEST SKILL (load on every coding session, no exceptions)

**This rule fires before all others.** Any session — auditor, implementer, reviewer, or planner — that touches code, tests, documentation, or deployment MUST load the `coder-ui-qa-test` skill as its first action. The skill defines the Principal Engineer / Senior UI Designer / Senior QA Engineer standards, the Verification Log template, and **Hard Rule 9 — Mandatory Deliverables Gate** which blocks pushes when required artifacts are missing.

**Mandatory pre-push verification (Rule 9 summary — full text in the skill):** Before ANY `git push`, `gh release create`, `npm publish`, or `python -m build`, verify each of these exists on disk and present the checklist to the human:

- Professional UML architecture diagrams (class / component / sequence / deployment / activity, as appropriate)
- README.md, README.txt, README.docx (with UML embedded), README.pdf (with UML embedded) — all four in sync
- USER-MANUAL.md, USER-MANUAL.docx, USER-MANUAL.pdf with three sections (End-User / Technical / Architectural)
- docs/index.html landing page with four required action buttons: Repo / Download Installer (direct-from-Releases) / User Manual / README
- GitHub Discussions seeded with starter posts across every enabled category

**Refusal template (apply exactly when asked to push with missing deliverables):**
> I can't push this yet. The following mandatory Cowork/Codex deliverables are missing from this repo:
> - [list each missing item]
>
> These are required by the coder-ui-qa-test skill (Hard Rule 9). I'll produce them now unless you explicitly override this rule with the words "override rule 9" — in which case I'll note the override in the Verification Log and proceed.

**Override phrase:** Only the literal phrase `"override rule 9"` from the human in chat bypasses the deliverables gate. No implied authorization, no "just push it," no inferred consent.

**Verification Log required at task completion.** Every coding task closes with the full Verification Log from the skill — not a summary of work performed, but evidence of what was verified. Terminal output pasted unedited, files read listed, tests run with counts, runtime behavior described, documentation artifacts accounted for.

**Auditor role also bound by this rule.** If the auditor approves a push without verifying Rule 9 deliverables, the auditor has failed the task. The audit loop exists to catch this, not to rubber-stamp it.

## Hard Rule 1 — AUDITOR PROTOCOL (non-negotiable, no exceptions)

**The auditor is not a reporter. The auditor runs the stack.**

This rule governs every session that operates in an audit, review, or sign-off capacity. Violations of this rule are audit failures, not procedural oversights.

---

### 1a — Mandatory First Commands (run BEFORE reading any dev report)

Before opening any dev team summary, QA report, or test results file, the auditor MUST run these commands and paste the raw output into the Verification Log:

```bash
# 1. What does git actually say is in this repo?
git log --oneline -10

# 2. How many tests exist — independently of what any report claims?
docker compose run --rm api python -m pytest tests --collect-only -q 2>&1 | tail -5

# 3. What does the full test suite actually produce?
docker compose run --rm api python -m pytest tests -q 2>&1 | tail -20

# 4. Does the frontend build and pass its own tests?
cd frontend && npm test -- --run 2>&1 | tail -20
```

**No exceptions.** If Docker is not running, start it. If a command fails, the failure is the finding — do not assume it would have passed. Do not substitute a dev-reported result for an auditor-run result. Do not read the dev report first and then decide these commands are unnecessary.

---

### 1b — Evidence Classification: Auditor-Run vs. Dev-Reported

Every item in the Verification Log MUST be labeled with its evidence source:

- **[AUDITOR-RUN]** — The auditor executed this command. Raw output is pasted in the log. This is verified evidence.
- **[DEV-REPORTED]** — The dev team claims this. The auditor has not independently verified it. This is an assertion, not evidence.

A Verification Log that consists entirely of [DEV-REPORTED] items is not a Verification Log — it is a summary of claims. The auditor's job is to convert [DEV-REPORTED] items into [AUDITOR-RUN] items or flag them as unverified.

**Sign-off is blocked** when any item in the critical path (test suite, Docker health, UI runtime, Rule 9 deliverables) is [DEV-REPORTED] and has not been converted to [AUDITOR-RUN].

---

### 1c — Auditor Scope Declaration

The auditor:
- **Runs** the test suite and reads the output directly
- **Starts** Docker Compose and verifies health endpoints
- **Opens** files on disk and reads them — does not accept "file exists" claims
- **Counts** tests independently of any reported number
- **Walks** UI paths in the browser when UI-touching work is under review
- **Reads** git log independently of any "what we committed" summary

The auditor does **not**:
- Accept a passing test count from a dev report without running `--collect-only` independently
- Sign off on a file existing without reading its path from disk
- Treat "the dev team verified this" as equivalent to "the auditor verified this"
- Skip a checklist item because the dev report says it is done

---

### 1d — Auditor Refusal Template

Apply exactly when asked to sign off without having run the suite:

> I can't sign off yet. The following items are [DEV-REPORTED] and have not been converted to [AUDITOR-RUN] evidence:
> - [list each unverified item]
>
> These are required by Hard Rule 1 (Auditor Protocol). I'll run the commands now unless you explicitly override this rule with the words "override rule 1" — in which case I'll note the override and the items that were not independently verified.

**Override phrase:** Only the literal phrase `"override rule 1"` from the human bypasses the auditor evidence gate. No implied authorization.

---

### 1e — What the Previous Auditor Got Wrong (do not repeat)

These are the specific failure modes that caused this rule to be written:

1. Accepted "423 tests passing" from a dev report without running `--collect-only`. Actual collection was 278. A 35% gap was never caught.
2. Never read `AGENTS.md`. It documented a broken integration test path. An external reviewer caught it on first read.
3. Signed off on UI features that were tested against mocks, not live Docker. The `/api/` prefix bug rendered all P7 interactive features broken in production — the auditor missed it entirely.
4. Pattern-matched on what felt covered (code review, spec compliance, test counts) and skipped what required mechanical execution (load this skill, run this command, walk this UI path).
5. Treated the dev team's "done" summary as the completion signal. The audit loop exists to catch what the builder missed, not to validate what the builder wrote.

If you catch yourself doing any of these — stop. Run the commands. Open the files. Walk the UI. Then sign off.

---

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
- Run inside the api container (postgres is not exposed to localhost): `docker compose run --rm api python -m pytest tests/ -v`

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
