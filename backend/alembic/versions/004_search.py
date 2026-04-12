"""Search tables, tsvector column, HNSW and GIN indexes

Revision ID: 004
Revises: 003
Create Date: 2026-04-12
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Search sessions
    op.create_table("search_sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_search_sessions_user_id", "search_sessions", ["user_id"])

    # Search queries
    op.create_table("search_queries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), sa.ForeignKey("search_sessions.id"), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("filters", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("results_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("synthesized_answer", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_search_queries_session_id", "search_queries", ["session_id"])

    # Search results
    op.create_table("search_results",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("query_id", sa.UUID(), sa.ForeignKey("search_queries.id"), nullable=False),
        sa.Column("chunk_id", sa.UUID(), sa.ForeignKey("document_chunks.id"), nullable=False),
        sa.Column("similarity_score", sa.Float(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_search_results_query_id", "search_results", ["query_id"])
    op.create_index("ix_search_results_chunk_id", "search_results", ["chunk_id"])

    # Add tsvector column to document_chunks for full-text search
    op.execute("""
        ALTER TABLE document_chunks
        ADD COLUMN content_tsvector tsvector
        GENERATED ALWAYS AS (to_tsvector('english', content_text)) STORED
    """)
    op.execute("CREATE INDEX ix_chunks_tsvector ON document_chunks USING GIN (content_tsvector)")

    # HNSW index on embedding column for fast semantic search
    op.execute("""
        CREATE INDEX ix_chunks_embedding_hnsw ON document_chunks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chunks_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_chunks_tsvector")
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS content_tsvector")
    op.drop_table("search_results")
    op.drop_table("search_queries")
    op.drop_table("search_sessions")
