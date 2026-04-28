#!/usr/bin/env python3
"""Generate the OpenAPI JSON schema from the FastAPI app.

Requires no live database connection — FastAPI introspects routes and
Pydantic models at import time.

Usage
-----
Via Docker (recommended — all deps pre-installed):

    docker compose run --rm --no-deps api \\
        python scripts/generate_openapi.py > docs/openapi.json

From backend/ with a local Python env:

    # Linux/macOS: stdout redirect gives correct UTF-8 + LF
    python scripts/generate_openapi.py > ../docs/openapi.json

    # Windows (PowerShell): stdout redirect adds BOM; use the -o flag instead
    python scripts/generate_openapi.py -o ../docs/openapi.json

After updating docs/openapi.json, regenerate frontend types:

    cd frontend && npm run generate:types
"""

import json
import os
import sys
from pathlib import Path

# Ensure backend/ (the parent of this scripts/ dir) is on sys.path so that
# `from app.main import app` resolves whether the script is invoked from the
# repo root, from backend/, or from inside the Docker container (/app).
_backend_root = Path(__file__).resolve().parent.parent
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))

# ---------------------------------------------------------------------------
# Provide placeholder values so app.config.Settings() can be instantiated
# at import time without live infrastructure. The validators only reject
# the documented insecure defaults; these values are not used beyond import.
# ---------------------------------------------------------------------------
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://x:x@localhost:5432/x",
)
os.environ.setdefault(
    "JWT_SECRET",
    # 64-char hex string — not in _INSECURE_SECRETS, not the empty default
    "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
)
os.environ.setdefault("FIRST_ADMIN_EMAIL", "admin@localhost")
os.environ.setdefault(
    "FIRST_ADMIN_PASSWORD",
    # ≥ 12 chars, not in _INSECURE_PASSWORDS
    "SchemaGen-CIonly-99!",
)
os.environ.setdefault(
    "ENCRYPTION_KEY",
    # 32 zero bytes as URL-safe base64. Valid Fernet shape for import-time
    # schema generation only; no live data is encrypted during OpenAPI export.
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
)

from app.main import app  # noqa: E402 — env must be set before this import

schema = app.openapi()
output = json.dumps(schema, indent=2) + "\n"

# -o <path>: write to file with explicit UTF-8 no-BOM + LF (safe on Windows).
# Default: write to stdout (works correctly on Linux/macOS and in Docker).
if "-o" in sys.argv:
    out_path = Path(sys.argv[sys.argv.index("-o") + 1])
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(output)
    print(f"Wrote {out_path.stat().st_size} bytes to {out_path}", file=sys.stderr)
else:
    sys.stdout.write(output)
