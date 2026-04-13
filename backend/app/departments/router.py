import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.logger import write_audit_log
from app.auth.dependencies import require_role
from app.database import get_async_session
from app.models.departments import Department
from app.models.user import User, UserRole
from app.schemas.department import DepartmentCreate, DepartmentRead, DepartmentUpdate

router = APIRouter(prefix="/departments", tags=["departments"])


@router.post("/", response_model=DepartmentRead, status_code=201)
async def create_department(
    data: DepartmentCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    existing = await session.execute(
        select(Department).where(Department.code == data.code)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Department code already exists")

    dept = Department(name=data.name, code=data.code, contact_email=data.contact_email)
    session.add(dept)
    await session.commit()
    await session.refresh(dept)

    await write_audit_log(
        session=session, action="create_department", resource_type="department",
        resource_id=str(dept.id), user_id=user.id,
        details={"name": data.name, "code": data.code},
    )
    return dept


@router.get("/", response_model=list[DepartmentRead])
async def list_departments(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.STAFF)),
):
    result = await session.execute(
        select(Department).order_by(Department.name)
    )
    return result.scalars().all()


@router.get("/{dept_id}", response_model=DepartmentRead)
async def get_department(
    dept_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.STAFF)),
):
    dept = await session.get(Department, dept_id)
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    return dept


@router.patch("/{dept_id}", response_model=DepartmentRead)
async def update_department(
    dept_id: uuid.UUID,
    data: DepartmentUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    dept = await session.get(Department, dept_id)
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")

    if data.name is not None:
        dept.name = data.name
    if data.code is not None:
        existing = await session.execute(
            select(Department).where(Department.code == data.code, Department.id != dept_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Department code already exists")
        dept.code = data.code
    if data.contact_email is not None:
        dept.contact_email = data.contact_email

    await session.commit()
    await session.refresh(dept)

    await write_audit_log(
        session=session, action="update_department", resource_type="department",
        resource_id=str(dept.id), user_id=user.id,
        details=data.model_dump(exclude_none=True),
    )
    return dept


@router.delete("/{dept_id}", status_code=204)
async def delete_department(
    dept_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    dept = await session.get(Department, dept_id)
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")

    user_count = (await session.execute(
        select(func.count(User.id)).where(User.department_id == dept_id)
    )).scalar() or 0
    if user_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete department with {user_count} assigned users",
        )

    await session.delete(dept)
    await session.commit()

    await write_audit_log(
        session=session, action="delete_department", resource_type="department",
        resource_id=str(dept_id), user_id=user.id,
        details={"name": dept.name, "code": dept.code},
    )
