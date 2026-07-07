from uuid import UUID

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from app.core.dependencies import get_current_user, get_document_service
from app.db.models.users import User
from app.schemas.documents import DocumentListResponse, DocumentResponse
from app.services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["documents"])

@router.post("/generate")
async def generate_document(
    job_id: UUID,
    document_type: str,
    _: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
) -> EventSourceResponse:
    async def event_stream():
        async for chunk in service.generate_stream(job_id, document_type):
            yield {"data": chunk}

    return EventSourceResponse(event_stream())

@router.get("/job/{job_id}", response_model=DocumentListResponse)
async def list_documents_for_job(
    job_id: UUID,
    _: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
) -> DocumentListResponse:
    return await service.list_for_job(job_id)


@router.get("/job/{job_id}/latest")
async def get_latest_document(
    job_id: UUID,
    document_type: str,
    _: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
) -> DocumentResponse:
    return await service.get_latest(job_id, document_type)

@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    _: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
) -> DocumentResponse:
    return await service.get_document(document_id)