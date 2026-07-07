from uuid import UUID
 
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
 
from app.db.models.documents import Document

class DocumentRepository:
    def __init__(self, db: AsyncSession) -> None: 
        self.db = db
    
    async def create(self, data: dict) -> Document:
        document  = Document(**data)
        self.db.add(document)
        await self.db.commit()
        await self.db.refresh(document)
        return document
    
    async def get_by_id(self, document_id: UUID) -> Document | None:
        result = await self.db.execute(select(Document).where(Document.id == document_id))
        return result.scalar_one_or_none()
    
    async def get_latest_for_job(self, job_id: UUID, document_type: str) -> Document | None:
        result = await self.db.execute(
            select(Document)
            .where(Document.job_id == job_id, Document.type == document_type)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_for_job(self, job_id: UUID) -> list[Document]:
        result = await self.db.execute(
            select(Document)
            .where(Document.job_id == job_id)
            .order_by(Document.created_at.desc())
        )
        return result.scalars().all()
    
    async def get_next_version(self, job_id: UUID, document_type: str) -> int:
        latest = await self.get_latest_for_job(job_id, document_type)
        return (latest.version + 1) if latest else 1
