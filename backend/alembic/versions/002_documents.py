"""Document ingestion tables: data_sources, documents, document_chunks

Revision ID: 002
Revises: 001
Create Date: 2026-04-11
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    source_type = postgresql.ENUM("upload", "directory", name="source_type", create_type=True)
    source_type.create(op.get_bind(), checkfirst=True)
    ingestion_status = postgresql.ENUM("pending", "processing", "completed", "failed", name="ingestion_status", create_type=True)
    ingestion_status.create(op.get_bind(), checkfirst=True)

    op.create_table("data_sources",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("source_type", sa.Enum("upload", "directory", name="source_type", create_type=False), nullable=False),
        sa.Column("connection_config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("schedule_minutes", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_ingestion_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table("documents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("source_id", sa.UUID(), sa.ForeignKey("data_sources.id"), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("file_type", sa.String(50), nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ingestion_status", sa.Enum("pending", "processing", "completed", "failed", name="ingestion_status", create_type=False), nullable=False, server_default="pending"),
        sa.Column("ingestion_error", sa.Text(), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_documents_source_id", "documents", ["source_id"])
    op.create_index("ix_documents_file_hash", "documents", ["file_hash"])
    op.create_index("ix_documents_source_hash", "documents", ["source_id", "file_hash"])
    op.create_table("document_chunks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(768), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])
    op.create_index("ix_chunks_doc_index", "document_chunks", ["document_id", "chunk_index"])

def downgrade() -> None:
    op.drop_table("document_chunks")
    op.drop_table("documents")
    op.drop_table("data_sources")
    op.execute("DROP TYPE IF EXISTS ingestion_status")
    op.execute("DROP TYPE IF EXISTS source_type")
