"""Request tracking tables: records_requests, request_documents, document_cache

Revision ID: 005
Revises: 004
Create Date: 2026-04-12
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table("records_requests",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("requester_name", sa.String(255), nullable=False),
        sa.Column("requester_email", sa.String(320), nullable=True),
        sa.Column("date_received", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("statutory_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.Enum("received", "searching", "in_review", "drafted", "approved", "sent", name="request_status", create_type=True), nullable=False, server_default="received"),
        sa.Column("assigned_to", sa.UUID(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("response_draft", sa.Text(), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_requests_status", "records_requests", ["status"])
    op.create_index("ix_requests_assigned_to", "records_requests", ["assigned_to"])
    op.create_index("ix_requests_deadline", "records_requests", ["statutory_deadline"])

    op.create_table("request_documents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("request_id", sa.UUID(), sa.ForeignKey("records_requests.id"), nullable=False),
        sa.Column("document_id", sa.UUID(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("relevance_note", sa.Text(), nullable=True),
        sa.Column("exemption_flags", postgresql.JSONB(), nullable=True),
        sa.Column("inclusion_status", sa.Enum("included", "excluded", "pending", name="inclusion_status", create_type=True), nullable=False, server_default="pending"),
        sa.Column("attached_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("attached_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_request_documents_request_id", "request_documents", ["request_id"])
    op.create_index("ix_request_documents_document_id", "request_documents", ["document_id"])

    op.create_table("document_cache",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("request_id", sa.UUID(), sa.ForeignKey("records_requests.id"), nullable=False),
        sa.Column("cached_file_path", sa.Text(), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cached_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_cache_document_id", "document_cache", ["document_id"])
    op.create_index("ix_document_cache_request_id", "document_cache", ["request_id"])


def downgrade() -> None:
    op.drop_table("document_cache")
    op.drop_table("request_documents")
    op.drop_table("records_requests")
    op.execute("DROP TYPE IF EXISTS inclusion_status")
    op.execute("DROP TYPE IF EXISTS request_status")
