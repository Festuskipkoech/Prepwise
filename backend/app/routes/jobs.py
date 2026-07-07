from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_current_user, get_job_service
from app.db.models.users import User
from app.schemas.jobs import (
    JobCreateFromSearchRequest,
    JobCreateManualRequest,
    JobListResponse,
    JobResponse,
    JobSearchRequest,
    JobSearchResponse,
    JobStatusUpdateRequest,
    SearchContextResponse,
)
from app.services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])

@router.get("/search-context", response_model=SearchContextResponse)
async def get_search_context(
    _: User = Depends(get_current_user),
    service: JobService = Depends(get_job_service),
) -> SearchContextResponse:
    return await service.get_search_context()

@router.post("/search", response_model=JobSearchResponse)
async def search_jobs(
    payload: JobSearchRequest,
    _: User = Depends(get_current_user),
    service: JobService = Depends(get_job_service),
) -> JobSearchResponse:
    return await service.search_jobs(payload)

@router.post("/from-search", response_model=JobResponse)
async def create_job_from_search(
    payload: JobCreateFromSearchRequest,
    _: User = Depends(get_current_user),
    service: JobService = Depends(get_job_service),
) -> JobResponse:
    return await service.create_from_search(payload)

@router.post("/", response_model=JobResponse)
async def create_manual_job(
    payload: JobCreateManualRequest,
    _: User = Depends(get_current_user),
    service: JobService = Depends(get_job_service),
) -> JobResponse:
    return await service.create_manual(payload)

@router.get("/", response_model=JobListResponse)
async def list_jobs(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0),
    _: User = Depends(get_current_user),
    service: JobService = Depends(get_job_service),
) -> JobListResponse:
    return await service.list_jobs(status=status, limit=limit, offset=offset)

@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: UUID,
    _: User = Depends(get_current_user),
    service: JobService = Depends(get_job_service),
) -> JobResponse:
    return await service.get_job(job_id)

@router.patch("/{job_id}/status", response_model=JobResponse)
async def update_job_status(
    job_id: UUID,
    payload: JobStatusUpdateRequest,
    _: User = Depends(get_current_user),
    service: JobService = Depends(get_job_service),
) -> JobResponse:
    return await service.update_status(job_id, payload)

@router.delete("/{job_id}", status_code=204)
async def delete_job(
    job_id: UUID,
    _: User = Depends(get_current_user),
    service: JobService = Depends(get_job_service),
) -> None:
    await service.delete_job(job_id)