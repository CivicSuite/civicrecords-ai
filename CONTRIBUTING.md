# Contributing to CivicRecords AI

Thank you for your interest in contributing to CivicRecords AI. This project helps American cities respond to open records requests using AI-powered document search — contributions that improve accuracy, coverage, or usability directly benefit municipal transparency.

## Development Setup

### Prerequisites

- **Docker Desktop** (Windows, macOS) or **Docker Engine** (Linux)
- **Python 3.12+** (for running tests locally)
- **Node.js 22+** (for frontend development)
- **Git**

### Getting Started

```bash
# Clone the repository
git clone https://github.com/scottconverse/civicrecords-ai.git
cd civicrecords-ai

# Create environment file
cp .env.example .env
# Edit .env — set JWT_SECRET (generate with: openssl rand -hex 32)

# Start all services
docker compose up -d

# Run database migrations
docker compose run --rm api alembic upgrade head

# Pull the embedding model
docker compose exec ollama ollama pull nomic-embed-text

# Verify it works
curl http://localhost:8000/health
# Open http://localhost:8080 in your browser
```

### Running Tests

```bash
cd backend

# Install dev dependencies
pip install -e ".[dev]"
pip install psycopg2-binary

# Ensure PostgreSQL is accessible on localhost:5432
# (use docker-compose.dev.yml to expose the port)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d postgres

# Run all tests
DATABASE_URL=postgresql+asyncpg://civicrecords:civicrecords@localhost:5432/civicrecords \
  python -m pytest tests/ -v
```

### Frontend Development

```bash
cd frontend
npm install
npm run dev    # Starts Vite dev server with hot reload
npm run build  # Production build
npx tsc --noEmit  # Type check
```

## How to Contribute

### Reporting Bugs

Open a GitHub Issue with:
- What you expected to happen
- What actually happened
- Steps to reproduce
- Your OS and Docker version

### Suggesting Features

Open a GitHub Discussion in the Ideas category. Describe:
- The problem you're trying to solve
- Your proposed solution
- Who benefits from it

### Submitting Code

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/your-feature`
3. Make your changes following the coding standards below
4. Write or update tests for your changes
5. Run the full test suite and ensure it passes
6. Commit with conventional commit messages: `feat:`, `fix:`, `docs:`, `chore:`
7. Push and open a Pull Request

### Coding Standards

**Python (Backend)**
- Follow existing patterns in the codebase
- Type hints on all public functions
- Use async/await consistently
- Every API endpoint must be audit-logged
- Every endpoint must use `require_role()` for authorization

**TypeScript (Frontend)**
- Strict mode enabled
- No `any` types except in catch blocks
- Use react-router `Link` for navigation (not `<a href>`)
- Every page needs loading, error, and empty states
- Add `aria-label` to interactive elements and tables

**Tests**
- Unit tests for pure logic (parsers, chunking, rules engine)
- Integration tests for API endpoints
- Mock external services (Ollama) in tests
- Use existing fixtures from `tests/conftest.py`

**Commits**
- One logical change per commit
- Conventional commit format: `feat:`, `fix:`, `docs:`, `chore:`, `test:`
- Run tests before committing

## Licensing

All dependencies must use permissive (MIT, Apache 2.0, BSD) or weak-copyleft (LGPL, MPL, EPL) licenses. No AGPL, SSPL, or BSL dependencies.

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.

## State Exemption Rules

A high-value contribution area: adding exemption rule sets for additional states. Each state has its own open records statute with specific exemption categories. See `backend/scripts/seed_rules.py` for the Colorado CORA example format.

## Questions?

Open a GitHub Discussion or reach out to the maintainers. We're happy to help you get started.
