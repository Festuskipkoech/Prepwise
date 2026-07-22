import logging
import uuid
from typing import Annotated, AsyncGenerator

import redis.asyncio as aioredis
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from langchain_anthropic import ChatAnthropic
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres.aio import AsyncPostgresStore
from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions.auth import InvalidTokenError
from app.core.security import decode_access_token
from app.db.models.users import User
from app.db.session import AsyncSessionFactory
from app.llm.client import LLMClient
from app.repositories.auth_repository import UserRepository
from app.repositories.session_repository import SessionRepository
from app.vector.embeddings import JinaEmbeddings
from app.websocket.manager import ConnectionManager
from app.websocket.pubsub import RedisPubSubManager

logger = logging.getLogger(__name__)
bearer_scheme = HTTPBearer(auto_error=False)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionFactory() as session:
        yield session

async def get_redis_auth(request: Request) -> aioredis.Redis:
    return request.app.state.redis_auth

async def get_redis_cache(request: Request) -> aioredis.Redis:
    return request.app.state.redis_cache

async def get_redis_ratelimit(request: Request) -> aioredis.Redis:
    return request.app.state.redis_ratelimit

async def get_llm_client(request: Request) -> LLMClient:
    return request.app.state.llm_client

async def get_embeddings(request: Request) -> JinaEmbeddings:
    return request.app.state.embeddings

async def get_qdrant_client(request: Request) -> AsyncQdrantClient:
    return request.app.state.qdrant_client

async def get_checkpointer(request: Request) -> AsyncPostgresSaver:
    return request.app.state.checkpointer

async def get_store(request: Request) -> AsyncPostgresStore:
    return request.app.state.store

async def get_connection_manager(request: Request) -> ConnectionManager:
    return request.app.state.connection_manager

async def get_pubsub_manager(request: Request) -> RedisPubSubManager:
    return request.app.state.redis_pubsub

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