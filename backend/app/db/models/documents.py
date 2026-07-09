import uuid
from typing import Optional

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import BaseModel

class Document(BaseModel):
    __tablename__ = "documents"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    chat_session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    type: Mapped[str] = mapped_column(String, nullable=False)
    content_md: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    user: Mapped["User"] = relationship("User", back_populates="documents")
    job: Mapped[Optional["Job"]] = relationship("Job", back_populates="documents")
    chat_session: Mapped[Optional["ChatSession"]] = relationship(
        "ChatSession", back_populates="documents"
    )

    __table_args__ = (
        CheckConstraint(
            "type IN ('resume', 'cover_letter')",
            name="ck_documents_type",
        ),
        Index("idx_documents_user_id", "user_id"),
        Index("idx_documents_job_id", "job_id"),
        Index("idx_documents_chat_session", "chat_session_id", "type", "version"),
        Index("idx_documents_latest", "job_id", "type", "version"),
    )