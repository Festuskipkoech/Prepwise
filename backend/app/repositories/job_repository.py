from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.jobs import Job

class JobRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, data: dict) -> Job:
        job = Job(**data)
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def get_by_id(self, job_id: UUID) -> Job | None:
        result = await self.db.execute(
            select(Job).where(Job.id == job_id)
        )
        return result.scalar_one_or_none()

    async def get_by_url(self, source_url: str) -> Job | None:
        result = await self.db.execute(
            select(Job).where(Job.source_url == source_url)
        )
        return result.scalar_one_or_none()

    async def list_all(
        self,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Job], int]:
        query = select(Job)
        count_query = select(func.count()).select_from(Job)

        if status:
            query = query.where(Job.status == status)
            count_query = count_query.where(Job.status == status)

        query = query.order_by(Job.created_at.desc()).limit(limit).offset(offset)

        results = await self.db.execute(query)
        count_result = await self.db.execute(count_query)

        return results.scalars().all(), count_result.scalar()

    async def update(self, job_id: UUID, data: dict) -> Job | None:
        job = await self.get_by_id(job_id)
        if not job:
            return None
        for key, value in data.items():
            if value is not None:
                setattr(job, key, value)
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def delete(self, job_id: UUID) -> bool:
        job = await self.get_by_id(job_id)
        if not job:
            return False
        await self.db.delete(job)
        await self.db.commit()
        return True

    async def list_history(
        self,
        page_size: int = 20,
        cursor_id: str | None = None,
        status: str | None = None,
    ) -> tuple[list[Job], bool]:
        from sqlalchemy import and_

        query = select(Job)
        conditions = []

        if status:
            conditions.append(Job.status == status)

        if cursor_id:
            from uuid import UUID as _UUID
            cursor_result = await self.db.execute(
                select(Job).where(Job.id == _UUID(cursor_id))
            )
            cursor_job = cursor_result.scalar_one_or_none()
            if cursor_job:
                conditions.append(
                    (Job.created_at < cursor_job.created_at)
                    | (
                        (Job.created_at == cursor_job.created_at)
                        & (Job.id < cursor_job.id)
                    )
                )

        if conditions:
            query = query.where(and_(*conditions))

        query = (
            query
            .order_by(Job.created_at.desc(), Job.id.desc())
            .limit(page_size + 1)
        )

        result = await self.db.execute(query)
        jobs = result.scalars().all()

        has_more = len(jobs) > page_size
        return jobs[:page_size], has_more