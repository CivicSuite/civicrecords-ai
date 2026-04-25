"""Phase 2 — backfill prompt_templates.consumer_app for records-ai overrides

Revision ID: 020_phase2_consumer_app_backfill
Revises: 019_encrypt_connection_config
Create Date: 2026-04-25

Context
-------
civiccore's ``civiccore_0002_llm`` migration ALTERs the shared
``prompt_templates`` table to:

* rename ``name`` → ``template_name``
* add ``consumer_app VARCHAR(100) NOT NULL DEFAULT 'civiccore'``
* add ``is_override BOOLEAN NOT NULL DEFAULT false``
* drop ``UNIQUE(name)`` and add ``UNIQUE(consumer_app, template_name, version)``

After that ALTER runs against an existing records-ai DB, every existing
``prompt_templates`` row inherits ``consumer_app='civiccore'`` and
``is_override=false`` from the column defaults. But those rows were written
by records-ai (civiccore v0.2.0 ships no DB-seed templates), and the
template resolver in :func:`civiccore.llm.templates.resolve_template`
needs records-ai-owned rows to carry the records-ai consumer label so the
override registry resolves them in front of any civiccore default. Without
this backfill, records-ai prompts would never be reached by the resolver.

The backfill is intentionally a single ``UPDATE`` with no WHERE pattern
beyond ``consumer_app = 'civiccore'`` — civiccore v0.2.0 ships zero
DB-seed prompt rows, so any row currently labelled ``'civiccore'`` is
records-ai data. Idempotency: re-running this migration after the records
rows already carry ``'civicrecords-ai'`` matches zero rows and is a no-op.
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers
revision: str = "020_phase2_consumer_app_backfill"
down_revision: Union[str, None] = "019_encrypt_connection_config"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Re-label every legacy 'civiccore'-defaulted row as a records-ai override.
    # Idempotent: matches zero rows on re-run after the relabel has already happened.
    op.execute(
        """
        UPDATE prompt_templates
        SET consumer_app = 'civicrecords-ai',
            is_override = true
        WHERE consumer_app = 'civiccore'
        """
    )


def downgrade() -> None:
    # Reverse the relabel. Symmetric and equally idempotent.
    op.execute(
        """
        UPDATE prompt_templates
        SET consumer_app = 'civiccore',
            is_override = false
        WHERE consumer_app = 'civicrecords-ai'
        """
    )
