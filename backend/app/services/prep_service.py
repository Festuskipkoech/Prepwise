import json
from collections.abc import AsyncGenerator
from pathlib import Path
from uuid import UUID

from langchain_core.language_models.chat_models import BaseChatModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph.prep_graph import (
    build_prep_path_graph,
    build_question_graph,
    build_subtopic_graph,
)
from app.agents.graph.roadmap_graph import build_roadmap_graph
from app.agents.prompts.prep_prompts import INTERVIEW_SESSION_SYSTEM
from app.agents.tools.prep_utils import (
    build_questions_data,
    build_roadmap_subjects_data,
    build_subtopics_data,
)
from app.core.config import settings
from app.core.exceptions.jobs import JobNotFoundError
from app.core.exceptions.prep import (
    PrepPathGenerationError,
    QuestionGenerationError,
    RoadmapGenerationError,
    SubjectNotFoundError,
    SubtopicNotFoundError,
    TopicNotFoundError,
    RoadmapNotFoundError
)
from app.repositories.job_repository import JobRepository
from app.repositories.prep_repository import PrepRepository
from app.schemas.prep import (
    PrepPathResponse,
    RoadmapResponse,
    SubjectResponse,
    SubjectWithTopicsResponse,
    SubtopicResponse,
    SubtopicWithQuestionsResponse,
    TopicResponse,
    TopicWithSubtopicsResponse,
)

