"""Exemption detection tables: exemption_rules, exemption_flags, disclosure_templates

Revision ID: 006
Revises: 005
Create Date: 2026-04-12
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table("exemption_rules",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("state_code", sa.String(2), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("rule_type", sa.Enum("regex", "keyword", "llm_prompt", name="rule_type", create_type=True), nullable=False),
        sa.Column("rule_definition", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_exemption_rules_state", "exemption_rules", ["state_code"])
    op.create_index("ix_exemption_rules_category", "exemption_rules", ["category"])

    op.create_table("exemption_flags",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("chunk_id", sa.UUID(), sa.ForeignKey("document_chunks.id"), nullable=False),
        sa.Column("rule_id", sa.UUID(), sa.ForeignKey("exemption_rules.id"), nullable=True),
        sa.Column("request_id", sa.UUID(), sa.ForeignKey("records_requests.id"), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("matched_text", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("status", sa.Enum("flagged", "reviewed", "accepted", "rejected", name="flag_status", create_type=True), nullable=False, server_default="flagged"),
        sa.Column("reviewed_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_exemption_flags_chunk", "exemption_flags", ["chunk_id"])
    op.create_index("ix_exemption_flags_rule", "exemption_flags", ["rule_id"])
    op.create_index("ix_exemption_flags_request", "exemption_flags", ["request_id"])
    op.create_index("ix_exemption_flags_status", "exemption_flags", ["status"])

    op.create_table("disclosure_templates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("template_type", sa.String(100), nullable=False),
        sa.Column("state_code", sa.String(2), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("disclosure_templates")
    op.drop_table("exemption_flags")
    op.drop_table("exemption_rules")
    op.execute("DROP TYPE IF EXISTS flag_status")
    op.execute("DROP TYPE IF EXISTS rule_type")
