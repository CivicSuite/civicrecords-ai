import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.logger import write_audit_log
from app.auth.dependencies import require_role
from app.database import get_async_session
from app.models.document import DataSource, Document, DocumentChunk
from app.models.search import SearchQuery, SearchResult, SearchSession
from app.models.user import User, UserRole
from app.schemas.search import (
    SearchFilterOptions,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    SearchSessionRead,
)
from app.search.engine import hybrid_search
from app.search.synthesizer import synthesize_answer

router = APIRouter(prefix="/search", tags=["search"])


@router.post("/query", response_model=SearchResponse)
async def execute_search(
    req: SearchRequest,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.STAFF)),
):
    """Execute a hybrid search query. Optionally synthesize an LLM answer."""
    # Get or create session
    if req.session_id:
        search_session = await session.get(SearchSession, req.session_id)
        if not search_session or search_session.user_id != user.id:
            raise HTTPException(status_code=404, detail="Search session not found")
    else:
        search_session = SearchSession(user_id=user.id)
        session.add(search_session)
        await session.flush()

    # Execute hybrid search
    hits = await hybrid_search(
        session=session,
        query_text=req.query,
        limit=req.limit,
        filters=req.filters,
    )

    # Optionally synthesize answer
    synthesized = None
    ai_generated = False
    if req.synthesize and hits:
        try:
            synthesized = await synthesize_answer(req.query, hits)
            ai_generated = True
        except Exception:
            synthesized = "LLM synthesis unavailable. Review the document excerpts below."
            ai_generated = True

    # Store query and results
    search_query = SearchQuery(
        session_id=search_session.id,
        query_text=req.query,
        filters=req.filters,
        results_count=len(hits),
        synthesized_answer=synthesized,
    )
    session.add(search_query)
    await session.flush()

    for hit in hits:
        search_result = SearchResult(
            query_id=search_query.id,
            chunk_id=hit.chunk_id,
            similarity_score=hit.similarity_score,
            rank=hit.rank,
        )
        session.add(search_result)

    await session.commit()

    # Audit log
    await write_audit_log(
        session=session,
        action="search_query",
        resource_type="search",
        resource_id=str(search_query.id),
        user_id=user.id,
        details={
            "query": req.query,
            "results_count": len(hits),
            "synthesized": req.synthesize,
            "session_id": str(search_session.id),
        },
        ai_generated=ai_generated,
    )

    # Build response
    result_items = [
        SearchResultItem(
            chunk_id=hit.chunk_id,
            document_id=hit.document_id,
            filename=hit.filename,
            file_type=hit.file_type,
            source_path=hit.source_path,
            page_number=hit.page_number,
            content_text=hit.content_text,
            similarity_score=hit.similarity_score,
            rank=hit.rank,
        )
        for hit in hits
    ]

    return SearchResponse(
        query_id=search_query.id,
        session_id=search_session.id,
        query_text=req.query,
        results=result_items,
        results_count=len(hits),
        synthesized_answer=synthesized,
        ai_generated=ai_generated,
    )


@router.get("/sessions", response_model=list[SearchSessionRead])
async def list_sessions(
    limit: int = 20,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.STAFF)),
):
    """List the current user's search sessions."""
    result = await session.execute(
        select(SearchSession)
        .where(SearchSession.user_id == user.id)
        .order_by(SearchSession.created_at.desc())
        .limit(limit)
    )
    sessions = result.scalars().all()

    output = []
    for s in sessions:
        queries_result = await session.execute(
            select(SearchQuery)
            .where(SearchQuery.session_id == s.id)
            .order_by(SearchQuery.created_at.asc())
        )
        queries = queries_result.scalars().all()
        output.append(SearchSessionRead(
            id=s.id,
            user_id=s.user_id,
            created_at=s.created_at,
            queries=[
                {
                    "id": str(q.id),
                    "query_text": q.query_text,
                    "results_count": q.results_count,
                    "created_at": q.created_at.isoformat(),
                }
                for q in queries
            ],
        ))
    return output


@router.get("/sessions/{session_id}", response_model=SearchSessionRead)
async def get_session(
    session_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.STAFF)),
):
    """Get a search session with its query history."""
    search_session = await session.get(SearchSession, session_id)
    if not search_session or search_session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Search session not found")

    queries_result = await session.execute(
        select(SearchQuery)
        .where(SearchQuery.session_id == session_id)
        .order_by(SearchQuery.created_at.asc())
    )
    queries = queries_result.scalars().all()

    return SearchSessionRead(
        id=search_session.id,
        user_id=search_session.user_id,
        created_at=search_session.created_at,
        queries=[
            {
                "id": str(q.id),
                "query_text": q.query_text,
                "results_count": q.results_count,
                "synthesized_answer": q.synthesized_answer,
                "created_at": q.created_at.isoformat(),
            }
            for q in queries
        ],
    )


@router.get("/filters", response_model=SearchFilterOptions)
async def get_filter_options(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.STAFF)),
):
    """Get available filter values for search."""
    # File types
    file_types_result = await session.execute(
        select(Document.file_type).distinct().order_by(Document.file_type)
    )
    file_types = [r[0] for r in file_types_result.fetchall()]

    # Source names
    sources_result = await session.execute(
        select(DataSource.name).order_by(DataSource.name)
    )
    source_names = [r[0] for r in sources_result.fetchall()]

    # Date range
    date_result = await session.execute(
        select(func.min(Document.ingested_at), func.max(Document.ingested_at))
    )
    date_row = date_result.one_or_none()
    date_range = None
    if date_row and date_row[0]:
        date_range = {
            "min": date_row[0].isoformat(),
            "max": date_row[1].isoformat() if date_row[1] else date_row[0].isoformat(),
        }

    return SearchFilterOptions(
        file_types=file_types,
        source_names=source_names,
        date_range=date_range,
    )
