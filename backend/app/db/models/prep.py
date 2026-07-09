import uuid
from typing import Optional

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import BaseModel

class PrepRoadmap(BaseModel):
    __tablename__ = "prep_roadmaps"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    chat_session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    target_role: Mapped[str] = mapped_column(Text, nullable=False)
    target_company: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_roadmap: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    current_subject_index: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    current_topic_index: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    topic_mastery: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")

    user: Mapped["User"] = relationship("User", back_populates="prep_roadmaps")
    chat_session: Mapped[Optional["ChatSession"]] = relationship(
        "ChatSession", back_populates="prep_roadmap"
    )
    job: Mapped[Optional["Job"]] = relationship("Job", back_populates="prep_roadmaps")

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'completed')",
            name="ck_prep_roadmaps_status",
        ),
        Index("idx_prep_roadmaps_user_id", "user_id"),
        Index("idx_prep_roadmaps_user_status", "user_id", "status"),
        Index("idx_prep_roadmaps_chat_session", "chat_session_id"),
        Index("idx_prep_roadmaps_job", "job_id"),
    )