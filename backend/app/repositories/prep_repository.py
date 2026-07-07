from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.prep import (
    JobPrepPath,
    RoadmapQuestion,
    RoadmapSubject,
    RoadmapSubtopic,
    RoadmapTopic,
)

class PrepRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # subjects
    async def create_subject(self, data: dict) -> RoadmapSubject:
        subject = RoadmapSubject(**data)
        self.db.add(subject)
        await self.db.commit()
        await self.db.refresh(subject)
        return subject

    async def get_subject_by_id(self, subject_id: UUID) -> RoadmapSubject | None:
        result = await self.db.execute(
            select(RoadmapSubject).where(RoadmapSubject.id == subject_id)
        )
        return result.scalar_one_or_none()

    async def get_subject_with_topics(
        self, subject_id: UUID
    ) -> RoadmapSubject | None:
        result = await self.db.execute(
            select(RoadmapSubject)
            .options(selectinload(RoadmapSubject.topics))
            .where(RoadmapSubject.id == subject_id)
        )
        return result.scalar_one_or_none()

    async def list_master_subjects(self) -> list[RoadmapSubject]:
        result = await self.db.execute(
            select(RoadmapSubject)
            .where(RoadmapSubject.source == "roadmap")
            .order_by(RoadmapSubject.order_index)
        )
        return result.scalars().all()

    async def count_master_subjects(self) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(RoadmapSubject)
            .where(RoadmapSubject.source == "roadmap")
        )
        return result.scalar()

    async def count_master_topics(self) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(RoadmapTopic)
            .join(RoadmapSubject, RoadmapTopic.subject_id == RoadmapSubject.id)
            .where(RoadmapSubject.source == "roadmap")
        )
        return result.scalar()

    async def get_job_subject(self, job_id: UUID) -> RoadmapSubject | None:
        result = await self.db.execute(
            select(RoadmapSubject)
            .where(
                RoadmapSubject.job_id == job_id,
                RoadmapSubject.source == "job_prep",
            )
        )
        return result.scalar_one_or_none()

    # topics
    async def create_topic(self, data: dict) -> RoadmapTopic:
        topic = RoadmapTopic(**data)
        self.db.add(topic)
        await self.db.commit()
        await self.db.refresh(topic)
        return topic

    async def bulk_create_topics(self, data_list: list[dict]) -> list[RoadmapTopic]:
        topics = [RoadmapTopic(**data) for data in data_list]
        self.db.add_all(topics)
        await self.db.commit()
        for topic in topics:
            await self.db.refresh(topic)
        return topics

    async def get_topic_by_id(self, topic_id: UUID) -> RoadmapTopic | None:
        result = await self.db.execute(
            select(RoadmapTopic).where(RoadmapTopic.id == topic_id)
        )
        return result.scalar_one_or_none()

    async def get_topic_with_subtopics(
        self, topic_id: UUID
    ) -> RoadmapTopic | None:
        result = await self.db.execute(
            select(RoadmapTopic)
            .options(selectinload(RoadmapTopic.subtopics))
            .where(RoadmapTopic.id == topic_id)
        )
        return result.scalar_one_or_none()

    async def update_topic_status(self, topic_id: UUID, status: str) -> RoadmapTopic | None:
        topic = await self.get_topic_by_id(topic_id)
        if not topic:
            return None
        topic.status = status
        await self.db.commit()
        await self.db.refresh(topic)
        return topic

    # subtopics
    async def bulk_create_subtopics(
        self, data_list: list[dict]
    ) -> list[RoadmapSubtopic]:
        subtopics = [RoadmapSubtopic(**data) for data in data_list]
        self.db.add_all(subtopics)
        await self.db.commit()
        for s in subtopics:
            await self.db.refresh(s)
        return subtopics

    async def get_subtopic_by_id(self, subtopic_id: UUID) -> RoadmapSubtopic | None:
        result = await self.db.execute(
            select(RoadmapSubtopic).where(RoadmapSubtopic.id == subtopic_id)
        )
        return result.scalar_one_or_none()

    async def get_subtopic_with_questions(
        self, subtopic_id: UUID
    ) -> RoadmapSubtopic | None:
        result = await self.db.execute(
            select(RoadmapSubtopic)
            .options(selectinload(RoadmapSubtopic.questions))
            .where(RoadmapSubtopic.id == subtopic_id)
        )
        return result.scalar_one_or_none()

    async def update_subtopic_status(
        self, subtopic_id: UUID, status: str
    ) -> RoadmapSubtopic | None:
        subtopic = await self.get_subtopic_by_id(subtopic_id)
        if not subtopic:
            return None
        subtopic.status = status
        await self.db.commit()
        await self.db.refresh(subtopic)
        return subtopic

    #questions
    async def bulk_create_questions(
        self, data_list: list[dict]
    ) -> list[RoadmapQuestion]:
        questions = [RoadmapQuestion(**data) for data in data_list]
        self.db.add_all(questions)
        await self.db.commit()
        for q in questions:
            await self.db.refresh(q)
        return questions

    async def list_questions_for_subtopic(
        self, subtopic_id: UUID
    ) -> list[RoadmapQuestion]:
        result = await self.db.execute(
            select(RoadmapQuestion)
            .where(RoadmapQuestion.subtopic_id == subtopic_id)
            .order_by(RoadmapQuestion.order_index)
        )
        return result.scalars().all()

    #prep path
    async def create_prep_path(self, data: dict) -> JobPrepPath:
        prep_path = JobPrepPath(**data)
        self.db.add(prep_path)
        await self.db.commit()
        await self.db.refresh(prep_path)
        return prep_path

    async def get_prep_path_by_job(self, job_id: UUID) -> JobPrepPath | None:
        result = await self.db.execute(
            select(JobPrepPath).where(JobPrepPath.job_id == job_id)
        )
        return result.scalar_one_or_none()

    async def update_prep_path(
        self, job_id: UUID, data: dict
    ) -> JobPrepPath | None:
        prep_path = await self.get_prep_path_by_job(job_id)
        if not prep_path:
            return None
        for key, value in data.items():
            setattr(prep_path, key, value)
        await self.db.commit()
        await self.db.refresh(prep_path)
        return prep_path