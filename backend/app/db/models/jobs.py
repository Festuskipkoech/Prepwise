import uuid
from datetime import date
from typing import Optional

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import BaseModel

class Job(BaseModel):
    __tablename__ = "jobs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    company: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    jd_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String, nullable=False, default="manual")
    status: Mapped[str] = mapped_column(String, nullable=False, default="bookmarked")
    applied_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    follow_up_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="jobs")
    documents: Mapped[list["Document"]] = relationship(
        "Document",
        back_populates="job",
        cascade="all, delete-orphan",
        lazy="noload",
    )
    prep_roadmaps: Mapped[list["PrepRoadmap"]] = relationship(
        "PrepRoadmap",
        back_populates="job",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    __table_args__ = (
        CheckConstraint(
            "source IN ('search', 'manual')",
            name="ck_jobs_source",
        ),
        CheckConstraint(
            "status IN ('bookmarked', 'applied', 'screening', 'interview', 'offer', 'rejected', 'withdrawn')",
            name="ck_jobs_status",
        ),
        Index("idx_jobs_user_id", "user_id"),
        Index("idx_jobs_user_status", "user_id", "status"),
        Index("idx_jobs_user_applied_date", "user_id", "applied_date"),
        Index(
            "idx_jobs_user_follow_up",
            "user_id",
            "follow_up_date",
            postgresql_where="follow_up_date IS NOT NULL",
        ),
        Index("idx_jobs_cursor", "user_id", "created_at", "id"),
    )