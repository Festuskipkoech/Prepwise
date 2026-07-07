from uuid import UUID

from pydantic import BaseModel

class StatusCount(BaseModel):
    status: str
    count: int

class ApplicationVelocity(BaseModel):
    week: str
    count: int

class DashboardResponse(BaseModel):
    total_applications: int
    status_breakdown: list[StatusCount]
    response_rate: float
    interview_rate: float
    offer_rate: float
    applications_this_week: int
    applications_this_month: int
    velocity: list[ApplicationVelocity]

class FollowUpJob(BaseModel):
    id: UUID
    title: str
    company: str | None
    status: str
    applied_date: str | None
    follow_up_date: str | None
    days_since_applied: int | None

    model_config = {"from_attributes": True}

class FollowUpResponse(BaseModel):
    due_today: list[FollowUpJob]
    overdue: list[FollowUpJob]
    upcoming: list[FollowUpJob]

class FunnelStage(BaseModel):
    stage: str
    drop_off_rate: float
    observation: str

class PatternAnalysisResponse(BaseModel):
    summary: str
    funnel_stages: list[FunnelStage]
    strongest_signal: str
    weakest_point: str
    recommendations: list[str]
    data_confidence: str