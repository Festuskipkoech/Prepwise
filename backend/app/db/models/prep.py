import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import BaseModel

class RoadmapSubject(BaseModel):
    __tablename__ = "roadmap_subjects"
 
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source: Mapped[str] = mapped_column(
        String, nullable=False, default="roadmap"
    )
    job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
 
    topics: Mapped[list["RoadmapTopic"]] = relationship(
        "RoadmapTopic",
        back_populates="subject",
        cascade="all, delete-orphan",
        order_by="RoadmapTopic.order_index",
        lazy="noload",
    )
    job: Mapped[Optional["Job"]] = relationship(
        "Job",
        back_populates="job_subjects",
        foreign_keys=[job_id],
        lazy="noload",
    )
 
 
class RoadmapTopic(BaseModel):
    __tablename__ = "roadmap_topics"
 
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roadmap_subjects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String, nullable=False, default="not_started")
 
    subject: Mapped["RoadmapSubject"] = relationship(
        "RoadmapSubject", back_populates="topics"
    )
    subtopics: Mapped[list["RoadmapSubtopic"]] = relationship(
        "RoadmapSubtopic",
        back_populates="topic",
        cascade="all, delete-orphan",
        order_by="RoadmapSubtopic.order_index",
        lazy="noload",
    )
 
 
class RoadmapSubtopic(BaseModel):
    __tablename__ = "roadmap_subtopics"
 
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roadmap_topics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    concept: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    project_evidence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String, nullable=False, default="not_started")
    generated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
 
    topic: Mapped["RoadmapTopic"] = relationship(
        "RoadmapTopic", back_populates="subtopics"
    )
    questions: Mapped[list["RoadmapQuestion"]] = relationship(
        "RoadmapQuestion",
        back_populates="subtopic",
        cascade="all, delete-orphan",
        order_by="RoadmapQuestion.order_index",
        lazy="noload",
    )
 
 
class RoadmapQuestion(BaseModel):
    __tablename__ = "roadmap_questions"
 
    subtopic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roadmap_subtopics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(String, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    generated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
 
    subtopic: Mapped["RoadmapSubtopic"] = relationship(
        "RoadmapSubtopic", back_populates="questions"
    )
 
 
class JobPrepPath(BaseModel):
    __tablename__ = "job_prep_paths"
 
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    generated_subject_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roadmap_subjects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    strong_matches: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    needs_sharpening: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    gaps: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    roadmap_links: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    talking_points: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    likely_angles: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    generated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
 
    job: Mapped["Job"] = relationship("Job", back_populates="prep_path")
    generated_subject: Mapped[Optional["RoadmapSubject"]] = relationship(
        "RoadmapSubject",
        foreign_keys=[generated_subject_id],
        lazy="noload",
    )