class PrepService:
    def __init__(self, db: AsyncSession, llm: BaseChatModel) -> None:
        self.repo = PrepRepository(db)
        self.job_repo = JobRepository(db)
        self.llm = llm

    def _read_profile(self) -> str:
        return Path(settings.profile_path).read_text(encoding="utf-8")

    # roadmap
    async def get_roadmap(self) -> RoadmapResponse:
        subjects = await self.repo.list_master_subjects()
        total_topics = await self.repo.count_master_topics()

        return RoadmapResponse(
            subjects=[SubjectResponse.model_validate(s) for s in subjects],
            total_subjects=len(subjects),
            total_topics=total_topics,
        )

    async def generate_roadmap(self) -> RoadmapResponse:
        profile_text = self._read_profile()

        graph = build_roadmap_graph(llm=self.llm)
        result = await graph.ainvoke(
            {
                "profile_text": profile_text,
                "subjects": [],
                "error": None,
            }
        )

        if result.get("error"):
            raise RoadmapGenerationError(result["error"])

        subjects_data, topics_data = build_roadmap_subjects_data(result["subjects"])

        subject_name_to_id: dict[str, UUID] = {}
        for subject_data in subjects_data:
            subject = await self.repo.create_subject(subject_data)
            subject_name_to_id[subject.name] = subject.id

        topics_to_create = []
        for topic_data in topics_data:
            subject_name = topic_data.pop("subject_name")
            subject_id = subject_name_to_id.get(subject_name)
            if subject_id:
                topics_to_create.append({**topic_data, "subject_id": subject_id})

        if topics_to_create:
            await self.repo.bulk_create_topics(topics_to_create)

        return await self.get_roadmap()

    # subjects/topics
    async def get_subject_with_topics(
        self, subject_id: UUID
    ) -> SubjectWithTopicsResponse:
        subject = await self.repo.get_subject_with_topics(subject_id)
        if not subject:
            raise SubjectNotFoundError()

        return SubjectWithTopicsResponse(
            subject=SubjectResponse.model_validate(subject),
            topics=[TopicResponse.model_validate(t) for t in subject.topics],
        )

    async def get_topic_with_subtopics(
        self, topic_id: UUID
    ) -> TopicWithSubtopicsResponse:
        topic = await self.repo.get_topic_with_subtopics(topic_id)
        if not topic:
            raise TopicNotFoundError()

        if not topic.subtopics:
            subtopics = await self._generate_subtopics(topic_id)
        else:
            subtopics = topic.subtopics

        return TopicWithSubtopicsResponse(
            topic=TopicResponse.model_validate(topic),
            subtopics=[SubtopicResponse.model_validate(s) for s in subtopics],
        )

    async def _generate_subtopics(self, topic_id: UUID):
        topic = await self.repo.get_topic_by_id(topic_id)
        if not topic:
            raise TopicNotFoundError()

        subject = await self.repo.get_subject_by_id(topic.subject_id)
        profile_text = self._read_profile()

        graph = build_subtopic_graph(llm=self.llm)
        result = await graph.ainvoke(
            {
                "topic_id": topic_id,
                "topic_name": topic.name,
                "subject_name": subject.name if subject else "",
                "profile_text": profile_text,
                "subtopics": [],
                "error": None,
            }
        )

        if result.get("error") or not result["subtopics"]:
            raise RoadmapGenerationError("Failed to generate subtopics")

        subtopics_data = build_subtopics_data(
            topic_id=str(topic_id),
            parsed=result["subtopics"],
        )
        return await self.repo.bulk_create_subtopics(subtopics_data)

    # questions
    async def get_subtopic_with_questions(
        self, subtopic_id: UUID
    ) -> SubtopicWithQuestionsResponse:
        subtopic = await self.repo.get_subtopic_with_questions(subtopic_id)
        if not subtopic:
            raise SubtopicNotFoundError()

        if not subtopic.questions:
            questions = await self._generate_questions(subtopic_id)
        else:
            questions = subtopic.questions

        return SubtopicWithQuestionsResponse(
            subtopic=SubtopicResponse.model_validate(subtopic),
            questions=questions,
        )

    async def _generate_questions(self, subtopic_id: UUID):
        subtopic = await self.repo.get_subtopic_by_id(subtopic_id)
        if not subtopic:
            raise SubtopicNotFoundError()

        profile_text = self._read_profile()

        graph = build_question_graph(llm=self.llm)
        result = await graph.ainvoke(
            {
                "subtopic_id": subtopic_id,
                "subtopic_name": subtopic.name,
                "concept": subtopic.concept or "",
                "project_evidence": subtopic.project_evidence or "",
                "profile_text": profile_text,
                "questions": [],
                "error": None,
            }
        )

        if result.get("error") or not result["questions"]:
            raise QuestionGenerationError()

        questions_data = build_questions_data(
            subtopic_id=str(subtopic_id),
            parsed=result["questions"],
        )
        return await self.repo.bulk_create_questions(questions_data)

    # interview session
    async def interview_session_stream(
        self,
        subtopic_id: UUID,
        conversation_history: list[dict],
        user_answer: str,
    ) -> AsyncGenerator[str, None]:
        subtopic = await self.repo.get_subtopic_by_id(subtopic_id)
        if not subtopic:
            raise SubtopicNotFoundError()

        system = INTERVIEW_SESSION_SYSTEM.format(
            subtopic_name=subtopic.name,
            concept=subtopic.concept or "",
        )

        messages = [{"role": "system", "content": system}]
        messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_answer})

        async for chunk in self.llm.astream(messages):
            token = getattr(chunk, "content", "")
            if token:
                yield json.dumps({"type": "chunk", "content": token})

        yield json.dumps({"type": "done"})

    # job prep path
    async def generate_prep_path_stream(
        self, job_id: UUID
    ) -> AsyncGenerator[str, None]:
        job = await self.job_repo.get_by_id(job_id)
        if not job:
            raise JobNotFoundError()

        if not job.jd_text:
            raise PrepPathGenerationError("Job has no JD text")

        profile_text = self._read_profile()
        graph = build_prep_path_graph(llm=self.llm)

        initial_state = {
            "job_id": job_id,
            "jd_text": job.jd_text,
            "profile_text": profile_text,
            "analysis": {},
            "generated_subject": {},
            "prep_path_data": {},
            "error": None,
        }

        final_state = None

        async for mode, chunk in graph.astream(
            initial_state,
            stream_mode=["custom", "updates"],
        ):
            if mode == "custom":
                yield json.dumps(chunk)
            elif mode == "updates":
                final_state = chunk

        if not final_state:
            raise PrepPathGenerationError("Prep path generation produced no output")

        last_node_output = list(final_state.values())[-1]

        if last_node_output.get("error"):
            raise PrepPathGenerationError(last_node_output["error"])

        generated_subject_data = last_node_output.get("generated_subject", {})
        prep_path_data = last_node_output.get("prep_path_data", {})

        generated_subject_id = None
        if generated_subject_data:
            subject = await self.repo.create_subject(
                {
                    "name": generated_subject_data["name"],
                    "description": generated_subject_data.get("description", ""),
                    "order_index": 0,
                    "source": "job_prep",
                    "job_id": job_id,
                }
            )
            generated_subject_id = subject.id

            topics_data = [
                {
                    "subject_id": subject.id,
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "order_index": t.get("order_index", i),
                    "status": "not_started",
                }
                for i, t in enumerate(generated_subject_data.get("topics", []))
            ]
            if topics_data:
                await self.repo.bulk_create_topics(topics_data)

        existing = await self.repo.get_prep_path_by_job(job_id)
        if existing:
            prep_path = await self.repo.update_prep_path(
                job_id,
                {
                    **prep_path_data,
                    "generated_subject_id": generated_subject_id,
                },
            )
        else:
            prep_path = await self.repo.create_prep_path(
                {
                    "job_id": job_id,
                    "generated_subject_id": generated_subject_id,
                    **prep_path_data,
                }
            )

        yield json.dumps(
            {
                "type": "done",
                "prep_path_id": str(prep_path.id),
                "generated_subject_id": str(generated_subject_id) if generated_subject_id else None,
            }
        )

    async def get_prep_path(self, job_id: UUID) -> PrepPathResponse:
        prep_path = await self.repo.get_prep_path_by_job(job_id)
        if not prep_path:
            raise RoadmapNotFoundError("No prep path found for this job")
        return PrepPathResponse.model_validate(prep_path)