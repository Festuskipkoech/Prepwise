from datetime import date
from typing import Optional

from sqlalchemy import Date, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import BaseModel
from app.db.models.documents import Document
from app.db.models.prep import JobPrepPath, RoadmapSubject


class Job(BaseModel):
    __tablename__ = "jobs"
 
    title: Mapped[str] = mapped_column(String, nullable=False)
    company: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    jd_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(
        String, nullable=False, default="manual"
    )
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="bookmarked"
    )
    applied_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    follow_up_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
 
    documents: Mapped[list["Document"]] = relationship(
        "Document",
        back_populates="job",
        cascade="all, delete-orphan",
        lazy="noload",
    )
    prep_path: Mapped[Optional["JobPrepPath"]] = relationship(
        "JobPrepPath",
        back_populates="job",
        cascade="all, delete-orphan",
        foreign_keys="JobPrepPath.job_id",
        uselist=False,
        lazy="noload",
    )
    job_subjects: Mapped[list["RoadmapSubject"]] = relationship(
        "RoadmapSubject",
        back_populates="job",
        cascade="all, delete-orphan",
        foreign_keys="RoadmapSubject.job_id",
        lazy="noload",
    )
 