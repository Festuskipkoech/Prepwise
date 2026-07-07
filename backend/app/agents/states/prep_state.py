from typing import Any
from uuid import UUID

from typing_extensions import TypedDict

class RoadmapState(TypedDict):
    profile_text: str
    subjects: list[dict[str, Any]]
    error: str | None

class SubtopicState(TypedDict):
    topic_id: UUID
    topic_name: str
    subject_name: str
    profile_text: str
    subtopics: list[dict[str, Any]]
    error: str | None

class QuestionState(TypedDict):
    subtopic_id: UUID
    subtopic_name: str
    concept: str
    project_evidence: str
    profile_text: str
    questions: list[dict[str, Any]]
    error: str | None

class PrepPathState(TypedDict):
    job_id: UUID
    jd_text: str
    profile_text: str
    analysis: dict[str, Any]
    generated_subject: dict[str, Any]
    prep_path_data: dict[str, Any]
    error: str | None