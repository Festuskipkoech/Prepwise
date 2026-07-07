from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

class SubjectResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    order_index: int
    source: str
    job_id: UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}

class TopicResponse(BaseModel):
    id: UUID
    subject_id: UUID
    name: str
    description: str | None
    order_index: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}

class SubtopicResponse(BaseModel):
    id: UUID
    topic_id: UUID
    name: str
    concept: str | None
    project_evidence: str | None
    order_index: int
    status: str
    generated_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}

class QuestionResponse(BaseModel):
    id: UUID
    subtopic_id: UUID
    type: str
    question: str
    answer: str
    order_index: int
    generated_at: datetime | None

    model_config = {"from_attributes": True}

class RoadmapResponse(BaseModel):
    subjects: list[SubjectResponse]
    total_subjects: int
    total_topics: int

class SubjectWithTopicsResponse(BaseModel):
    subject: SubjectResponse
    topics: list[TopicResponse]

class TopicWithSubtopicsResponse(BaseModel):
    topic: TopicResponse
    subtopics: list[SubtopicResponse]

class SubtopicWithQuestionsResponse(BaseModel):
    subtopic: SubtopicResponse
    questions: list[QuestionResponse]

class InterviewMessageRequest(BaseModel):
    subtopic_id: UUID
    conversation_history: list[dict]
    user_answer: str

class PrepPathResponse(BaseModel):
    id: UUID
    job_id: UUID
    strong_matches: dict | None
    needs_sharpening: dict | None
    gaps: dict | None
    roadmap_links: dict | None
    talking_points: dict | None
    likely_angles: dict | None
    generated_subject_id: UUID | None
    generated_at: datetime | None

    model_config = {"from_attributes": True}

class TopicStatusUpdateRequest(BaseModel):
    status: str

class SubtopicStatusUpdateRequest(BaseModel):
    status: str