import secrets
import uuid
from hashlib import sha256

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.logger import write_audit_log
from app.auth.dependencies import require_role
from app.database import get_async_session
from app.models.service_account import ServiceAccount
from app.models.user import User, UserRole
from app.schemas.service_account import (
    ServiceAccountCreate,
    ServiceAccountCreated,
    ServiceAccountRead,
    ServiceAccountUpdate,
)

router = APIRouter(prefix="/service-accounts", tags=["service-accounts"])


def _hash_api_key(key: str) -> str:
    return sha256(key.encode()).hexdigest()


@router.post("/", response_model=ServiceAccountCreated, status_code=201)
async def create_service_account(
    data: ServiceAccountCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    existing = await session.execute(
        select(ServiceAccount).where(ServiceAccount.name == data.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Name already taken")

    api_key = f"cr_{secrets.token_hex(32)}"
    account = ServiceAccount(
        name=data.name,
        api_key_hash=_hash_api_key(api_key),
        role=data.role,
        created_by=user.id,
    )
    session.add(account)
    await session.commit()
    await session.refresh(account)

    await write_audit_log(
        session=session,
        action="create_service_account",
        resource_type="service_account",
        resource_id=str(account.id),
        user_id=user.id,
        details={"name": data.name, "role": data.role.value},
    )

    return ServiceAccountCreated(
        id=account.id,
        name=account.name,
        role=account.role,
        created_by=account.created_by,
        created_at=account.created_at,
        is_active=account.is_active,
        api_key=api_key,
    )


@router.get("/", response_model=list[ServiceAccountRead])
async def list_service_accounts(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    result = await session.execute(select(ServiceAccount).order_by(ServiceAccount.created_at.desc()))
    return result.scalars().all()


@router.patch("/{account_id}", response_model=ServiceAccountRead)
async def update_service_account(
    account_id: uuid.UUID,
    data: ServiceAccountUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    result = await session.execute(
        select(ServiceAccount).where(ServiceAccount.id == account_id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Service account not found")

    if data.role is not None:
        account.role = data.role
    if data.is_active is not None:
        account.is_active = data.is_active

    await session.commit()
    await session.refresh(account)

    await write_audit_log(
        session=session,
        action="update_service_account",
        resource_type="service_account",
        resource_id=str(account.id),
        user_id=user.id,
        details={"changes": data.model_dump(exclude_none=True)},
    )

    return account
