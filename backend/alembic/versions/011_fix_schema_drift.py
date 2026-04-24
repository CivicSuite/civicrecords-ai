"""fix schema drift: notification_log.subject/body and exemption_rules.version

Revision ID: 011_fix_drift
Revises: 010_remove_sent
Create Date: 2026-04-14

Adds three columns that exist in the SQLAlchemy model definitions but were never
added to the database schema by an earlier Alembic migration.

Background
----------
This drift was discovered during end-to-end manual verification of the SENT
removal work in migration 010. The "Mark Fulfilled" button (RequestDetail.tsx)
had been pointing at a non-existent endpoint and 404'ing on every click since
it was written, which meant nothing in the UI had ever successfully reached the
notification dispatch path. Once the button was fixed to PATCH the request to
status='fulfilled', the dispatch path finally ran and immediately produced:

    sqlalchemy.exc.ProgrammingError: column "subject" of relation
    "notification_log" does not exist

Audit of all 15 model files against all 9 prior migrations found two drift
instances:

1. notification_log
   - Model declares: subject (String 500, nullable), body (Text, nullable)
   - Migration 787207afc66a (which created the table) defines neither
   - No subsequent migration adds them
   - Result: notification dispatch INSERTs fail with UndefinedColumnError

2. exemption_rules
   - Model declares: version (Integer, default=1)
   - Migration 006_exemptions (which created the table) does not include it
   - No subsequent migration adds it
   - Result: any path that reads or writes ExemptionRule.version would fail
     against the live DB. The integration test suite uses create_all() against
     the model definitions and so does not surface this drift.

The disclosure_templates.version column was checked and is correctly present
in the live schema. Everything else is clean per the wider drift audit.

Why the test suite missed this
------------------------------
Integration test fixtures synthesize the schema from SQLAlchemy model metadata
via create_all(), bypassing the migration history entirely. Tests therefore see
a schema that matches the models, while the live dev database — built by
walking migrations — does not. Both drift instances ship to every operator
install whose database was created via Alembic.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

from civiccore.migrations.guards import idempotent_add_column


# revision identifiers
revision: str = '011_fix_drift'
down_revision: Union[str, None] = '010_remove_sent'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. notification_log.subject — nullable VARCHAR(500), matches the model.
    op.add_column(
        "notification_log",
        sa.Column("subject", sa.String(length=500), nullable=True),
    )

    # 2. notification_log.body — nullable TEXT, matches the model.
    op.add_column(
        "notification_log",
        sa.Column("body", sa.Text(), nullable=True),
    )

    # 3. exemption_rules.version — INTEGER NOT NULL with server_default '1'.
    #    server_default ensures any pre-existing rows backfill cleanly. The
    #    model declares default=1 (Python-side) so new ORM inserts will also
    #    pass an explicit value.
    #    SHARED table (exemption_rules is CivicCore-owned) — guarded.
    idempotent_add_column(
        "exemption_rules",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    # Drop in reverse order. Safe to drop because these columns were never
    # supposed to be missing in the first place — restoring the drifted state
    # is what "downgrade" means here, and these columns hold no data that
    # predates the upgrade.
    op.drop_column("exemption_rules", "version")
    op.drop_column("notification_log", "body")
    op.drop_column("notification_log", "subject")
