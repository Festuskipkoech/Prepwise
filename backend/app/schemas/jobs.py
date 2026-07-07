from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class JobCreateManualRequest(BaseModel):
    title: str
    company: str | None = None
    jd_text: str
    source_url: str | None = None
    notes: str | None = None


class JobCreateFromSearchRequest(BaseModel):
    title: str
    company: str | None = None
    source_url: str
    jd_text: str


class JobSearchRequest(BaseModel):
    query: str
    location: str = "remote"
    limit: int = 10


class JobStatusUpdateRequest(BaseModel):
    status: str
    rejection_reason: str | None = None
    notes: str | None = None
    applied_date: date | None = None
    follow_up_date: date | None = None


class JobSearchResult(BaseModel):
    title: str
    company: str | None = None
    source_url: str
    location: str | None = None
    via: str | None = None
    snippet: str | None = None
    fit_score: int
    fit_reason: str


class JobSearchResponse(BaseModel):
    results: list[JobSearchResult]
    query: str


class SuggestedTitle(BaseModel):
    title: str
    reason: str
    seniority: str
    priority: int


class SearchContextResponse(BaseModel):
    suggested_titles: list[SuggestedTitle]
    recommended_keywords: list[str]
    avoid_titles: list[str]
    strongest_lane: str


class JobResponse(BaseModel):
    id: UUID
    title: str
    company: str | None = None
    source_url: str | None = None
    jd_text: str | None = None
    source: str
    status: str
    applied_date: date | None = None
    follow_up_date: date | None = None
    rejection_reason: str | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobListResponse(BaseModel):
    jobs: list[JobResponse]
    total: int