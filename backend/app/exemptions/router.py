import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.logger import write_audit_log
from app.auth.dependencies import require_role
from app.database import get_async_session
from app.exemptions.engine import scan_request_documents
from app.models.exemption import (
    DisclosureTemplate, ExemptionFlag, ExemptionRule, FlagStatus, RuleType,
)
from app.models.user import User, UserRole
from app.schemas.exemption import (
    DisclosureTemplateCreate, DisclosureTemplateRead,
    ExemptionDashboard, ExemptionFlagRead, ExemptionFlagReview,
    ExemptionRuleCreate, ExemptionRuleRead, ExemptionRuleUpdate,
)

router = APIRouter(prefix="/exemptions", tags=["exemptions"])


# --- Rules CRUD ---

@router.post("/rules/", response_model=ExemptionRuleRead, status_code=201)
async def create_rule(
    data: ExemptionRuleCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    rule = ExemptionRule(
        state_code=data.state_code,
        category=data.category,
        rule_type=data.rule_type,
        rule_definition=data.rule_definition,
        description=data.description,
        enabled=data.enabled,
        created_by=user.id,
    )
    session.add(rule)
    await session.commit()
    await session.refresh(rule)

    await write_audit_log(
        session=session, action="create_exemption_rule", resource_type="exemption_rule",
        resource_id=str(rule.id), user_id=user.id,
        details={"state": data.state_code, "category": data.category, "type": data.rule_type.value},
    )
    return rule


@router.get("/rules/", response_model=list[ExemptionRuleRead])
async def list_rules(
    state_code: str | None = None,
    enabled: bool | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.STAFF)),
):
    stmt = select(ExemptionRule).order_by(ExemptionRule.state_code, ExemptionRule.category)
    if state_code:
        stmt = stmt.where(ExemptionRule.state_code == state_code)
    if enabled is not None:
        stmt = stmt.where(ExemptionRule.enabled == enabled)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.patch("/rules/{rule_id}", response_model=ExemptionRuleRead)
async def update_rule(
    rule_id: uuid.UUID,
    data: ExemptionRuleUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    rule = await session.get(ExemptionRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    if data.rule_definition is not None:
        rule.rule_definition = data.rule_definition
    if data.description is not None:
        rule.description = data.description
    if data.enabled is not None:
        rule.enabled = data.enabled

    await session.commit()
    await session.refresh(rule)

    await write_audit_log(
        session=session, action="update_exemption_rule", resource_type="exemption_rule",
        resource_id=str(rule.id), user_id=user.id,
        details=data.model_dump(exclude_none=True),
    )
    return rule


# --- Scanning ---

@router.post("/scan/{request_id}")
async def scan_for_exemptions(
    request_id: uuid.UUID,
    state_code: str = Query(default="CO", pattern="^[A-Z]{2}$"),
    use_llm: bool = False,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.STAFF)),
):
    """Scan all documents attached to a request for exemptions."""
    from app.models.request import RecordsRequest
    req = await session.get(RecordsRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    flags = await scan_request_documents(session, request_id, state_code)

    # Optional LLM secondary pass
    llm_flags = []
    if use_llm:
        from app.exemptions.llm_reviewer import llm_suggest_exemptions
        from app.models.document import DocumentChunk
        from app.models.request import RequestDocument

        result = await session.execute(
            select(RequestDocument.document_id).where(RequestDocument.request_id == request_id)
        )
        doc_ids = [r[0] for r in result.fetchall()]
        if doc_ids:
            chunks_result = await session.execute(
                select(DocumentChunk).where(DocumentChunk.document_id.in_(doc_ids))
            )
            for chunk in chunks_result.scalars().all():
                suggestions = await llm_suggest_exemptions(
                    chunk.content_text, chunk.id, request_id, state_code
                )
                for s in suggestions:
                    flag = ExemptionFlag(
                        chunk_id=s["chunk_id"],
                        request_id=s["request_id"],
                        category=s["category"],
                        matched_text=s["matched_text"],
                        confidence=s["confidence"],
                        status=FlagStatus.FLAGGED,
                    )
                    session.add(flag)
                    llm_flags.append(flag)
            await session.commit()

    await write_audit_log(
        session=session, action="scan_exemptions", resource_type="request",
        resource_id=str(request_id), user_id=user.id,
        details={
            "state_code": state_code, "rules_flags": len(flags),
            "llm_flags": len(llm_flags), "use_llm": use_llm,
        },
        ai_generated=use_llm,
    )

    return {
        "request_id": str(request_id),
        "rules_flags_created": len(flags),
        "llm_flags_created": len(llm_flags),
        "total_flags": len(flags) + len(llm_flags),
    }


# --- Flag Review ---

@router.get("/flags/{request_id}", response_model=list[ExemptionFlagRead])
async def list_flags(
    request_id: uuid.UUID,
    status: FlagStatus | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.STAFF)),
):
    stmt = select(ExemptionFlag).where(
        ExemptionFlag.request_id == request_id
    ).order_by(ExemptionFlag.confidence.desc())
    if status:
        stmt = stmt.where(ExemptionFlag.status == status)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.patch("/flags/{flag_id}", response_model=ExemptionFlagRead)
