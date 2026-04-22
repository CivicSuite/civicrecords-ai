# Phase 2 (v1.1.0) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement department-level access controls, expand exemption rules to all 50 states, ship 5 compliance template documents, and add model registry CRUD — completing Phase 2 of the master design spec.

**Architecture:** Adds department-scoping middleware that composes with existing `require_role()`. All list/get endpoints for requests, documents, and search results filtered by `user.department_id` for non-admins. Compliance templates stored as markdown files, seeded into `disclosure_templates` table, rendered with city profile variable substitution.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 async, PostgreSQL + pgvector, pytest + httpx AsyncClient, Alembic.

---

## Task 1: Update Test Fixtures for Department-Aware Users

**Files:**
- Modify: `backend/tests/conftest.py`
- Modify: `backend/app/schemas/user.py`

This task updates the test infrastructure so all subsequent tasks can create users with department assignments.

- [ ] **Step 1: Add department_id to AdminUserCreate schema**

In `backend/app/schemas/user.py`, add the optional `department_id` field:

```python
class AdminUserCreate(schemas.BaseUserCreate):
    """Schema for admin-only user creation endpoint. Role IS caller-supplied."""
    full_name: str = ""
    role: UserRole = UserRole.STAFF
    department_id: uuid.UUID | None = None
```

- [ ] **Step 2: Add department_id to UserRead schema**

In `backend/app/schemas/user.py`, add:

```python
class UserRead(schemas.BaseUser[uuid.UUID]):
    full_name: str
    role: UserRole
    created_at: datetime
    last_login: datetime | None
    department_id: uuid.UUID | None = None
```

- [ ] **Step 3: Add department helper fixtures to conftest.py**

Add to `backend/tests/conftest.py`:

```python
from app.models.departments import Department


async def _create_department(name: str, code: str) -> uuid.UUID:
    """Create a department directly in test DB, return its ID."""
    async with test_session_maker() as session:
        dept = Department(name=name, code=code)
        session.add(dept)
        await session.commit()
        await session.refresh(dept)
        return dept.id


async def _create_test_user_in_dept(
    email: str, password: str, full_name: str, role: UserRole, department_id: uuid.UUID
) -> None:
    """Create a user with a department assignment."""
    from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
    from app.auth.manager import UserManager
    from app.schemas.user import AdminUserCreate

    async with test_session_maker() as session:
        user_db = SQLAlchemyUserDatabase(session, User)
        manager = UserManager(session=session, user_db=user_db)
        user_create = AdminUserCreate(
            email=email,
            password=password,
            full_name=full_name,
            role=role,
            department_id=department_id,
            is_active=True,
            is_verified=True,
            is_superuser=False,
        )
        await manager.create(user_create)


@pytest.fixture
async def dept_a(client: AsyncClient) -> uuid.UUID:
    """Create department A for testing."""
    return await _create_department("Police Department", "PD")


@pytest.fixture
async def dept_b(client: AsyncClient) -> uuid.UUID:
    """Create department B for testing."""
    return await _create_department("Finance Department", "FIN")


@pytest.fixture
async def staff_token_dept_a(client: AsyncClient, dept_a: uuid.UUID) -> str:
    """Staff user in department A."""
    email = f"staff-a-{uuid.uuid4().hex[:8]}@test.com"
    password = "staffpass123"
    await _create_test_user_in_dept(email, password, "Staff A", UserRole.STAFF, dept_a)
    login = await client.post("/auth/jwt/login", data={"username": email, "password": password})
    return login.json()["access_token"]


@pytest.fixture
async def staff_token_dept_b(client: AsyncClient, dept_b: uuid.UUID) -> str:
    """Staff user in department B."""
    email = f"staff-b-{uuid.uuid4().hex[:8]}@test.com"
    password = "staffpass123"
    await _create_test_user_in_dept(email, password, "Staff B", UserRole.STAFF, dept_b)
    login = await client.post("/auth/jwt/login", data={"username": email, "password": password})
    return login.json()["access_token"]


@pytest.fixture
async def reviewer_token_dept_a(client: AsyncClient, dept_a: uuid.UUID) -> str:
    """Reviewer user in department A."""
    email = f"reviewer-a-{uuid.uuid4().hex[:8]}@test.com"
    password = "reviewerpass123"
    await _create_test_user_in_dept(email, password, "Reviewer A", UserRole.REVIEWER, dept_a)
    login = await client.post("/auth/jwt/login", data={"username": email, "password": password})
    return login.json()["access_token"]
```

- [ ] **Step 4: Run existing tests to verify fixtures don't break anything**

Run: `docker compose exec -T api sh -c "TESTING=1 python -m pytest tests/ -v"`
Expected: 104 passed (all existing tests unaffected)

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/user.py backend/tests/conftest.py
git commit -m "feat(phase2): add department-aware test fixtures and user schema fields"
```

---

## Task 2: Department CRUD Router

**Files:**
- Create: `backend/app/departments/router.py`
- Create: `backend/app/departments/__init__.py`
- Create: `backend/app/schemas/department.py`
- Modify: `backend/app/main.py` (register router)
- Create: `backend/tests/test_departments.py`

- [ ] **Step 1: Create department schemas**

Create `backend/app/schemas/department.py`:

```python
import uuid
from datetime import datetime
from pydantic import BaseModel


class DepartmentCreate(BaseModel):
    name: str
    code: str
    contact_email: str | None = None


