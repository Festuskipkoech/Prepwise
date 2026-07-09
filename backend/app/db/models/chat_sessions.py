import uuid
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import BaseModel

class ChatSession(BaseModel):
    __tablename__ = "chat_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    engine_type: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    user: Mapped["User"] = relationship("User", back_populates="chat_sessions")
    documents: Mapped[list["Document"]] = relationship(
        "Document",
        back_populates="chat_session",
        cascade="all, delete-orphan",
        lazy="noload",
    )
    prep_roadmap: Mapped[Optional["PrepRoadmap"]] = relationship(
        "PrepRoadmap",
        back_populates="chat_session",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="noload",
    )

    __table_args__ = (
        CheckConstraint(
            "engine_type IN ('job', 'prep', 'document', 'tracker')",
            name="ck_chat_sessions_engine_type",
        ),
        Index("idx_chat_sessions_user_id", "user_id"),
        Index("idx_chat_sessions_user_engine", "user_id", "engine_type"),
        Index("idx_chat_sessions_updated", "user_id", "updated_at"),
        Index(
            "idx_chat_sessions_active",
            "user_id",
            postgresql_where="is_archived = false",
        ),
    )