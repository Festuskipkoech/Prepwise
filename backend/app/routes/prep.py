from uuid import UUID

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from app.core.dependencies import get_current_user, get_prep_service
from app.db.models.users import User
from app.schemas.prep import (
    InterviewMessageRequest,
    PrepPathResponse,
    RoadmapResponse,
    SubjectWithTopicsResponse,
    SubtopicStatusUpdateRequest,
    SubtopicWithQuestionsResponse,
    TopicStatusUpdateRequest,
    TopicWithSubtopicsResponse,
)
from app.services.prep_service import PrepService

router = APIRouter(prefix="/prep", tags=["prep"])

@router.get("/roadmap", response_model=RoadmapResponse)
async def get_roadmap(
    _: User = Depends(get_current_user),
    service: PrepService = Depends(get_prep_service),
) -> RoadmapResponse:
    return await service.get_roadmap()

@router.post("/roadmap/generate", response_model=RoadmapResponse)
async def generate_roadmap(
    _: User = Depends(get_current_user),
    service: PrepService = Depends(get_prep_service),
) -> RoadmapResponse:
    return await service.generate_roadmap()

@router.get("/subjects/{subject_id}", response_model=SubjectWithTopicsResponse)
async def get_subject_with_topics(
    subject_id: UUID,
    _: User = Depends(get_current_user),
    service: PrepService = Depends(get_prep_service),
) -> SubjectWithTopicsResponse:
    return await service.get_subject_with_topics(subject_id)

@router.get("/topics/{topic_id}", response_model=TopicWithSubtopicsResponse)
async def get_topic_with_subtopics(
    topic_id: UUID,
    _: User = Depends(get_current_user),
    service: PrepService = Depends(get_prep_service),
) -> TopicWithSubtopicsResponse:
    return await service.get_topic_with_subtopics(topic_id)

@router.patch("/topics/{topic_id}/status")
async def update_topic_status(
    topic_id: UUID,
    payload: TopicStatusUpdateRequest,
    _: User = Depends(get_current_user),
    service: PrepService = Depends(get_prep_service),
) -> dict:
    await service.repo.update_topic_status(topic_id, payload.status)
    return {"message": "Topic status updated"}

@router.get("/subtopics/{subtopic_id}", response_model=SubtopicWithQuestionsResponse)
async def get_subtopic_with_questions(
    subtopic_id: UUID,
    _: User = Depends(get_current_user),
    service: PrepService = Depends(get_prep_service),
) -> SubtopicWithQuestionsResponse:
    return await service.get_subtopic_with_questions(subtopic_id)

@router.patch("/subtopics/{subtopic_id}/status")
async def update_subtopic_status(
    subtopic_id: UUID,
    payload: SubtopicStatusUpdateRequest,
    _: User = Depends(get_current_user),
    service: PrepService = Depends(get_prep_service),
) -> dict:
    await service.repo.update_subtopic_status(subtopic_id, payload.status)
    return {"message": "Subtopic status updated"}

@router.post("/interview/session")
async def interview_session(
    payload: InterviewMessageRequest,
    _: User = Depends(get_current_user),
    service: PrepService = Depends(get_prep_service),
) -> EventSourceResponse:
    async def event_stream():
        async for chunk in service.interview_session_stream(
            subtopic_id=payload.subtopic_id,
            conversation_history=payload.conversation_history,
            user_answer=payload.user_answer,
        ):
            yield {"data": chunk}

    return EventSourceResponse(event_stream())

@router.post("/jobs/{job_id}/prep-path")
async def generate_prep_path(
    job_id: UUID,
    _: User = Depends(get_current_user),
    service: PrepService = Depends(get_prep_service),
) -> EventSourceResponse:
    async def event_stream():
        async for chunk in service.generate_prep_path_stream(job_id):
            yield {"data": chunk}

    return EventSourceResponse(event_stream())

@router.get("/jobs/{job_id}/prep-path", response_model=PrepPathResponse)
async def get_prep_path(
    job_id: UUID,
    _: User = Depends(get_current_user),
    service: PrepService = Depends(get_prep_service),
) -> PrepPathResponse:
    return await service.get_prep_path(job_id)