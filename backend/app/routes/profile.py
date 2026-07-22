from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from qdrant_client import AsyncQdrantClient

from app.core.dependencies import (
    CurrentUser,
    get_db,
    get_embeddings,
    get_llm_client,
    get_qdrant_client,
)
from app.core.exceptions.profile import ProfileParseError
from app.llm.client import LLMClient
from app.llm.router import LLMTask, get_llm
from app.profile.extractor import detect_file_type
from app.schemas.profile import ProfileStatusResponse, ProfileUploadResponse
from app.services.profile_service import ProfileService
from app.vector.embeddings import JinaEmbeddings

router = APIRouter(prefix="/profile", tags=["profile"])

@router.post("", response_model=ProfileUploadResponse)
async def upload_profile(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    llm_client: LLMClient = Depends(get_llm_client),
    qdrant: AsyncQdrantClient = Depends(get_qdrant_client),
    embeddings: JinaEmbeddings = Depends(get_embeddings),
    file: UploadFile = File(...),
) -> ProfileUploadResponse:
    file_data = await file.read()
    try:
        file_type = detect_file_type(file.filename or "", file.content_type or "")
    except ValueError as e:
        raise ProfileParseError(message=str(e))
    llm = get_llm(llm_client, LLMTask.PROFILE_NORMALISE)

    service = ProfileService(
        db=db,
        llm=llm,
        qdrant=qdrant,
        embeddings=embeddings,
    )
    return await service.ingest_profile(
        user_id=current_user.id,
        file_data=file_data,
        file_name=file.filename or "upload",
        file_type=file_type,
    )

@router.get("/status", response_model=ProfileStatusResponse)
async def profile_status(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    llm_client: LLMClient = Depends(get_llm_client),
    qdrant: AsyncQdrantClient = Depends(get_qdrant_client),
    embeddings: JinaEmbeddings = Depends(get_embeddings),
) -> ProfileStatusResponse:
    service = ProfileService(
        db=db,
        llm=llm_client.large,
        qdrant=qdrant,
        embeddings=embeddings,
    )
    return await service.get_status(user_id=current_user.id)