"""P6a: connector_type column, partial UNIQUE indexes, updated_at, dedup structured docs

Revision ID: 014_p6a_idempotency
Revises: 013_connector_types
Create Date: 2026-04-17

NOTE: As of 2026-04-17, no production rows have source_type IN ('rest_api', 'odbc').
The dedup step is defensive — it will find 0 rows to remove in a clean deployment.
Verify before running on any deployment that has ingested REST/ODBC data.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '014_p6a_idempotency'
down_revision: Union[str, None] = '013_connector_types'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add connector_type column to documents (denormalized from data_sources.source_type)
    op.add_column(
        "documents",
        sa.Column("connector_type", sa.String(20), nullable=True),
    )

    # 2. Add updated_at column to documents
    op.add_column(
        "documents",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 3. Backfill connector_type from data_sources
    op.execute("""
        UPDATE documents d
        SET connector_type = ds.source_type
        FROM data_sources ds
        WHERE d.source_id = ds.id
    """)

    # 4. Dedup structured source docs: for (source_id, source_path) dupes,
    #    keep the row with the latest ingested_at. This is defensive — see note above.
    op.execute("""
        DELETE FROM documents d1
        WHERE d1.connector_type IN ('rest_api', 'odbc')
          AND EXISTS (
            SELECT 1 FROM documents d2
            WHERE d2.source_id = d1.source_id
              AND d2.source_path = d1.source_path
              AND (d2.ingested_at > d1.ingested_at
              OR (d2.ingested_at = d1.ingested_at AND d2.id > d1.id))
          )
    """)

    # 5. Add source_path max length constraint (2048 chars)
    op.create_check_constraint(
        "chk_source_path_length",
        "documents",
        "source_path IS NULL OR length(source_path) <= 2048",
    )

    # 6. Partial UNIQUE index for binary connectors: dedup by (source_id, file_hash)
    #    Excludes structured connectors (rest_api, odbc).
    op.create_index(
        "uq_documents_binary_hash",
        "documents",
        ["source_id", "file_hash"],
        unique=True,
        postgresql_where=sa.text("connector_type NOT IN ('rest_api', 'odbc')"),
    )

    # 7. Partial UNIQUE index for structured connectors: dedup by (source_id, source_path)
    op.create_index(
        "uq_documents_structured_path",
        "documents",
        ["source_id", "source_path"],
        unique=True,
        postgresql_where=sa.text("connector_type IN ('rest_api', 'odbc')"),
    )


def downgrade() -> None:
    op.drop_index("uq_documents_structured_path", table_name="documents")
    op.drop_index("uq_documents_binary_hash", table_name="documents")
    op.drop_constraint("chk_source_path_length", "documents", type_="check")
    op.drop_column("documents", "updated_at")
    op.drop_column("documents", "connector_type")
