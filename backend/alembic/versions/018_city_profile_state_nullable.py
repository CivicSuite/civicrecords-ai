"""Make city_profile.state nullable to allow in-progress onboarding state.

T5A (Tier 5 Blocker A): the onboarding interview must be able to create a
CityProfile row with just the first answer (city_name). Previously the
`state` column was NOT NULL, blocking any partial-state row. Making it
nullable is the truthful modeling of a row whose `onboarding_status` is
`in_progress` — the operator hasn't answered every question yet, and the
DB should reflect that rather than demand a placeholder value.

`city_name` stays NOT NULL because the onboarding walk always asks
`city_name` first and only creates the row after that answer arrives.

Revision ID: 018_city_profile_state_nullable
Revises: 017_rename_connector_enum_values
Create Date: 2026-04-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '018_city_profile_state_nullable'
down_revision: Union[str, None] = '017_rename_connector_enum_values'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'city_profile',
        'state',
        existing_type=sa.String(length=2),
        nullable=True,
    )


def downgrade() -> None:
    # Backfill any null states with a sentinel before re-adding NOT NULL.
    # A caller that needs to downgrade past this point is explicitly
    # choosing to reject in-progress onboarding rows; the sentinel makes
    # the required follow-up cleanup discoverable.
    op.execute("UPDATE city_profile SET state = 'XX' WHERE state IS NULL")
    op.alter_column(
        'city_profile',
        'state',
        existing_type=sa.String(length=2),
        nullable=False,
    )
