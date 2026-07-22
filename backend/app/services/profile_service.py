import logging
import uuid
from datetime import datetime, timezone

from langchain_anthropic import ChatAnthropic
from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.profile.extractor import SupportedFileType, extract_text
from app.profile.indexer import index_profile
from app.profile.normaliser import normalise_profile
from app.repositories.profile_repository import ProfileRepository
from app.schemas.profile import ProfileStatusResponse, ProfileUploadResponse
from app.vector.embeddings import JinaEmbeddings

logger = logging.getLogger(__name__)

class ProfileService:
    def __init__(
        self,
        db: AsyncSession,
        llm: ChatAnthropic,
        qdrant: AsyncQdrantClient,
        embeddings: JinaEmbeddings,
    ) -> None:
        self._db = db
        self._llm = llm
        self._qdrant = qdrant
        self._embeddings = embeddings
        self._repo = ProfileRepository(db)

    async def ingest_profile(
        self,
        user_id: uuid.UUID,
        file_data: bytes,
        file_name: str,
        file_type: SupportedFileType,
    ) -> ProfileUploadResponse:
        """Full profile ingestion pipeline.

        1. Extract raw text from the uploaded file
        2. Normalise to canonical Prepwise markdown via LLM
        3. Persist raw and normalised text to user_profiles via repository
        4. Chunk, embed, and upsert into Qdrant
        5. Mark indexed_at via repository

        Re-upload is fully supported — existing vectors are deleted
        and the profile row is overwritten.
        """
        logger.info(
            "Starting profile ingestion for user %s — file: %s (%s)",
            user_id,
            file_name,
            file_type,
        )

        raw_text = extract_text(file_data, file_type)

        normalised_md = await normalise_profile(raw_text, self._llm)

        await self._repo.upsert(
            user_id=user_id,
            raw_text=raw_text,
            normalised_md=normalised_md,
            file_name=file_name,
            file_type=file_type,
        )

        chunks_indexed = await index_profile(
            user_id=str(user_id),
            normalised_md=normalised_md,
            qdrant=self._qdrant,
            embeddings=self._embeddings,
        )

        indexed_at = datetime.now(timezone.utc)
        await self._repo.mark_indexed(user_id=user_id, indexed_at=indexed_at)

        logger.info(
            "Profile ingestion complete for user %s — %d chunks indexed",
            user_id,
            chunks_indexed,
        )

        return ProfileUploadResponse(
            message="Profile uploaded and indexed successfully.",
            chunks_indexed=chunks_indexed,
            indexed_at=indexed_at,
        )

    async def get_status(self, user_id: uuid.UUID) -> ProfileStatusResponse:
        """Return profile existence and metadata for the frontend status check."""
        profile = await self._repo.get_by_user_id(user_id)

        if profile is None:
            return ProfileStatusResponse(has_profile=False)

        return ProfileStatusResponse(
            has_profile=profile.indexed_at is not None,
            file_name=profile.file_name,
            file_type=profile.file_type,
            indexed_at=profile.indexed_at,
            created_at=profile.created_at,
        )