async def review_flag(
    flag_id: uuid.UUID,
    data: ExemptionFlagReview,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.STAFF)),
):
    flag = await session.get(ExemptionFlag, flag_id)
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found")

    if data.status not in (FlagStatus.ACCEPTED, FlagStatus.REJECTED, FlagStatus.REVIEWED):
        raise HTTPException(status_code=400, detail="Status must be accepted, rejected, or reviewed")

    flag.status = data.status
    flag.reviewed_by = user.id
    flag.reviewed_at = datetime.now(timezone.utc)
    flag.review_reason = data.review_reason

    await session.commit()
    await session.refresh(flag)

    await write_audit_log(
        session=session, action="review_exemption_flag", resource_type="exemption_flag",
        resource_id=str(flag.id), user_id=user.id,
        details={
            "category": flag.category, "decision": data.status.value,
            "reason": data.review_reason, "request_id": str(flag.request_id),
        },
    )
    return flag


# --- Dashboard ---

@router.get("/dashboard", response_model=ExemptionDashboard)
async def exemption_dashboard(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    total = (await session.execute(select(func.count(ExemptionFlag.id)))).scalar() or 0

    by_status = {}
    for s in FlagStatus:
        count = (await session.execute(
            select(func.count(ExemptionFlag.id)).where(ExemptionFlag.status == s)
        )).scalar() or 0
        by_status[s.value] = count

    by_category = {}
    cat_result = await session.execute(
        select(ExemptionFlag.category, func.count(ExemptionFlag.id))
        .group_by(ExemptionFlag.category)
    )
    for cat, count in cat_result.fetchall():
        by_category[cat] = count

    reviewed = by_status.get("accepted", 0) + by_status.get("rejected", 0)
    acceptance_rate = by_status.get("accepted", 0) / reviewed if reviewed > 0 else 0.0

    total_rules = (await session.execute(select(func.count(ExemptionRule.id)))).scalar() or 0
    active_rules = (await session.execute(
        select(func.count(ExemptionRule.id)).where(ExemptionRule.enabled.is_(True))
    )).scalar() or 0

    return ExemptionDashboard(
        total_flags=total, by_status=by_status, by_category=by_category,
        acceptance_rate=round(acceptance_rate, 3),
        total_rules=total_rules, active_rules=active_rules,
    )


# --- Templates ---

@router.get("/templates/", response_model=list[DisclosureTemplateRead])
async def list_templates(
    template_type: str | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.STAFF)),
):
    stmt = select(DisclosureTemplate).order_by(DisclosureTemplate.template_type)
    if template_type:
        stmt = stmt.where(DisclosureTemplate.template_type == template_type)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.post("/templates/", response_model=DisclosureTemplateRead, status_code=201)
async def create_template(
    data: DisclosureTemplateCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    template = DisclosureTemplate(
        template_type=data.template_type,
        state_code=data.state_code,
        content=data.content,
        updated_by=user.id,
    )
    session.add(template)
    await session.commit()
    await session.refresh(template)

    await write_audit_log(
        session=session, action="create_disclosure_template", resource_type="disclosure_template",
        resource_id=str(template.id), user_id=user.id,
        details={"type": data.template_type, "state": data.state_code},
    )
    return template
