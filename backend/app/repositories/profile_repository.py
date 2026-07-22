import logging
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user_profiles import UserProfile

logger = logging.getLogger(__name__)

class ProfileRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_user_id(self, user_id: uuid.UUID) -> Optional[UserProfile]:
        result = await self._db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        user_id: uuid.UUID,
        raw_text: str,
        normalised_md: str,
        file_name: str,
        file_type: str,
    ) -> UserProfile:
        profile = await self.get_by_user_id(user_id)

        if profile is None:
            profile = UserProfile(
                user_id=user_id,
                raw_text=raw_text,
                normalised_md=normalised_md,
                file_name=file_name,
                file_type=file_type,
            )
            self._db.add(profile)
        else:
            profile.raw_text = raw_text
            profile.normalised_md = normalised_md
            profile.file_name = file_name
            profile.file_type = file_type
            profile.indexed_at = None

        await self._db.commit()
        await self._db.refresh(profile)
        logger.debug("Upserted profile for user %s", user_id)
        return profile

    async def mark_indexed(
        self, user_id: uuid.UUID, indexed_at: datetime
    ) -> None:
        profile = await self.get_by_user_id(user_id)
        if profile is None:
            raise ValueError(f"UserProfile not found for user_id {user_id}")
        profile.indexed_at = indexed_at
        await self._db.commit()
        logger.debug("Marked profile indexed for user %s at %s", user_id, indexed_at)

    async def exists(self, user_id: uuid.UUID) -> bool:
        profile = await self.get_by_user_id(user_id)
        return profile is not None and profile.indexed_at is not None