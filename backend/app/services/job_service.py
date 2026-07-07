from pathlib import Path
from uuid import UUID

from langchain_core.language_models.chat_models import BaseChatModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph.job_search_graph import build_job_search_graph
from app.agents.tools.job_search import generate_search_context
from app.core.config import settings
from app.core.exceptions.jobs import JobAlreadyExistsError, JobNotFoundError
from app.repositories.job_repository import JobRepository
from app.schemas.jobs import (
    JobCreateFromSearchRequest,
    JobCreateManualRequest,
    JobListResponse,
    JobResponse,
    JobSearchRequest,
    JobSearchResponse,
    JobSearchResult,
    JobStatusUpdateRequest,
    SearchContextResponse,
    SuggestedTitle,
)

class JobService:
    def __init__(self, db: AsyncSession, llm: BaseChatModel) -> None:
        self.repo = JobRepository(db)
        self.llm = llm

    def _read_profile(self) -> str:
        return Path(settings.profile_path).read_text(encoding="utf-8")

    async def get_search_context(self) -> SearchContextResponse:
        profile_text = self._read_profile()
        data = await generate_search_context(profile_text=profile_text, llm=self.llm)

        return SearchContextResponse(
            suggested_titles=[
                SuggestedTitle(**t) for t in data.get("suggested_titles", [])
            ],
            recommended_keywords=data.get("recommended_keywords", []),
            avoid_titles=data.get("avoid_titles", []),
            strongest_lane=data.get("strongest_lane", ""),
        )

    async def search_jobs(self, request: JobSearchRequest) -> JobSearchResponse:
        profile_text = self._read_profile()

        graph = build_job_search_graph(llm=self.llm)
        result = await graph.ainvoke(
            {
                "query": request.query,
                "location": request.location,
                "limit": request.limit,
                "profile_text": profile_text,
                "raw_results": [],
                "scored_results": [],
                "error": None,
            }
        )

        results = [
            JobSearchResult(
                title=r["title"],
                company=r.get("company"),
                source_url=r["source_url"],
                location=r.get("location"),
                via=r.get("via"),
                snippet=r.get("snippet"),
                fit_score=r["fit_score"],
                fit_reason=r["fit_reason"],
            )
            for r in result["scored_results"]
        ]

        return JobSearchResponse(results=results, query=request.query)

    async def create_manual(self, request: JobCreateManualRequest) -> JobResponse:
        if request.source_url:
            existing = await self.repo.get_by_url(request.source_url)
            if existing:
                raise JobAlreadyExistsError()

        job = await self.repo.create(
            {
                "title": request.title,
                "company": request.company,
                "jd_text": request.jd_text,
                "source_url": request.source_url,
                "notes": request.notes,
                "source": "manual",
                "status": "bookmarked",
            }
        )
        return JobResponse.model_validate(job)

    async def create_from_search(
        self, request: JobCreateFromSearchRequest
    ) -> JobResponse:
        existing = await self.repo.get_by_url(request.source_url)
        if existing:
            raise JobAlreadyExistsError()

        job = await self.repo.create(
            {
                "title": request.title,
                "company": request.company,
                "source_url": request.source_url,
                "jd_text": request.jd_text,
                "source": "search",
                "status": "bookmarked",
            }
        )
        return JobResponse.model_validate(job)

    async def get_job(self, job_id: UUID) -> JobResponse:
        job = await self.repo.get_by_id(job_id)
        if not job:
            raise JobNotFoundError()
        return JobResponse.model_validate(job)

    async def list_jobs(
        self,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> JobListResponse:
        jobs, total = await self.repo.list_all(
            status=status, limit=limit, offset=offset
        )
        return JobListResponse(
            jobs=[JobResponse.model_validate(j) for j in jobs],
            total=total,
        )

    async def update_status(
        self, job_id: UUID, request: JobStatusUpdateRequest
    ) -> JobResponse:
        job = await self.repo.update(
            job_id,
            {
                "status": request.status,
                "rejection_reason": request.rejection_reason,
                "notes": request.notes,
                "applied_date": request.applied_date,
                "follow_up_date": request.follow_up_date,
            },
        )
        if not job:
            raise JobNotFoundError()
        return JobResponse.model_validate(job)

    async def delete_job(self, job_id: UUID) -> None:
        deleted = await self.repo.delete(job_id)
        if not deleted:
            raise JobNotFoundError()