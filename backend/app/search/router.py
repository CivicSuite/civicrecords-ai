import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.logger import write_audit_log
from app.auth.dependencies import require_role, require_department_filter
from app.database import get_async_session
from app.models.departments import Department
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
    user: User = Depends(require_role(UserRole.LIAISON)),
):
    """Execute a hybrid search query. Optionally synthesize an LLM answer."""
    # Dept scoping fail-closed guard runs FIRST — before any session load
    # or insert. Otherwise a null-dept non-admin would create a SearchSession
    # row (session.add + flush below) before the 403 fired, leaving orphan
    # audit noise behind.
    dept_filter_id = require_department_filter(user)

    # Get or create session
    if req.session_id:
        search_session = await session.get(SearchSession, req.session_id)
        if not search_session or search_session.user_id != user.id:
            raise HTTPException(status_code=404, detail="Search session not found")
    else:
        search_session = SearchSession(user_id=user.id)
        session.add(search_session)
        await session.flush()

    # Department scoping: apply the resolved filter (server authority is
    # intentional — any caller-supplied department_id is overwritten).
    effective_filters = dict(req.filters or {})
    if dept_filter_id is not None:
        effective_filters["department_id"] = str(dept_filter_id)

    # Execute hybrid search
    hits = await hybrid_search(
        session=session,
        query_text=req.query,
        limit=req.limit,
        filters=effective_filters if effective_filters else None,
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

    # Batch-load all queries for these sessions (avoids N+1)
    if sessions:
        from collections import defaultdict
        session_ids = [s.id for s in sessions]
        all_queries_result = await session.execute(
            select(SearchQuery)
            .where(SearchQuery.session_id.in_(session_ids))
            .order_by(SearchQuery.created_at.asc())
        )
        queries_by_session: dict[uuid.UUID, list] = defaultdict(list)
        for q in all_queries_result.scalars().all():
            queries_by_session[q.session_id].append(q)
    else:
        queries_by_session = {}

    output = []
    for s in sessions:
        queries = queries_by_session.get(s.id, [])
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

    # Departments
    depts_result = await session.execute(
        select(Department.id, Department.name).order_by(Department.name)
    )
    departments = [{"id": str(r[0]), "name": r[1]} for r in depts_result.fetchall()]

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
        departments=departments,
        date_range=date_range,
    )


@router.get("/export")
async def export_search_results(
    query: str,
    format: str = "csv",
    department_id: str | None = None,
    file_type: str | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.STAFF)),
):
    """Export search results as CSV. Runs a search and streams the results."""
    import csv
    import io

    from fastapi.responses import StreamingResponse

    filters: dict = {}
    if department_id:
        filters["department_id"] = department_id
    if file_type:
        filters["file_type"] = file_type

    # Department scoping via require_department_filter: same fail-closed
    # behavior as POST /search/query (non-admin without a department → 403).
    # Server authority is intentional — any caller-supplied department_id
    # filter is overwritten.
    dept_filter_id = require_department_filter(user)
    if dept_filter_id is not None:
        filters["department_id"] = str(dept_filter_id)

    hits = await hybrid_search(session=session, query_text=query, limit=50, filters=filters or None)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Rank", "Filename", "File Type", "Page", "Score", "Content"])
    for hit in hits:
        writer.writerow([
            hit.rank,
            hit.filename,
            hit.file_type,
            hit.page_number or "",
            f"{hit.similarity_score:.3f}",
            hit.content_text[:500],
        ])
    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=search-results.csv"},
    )
