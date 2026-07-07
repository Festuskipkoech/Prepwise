from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

class DocumentGenerateRequest(BaseModel):
    job_id: UUID
    type: str

class ResumeContent(BaseModel):
    profile_summary: str
    experience: list[dict]
    projects: list[dict]
    skills: str
    certifications: str | None = None
    education: str | None = None

class CoverLetterContent(BaseModel):
    opening_paragraph: str
    body_paragraph_1: str
    body_paragraph_2: str
    closing_paragraph: str

class DocumentResponse(BaseModel):
    id: UUID
    job_id: UUID
    type: str
    content: dict
    version: int
    created_at: datetime

    model_config = {"from_attributes": True}

class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]