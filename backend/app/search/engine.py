import uuid
from dataclasses import dataclass

from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.embedder import embed_text
from app.models.document import Document, DocumentChunk


@dataclass
class SearchHit:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    file_type: str
    source_path: str
    page_number: int | None
    content_text: str
    similarity_score: float
    rank: int


async def semantic_search(
    session: AsyncSession,
    query_embedding: list[float],
    limit: int = 20,
    filters: dict | None = None,
) -> list[tuple[uuid.UUID, float]]:
    """Search by vector similarity. Returns (chunk_id, distance) pairs."""
    embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    filter_clause = ""
    params = {"embedding": embedding_str, "limit": limit}

    if filters:
        if filters.get("file_type"):
            filter_clause += " AND d.file_type = :file_type"
            params["file_type"] = filters["file_type"]
        if filters.get("source_id"):
            filter_clause += " AND d.source_id = :source_id"
            params["source_id"] = filters["source_id"]

    sql = text(f"""
        SELECT c.id, c.embedding <=> CAST(:embedding AS vector) AS distance
        FROM document_chunks c
        JOIN documents d ON c.document_id = d.id
        WHERE c.embedding IS NOT NULL {filter_clause}
        ORDER BY c.embedding <=> CAST(:embedding AS vector)
        LIMIT :limit
    """)

    result = await session.execute(sql, params)
    return [(row[0], float(row[1])) for row in result.fetchall()]


async def keyword_search(
    session: AsyncSession,
    query_text: str,
    limit: int = 20,
    filters: dict | None = None,
) -> list[tuple[uuid.UUID, float]]:
    """Search by full-text. Returns (chunk_id, rank_score) pairs."""
    filter_clause = ""
    params = {"query": query_text, "limit": limit}

    if filters:
        if filters.get("file_type"):
            filter_clause += " AND d.file_type = :file_type"
            params["file_type"] = filters["file_type"]
        if filters.get("source_id"):
            filter_clause += " AND d.source_id = :source_id"
            params["source_id"] = filters["source_id"]

    sql = text(f"""
        SELECT c.id, ts_rank(c.content_tsvector, plainto_tsquery('english', :query)) AS rank_score
        FROM document_chunks c
        JOIN documents d ON c.document_id = d.id
        WHERE c.content_tsvector @@ plainto_tsquery('english', :query) {filter_clause}
        ORDER BY rank_score DESC
        LIMIT :limit
    """)

    result = await session.execute(sql, params)
    return [(row[0], float(row[1])) for row in result.fetchall()]


def reciprocal_rank_fusion(
    semantic_results: list[tuple[uuid.UUID, float]],
    keyword_results: list[tuple[uuid.UUID, float]],
    k: int = 60,
    semantic_weight: float = 0.7,
    keyword_weight: float = 0.3,
) -> list[tuple[uuid.UUID, float]]:
    """Combine semantic and keyword results using RRF."""
    scores: dict[uuid.UUID, float] = {}

    for rank, (chunk_id, _) in enumerate(semantic_results):
        scores[chunk_id] = scores.get(chunk_id, 0) + semantic_weight / (k + rank + 1)

    for rank, (chunk_id, _) in enumerate(keyword_results):
        scores[chunk_id] = scores.get(chunk_id, 0) + keyword_weight / (k + rank + 1)

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return ranked


async def hybrid_search(
    session: AsyncSession,
    query_text: str,
    limit: int = 10,
    filters: dict | None = None,
    semantic_weight: float = 0.7,
) -> list[SearchHit]:
    """Execute hybrid search: semantic + keyword with RRF fusion."""
    # Step 1: Embed the query
    query_embedding = await embed_text(query_text)

    # Step 2: Run both searches (fetch more than needed for fusion)
    fetch_limit = min(limit * 3, 50)
    semantic_results = await semantic_search(session, query_embedding, fetch_limit, filters)
    keyword_results = await keyword_search(session, query_text, fetch_limit, filters)

    # Step 3: Fuse results
    fused = reciprocal_rank_fusion(
        semantic_results, keyword_results,
        semantic_weight=semantic_weight,
        keyword_weight=1.0 - semantic_weight,
    )

    # Step 4: Fetch chunk + document details for top results
    top_chunk_ids = [cid for cid, _ in fused[:limit]]
    if not top_chunk_ids:
        return []

    # Build score lookup and rank
    score_map = {cid: score for cid, score in fused[:limit]}

    hits = []
    for rank, chunk_id in enumerate(top_chunk_ids):
        # Fetch chunk with document join
        result = await session.execute(
            select(DocumentChunk, Document)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(DocumentChunk.id == chunk_id)
        )
        row = result.one_or_none()
        if row:
            chunk, doc = row
            hits.append(SearchHit(
                chunk_id=chunk.id,
                document_id=doc.id,
                filename=doc.filename,
                file_type=doc.file_type,
                source_path=doc.source_path,
                page_number=chunk.page_number,
                content_text=chunk.content_text,
                similarity_score=score_map.get(chunk_id, 0.0),
                rank=rank + 1,
            ))

    return hits
