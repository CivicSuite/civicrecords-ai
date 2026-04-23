"""T6 / ENG-001 — operator verification script for at-rest encryption.

Checks that every row in ``data_sources`` stores its ``connection_config``
as the v1 versioned envelope ``{"v": 1, "ct": "..."}``. A single plaintext
row is a Tier-6 compliance break.

Usage (from repo root):

    docker compose run --rm --no-deps api python scripts/verify_at_rest.py

Exit codes:

    0 — every row is encrypted.
    1 — at least one row is not encrypted (plaintext or unknown shape).
    2 — unexpected runtime error (DB unreachable, etc.).

This script is intended as a post-deploy sanity check. The Alembic
migration ``019_encrypt_connection_config`` runs automatically on
startup; running this afterward is belt-and-suspenders verification that
all rows actually landed in the encrypted shape.

Does NOT decrypt any row. Only inspects the envelope shape. That means
it succeeds even if the operator's encryption key has since been
rotated or lost — it is purely a shape check, not a correctness check.
"""
from __future__ import annotations

import asyncio
import json
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings
from app.security.at_rest import is_encrypted


async def _main() -> int:
    engine = create_async_engine(settings.database_url, echo=False)
    total = 0
    ok = 0
    bad: list[tuple[str, str]] = []
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT id, connection_config FROM data_sources")
            )
            for row in result:
                total += 1
                cfg = row.connection_config
                if isinstance(cfg, str):
                    # Defensive: asyncpg may return JSONB as string in some
                    # configurations. Parse and re-check.
                    cfg = json.loads(cfg)
                if is_encrypted(cfg):
                    ok += 1
                else:
                    # Surface the row id and the keys (not values) of the
                    # offending dict so operators have something actionable
                    # without leaking plaintext credentials into the output.
                    if isinstance(cfg, dict):
                        shape = "dict with keys " + ", ".join(sorted(cfg.keys())[:10])
                    else:
                        shape = type(cfg).__name__
                    bad.append((str(row.id), shape))
    finally:
        await engine.dispose()

    print(f"data_sources rows inspected: {total}")
    print(f"  encrypted (v1 envelope):   {ok}")
    print(f"  NOT encrypted:             {len(bad)}")
    if bad:
        print("")
        print("Offending rows (id + value shape; values NOT printed):")
        for row_id, shape in bad:
            print(f"  {row_id}  ->  {shape}")
        print("")
        print(
            "To remediate: re-run the Alembic migration, which is "
            "idempotent — it will skip already-encrypted rows and "
            "encrypt the remainder:"
        )
        print(
            "    docker compose run --rm --no-deps api "
            "python -m alembic upgrade head"
        )
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(_main()))
    except Exception as exc:  # noqa: BLE001 — operator-facing tool
        print(f"verify_at_rest: unexpected error: {exc}", file=sys.stderr)
        sys.exit(2)
