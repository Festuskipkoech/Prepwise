import uuid
from datetime import datetime, timezone
from typing import Optional

import redis.asyncio as aioredis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.sessions import Session

class SessionRepository:
    def __init__(self, db: AsyncSession, redis_auth: aioredis.Redis) -> None:
        self._db = db
        self._redis = redis_auth

    async def create(
        self,
        user_id: uuid.UUID,
        refresh_token_hash: str,
        access_token_jti: str,
        expires_at: datetime,
        device_info: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Session:
        session = Session(
            user_id=user_id,
            refresh_token=refresh_token_hash,
            access_token_jti=access_token_jti,
            expires_at=expires_at,
            device_info=device_info,
            ip_address=ip_address,
        )
        self._db.add(session)
        await self._db.flush()
        await self._db.refresh(session)
        return session

    async def get_by_refresh_token_hash(
        self, token_hash: str
    ) -> Optional[Session]:
        result = await self._db.execute(
            select(Session).where(
                Session.refresh_token == token_hash,
                Session.revoked_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_jti(self, jti: str) -> Optional[Session]:
        result = await self._db.execute(
            select(Session).where(
                Session.access_token_jti == jti,
                Session.revoked_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, session_id: uuid.UUID) -> Optional[Session]:
        result = await self._db.execute(
            select(Session).where(Session.id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_active_by_user(self, user_id: uuid.UUID) -> list[Session]:
        result = await self._db.execute(
            select(Session).where(
                Session.user_id == user_id,
                Session.revoked_at.is_(None),
            )
        )
        return list(result.scalars().all())

    async def rotate(
        self,
        session: Session,
        new_refresh_token_hash: str,
        new_access_token_jti: str,
        new_expires_at: datetime,
    ) -> Session:
        session.refresh_token = new_refresh_token_hash
        session.access_token_jti = new_access_token_jti
        session.expires_at = new_expires_at
        session.last_used_at = datetime.now(timezone.utc)
        await self._db.flush()
        await self._db.refresh(session)
        return session

    async def revoke(self, session: Session) -> None:
        session.revoked_at = datetime.now(timezone.utc)
        await self._db.flush()

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        await self._db.execute(
            update(Session)
            .where(Session.user_id == user_id, Session.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )

    # Redis operations
    async def cache_access_token(self, jti: str, user_id: str) -> None:
        try:
            await self._redis.setex(
                f"access:{jti}",
                settings.jwt_access_expiry_minutes * 60,
                user_id,
            )
        except Exception:
            pass

    async def cache_refresh_token(self, token_hash: str, session_id: str) -> None:
        try:
            await self._redis.setex(
                f"refresh:{token_hash}",
                settings.jwt_refresh_expiry_days * 86400,
                session_id,
            )
        except Exception:
            pass

    async def get_cached_access_token(self, jti: str) -> Optional[str]:
        try:
            return await self._redis.get(f"access:{jti}")
        except Exception:
            return None

    async def get_cached_refresh_token(self, token_hash: str) -> Optional[str]:
        try:
            return await self._redis.get(f"refresh:{token_hash}")
        except Exception:
            return None

    async def delete_access_token_cache(self, jti: str) -> None:
        try:
            await self._redis.delete(f"access:{jti}")
        except Exception:
            pass

    async def delete_refresh_token_cache(self, token_hash: str) -> None:
        try:
            await self._redis.delete(f"refresh:{token_hash}")
        except Exception:
            pass

    async def delete_all_user_token_caches(
        self, sessions: list[Session]
    ) -> None:
        try:
            pipe = self._redis.pipeline()
            for session in sessions:
                pipe.delete(f"access:{session.access_token_jti}")
                pipe.delete(f"refresh:{session.refresh_token}")
            await pipe.execute()
        except Exception:
            pass