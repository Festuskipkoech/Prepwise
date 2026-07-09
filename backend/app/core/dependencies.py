import uuid
import logging
from typing import Annotated, AsyncGenerator

import redis.asyncio as aioredis
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions.auth import InvalidTokenError
from app.core.security import decode_access_token
from app.db.models.users import User
from app.db.session import AsyncSessionFactory
from app.repositories.auth_repository import UserRepository
from app.repositories.session_repository import SessionRepository

logger = logging.getLogger(__name__)
bearer_scheme = HTTPBearer(auto_error=False)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionFactory() as session:
        yield session

async def get_redis_auth(request: Request) -> aioredis.Redis:
    return request.app.state.redis_auth
async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials, Depends(bearer_scheme)
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_auth: Annotated[aioredis.Redis, Depends(get_redis_auth)],
) -> User:
    if not credentials:
        raise InvalidTokenError()

    decoded = decode_access_token(credentials.credentials)
    jti = decoded["jti"]
    user_id_str = decoded["user_id"]

    session_repo = SessionRepository(db, redis_auth)
    cached_user_id = await session_repo.get_cached_access_token(jti)

    if cached_user_id:
        if cached_user_id != user_id_str:
            raise InvalidTokenError()
    else:
        session = await session_repo.get_by_jti(jti)
        if not session:
            raise InvalidTokenError()
        await session_repo.cache_access_token(jti, str(session.user_id))

    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(uuid.UUID(user_id_str))

    if not user or not user.is_active:
        raise InvalidTokenError()

    return user

CurrentUser = Annotated[User, Depends(get_current_user)]