class DepartmentRead(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    contact_email: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


class DepartmentUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    contact_email: str | None = None
```

- [ ] **Step 2: Create department router**

Create `backend/app/departments/__init__.py` (empty file).

Create `backend/app/departments/router.py`:

```python
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
        # Check uniqueness
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

    # Check for assigned users
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
```

- [ ] **Step 3: Register router in main.py**

In `backend/app/main.py`, add the import and include:

```python
from app.departments.router import router as departments_router
```

And in the `create_app()` function, add:

```python
app.include_router(departments_router)
```

- [ ] **Step 4: Write department CRUD tests**

Create `backend/tests/test_departments.py`:

```python
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_department(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/departments/",
        json={"name": "Police Department", "code": "PD", "contact_email": "pd@city.gov"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Police Department"
    assert data["code"] == "PD"
    assert data["contact_email"] == "pd@city.gov"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_department_requires_admin(client: AsyncClient, staff_token: str):
    resp = await client.post(
        "/departments/",
        json={"name": "Finance", "code": "FIN"},
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_department_duplicate_code(client: AsyncClient, admin_token: str):
    await client.post(
        "/departments/",
        json={"name": "Police", "code": "PD"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = await client.post(
        "/departments/",
        json={"name": "Public Defense", "code": "PD"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_departments(client: AsyncClient, admin_token: str, staff_token: str):
    await client.post(
        "/departments/",
        json={"name": "Police", "code": "PD"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    await client.post(
        "/departments/",
        json={"name": "Finance", "code": "FIN"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = await client.get(
        "/departments/",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_update_department(client: AsyncClient, admin_token: str):
    create = await client.post(
        "/departments/",
        json={"name": "Police", "code": "PD"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    dept_id = create.json()["id"]
    resp = await client.patch(
        f"/departments/{dept_id}",
        json={"name": "Police Department (Updated)"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Police Department (Updated)"


@pytest.mark.asyncio
async def test_delete_empty_department(client: AsyncClient, admin_token: str):
    create = await client.post(
        "/departments/",
        json={"name": "Temp Dept", "code": "TMP"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    dept_id = create.json()["id"]
    resp = await client.delete(
        f"/departments/{dept_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_department_with_users_fails(
    client: AsyncClient, admin_token: str, staff_token_dept_a: str, dept_a
):
    resp = await client.delete(
        f"/departments/{dept_a}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 409
    assert "assigned users" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_department_crud_creates_audit_log(client: AsyncClient, admin_token: str):
    await client.post(
        "/departments/",
        json={"name": "Audit Test Dept", "code": "AUD"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    # Check audit log via admin status (audit_log_count increases)
    resp = await client.get(
        "/admin/status",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.json()["audit_log_count"] > 0
```

- [ ] **Step 5: Run tests**

Run: `docker compose exec -T api sh -c "TESTING=1 python -m pytest tests/test_departments.py -v"`
Expected: 8 passed

- [ ] **Step 6: Run full suite**

Run: `docker compose exec -T api sh -c "TESTING=1 python -m pytest tests/ -v"`
Expected: 112 passed (104 existing + 8 new)

- [ ] **Step 7: Commit**

```bash
git add backend/app/departments/ backend/app/schemas/department.py backend/tests/test_departments.py backend/app/main.py
git commit -m "feat(phase2): department CRUD API with audit logging"
```

---

## Task 3: Department Scoping Middleware

**Files:**
- Modify: `backend/app/auth/dependencies.py`
- Create: `backend/tests/test_department_scoping.py`

- [ ] **Step 1: Add department scoping dependency**

Add to `backend/app/auth/dependencies.py`:

```python
def require_department_access(minimum_role: UserRole):
    """Dependency that enforces role + department scoping.

    Admins see everything. Other roles only see resources in their department
    or shared resources (department_id=None).
    """

    async def _check(
        user: User = Depends(current_active_user),
    ) -> User:
        if ROLE_HIERARCHY.get(user.role, 0) < ROLE_HIERARCHY[minimum_role]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {minimum_role.value} role or higher",
            )
        return user

    return _check


def check_department_access(user: User, resource_department_id: uuid.UUID | None) -> None:
    """Raise 403 if non-admin user tries to access resource in another department.

    Call this in endpoint logic after loading the resource.
    Shared resources (department_id=None) are accessible to everyone.
    """
    if user.role == UserRole.ADMIN:
        return
    if resource_department_id is None:
        return  # shared resource
    if user.department_id != resource_department_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: resource belongs to another department",
        )
```

- [ ] **Step 2: Write scoping unit tests**

Create `backend/tests/test_department_scoping.py` with initial middleware tests:

```python
import uuid
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_staff_lists_own_department_requests_only(
    client: AsyncClient, admin_token: str,
    staff_token_dept_a: str, staff_token_dept_b: str,
    dept_a: uuid.UUID, dept_b: uuid.UUID,
):
    """Staff in dept A should not see dept B requests."""
    # Admin creates requests in both departments
    # We need to set department_id on requests — this requires
    # the requests router to be updated (Task 4). For now, skip.
    pass  # Placeholder — implemented in Task 4


@pytest.mark.asyncio
async def test_admin_sees_all_department_requests(
    client: AsyncClient, admin_token: str,
    dept_a: uuid.UUID, dept_b: uuid.UUID,
):
    """Admin should see requests from all departments."""
    pass  # Placeholder — implemented in Task 4
```

Note: The full scoping tests require endpoint modifications (Task 4). This task establishes the middleware. Full integration tests are in Task 4.

- [ ] **Step 3: Run tests**

Run: `docker compose exec -T api sh -c "TESTING=1 python -m pytest tests/ -v"`
Expected: All tests pass (middleware addition doesn't break existing tests)

- [ ] **Step 4: Commit**

```bash
git add backend/app/auth/dependencies.py backend/tests/test_department_scoping.py
git commit -m "feat(phase2): department scoping middleware (check_department_access)"
```

---

## Task 4: Scope Requests Endpoints by Department

**Files:**
- Modify: `backend/app/requests/router.py`
- Modify: `backend/app/schemas/request.py`
- Modify: `backend/tests/test_department_scoping.py`

- [ ] **Step 1: Add department_id to RequestCreate and RequestRead schemas**

In `backend/app/schemas/request.py`, add `department_id` to `RequestCreate`:

```python
class RequestCreate(BaseModel):
    requester_name: str
    requester_email: str | None = None
    description: str
    statutory_deadline: datetime | None = None
    department_id: uuid.UUID | None = None  # Auto-set from user if not provided
```

Add to `RequestRead`:

```python
class RequestRead(BaseModel):
    # ... existing fields ...
    department_id: uuid.UUID | None = None
    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Update create_request to set department_id**

In `backend/app/requests/router.py`, modify `create_request`:

```python
@router.post("/", response_model=RequestRead, status_code=201)
async def create_request(
    data: RequestCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.STAFF)),
):
    # Department: use explicit value if admin, otherwise use user's department
    dept_id = data.department_id
    if user.role != UserRole.ADMIN:
        dept_id = user.department_id  # Staff always uses their own department

    req = RecordsRequest(
        requester_name=data.requester_name,
        requester_email=data.requester_email,
        description=data.description,
        statutory_deadline=data.statutory_deadline,
        created_by=user.id,
        assigned_to=user.id,
        department_id=dept_id,
    )
    session.add(req)
    await session.commit()
    await session.refresh(req)

    await write_audit_log(
        session=session, action="create_request", resource_type="request",
        resource_id=str(req.id), user_id=user.id,
        details={"requester": data.requester_name, "description": data.description[:100]},
    )
    return req
```

- [ ] **Step 3: Update list_requests to filter by department**

In `backend/app/requests/router.py`, add department import and modify `list_requests`:

```python
from app.auth.dependencies import require_role, check_department_access
```

```python
@router.get("/", response_model=list[RequestRead])
async def list_requests(
    status: RequestStatus | None = None,
    assigned_to: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.STAFF)),
):
    stmt = select(RecordsRequest).order_by(RecordsRequest.created_at.desc())

    # Department scoping: non-admins see only their department
    if user.role != UserRole.ADMIN and user.department_id is not None:
        stmt = stmt.where(RecordsRequest.department_id == user.department_id)

    if status:
        stmt = stmt.where(RecordsRequest.status == status)
    if assigned_to:
        stmt = stmt.where(RecordsRequest.assigned_to == assigned_to)
    stmt = stmt.offset(offset).limit(limit)
    result = await session.execute(stmt)
    return result.scalars().all()
```

- [ ] **Step 4: Update get_request to check department access**

```python
@router.get("/{request_id}", response_model=RequestRead)
async def get_request(
    request_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.STAFF)),
):
    req = await session.get(RecordsRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    check_department_access(user, req.department_id)
    return req
```

- [ ] **Step 5: Update request_stats to scope by department**

```python
@router.get("/stats", response_model=RequestStats)
async def request_stats(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.STAFF)),
):
    # Base filter: department scoping
    dept_filter = []
    if user.role != UserRole.ADMIN and user.department_id is not None:
        dept_filter = [RecordsRequest.department_id == user.department_id]

    total = (await session.execute(
        select(func.count(RecordsRequest.id)).where(*dept_filter)
    )).scalar() or 0

    by_status = {}
    for s in RequestStatus:
        count = (await session.execute(
            select(func.count(RecordsRequest.id)).where(
                RecordsRequest.status == s, *dept_filter
            )
        )).scalar() or 0
        by_status[s.value] = count

    now = datetime.now(timezone.utc)
    three_days = now + timedelta(days=3)

    approaching = (await session.execute(
        select(func.count(RecordsRequest.id)).where(
            RecordsRequest.statutory_deadline.isnot(None),
            RecordsRequest.statutory_deadline <= three_days,
            RecordsRequest.statutory_deadline > now,
            RecordsRequest.status.notin_([RequestStatus.FULFILLED, RequestStatus.CLOSED, RequestStatus.SENT]),
            *dept_filter,
        )
    )).scalar() or 0

    overdue = (await session.execute(
        select(func.count(RecordsRequest.id)).where(
            RecordsRequest.statutory_deadline.isnot(None),
            RecordsRequest.statutory_deadline < now,
            RecordsRequest.status.notin_([RequestStatus.FULFILLED, RequestStatus.CLOSED, RequestStatus.SENT]),
            *dept_filter,
        )
    )).scalar() or 0

    return RequestStats(
        total_requests=total, by_status=by_status,
        approaching_deadline=approaching, overdue=overdue,
    )
```

- [ ] **Step 6: Add check_department_access to all request sub-endpoints**

For every endpoint that takes `request_id` in the path (`update_request`, `attach_document`, `list_attached_documents`, `remove_document`, `submit_for_review`, `mark_ready_for_release`, `approve_request`, `reject_request`, `get_timeline`, `add_timeline_event`, `get_messages`, `add_message`, `get_fees`, `add_fee`, `generate_response_letter`, `get_response_letter`, `update_response_letter`), add after loading the request:

```python
    req = await session.get(RecordsRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    check_department_access(user, req.department_id)
```

For endpoints that don't load the request directly (e.g., `get_fees`, `get_timeline`, `get_messages`), add a request lookup:

```python
    from app.models.request import RecordsRequest
    req = await session.get(RecordsRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    check_department_access(user, req.department_id)
```

- [ ] **Step 7: Write department scoping tests for requests**

Replace placeholder tests in `backend/tests/test_department_scoping.py`:

```python
import uuid
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_staff_lists_own_department_requests_only(
    client: AsyncClient, admin_token: str,
    staff_token_dept_a: str, staff_token_dept_b: str,
    dept_a: uuid.UUID, dept_b: uuid.UUID,
):
    """Staff in dept A should not see dept B requests."""
    # Create request in dept A (as staff A)
    await client.post(
        "/requests/",
        json={"requester_name": "Alice", "description": "Dept A request"},
        headers={"Authorization": f"Bearer {staff_token_dept_a}"},
    )
    # Create request in dept B (as staff B)
    await client.post(
        "/requests/",
        json={"requester_name": "Bob", "description": "Dept B request"},
        headers={"Authorization": f"Bearer {staff_token_dept_b}"},
    )
    # Staff A lists — should see only dept A
    resp = await client.get(
        "/requests/",
        headers={"Authorization": f"Bearer {staff_token_dept_a}"},
    )
    assert resp.status_code == 200
    requests = resp.json()
    assert len(requests) == 1
    assert requests[0]["description"] == "Dept A request"


@pytest.mark.asyncio
async def test_admin_sees_all_departments(
    client: AsyncClient, admin_token: str,
    staff_token_dept_a: str, staff_token_dept_b: str,
):
    """Admin sees requests from all departments."""
    await client.post(
        "/requests/",
        json={"requester_name": "Alice", "description": "Dept A"},
        headers={"Authorization": f"Bearer {staff_token_dept_a}"},
    )
    await client.post(
        "/requests/",
        json={"requester_name": "Bob", "description": "Dept B"},
        headers={"Authorization": f"Bearer {staff_token_dept_b}"},
    )
    resp = await client.get(
        "/requests/",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_staff_gets_request_in_own_department(
    client: AsyncClient, staff_token_dept_a: str,
):
    create = await client.post(
        "/requests/",
        json={"requester_name": "Alice", "description": "My dept"},
        headers={"Authorization": f"Bearer {staff_token_dept_a}"},
    )
    req_id = create.json()["id"]
    resp = await client.get(
        f"/requests/{req_id}",
        headers={"Authorization": f"Bearer {staff_token_dept_a}"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_staff_gets_request_in_other_department_403(
    client: AsyncClient,
    staff_token_dept_a: str, staff_token_dept_b: str,
):
    create = await client.post(
        "/requests/",
        json={"requester_name": "Bob", "description": "Dept B"},
        headers={"Authorization": f"Bearer {staff_token_dept_b}"},
    )
    req_id = create.json()["id"]
    resp = await client.get(
        f"/requests/{req_id}",
        headers={"Authorization": f"Bearer {staff_token_dept_a}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_request_auto_sets_department_from_user(
    client: AsyncClient, staff_token_dept_a: str, dept_a: uuid.UUID,
):
    resp = await client.post(
        "/requests/",
        json={"requester_name": "Alice", "description": "Auto dept"},
        headers={"Authorization": f"Bearer {staff_token_dept_a}"},
    )
    assert resp.status_code == 201
    assert resp.json()["department_id"] == str(dept_a)


@pytest.mark.asyncio
async def test_admin_can_specify_any_department(
    client: AsyncClient, admin_token: str, dept_b: uuid.UUID,
):
    resp = await client.post(
        "/requests/",
        json={
            "requester_name": "Admin Request",
            "description": "Cross-dept",
            "department_id": str(dept_b),
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["department_id"] == str(dept_b)


@pytest.mark.asyncio
async def test_reviewer_approves_own_department(
    client: AsyncClient,
    staff_token_dept_a: str, reviewer_token_dept_a: str,
):
    create = await client.post(
        "/requests/",
        json={"requester_name": "Alice", "description": "Review me"},
        headers={"Authorization": f"Bearer {staff_token_dept_a}"},
    )
    req_id = create.json()["id"]
    # Move to searching, then in_review
    await client.patch(
        f"/requests/{req_id}",
        json={"status": "searching"},
        headers={"Authorization": f"Bearer {staff_token_dept_a}"},
    )
    await client.post(
        f"/requests/{req_id}/submit-review",
        headers={"Authorization": f"Bearer {staff_token_dept_a}"},
    )
    # Reviewer in same dept approves
    resp = await client.post(
        f"/requests/{req_id}/ready-for-release",
        headers={"Authorization": f"Bearer {reviewer_token_dept_a}"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_reviewer_cannot_approve_other_department(
    client: AsyncClient,
    staff_token_dept_b: str, reviewer_token_dept_a: str,
):
    create = await client.post(
        "/requests/",
        json={"requester_name": "Bob", "description": "Other dept"},
        headers={"Authorization": f"Bearer {staff_token_dept_b}"},
    )
    req_id = create.json()["id"]
    await client.patch(
        f"/requests/{req_id}",
        json={"status": "searching"},
        headers={"Authorization": f"Bearer {staff_token_dept_b}"},
    )
    await client.post(
        f"/requests/{req_id}/submit-review",
        headers={"Authorization": f"Bearer {staff_token_dept_b}"},
    )
    # Reviewer in dept A cannot touch dept B request
    resp = await client.post(
        f"/requests/{req_id}/ready-for-release",
        headers={"Authorization": f"Bearer {reviewer_token_dept_a}"},
    )
    assert resp.status_code == 403
```

- [ ] **Step 8: Run tests**

Run: `docker compose exec -T api sh -c "TESTING=1 python -m pytest tests/test_department_scoping.py -v"`
Expected: 8 passed

Run: `docker compose exec -T api sh -c "TESTING=1 python -m pytest tests/ -v"`
Expected: 120 passed (112 + 8 scoping)

- [ ] **Step 9: Commit**

```bash
git add backend/app/requests/router.py backend/app/schemas/request.py backend/tests/test_department_scoping.py
git commit -m "feat(phase2): department scoping on requests endpoints"
```

---

## Task 5: Scope Exemption Flag Endpoints by Department

**Files:**
- Modify: `backend/app/exemptions/router.py`

- [ ] **Step 1: Add department check to flag endpoints**

In `backend/app/exemptions/router.py`, add import:

```python
from app.auth.dependencies import require_role, check_department_access
from app.models.request import RecordsRequest
```

Modify `list_flags` to check department:

```python
@router.get("/flags/{request_id}", response_model=list[ExemptionFlagRead])
async def list_flags(
    request_id: uuid.UUID,
    status: FlagStatus | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.STAFF)),
):
    req = await session.get(RecordsRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    check_department_access(user, req.department_id)

    stmt = select(ExemptionFlag).where(
        ExemptionFlag.request_id == request_id
    ).order_by(ExemptionFlag.confidence.desc())
    if status:
        stmt = stmt.where(ExemptionFlag.status == status)
    result = await session.execute(stmt)
    return result.scalars().all()
```

Modify `scan_for_exemptions` similarly — add after loading the request:

```python
    check_department_access(user, req.department_id)
```

Modify `review_flag` — look up the request through the flag:

```python
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

    # Department check via the flag's request
    req = await session.get(RecordsRequest, flag.request_id)
    if req:
        check_department_access(user, req.department_id)

    # ... rest unchanged ...
```

- [ ] **Step 2: Run tests**

Run: `docker compose exec -T api sh -c "TESTING=1 python -m pytest tests/ -v"`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add backend/app/exemptions/router.py
git commit -m "feat(phase2): department scoping on exemption flag endpoints"
```

---

## Task 6: Compliance Template Documents

**Files:**
- Create: `backend/compliance_templates/ai-use-disclosure.md`
- Create: `backend/compliance_templates/response-letter-disclosure.md`
- Create: `backend/compliance_templates/caia-impact-assessment.md`
- Create: `backend/compliance_templates/ai-governance-policy.md`
- Create: `backend/compliance_templates/data-residency-attestation.md`
- Create: `backend/scripts/seed_templates.py`
- Create: `backend/tests/test_compliance_templates.py`

- [ ] **Step 1: Create AI Use Disclosure template**

Create `backend/compliance_templates/ai-use-disclosure.md`:

```markdown
# Public AI Use Disclosure

**{{CITY_NAME}}, {{STATE}}**
**Effective Date:** {{EFFECTIVE_DATE}}

## Purpose

This disclosure informs the public that {{CITY_NAME}} uses an artificial intelligence system to assist staff in processing public records requests under {{STATE_STATUTE}}.

## System Description

{{CITY_NAME}} uses CivicRecords AI, an open-source, locally-hosted software system, to:

- **Search and retrieve** potentially responsive documents from city records using natural language queries
- **Flag potential exemptions** in responsive documents using pattern-matching rules and AI-assisted review
- **Draft response letters** summarizing responsive and withheld documents

## What the AI Does NOT Do

- The AI does not make final decisions about what records to release or withhold
- The AI does not automatically redact documents
- The AI does not deny or approve records requests
- The AI does not communicate directly with requesters

## Human Oversight

All AI-generated suggestions, search results, exemption flags, and draft letters are reviewed and approved by trained city staff before any action is taken. No records request response is sent without explicit human authorization.

## Data Sovereignty

All data processed by this system remains on {{CITY_NAME}}-owned hardware within the city's network. No resident data is transmitted to cloud services, third parties, or external servers.

## Contact

Questions about this disclosure may be directed to:
{{CONTACT_NAME}}
{{CONTACT_EMAIL}}

---

*This disclosure was prepared in accordance with transparency requirements for government use of artificial intelligence. Template provided by CivicRecords AI (Apache 2.0). Consult your city attorney before adoption.*
```

- [ ] **Step 2: Create Response Letter Disclosure template**

Create `backend/compliance_templates/response-letter-disclosure.md`:

```markdown
# Response Letter AI Disclosure Language

**For inclusion in records request response letters**

---

## Standard Disclosure Paragraph

The following paragraph should be included in all records request response letters when CivicRecords AI was used to assist in processing the request:

> **AI Assistance Disclosure:** This response was prepared with the assistance of CivicRecords AI, an artificial intelligence system used by {{CITY_NAME}} to search and retrieve potentially responsive documents. All documents identified by the AI system were reviewed by city staff, and all decisions regarding disclosure, withholding, and redaction were made by authorized personnel. The AI system did not make any independent decisions regarding this response.

## When to Include

Include this disclosure when any of the following AI features were used during request processing:

1. AI-powered document search (semantic or hybrid search)
2. AI-assisted exemption detection
3. AI-drafted response letter content

## Placement

Insert the disclosure paragraph:
- After the list of responsive documents
- Before the closing signature
- In a clearly labeled section

---

*Template provided by CivicRecords AI (Apache 2.0). Consult your city attorney before adoption.*
```

- [ ] **Step 3: Create CAIA Impact Assessment template**

Create `backend/compliance_templates/caia-impact-assessment.md`:

```markdown
# Colorado AI Act (CAIA) Impact Assessment

**System:** CivicRecords AI
**Deployer:** {{CITY_NAME}}, {{STATE}}
**Assessment Date:** {{EFFECTIVE_DATE}}
**Assessor:** {{CONTACT_NAME}}

---

## 1. System Classification

**Classification: NOT a High-Risk AI System**

CivicRecords AI is a staff productivity tool that assists municipal employees in processing public records requests. It does not make consequential decisions as defined under SB 24-205.

### Rationale

The system does NOT:
- Automatically deny, approve, or release records requests
- Make autonomous decisions affecting individual rights or access to services
- Perform automated redaction without human review
- Communicate decisions directly to requesters
- Operate without human oversight at any decision point

The system DOES:
- Suggest potentially responsive documents (staff reviews and selects)
- Flag potential exemptions (staff reviews, accepts, or rejects each flag)
- Draft response letters (staff reviews and approves before sending)

All outputs are explicitly labeled as "AI-generated draft requiring human review" at both the API and UI layers.

## 2. Human-in-the-Loop Enforcement

| Decision Point | AI Role | Human Role | Enforcement |
|---------------|---------|------------|-------------|
| Document search results | Ranks and suggests | Reviews and selects | UI requires explicit selection |
| Exemption flags | Detects and flags | Accepts or rejects each flag | API prevents auto-acceptance |
| Response letters | Generates draft | Reviews, edits, approves | API requires authenticated approval |
| Record release | None | Full authority | No API endpoint for auto-release |

## 3. Data Governance

- All data resides on {{CITY_NAME}}-owned hardware
- No data transmitted to cloud services or third parties
- No telemetry, analytics, or crash reporting
- Data sovereignty verified via automated script
- Audit logs are hash-chained and append-only

## 4. Transparency Measures

- Public AI Use Disclosure posted at {{DISCLOSURE_URL}}
- Response letters include AI assistance disclosure language
- All AI-generated content visually labeled in the user interface
- AI content labels enforced at the API response layer
- Source code publicly available (Apache 2.0 license)

## 5. Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| AI hallucinates non-existent records | Search results cite specific documents with page numbers |
| AI misses an exemption | Rules-primary detection; LLM is secondary suggestion only |
| AI over-flags exemptions | All flags require human review; acceptance rate tracked |
| Bias in search results | Hybrid search (semantic + keyword) reduces single-model bias |
| Data breach | Air-gapped deployment; no outbound connections |

## 6. Ongoing Monitoring

- Exemption flag acceptance/rejection rates tracked by category
- Audit logs reviewed periodically for anomalies
- Model updates require admin authorization
- Assessment reviewed annually or when system capabilities change

---

*This assessment template is pre-filled based on CivicRecords AI architecture. Consult your city attorney and Colorado Attorney General guidance for final compliance determination. Template provided by CivicRecords AI (Apache 2.0).*
```

- [ ] **Step 4: Create AI Governance Policy template**

Create `backend/compliance_templates/ai-governance-policy.md`:

```markdown
# AI Governance Policy

**{{CITY_NAME}}, {{STATE}}**
**Effective Date:** {{EFFECTIVE_DATE}}
**Policy Owner:** {{CONTACT_NAME}}

---

## 1. Purpose

This policy establishes governance principles for the use of artificial intelligence systems by {{CITY_NAME}} municipal operations, beginning with CivicRecords AI for public records request processing.

## 2. Scope

This policy applies to all AI systems deployed by {{CITY_NAME}} that assist in government decision-making, service delivery, or administrative functions.

## 3. Governing Principles

### 3.1 Human Authority
AI systems shall augment, not replace, human decision-making. No AI system shall make final decisions regarding resident rights, access to services, or legal determinations without explicit human review and authorization.

### 3.2 Transparency
The public shall be informed when AI systems are used in government operations that affect them. AI-generated content shall be clearly labeled. Source code for AI systems should be publicly available where feasible.

### 3.3 Data Sovereignty
Resident data processed by AI systems shall remain on city-owned or city-controlled infrastructure. No resident data shall be transmitted to third-party cloud services for AI processing without explicit authorization from the City Manager and public notice.

### 3.4 Accountability
Each AI system shall have a designated human owner responsible for its operation, monitoring, and compliance. All AI system actions shall be logged in tamper-evident audit trails.

### 3.5 Fairness and Non-Discrimination
AI systems shall be monitored for biased outcomes. Detection rates, error rates, and outcomes shall be tracked by category to identify and correct disparate impacts.

## 4. Approval Process

New AI system deployments require:
1. Impact assessment (using CAIA template or equivalent)
2. Review by City Attorney
3. Approval by City Manager
4. Public disclosure posting
5. Staff training completion

## 5. Ongoing Compliance

- Annual review of each deployed AI system
- Quarterly audit log review
- Public reporting of AI system performance metrics
- Incident response procedure for AI system failures or misuse

## 6. References

- Colorado AI Act (SB 24-205)
- GovAI Coalition Framework
- City of Boston AI Executive Order (2024)
- City of San Jose AI Policy (2019)
- City of Bellevue AI Principles (2023)

---

*Template based on frameworks from GovAI Coalition, Boston, San Jose, Bellevue, and Garfield County CO. Consult your city attorney before adoption. Template provided by CivicRecords AI (Apache 2.0).*
```

- [ ] **Step 5: Create Data Residency Attestation template**

Create `backend/compliance_templates/data-residency-attestation.md`:

```markdown
# Data Residency Attestation

**{{CITY_NAME}}, {{STATE}}**
**Date:** {{EFFECTIVE_DATE}}

---

## Attestation

I, {{CONTACT_NAME}}, {{CONTACT_TITLE}}, hereby attest that:

1. **Local Deployment:** CivicRecords AI is installed and operates entirely on hardware owned and controlled by {{CITY_NAME}}, located at {{FACILITY_ADDRESS}}.

2. **No Cloud Dependencies:** The system does not transmit any data — including documents, search queries, AI model inputs/outputs, user information, or audit logs — to any cloud service, third-party server, or external endpoint.

3. **No Telemetry:** The system does not collect or transmit telemetry, usage analytics, crash reports, or any other operational data to external parties.

4. **Local AI Processing:** All artificial intelligence inference (document search, exemption detection, response drafting) is performed locally using the Ollama runtime on city-owned hardware. No AI queries are sent to cloud-based AI services.

5. **Verification:** Data residency has been verified using the automated sovereignty verification script included with the software (`verify-sovereignty.sh` / `verify-sovereignty.ps1`), which confirms no outbound network connections from the application.

6. **Network Isolation:** The system is configured to operate on the city's internal network and is not exposed to the public internet.

## Hardware Specifications

| Component | Details |
|-----------|---------|
| Server Location | {{FACILITY_ADDRESS}} |
| Operating System | {{SERVER_OS}} |
| CPU | {{SERVER_CPU}} |
| RAM | {{SERVER_RAM}} |
| Storage | {{SERVER_STORAGE}} |

## Authorized Signatories

**IT Director / System Administrator:**

Signature: ________________________
Name: {{CONTACT_NAME}}
Title: {{CONTACT_TITLE}}
Date: {{EFFECTIVE_DATE}}

**City Manager / Authorized Official:**

Signature: ________________________
Name: ________________________
Title: ________________________
Date: ________________________

---

*This attestation template is provided by CivicRecords AI (Apache 2.0). Consult your city attorney regarding attestation requirements in your jurisdiction.*
```

- [ ] **Step 6: Create seed script**

Create `backend/scripts/seed_templates.py`:

```python
"""Seed compliance template documents into the disclosure_templates table.

Usage:
    python -m scripts.seed_templates

Idempotent — skips templates that already exist by template_type.
"""
import asyncio
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.exemption import DisclosureTemplate
from app.models.user import User, UserRole

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "compliance_templates"

TEMPLATES = [
    ("ai_use_disclosure", "ai-use-disclosure.md"),
    ("response_letter_disclosure", "response-letter-disclosure.md"),
    ("caia_impact_assessment", "caia-impact-assessment.md"),
    ("ai_governance_policy", "ai-governance-policy.md"),
    ("data_residency_attestation", "data-residency-attestation.md"),
]


async def seed_templates(session: AsyncSession) -> int:
    """Seed compliance templates. Returns count of newly created templates."""
    # Find an admin user to attribute the templates to
    result = await session.execute(
        select(User).where(User.role == UserRole.ADMIN).limit(1)
    )
    admin = result.scalar_one_or_none()
    if not admin:
        print("ERROR: No admin user found. Create an admin user first.")
        return 0

    created = 0
    for template_type, filename in TEMPLATES:
        # Skip if already seeded
        existing = await session.execute(
            select(DisclosureTemplate).where(
                DisclosureTemplate.template_type == template_type
            )
        )
        if existing.scalar_one_or_none():
            print(f"  SKIP: {template_type} (already exists)")
            continue

        filepath = TEMPLATE_DIR / filename
        if not filepath.exists():
            print(f"  WARN: {filename} not found at {filepath}")
            continue

        content = filepath.read_text(encoding="utf-8")
        template = DisclosureTemplate(
            template_type=template_type,
            content=content,
            updated_by=admin.id,
        )
        session.add(template)
        created += 1
        print(f"  CREATE: {template_type}")

    await session.commit()
    return created


async def main():
    engine = create_async_engine(settings.database_url)
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as session:
        count = await seed_templates(session)
        print(f"\nSeeded {count} compliance templates.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 7: Write compliance template tests**

Create `backend/tests/test_compliance_templates.py`:

```python
import re
from pathlib import Path

import pytest
from httpx import AsyncClient

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "compliance_templates"

EXPECTED_TYPES = [
    "ai_use_disclosure",
    "response_letter_disclosure",
    "caia_impact_assessment",
    "ai_governance_policy",
    "data_residency_attestation",
]


def test_all_template_files_exist():
    """T-U8: Each template file exists and has content."""
    files = [
        "ai-use-disclosure.md",
        "response-letter-disclosure.md",
        "caia-impact-assessment.md",
        "ai-governance-policy.md",
        "data-residency-attestation.md",
    ]
    for f in files:
        path = TEMPLATE_DIR / f
        assert path.exists(), f"Missing template file: {f}"
        content = path.read_text(encoding="utf-8")
        assert len(content) > 100, f"Template {f} is too short"


def test_templates_contain_placeholder_variables():
    """Templates use {{VARIABLE}} syntax for city-specific values."""
    for f in TEMPLATE_DIR.glob("*.md"):
        content = f.read_text(encoding="utf-8")
        placeholders = re.findall(r"\{\{(\w+)\}\}", content)
        assert len(placeholders) > 0, f"Template {f.name} has no placeholder variables"
        assert "CITY_NAME" in placeholders, f"Template {f.name} missing {{{{CITY_NAME}}}}"


def test_template_render_replaces_variables():
    """T-U1/T-U2/T-U3: Variable substitution works."""
    template = "Dear {{CITY_NAME}} in {{STATE}}, effective {{EFFECTIVE_DATE}}."
    variables = {
        "CITY_NAME": "Springfield",
        "STATE": "Colorado",
        "EFFECTIVE_DATE": "2026-01-01",
    }
    rendered = template
    for key, value in variables.items():
        rendered = rendered.replace("{{" + key + "}}", value)

    assert "Springfield" in rendered
    assert "Colorado" in rendered
    assert "2026-01-01" in rendered
    assert "{{" not in rendered


def test_template_render_missing_variables_preserved():
    """T-U4: Missing variables remain as placeholders."""
    template = "{{CITY_NAME}} uses {{UNKNOWN_VAR}} system."
    variables = {"CITY_NAME": "Springfield"}
    rendered = template
    for key, value in variables.items():
        rendered = rendered.replace("{{" + key + "}}", value)

    assert "Springfield" in rendered
    assert "{{UNKNOWN_VAR}}" in rendered


@pytest.mark.asyncio
async def test_list_templates_unauthenticated(client: AsyncClient):
    """T-I2: Unauthenticated access rejected."""
    resp = await client.get("/exemptions/templates/")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_template_staff_forbidden(client: AsyncClient, staff_token: str):
    """T-I7: Staff cannot create templates."""
    resp = await client.post(
        "/exemptions/templates/",
        json={"template_type": "custom", "content": "test"},
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert resp.status_code == 403
```

- [ ] **Step 8: Run tests**

Run: `docker compose exec -T api sh -c "TESTING=1 python -m pytest tests/test_compliance_templates.py -v"`
Expected: 6 passed

- [ ] **Step 9: Commit**

```bash
git add backend/compliance_templates/ backend/scripts/seed_templates.py backend/tests/test_compliance_templates.py
git commit -m "feat(phase2): compliance template documents and seed script (spec 6.4/6.5)"
```

---

## Task 7: Template Render Endpoint

**Files:**
- Modify: `backend/app/exemptions/router.py`
- Modify: `backend/app/schemas/exemption.py`
- Modify: `backend/tests/test_compliance_templates.py`

- [ ] **Step 1: Add render schema**

Add to `backend/app/schemas/exemption.py`:

```python
class DisclosureTemplateRendered(BaseModel):
    id: uuid.UUID
    template_type: str
    rendered_content: str
    has_unresolved_variables: bool
```

- [ ] **Step 2: Add render endpoint**

Add to `backend/app/exemptions/router.py`:

```python
from app.models.city_profile import CityProfile
from app.schemas.exemption import DisclosureTemplateRendered
import re


@router.get("/templates/{template_id}/render", response_model=DisclosureTemplateRendered)
async def render_template(
    template_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.STAFF)),
):
    """Render a template with city profile variables substituted."""
    template = await session.get(DisclosureTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Load city profile for variable substitution
    result = await session.execute(select(CityProfile).limit(1))
    profile = result.scalar_one_or_none()

    variables = {}
    if profile:
        variables = {
            "CITY_NAME": profile.city_name or "",
            "STATE": profile.state or "",
            "CONTACT_NAME": "",
            "CONTACT_EMAIL": "",
            "CONTACT_TITLE": "",
            "EFFECTIVE_DATE": datetime.now(timezone.utc).strftime("%B %d, %Y"),
            "STATE_STATUTE": "",
            "DISCLOSURE_URL": "",
            "FACILITY_ADDRESS": "",
            "SERVER_OS": "",
            "SERVER_CPU": "",
            "SERVER_RAM": "",
            "SERVER_STORAGE": "",
        }
        # Pull extra fields from profile_data JSONB if available
        if profile.profile_data and isinstance(profile.profile_data, dict):
            for key in variables:
                if key.lower() in profile.profile_data:
                    variables[key] = str(profile.profile_data[key.lower()])

    rendered = template.content
    for key, value in variables.items():
        if value:
            rendered = rendered.replace("{{" + key + "}}", value)

    has_unresolved = bool(re.search(r"\{\{\w+\}\}", rendered))

    return DisclosureTemplateRendered(
        id=template.id,
        template_type=template.template_type,
        rendered_content=rendered,
        has_unresolved_variables=has_unresolved,
    )
```

- [ ] **Step 3: Add update endpoint for templates**

Add to `backend/app/exemptions/router.py`:

```python
class DisclosureTemplateUpdate(BaseModel):
    content: str | None = None
    state_code: str | None = None
```

Add to `backend/app/schemas/exemption.py`:

```python
class DisclosureTemplateUpdate(BaseModel):
    content: str | None = None
    state_code: str | None = None
```

```python
@router.put("/templates/{template_id}", response_model=DisclosureTemplateRead)
async def update_template(
    template_id: uuid.UUID,
    data: DisclosureTemplateUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    template = await session.get(DisclosureTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    if data.content is not None:
        template.content = data.content
        template.version += 1
    if data.state_code is not None:
        template.state_code = data.state_code
    template.updated_by = user.id
    template.updated_at = datetime.now(timezone.utc)

    await session.commit()
    await session.refresh(template)

    await write_audit_log(
        session=session, action="update_disclosure_template", resource_type="disclosure_template",
        resource_id=str(template.id), user_id=user.id,
        details={"template_type": template.template_type, "new_version": template.version},
    )
    return template
```

- [ ] **Step 4: Add render and update tests**

Add to `backend/tests/test_compliance_templates.py`:

```python
@pytest.mark.asyncio
async def test_render_template_with_profile(client: AsyncClient, admin_token: str):
    """T-I4: Render substitutes city profile variables."""
    # Create city profile
    await client.post(
        "/city-profile",
        json={"city_name": "Springfield", "state": "CO"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    # Create a template
    create = await client.post(
        "/exemptions/templates/",
        json={
            "template_type": "test_render",
            "content": "Welcome to {{CITY_NAME}}, {{STATE}}!",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    template_id = create.json()["id"]

    resp = await client.get(
        f"/exemptions/templates/{template_id}/render",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "Springfield" in data["rendered_content"]
    assert "CO" in data["rendered_content"]
    assert data["has_unresolved_variables"] is False


@pytest.mark.asyncio
async def test_render_template_without_profile(client: AsyncClient, admin_token: str):
    """T-I5: Without profile, placeholders remain."""
    create = await client.post(
        "/exemptions/templates/",
        json={
            "template_type": "test_no_profile",
            "content": "Hello {{CITY_NAME}}",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    template_id = create.json()["id"]

    resp = await client.get(
        f"/exemptions/templates/{template_id}/render",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["has_unresolved_variables"] is True


@pytest.mark.asyncio
async def test_update_template_admin(client: AsyncClient, admin_token: str):
    """T-I8: Admin can update template."""
    create = await client.post(
        "/exemptions/templates/",
        json={"template_type": "test_update", "content": "Original"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    template_id = create.json()["id"]

    resp = await client.put(
        f"/exemptions/templates/{template_id}",
        json={"content": "Updated content"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["content"] == "Updated content"
    assert resp.json()["version"] == 2


@pytest.mark.asyncio
async def test_update_template_staff_forbidden(client: AsyncClient, admin_token: str, staff_token: str):
    """T-I9: Staff cannot update templates."""
    create = await client.post(
        "/exemptions/templates/",
        json={"template_type": "test_no_edit", "content": "Original"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    template_id = create.json()["id"]

    resp = await client.put(
        f"/exemptions/templates/{template_id}",
        json={"content": "Hacked"},
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert resp.status_code == 403
```

- [ ] **Step 5: Run tests**

Run: `docker compose exec -T api sh -c "TESTING=1 python -m pytest tests/test_compliance_templates.py -v"`
Expected: 10 passed

- [ ] **Step 6: Commit**

```bash
git add backend/app/exemptions/router.py backend/app/schemas/exemption.py backend/tests/test_compliance_templates.py
git commit -m "feat(phase2): template render endpoint with city profile variable substitution"
```

---

## Task 8: Model Registry CRUD Endpoints

**Files:**
- Create: `backend/app/schemas/model_registry.py`
- Modify: `backend/app/admin/router.py`
- Create: `backend/tests/test_model_registry.py`

- [ ] **Step 1: Create model registry schemas**

Create `backend/app/schemas/model_registry.py`:

```python
from datetime import datetime
from pydantic import BaseModel


class ModelRegistryCreate(BaseModel):
    model_name: str
    model_version: str | None = None
    parameter_count: int | None = None
    license: str | None = None
    model_card_url: str | None = None
    context_window_size: int | None = None
    supports_ner: bool = False
    supports_vision: bool = False


class ModelRegistryRead(BaseModel):
    id: int
    model_name: str
    model_version: str | None
    parameter_count: int | None
    license: str | None
    model_card_url: str | None
    is_active: bool
    added_at: datetime
    context_window_size: int | None
    supports_ner: bool
    supports_vision: bool
    model_config = {"from_attributes": True}


class ModelRegistryUpdate(BaseModel):
    model_version: str | None = None
    parameter_count: int | None = None
    license: str | None = None
    model_card_url: str | None = None
    is_active: bool | None = None
    context_window_size: int | None = None
    supports_ner: bool | None = None
    supports_vision: bool | None = None
```

- [ ] **Step 2: Add registry endpoints to admin router**

Add to `backend/app/admin/router.py`:

```python
from app.models.document import ModelRegistry
from app.schemas.model_registry import ModelRegistryCreate, ModelRegistryRead, ModelRegistryUpdate


@router.get("/models/registry", response_model=list[ModelRegistryRead])
async def list_model_registry(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    result = await session.execute(
        select(ModelRegistry).order_by(ModelRegistry.added_at.desc())
    )
    return result.scalars().all()


@router.post("/models/registry", response_model=ModelRegistryRead, status_code=201)
async def register_model(
    data: ModelRegistryCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    model = ModelRegistry(
        model_name=data.model_name,
        model_version=data.model_version,
        parameter_count=data.parameter_count,
        license=data.license,
        model_card_url=data.model_card_url,
        context_window_size=data.context_window_size,
        supports_ner=data.supports_ner,
        supports_vision=data.supports_vision,
    )
    session.add(model)
    await session.commit()
    await session.refresh(model)

    await write_audit_log(
        session=session, action="register_model", resource_type="model_registry",
        resource_id=str(model.id), user_id=user.id,
        details={"model_name": data.model_name},
    )
    return model


@router.patch("/models/registry/{model_id}", response_model=ModelRegistryRead)
async def update_model_registry(
    model_id: int,
    data: ModelRegistryUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    model = await session.get(ModelRegistry, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(model, field, value)

    await session.commit()
    await session.refresh(model)

    await write_audit_log(
        session=session, action="update_model_registry", resource_type="model_registry",
        resource_id=str(model.id), user_id=user.id,
        details=data.model_dump(exclude_none=True),
    )
    return model


@router.delete("/models/registry/{model_id}", status_code=204)
async def delete_model_registry(
    model_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    model = await session.get(ModelRegistry, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    await session.delete(model)
    await session.commit()

    await write_audit_log(
        session=session, action="delete_model_registry", resource_type="model_registry",
        resource_id=str(model_id), user_id=user.id,
        details={"model_name": model.model_name},
    )
```

- [ ] **Step 3: Write model registry tests**

Create `backend/tests/test_model_registry.py`:

```python
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_model(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/admin/models/registry",
        json={
            "model_name": "gemma4:e4b",
            "model_version": "4.0",
            "parameter_count": 4500000000,
            "license": "Apache 2.0",
            "model_card_url": "https://ai.google.dev/gemma",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["model_name"] == "gemma4:e4b"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_register_model_requires_admin(client: AsyncClient, staff_token: str):
    resp = await client.post(
        "/admin/models/registry",
        json={"model_name": "test"},
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_model_registry(client: AsyncClient, admin_token: str):
    await client.post(
        "/admin/models/registry",
        json={"model_name": "gemma4:e4b"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = await client.get(
        "/admin/models/registry",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_update_model_registry(client: AsyncClient, admin_token: str):
    create = await client.post(
        "/admin/models/registry",
        json={"model_name": "gemma4:e4b"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    model_id = create.json()["id"]
    resp = await client.patch(
        f"/admin/models/registry/{model_id}",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_delete_model_registry(client: AsyncClient, admin_token: str):
    create = await client.post(
        "/admin/models/registry",
        json={"model_name": "delete-me"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    model_id = create.json()["id"]
    resp = await client.delete(
        f"/admin/models/registry/{model_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_existing_models_endpoint_still_works(client: AsyncClient, admin_token: str):
    """M-I6: Original /admin/models endpoint unchanged."""
    resp = await client.get(
        "/admin/models",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert "status" in resp.json()
```

- [ ] **Step 4: Run tests**

Run: `docker compose exec -T api sh -c "TESTING=1 python -m pytest tests/test_model_registry.py -v"`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/model_registry.py backend/app/admin/router.py backend/tests/test_model_registry.py
git commit -m "feat(phase2): model registry CRUD endpoints (spec 6.7)"
```

---

## Task 9: 50-State Exemption Rules Seed Script

**Files:**
- Modify: `backend/scripts/seed_rules.py`
- Create: `backend/tests/test_exemption_rules_seed.py`

This is the largest single task. The seed script must cover all 50 states + DC with at least one keyword rule per state (the statute-specific exemption categories). Universal PII regex rules apply to all states.

- [ ] **Step 1: Research and write 50-state rules**

Extend `backend/scripts/seed_rules.py` to cover all 50 states + DC. Each state needs:
- The governing statute name in the description
- At least 2-3 keyword exemption categories per state
- Universal PII regex rules shared across all states

The existing pattern:

```python
RULES = [
    # Colorado CORA
    {"state_code": "CO", "category": "law_enforcement", "rule_type": "keyword",
     "rule_definition": "investigation|informant|undercover|law enforcement",
     "description": "CRS 24-72-305.5 — active criminal investigation"},
    # ... more states
]
```

Expand to all 50 states following this exact pattern. Group by region for maintainability. Each state must reference its actual open records statute.

Note: This step requires statutory research for each state. The implementer should reference each state's open records/FOIA statute to identify the key exemption categories (typically: law enforcement, personnel records, attorney-client privilege, trade secrets, personal privacy, medical records, security, deliberative process).

- [ ] **Step 2: Add idempotency check**

The existing script already checks: `if existing rule with same category + state_code exists, skip`. Verify this works correctly for all new rules.

- [ ] **Step 3: Write seed validation tests**

Create `backend/tests/test_exemption_rules_seed.py`:

```python
import re
import pytest


def test_all_50_states_covered():
    """E-U1: At least one rule per state."""
    from scripts.seed_rules import RULES

    state_codes = {r["state_code"] for r in RULES}
    all_states = {
        "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
        "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
        "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
        "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
        "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
        "DC",
    }
    missing = all_states - state_codes
    assert not missing, f"Missing states: {missing}"


def test_each_state_has_keyword_rule():
    """E-U4: Every state has at least one keyword rule."""
    from scripts.seed_rules import RULES

    keyword_states = {r["state_code"] for r in RULES if r["rule_type"] == "keyword"}
    all_states = {
        "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
        "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
        "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
        "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
        "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
        "DC",
    }
    missing = all_states - keyword_states
    assert not missing, f"States without keyword rules: {missing}"


def test_regex_rules_are_valid():
    """E-U5: All regex rule definitions compile successfully."""
    from scripts.seed_rules import RULES

    for rule in RULES:
        if rule["rule_type"] == "regex":
            try:
                re.compile(rule["rule_definition"])
            except re.error as e:
                pytest.fail(
                    f"Invalid regex for {rule['state_code']}/{rule['category']}: "
                    f"{rule['rule_definition']} — {e}"
                )


def test_all_rules_have_descriptions():
    """Every rule has a non-empty description."""
    from scripts.seed_rules import RULES

    for i, rule in enumerate(RULES):
        assert rule.get("description"), f"Rule {i} ({rule['state_code']}/{rule['category']}) missing description"
```

- [ ] **Step 4: Run tests**

Run: `docker compose exec -T api sh -c "TESTING=1 python -m pytest tests/test_exemption_rules_seed.py -v"`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/seed_rules.py backend/tests/test_exemption_rules_seed.py
git commit -m "feat(phase2): expand exemption rules to all 50 states + DC"
```

---

## Task 10: Exemption Auditability Dashboard Enhancements

**Files:**
- Modify: `backend/app/exemptions/router.py`
- Modify: `backend/app/schemas/exemption.py`
- Create: `backend/tests/test_exemption_dashboard.py`

- [ ] **Step 1: Add enhanced dashboard schemas**

Add to `backend/app/schemas/exemption.py`:

```python
class ExemptionAccuracyReport(BaseModel):
    category: str
    total_flags: int
    accepted: int
    rejected: int
    pending: int
    acceptance_rate: float


class ExemptionDashboardEnhanced(ExemptionDashboard):
    accuracy_by_category: list[ExemptionAccuracyReport]
```

- [ ] **Step 2: Add accuracy dashboard endpoint**

Add to `backend/app/exemptions/router.py`:

```python
from app.schemas.exemption import ExemptionAccuracyReport

@router.get("/dashboard/accuracy", response_model=list[ExemptionAccuracyReport])
async def exemption_accuracy(
    department_id: uuid.UUID | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Acceptance/rejection rates by category, optionally filtered by department."""
    stmt = (
        select(
            ExemptionFlag.category,
            ExemptionFlag.status,
            func.count(ExemptionFlag.id),
        )
        .group_by(ExemptionFlag.category, ExemptionFlag.status)
    )

    if department_id:
        stmt = stmt.join(
            RecordsRequest, ExemptionFlag.request_id == RecordsRequest.id
        ).where(RecordsRequest.department_id == department_id)

    result = await session.execute(stmt)
    rows = result.fetchall()

    # Aggregate by category
    cats: dict[str, dict] = {}
    for category, status, count in rows:
        if category not in cats:
            cats[category] = {"total": 0, "accepted": 0, "rejected": 0, "pending": 0}
        cats[category]["total"] += count
        if status == FlagStatus.ACCEPTED:
            cats[category]["accepted"] += count
        elif status == FlagStatus.REJECTED:
            cats[category]["rejected"] += count
        else:
            cats[category]["pending"] += count

    reports = []
    for cat, data in sorted(cats.items()):
        reviewed = data["accepted"] + data["rejected"]
        rate = data["accepted"] / reviewed if reviewed > 0 else 0.0
        reports.append(ExemptionAccuracyReport(
            category=cat,
            total_flags=data["total"],
            accepted=data["accepted"],
            rejected=data["rejected"],
            pending=data["pending"],
            acceptance_rate=round(rate, 3),
        ))
    return reports


@router.get("/dashboard/export")
async def export_flag_data(
    format: str = "json",
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Export exemption flag data as JSON or CSV."""
    result = await session.execute(
        select(ExemptionFlag).order_by(ExemptionFlag.created_at.desc())
    )
    flags = result.scalars().all()

    if format == "csv":
        import csv
        import io
        from fastapi.responses import StreamingResponse

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "id", "request_id", "category", "confidence",
            "status", "reviewed_by", "reviewed_at", "created_at",
        ])
        for f in flags:
            writer.writerow([
                str(f.id), str(f.request_id), f.category, f.confidence,
                f.status.value, str(f.reviewed_by) if f.reviewed_by else "",
                str(f.reviewed_at) if f.reviewed_at else "", str(f.created_at),
            ])
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=exemption-flags.csv"},
        )

    # Default: JSON
    return [
        {
            "id": str(f.id),
            "request_id": str(f.request_id),
            "category": f.category,
            "confidence": f.confidence,
            "status": f.status.value,
            "reviewed_by": str(f.reviewed_by) if f.reviewed_by else None,
            "reviewed_at": str(f.reviewed_at) if f.reviewed_at else None,
            "created_at": str(f.created_at),
        }
        for f in flags
    ]
```

- [ ] **Step 3: Write dashboard tests**

Create `backend/tests/test_exemption_dashboard.py`:

```python
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_accuracy_endpoint_empty(client: AsyncClient, admin_token: str):
    resp = await client.get(
        "/exemptions/dashboard/accuracy",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_export_json(client: AsyncClient, admin_token: str):
    resp = await client.get(
        "/exemptions/dashboard/export?format=json",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_export_csv(client: AsyncClient, admin_token: str):
    resp = await client.get(
        "/exemptions/dashboard/export?format=csv",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_dashboard_requires_admin(client: AsyncClient, staff_token: str):
    resp = await client.get(
        "/exemptions/dashboard/accuracy",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert resp.status_code == 403
```

- [ ] **Step 4: Run tests**

Run: `docker compose exec -T api sh -c "TESTING=1 python -m pytest tests/test_exemption_dashboard.py -v"`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/exemptions/router.py backend/app/schemas/exemption.py backend/tests/test_exemption_dashboard.py
git commit -m "feat(phase2): exemption auditability dashboard with accuracy rates and export (spec 6.6)"
```

---

## Task 11: Version Bump and Final Regression

**Files:**
- Modify: `backend/app/config.py`
- Modify: `README.md`
- Modify: `docs/index.html`

- [ ] **Step 1: Bump version to 1.1.0**

In `backend/app/config.py`, change:

```python
APP_VERSION = "1.1.0"
```

- [ ] **Step 2: Update README status section**

Update the Status section to reflect v1.1.0 and Phase 2 deliverables.

- [ ] **Step 3: Update landing page version badge**

In `docs/index.html`, change `v1.0.1` to `v1.1.0` in the hero badge.

- [ ] **Step 4: Run full test suite**

Run: `docker compose exec -T api sh -c "TESTING=1 python -m pytest tests/ -v"`
Expected: 150+ passed (104 existing + all new Phase 2 tests)

- [ ] **Step 5: Verify all existing tests still pass**

Specifically check:
- `test_health.py` — uses APP_VERSION, should show 1.1.0
- `test_admin.py` — uses APP_VERSION
- All auth tests, request tests, exemption tests unbroken

- [ ] **Step 6: Commit**

```bash
git add backend/app/config.py README.md docs/index.html
git commit -m "chore: bump version to v1.1.0 (Phase 2)"
```

---

## Execution Order Summary

| Task | Description | New Tests | Depends On |
|------|-------------|-----------|------------|
| 1 | Test fixtures + user schema | 0 (infrastructure) | — |
| 2 | Department CRUD router | 8 | Task 1 |
| 3 | Department scoping middleware | 0 (middleware only) | Task 1 |
| 4 | Scope requests endpoints | 8 | Tasks 2, 3 |
| 5 | Scope exemption flag endpoints | 0 (uses Task 4 pattern) | Task 3 |
| 6 | Compliance template documents | 6 | — |
| 7 | Template render endpoint | 4 | Task 6 |
| 8 | Model registry CRUD | 6 | — |
| 9 | 50-state exemption rules | 4 | — |
| 10 | Exemption auditability dashboard | 4 | — |
| 11 | Version bump + regression | 0 (verification) | All |

**Tasks 6, 8, 9, 10 are independent** and can be done in any order or in parallel.
**Tasks 1→2→3→4→5 are sequential** (department infrastructure).
**Task 7 depends on Task 6** (templates must exist before render).
**Task 11 is always last.**

**Total new automated tests:** ~40 in this plan (remaining tests from the spec's 73 target will be filled in during implementation as edge cases are discovered).
