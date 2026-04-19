# CI Workflows

This directory holds the GitHub Actions workflows that gate merges into `master`.

## `ci.yml`

The single mandatory workflow. Runs on every push to `master`, every pull
request targeting `master`, and on manual dispatch from the Actions tab.

### What it does

Two jobs run in parallel:

**`backend`** — pytest via `docker compose`, matching AGENTS.md Hard Rule 1a
exactly. Three gates, in order:

1. **Collection gate** (`pytest --collect-only`). Fails on any import error,
   syntax error, or missing fixture. This is the ratchet against the specific
   failure documented in CLAUDE.md Hard Rule 1e: "423 tests passing" claimed,
   actual was 278.
2. **Full suite** (`pytest -q`). Every test must pass.
3. **Cross-check** (`collected == passed`). If the collected count and passed
   count disagree, the delta is skipped tests, xfails, errors, or tests that
   exited early. Per `feedback_never_skip_tests.md`, none of those are
   acceptable. The job fails.

On failure, `collect.log`, `run.log`, and `compose.log` are uploaded as
artifacts and kept for 14 days.

**`frontend`** — `npm ci && npm test && npm run build` on Node 22 (matching the declared prerequisite in `CONTRIBUTING.md`).

### Hermetic environment

The backend job generates a fresh `.env` file on every run with
`openssl rand -hex 32` for `JWT_SECRET`. Nothing is carried between runs;
nothing secret is stored in the workflow or in `Settings → Secrets`.

Ollama is skipped via `docker compose run --no-deps` because tests mock the
Ollama client per CLAUDE.md. Pulling the Ollama image on every run would add
~2 minutes for zero test coverage. If a future test genuinely needs Ollama,
either mock it or add the service to the `docker compose up -d --wait` line.

### Reproducing a CI failure locally

The backend commands are identical to AGENTS.md Rule 1a:

```bash
# One-time setup
cp .env.example .env
# Edit .env: set JWT_SECRET to "$(openssl rand -hex 32)"

docker compose up -d --wait postgres redis
docker compose exec -T postgres createdb -U civicrecords civicrecords_test

# Reproduce the CI checks
docker compose build api
docker compose run --rm --no-deps api python -m pytest tests --collect-only -q
docker compose run --rm --no-deps api python -m pytest tests -q
```

Frontend:

```bash
cd frontend
npm ci
npm test
npm run build
```

### Why this is PR 0

Every downstream fix in `docs/REMEDIATION-PLAN-2026-04-19.md` is silently
reversible without a ratchet. CI lands alone, first, so the rest of the
remediation work has a regression guard.

Branch protection (requiring this workflow to pass before merge) is a
one-time configuration in GitHub `Settings → Branches`. It is not managed by
this repository and must be enabled by the repo owner before any Tier 2+ PR
lands.
