import json
from collections.abc import AsyncGenerator
from datetime import date, datetime, timedelta, timezone

from langchain_core.language_models.chat_models import BaseChatModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph.job_tracker_graph import build_tracker_graph
from app.db.models.jobs import Job
from app.core.exceptions.prep import RoadmapGenerationError
from app.llm.client import build_llm_client
from app.llm.router import LLMTask, resolve_model
from app.repositories.job_repository import JobRepository
from app.schemas.tracker import (
    ApplicationHistoryItem,
    ApplicationHistoryResponse,
    ApplicationVelocity,
    DashboardResponse,
    FollowUpJob,
    FollowUpResponse,
    FunnelStage,
    PatternAnalysisResponse,
    StatusCount,
)

TERMINAL_STATUSES = {"rejected", "withdrawn", "offer"}
RESPONSE_STATUSES = {"screening", "interview", "offer", "rejected"}
INTERVIEW_STATUSES = {"interview", "offer"}

class TrackerService:
    def __init__(self, db: AsyncSession, llm: BaseChatModel) -> None:
        self.db = db
        self.llm = llm
        self.repo = JobRepository(db)

    async def _fetch_all_jobs(self) -> list[Job]:
        result = await self.db.execute(
            select(Job).order_by(Job.created_at.desc())
        )
        return result.scalars().all()

    async def get_dashboard(self) -> DashboardResponse:
        jobs = await self._fetch_all_jobs()

        total = len(jobs)
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)

        status_counts: dict[str, int] = {}
        applications_this_week = 0
        applications_this_month = 0
        weekly_buckets: dict[str, int] = {}

        for job in jobs:
            status_counts[job.status] = status_counts.get(job.status, 0) + 1

            created = job.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)

            if created >= week_ago:
                applications_this_week += 1
            if created >= month_ago:
                applications_this_month += 1

            week_label = created.strftime("%Y-W%W")
            weekly_buckets[week_label] = weekly_buckets.get(week_label, 0) + 1

        applied = total
        responses = sum(status_counts.get(s, 0) for s in RESPONSE_STATUSES)
        interviews = sum(status_counts.get(s, 0) for s in INTERVIEW_STATUSES)
        offers = status_counts.get("offer", 0)

        return DashboardResponse(
            total_applications=total,
            status_breakdown=[
                StatusCount(status=s, count=c)
                for s, c in sorted(status_counts.items())
            ],
            response_rate=round(responses / applied, 4) if applied else 0.0,
            interview_rate=round(interviews / applied, 4) if applied else 0.0,
            offer_rate=round(offers / applied, 4) if applied else 0.0,
            applications_this_week=applications_this_week,
            applications_this_month=applications_this_month,
            velocity=[
                ApplicationVelocity(week=w, count=c)
                for w, c in sorted(weekly_buckets.items())
            ],
        )

    async def get_follow_ups(self) -> FollowUpResponse:
        jobs = await self._fetch_all_jobs()
        today = date.today()

        due_today: list[FollowUpJob] = []
        overdue: list[FollowUpJob] = []
        upcoming: list[FollowUpJob] = []

        for job in jobs:
            if job.status in TERMINAL_STATUSES or not job.follow_up_date:
                continue

            applied = job.applied_date
            days_since = (today - applied).days if applied else None

            entry = FollowUpJob(
                id=job.id,
                title=job.title,
                company=job.company,
                status=job.status,
                applied_date=str(applied) if applied else None,
                follow_up_date=str(job.follow_up_date),
                days_since_applied=days_since,
            )

            if job.follow_up_date == today:
                due_today.append(entry)
            elif job.follow_up_date < today:
                overdue.append(entry)
            elif job.follow_up_date <= today + timedelta(days=7):
                upcoming.append(entry)

        overdue.sort(key=lambda x: x.follow_up_date or "")
        upcoming.sort(key=lambda x: x.follow_up_date or "")

        return FollowUpResponse(
            due_today=due_today,
            overdue=overdue,
            upcoming=upcoming,
        )

    async def get_history(
        self,
        page_size: int = 20,
        cursor_id: str | None = None,
        status: str | None = None,
    ) -> ApplicationHistoryResponse:
        jobs, has_more = await self.repo.list_history(
            page_size=page_size,
            cursor_id=cursor_id,
            status=status,
        )

        next_cursor = str(jobs[-1].id) if has_more and jobs else None

        return ApplicationHistoryResponse(
            items=[
                ApplicationHistoryItem(
                    id=job.id,
                    title=job.title,
                    company=job.company,
                    status=job.status,
                    source=job.source,
                    applied_date=str(job.applied_date) if job.applied_date else None,
                    follow_up_date=str(job.follow_up_date) if job.follow_up_date else None,
                    rejection_reason=job.rejection_reason,
                    notes=job.notes,
                    created_at=job.created_at,
                )
                for job in jobs
            ],
            next_cursor=next_cursor,
            has_more=has_more,
            page_size=page_size,
        )

    async def analyse_patterns_stream(self) -> AsyncGenerator[str, None]:
        jobs = await self._fetch_all_jobs()

        total = len(jobs)
        status_counts: dict[str, int] = {}
        rejection_reasons: list[str] = []
        companies: list[str] = []

        for job in jobs:
            status_counts[job.status] = status_counts.get(job.status, 0) + 1
            if job.rejection_reason:
                rejection_reasons.append(job.rejection_reason)
            if job.company:
                companies.append(job.company)

        responses = sum(status_counts.get(s, 0) for s in RESPONSE_STATUSES)
        interviews = sum(status_counts.get(s, 0) for s in INTERVIEW_STATUSES)
        offers = status_counts.get("offer", 0)

        application_data = {
            "total_applications": total,
            "status_breakdown": status_counts,
            "response_rate": round(responses / total, 4) if total else 0,
            "interview_rate": round(interviews / total, 4) if total else 0,
            "offer_rate": round(offers / total, 4) if total else 0,
            "rejection_reasons": rejection_reasons,
            "unique_companies_applied": len(set(companies)),
        }

        model_name = resolve_model(LLMTask.TRACKER_SUMMARY)
        haiku = build_llm_client(model_name)

        graph = build_tracker_graph(llm=haiku)

        final_state = None

        async for mode, chunk in graph.astream(
            {
                "application_data": application_data,
                "analysis": {},
                "error": None,
            },
            stream_mode=["custom", "updates"],
        ):
            if mode == "custom":
                yield json.dumps(chunk)
            elif mode == "updates":
                final_state = chunk

        if not final_state:
            raise RoadmapGenerationError("Pattern analysis produced no output")

        last_output = list(final_state.values())[-1]

        if last_output.get("error"):
            yield json.dumps(
                {"type": "error", "message": last_output["error"]}
            )
            return

        parsed = last_output.get("analysis", {})

        result = PatternAnalysisResponse(
            summary=parsed.get("summary", ""),
            funnel_stages=[
                FunnelStage(**stage)
                for stage in parsed.get("funnel_stages", [])
            ],
            strongest_signal=parsed.get("strongest_signal", ""),
            weakest_point=parsed.get("weakest_point", ""),
            recommendations=parsed.get("recommendations", []),
            data_confidence=parsed.get("data_confidence", "low"),
        )

        yield json.dumps({"type": "done", "data": result.model_dump()})