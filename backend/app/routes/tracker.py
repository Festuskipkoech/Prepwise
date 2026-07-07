from fastapi import APIRouter, Depends, Query
from sse_starlette.sse import EventSourceResponse

from app.core.dependencies import get_current_user, get_tracker_service
from app.db.models.users import User
from app.schemas.tracker import (
    ApplicationHistoryResponse,
    DashboardResponse,
    FollowUpResponse,
)
from app.services.tracker_service import TrackerService

router = APIRouter(prefix="/tracker", tags=["tracker"])

@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    _: User = Depends(get_current_user),
    service: TrackerService = Depends(get_tracker_service),
) -> DashboardResponse:
    return await service.get_dashboard()

@router.get("/follow-ups", response_model=FollowUpResponse)
async def get_follow_ups(
    _: User = Depends(get_current_user),
    service: TrackerService = Depends(get_tracker_service),
) -> FollowUpResponse:
    return await service.get_follow_ups()

@router.get("/history", response_model=ApplicationHistoryResponse)
async def get_history(
    page_size: int = Query(default=20, ge=1, le=100),
    cursor_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    _: User = Depends(get_current_user),
    service: TrackerService = Depends(get_tracker_service),
) -> ApplicationHistoryResponse:
    return await service.get_history(
        page_size=page_size,
        cursor_id=cursor_id,
        status=status,
    )

@router.get("/patterns")
async def analyse_patterns(
    _: User = Depends(get_current_user),
    service: TrackerService = Depends(get_tracker_service),
) -> EventSourceResponse:
    async def event_stream():
        async for chunk in service.analyse_patterns_stream():
            yield {"data": chunk}

    return EventSourceResponse(event_stream())