from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.config import settings
from app.database import get_async_session
from app.models.audit import AuditLog
from app.models.user import User, UserRole

router = APIRouter(prefix="/admin", tags=["admin"])


class SystemStatus(BaseModel):
    version: str
    database: str
    ollama: str
    redis: str
    user_count: int
    audit_log_count: int


class OllamaModelInfo(BaseModel):
    name: str
    size: int | None = None
    details: dict | None = None


class OllamaStatus(BaseModel):
    status: str
    models: list[OllamaModelInfo]


@router.get("/status", response_model=SystemStatus)
async def system_status(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    import httpx

    try:
        await session.execute(select(func.count(User.id)))
        db_status = "connected"
    except Exception:
        db_status = "error"

    result = await session.execute(select(func.count(User.id)))
    user_count = result.scalar() or 0

    result = await session.execute(select(func.count(AuditLog.id)))
    audit_count = result.scalar() or 0

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            ollama_status = "connected" if resp.status_code == 200 else "error"
    except Exception:
        ollama_status = "unreachable"

    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.redis_url)
        await r.ping()
        redis_status = "connected"
        await r.aclose()
    except Exception:
        redis_status = "unreachable"

    return SystemStatus(
        version="0.1.0",
        database=db_status,
        ollama=ollama_status,
        redis=redis_status,
        user_count=user_count,
        audit_log_count=audit_count,
    )


@router.get("/models", response_model=OllamaStatus)
async def list_models(
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    import httpx

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                models = [
                    OllamaModelInfo(
                        name=m.get("name", ""),
                        size=m.get("size"),
                        details=m.get("details"),
                    )
                    for m in data.get("models", [])
                ]
                return OllamaStatus(status="connected", models=models)
    except Exception:
        pass

    return OllamaStatus(status="unreachable", models=[])
