import uuid
from datetime import datetime, timezone

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, UUIDIDMixin
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.models.user import User


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = "reset-secret"
    verification_token_secret = "verify-secret"

    def __init__(self, session: AsyncSession, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._session = session

    async def on_after_login(self, user: User, request: Request | None = None, response=None):
        await self._session.execute(
            update(User).where(User.id == user.id).values(last_login=datetime.now(timezone.utc))
        )
        await self._session.commit()


async def get_user_manager(session: AsyncSession = Depends(get_async_session)):
    from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase

    user_db = SQLAlchemyUserDatabase(session, User)
    yield UserManager(session=session, user_db=user_db)
