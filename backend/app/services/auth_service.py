import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as aioredis

from app.core.exceptions.auth import (
    AuthenticationError,
    InactiveAccountError,
    InvalidTokenError,
    UserAlreadyExistsError,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.db.models.sessions import Session
from app.repositories.auth_repository import UserRepository
from app.repositories.session_repository import SessionRepository

from app.core.config import settings

class AuthService:
    def __init__(self, db: AsyncSession, redis_auth: aioredis.Redis) -> None:
        self._user_repo = UserRepository(db)
        self._session_repo = SessionRepository(db, redis_auth)
        self._db = db

    async def register(
        self,
        email: str,
        password: str,
        full_name: Optional[str] = None,
    ) -> None:
        existing = await self._user_repo.get_by_email(email)
        if existing:
            raise UserAlreadyExistsError()

        password_hash = hash_password(password)
        await self._user_repo.create(
            email=email,
            password_hash=password_hash,
            full_name=full_name,
        )
        await self._db.commit()

    async def login(
        self,
        email: str,
        password: str,
        device_info: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> tuple[str, str]:
        user = await self._user_repo.get_by_email(email)
        if not user or not verify_password(password, user.password_hash):
            raise AuthenticationError()

        if not user.is_active:
            raise InactiveAccountError()

        access_token, jti = create_access_token(
            user_id=str(user.id), email=user.email
        )
        refresh_token, token_hash = create_refresh_token(user_id=str(user.id))

        expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.jwt_refresh_expiry_days
        )

        session = await self._session_repo.create(
            user_id=user.id,
            refresh_token_hash=token_hash,
            access_token_jti=jti,
            expires_at=expires_at,
            device_info=device_info,
            ip_address=ip_address,
        )
        await self._db.commit()

        await self._session_repo.cache_access_token(jti, str(user.id))
        await self._session_repo.cache_refresh_token(token_hash, str(session.id))

        return access_token, refresh_token

    async def refresh(self, raw_refresh_token: str) -> tuple[str, str]:
        decoded = decode_refresh_token(raw_refresh_token)
        old_token_hash = decoded["token_hash"]

        cached_session_id = await self._session_repo.get_cached_refresh_token(
            old_token_hash
        )

        if cached_session_id:
            session = await self._session_repo.get_by_id(
                uuid.UUID(cached_session_id)
            )
        else:
            session = await self._session_repo.get_by_refresh_token_hash(
                old_token_hash
            )

        if not session or session.revoked_at is not None:
            raise InvalidTokenError()

        if session.expires_at < datetime.now(timezone.utc):
            raise InvalidTokenError()

        user = await self._user_repo.get_by_id(session.user_id)
        if not user or not user.is_active:
            raise InvalidTokenError()

        new_access_token, new_jti = create_access_token(
            user_id=str(user.id), email=user.email
        )
        new_refresh_token, new_token_hash = create_refresh_token(
            user_id=str(user.id)
        )
        new_expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.jwt_refresh_expiry_days
        )

        await self._session_repo.delete_access_token_cache(
            session.access_token_jti
        )
        await self._session_repo.delete_refresh_token_cache(old_token_hash)

        await self._session_repo.rotate(
            session=session,
            new_refresh_token_hash=new_token_hash,
            new_access_token_jti=new_jti,
            new_expires_at=new_expires_at,
        )
        await self._db.commit()

        await self._session_repo.cache_access_token(new_jti, str(user.id))
        await self._session_repo.cache_refresh_token(
            new_token_hash, str(session.id)
        )

        return new_access_token, new_refresh_token

    async def logout(self, jti: str, token_hash: str) -> None:
        await self._session_repo.delete_access_token_cache(jti)
        await self._session_repo.delete_refresh_token_cache(token_hash)

        session = await self._session_repo.get_by_jti(jti)
        if session:
            await self._session_repo.revoke(session)
            await self._db.commit()

    async def logout_all(self, user_id: uuid.UUID) -> None:
        sessions = await self._session_repo.get_active_by_user(user_id)
        await self._session_repo.delete_all_user_token_caches(sessions)
        await self._session_repo.revoke_all_for_user(user_id)
        await self._db.commit()

    async def get_sessions(self, user_id: uuid.UUID) -> list[Session]:
        return await self._session_repo.get_active_by_user(user_id)

    async def revoke_session(
        self, user_id: uuid.UUID, session_id: uuid.UUID
    ) -> None:
        session = await self._session_repo.get_by_id(session_id)

        if not session or session.user_id != user_id:
            raise InvalidTokenError("Session not found.")

        if session.revoked_at is not None:
            raise InvalidTokenError("Session is already revoked.")

        await self._session_repo.delete_access_token_cache(
            session.access_token_jti
        )
        await self._session_repo.delete_refresh_token_cache(session.refresh_token)
        await self._session_repo.revoke(session)
        await self._db.commit()

    async def validate_access_token(self, jti: str) -> Optional[str]:
        cached_user_id = await self._session_repo.get_cached_access_token(jti)
        if cached_user_id:
            return cached_user_id

        session = await self._session_repo.get_by_jti(jti)
        if not session:
            return None

        await self._session_repo.cache_access_token(
            jti, str(session.user_id)
        )
        return str(session.user_id)