"""Encrypt data_sources.connection_config at rest (Tier 6 / ENG-001).

T2B closed the runtime-exposure side of connector credentials (redacted
from staff-role responses via `DataSourceRead`). ENG-001 remained open
for the at-rest side: plaintext JSON in the `connection_config` column
was still visible to any operator with DB access — `pg_dump` output,
restored snapshots, Postgres superuser sessions, SQL-level backups.

This migration closes that gap. The column stays JSONB in Postgres; the
cell contents become the versioned envelope
``{"v": 1, "ct": "<fernet-token>"}`` produced by
:mod:`app.security.at_rest`. Runtime code continues to see a plain dict
thanks to the ``EncryptedJSONB`` TypeDecorator on the SQLAlchemy column.

Properties:

* **Reversible.** ``upgrade()`` encrypts every plaintext row.
  ``downgrade()`` decrypts every envelope row back to plaintext.
* **Idempotent.** Both directions skip rows that already match the
  target shape. Re-running ``upgrade`` on an already-encrypted table is
  a no-op; same for ``downgrade`` on an already-decrypted one.
* **Key-required in both directions.** The operator must have
  ``ENCRYPTION_KEY`` set for EITHER direction. Downgrade
  with a missing/rotated key fails loudly rather than silently wiping
  data.

Operator rollout note (also documented in USER-MANUAL.md): set the
encryption key env var BEFORE restarting the app. The migration runs
on startup (see `app.main.lifespan`); a missing key causes the fail-fast
check in `Settings.check_encryption_key` to raise before any row is
touched.

Revision ID: 019_encrypt_connection_config
Revises: 018_city_profile_state_nullable
Create Date: 2026-04-23
"""
from __future__ import annotations

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.security.at_rest import decrypt_json, encrypt_json, is_encrypted

revision: str = '019_encrypt_connection_config'
down_revision: Union[str, None] = '018_city_profile_state_nullable'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _iter_rows(conn):
    """Yield (id, connection_config_dict) for every row in data_sources.

    Using raw SQL (not the ORM) so the migration is not coupled to the
    live EncryptedJSONB TypeDecorator state. We want to see the actual
    stored JSON, whatever shape it's in right now, and decide per-row.
    """
    result = conn.execute(
        sa.text("SELECT id, connection_config FROM data_sources")
    )
    for row in result:
        # asyncpg/psycopg both return JSONB as a parsed Python dict by
        # default, but be defensive: if we somehow got a string, parse it.
        cfg = row.connection_config
        if isinstance(cfg, str):
            cfg = json.loads(cfg)
        yield row.id, cfg


def _write_row(conn, row_id, new_value) -> None:
    conn.execute(
        sa.text(
            "UPDATE data_sources SET connection_config = "
            "CAST(:cfg AS JSONB) WHERE id = :id"
        ),
        {"cfg": json.dumps(new_value), "id": row_id},
    )


def upgrade() -> None:
    """Encrypt every plaintext row. Skip already-encrypted rows."""
    conn = op.get_bind()
    encrypted = 0
    skipped = 0
    for row_id, cfg in _iter_rows(conn):
        if is_encrypted(cfg):
            skipped += 1
            continue
        # A non-dict plaintext here would be a pre-existing data
        # integrity issue (the column contract is "JSON object"). Raise
        # loudly so the migration fails fast rather than silently
        # encrypting garbage.
        if not isinstance(cfg, dict):
            raise RuntimeError(
                f"data_sources.id={row_id}: connection_config is not a "
                f"dict ({type(cfg).__name__}). Fix the offending row "
                "before rerunning the T6 migration."
            )
        _write_row(conn, row_id, encrypt_json(cfg))
        encrypted += 1
    # Leave breadcrumbs in the alembic log so operators can verify.
    print(
        f"[019_encrypt_connection_config] upgrade complete: "
        f"encrypted={encrypted}, skipped_already_encrypted={skipped}"
    )


def downgrade() -> None:
    """Decrypt every envelope row back to plaintext. Skip already-plaintext."""
    conn = op.get_bind()
    decrypted = 0
    skipped = 0
    for row_id, cfg in _iter_rows(conn):
        if not is_encrypted(cfg):
            skipped += 1
            continue
        _write_row(conn, row_id, decrypt_json(cfg))
        decrypted += 1
    print(
        f"[019_encrypt_connection_config] downgrade complete: "
        f"decrypted={decrypted}, skipped_already_plaintext={skipped}"
    )
