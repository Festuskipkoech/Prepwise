import json
from collections.abc import AsyncGenerator
from uuid import UUID

from langchain_core.language_models.chat_models import BaseChatModel
from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph.document_graph import build_document_graph
from app.agents.tools.document_utils import parse_document_output
from app.core.exceptions.documents import (
    DocumentGenerationError,
    DocumentNotFoundError,
    JDMissingError,
)
from app.core.exceptions.jobs import JobNotFoundError
from app.repositories.document_repository import DocumentRepository
from app.repositories.job_repository import JobRepository
from app.schemas.documents import DocumentListResponse, DocumentResponse

VALID_TYPES = {"resume", "cover_letter"}

class DocumentService:
    def __init__(
        self,
        db: AsyncSession,
        llm: BaseChatModel,
        qdrant: AsyncQdrantClient,
    ) -> None:
        self.doc_repo = DocumentRepository(db)
        self.job_repo = JobRepository(db)
        self.llm = llm
        self.qdrant = qdrant

    async def generate_stream(
        self, job_id: UUID, document_type: str
    ) -> AsyncGenerator[str, None]:
        if document_type not in VALID_TYPES:
            raise DocumentGenerationError(
                f"Invalid document type. Must be one of: {', '.join(VALID_TYPES)}"
            )

        job = await self.job_repo.get_by_id(job_id)
        if not job:
            raise JobNotFoundError()

        if not job.jd_text:
            raise JDMissingError()

        graph = build_document_graph(llm=self.llm, qdrant=self.qdrant)

        initial_state = {
            "job_id": job_id,
            "document_type": document_type,
            "jd_text": job.jd_text,
            "retrieved_chunks": [],
            "jd_analysis": {},
            "generated_content": {},
            "error": None,
        }

        full_content = ""

        async for mode, chunk in graph.astream(
            initial_state,
            stream_mode=["custom", "messages"],
        ):
            if mode == "custom":
                yield json.dumps(chunk)

            elif mode == "messages":
                message_chunk, metadata = chunk
                token = getattr(message_chunk, "content", "")
                if token and metadata.get("langgraph_node") == "generate":
                    full_content += token
                    yield json.dumps({"type": "chunk", "content": token})

        if not full_content:
            raise DocumentGenerationError("Generation produced no content")

        structured = parse_document_output(full_content)

        version = await self.doc_repo.get_next_version(job_id, document_type)
        document = await self.doc_repo.create(
            {
                "job_id": job_id,
                "type": document_type,
                "content": structured,
                "version": version,
            }
        )

        yield json.dumps(
            {
                "type": "done",
                "document_id": str(document.id),
                "version": document.version,
            }
        )

    async def get_document(self, document_id: UUID) -> DocumentResponse:
        document = await self.doc_repo.get_by_id(document_id)
        if not document:
            raise DocumentNotFoundError()
        return DocumentResponse.model_validate(document)

    async def get_latest(self, job_id: UUID, document_type: str) -> DocumentResponse:
        document = await self.doc_repo.get_latest_for_job(job_id, document_type)
        if not document:
            raise DocumentNotFoundError()
        return DocumentResponse.model_validate(document)

    async def list_for_job(self, job_id: UUID) -> DocumentListResponse:
        documents = await self.doc_repo.list_for_job(job_id)
        return DocumentListResponse(
            documents=[DocumentResponse.model_validate(d) for d in documents]
        )