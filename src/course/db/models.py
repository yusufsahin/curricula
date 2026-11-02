"""ORM models — Phase 1 tables plus forward-compatible stubs."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from course.db.base import Base


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    locale: Mapped[str] = mapped_column(String(16), nullable=False, default="tr")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    videos: Mapped[list[Video]] = relationship(back_populates="course")


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    course_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("courses.id"), nullable=False, index=True
    )
    path: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    duration_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    codec: Mapped[str | None] = mapped_column(String(64), nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    filesize: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    meta_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    course: Mapped[Course] = relationship(back_populates="videos")
    transcript_segments: Mapped[list[TranscriptSegment]] = relationship(
        back_populates="video"
    )


class TranscriptSegment(Base):
    __tablename__ = "transcript_segments"
    __table_args__ = (UniqueConstraint("video_id", "seg_index", name="uq_segment_video_index"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    video_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("videos.id"), nullable=False, index=True
    )
    seg_index: Mapped[int] = mapped_column(Integer, nullable=False)
    start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    end_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    text_raw: Mapped[str] = mapped_column(Text, nullable=False)
    text_normalized: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="tr")
    avg_logprob: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    video: Mapped[Video] = relationship(back_populates="transcript_segments")


class SourceReference(Base):
    __tablename__ = "source_references"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    video_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("videos.id"), nullable=True, index=True
    )
    start_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    layer: Mapped[str] = mapped_column(String(32), nullable=False, default="raw")
    ref_type: Mapped[str] = mapped_column(String(32), nullable=False)
    uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"
    __table_args__ = (
        UniqueConstraint("stage", "input_fingerprint", name="uq_job_stage_fingerprint"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    stage: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    video_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("videos.id"), nullable=True
    )
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifact_paths_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    metrics_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")


class ArtifactVersion(Base):
    __tablename__ = "artifact_versions"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload_path: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False, default="system")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    parent_version_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("artifact_versions.id"), nullable=True
    )


# --- Forward-compatible stubs (Phase 2–4); created in Phase 1 schema for continuity ---


class VisualEvidence(Base):
    __tablename__ = "visual_evidence"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    video_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("videos.id"), nullable=False, index=True
    )
    timestamp_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    frame_path: Mapped[str] = mapped_column(Text, nullable=False)
    scene_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    uncertainty_flags_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class CodeSnippet(Base):
    __tablename__ = "code_snippets"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    video_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("videos.id"), nullable=True
    )
    source_ref_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("source_references.id"), nullable=True
    )
    language: Mapped[str] = mapped_column(String(32), nullable=False, default="abap")
    code_text: Mapped[str] = mapped_column(Text, nullable=False)
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    stable_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    title_tr: Mapped[str] = mapped_column(String(512), nullable=False)
    title_canonical: Mapped[str | None] = mapped_column(String(512), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unreviewed")
    enrichment_status: Mapped[str] = mapped_column(String(32), nullable=False, default="none")
    source_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    learning_order: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Concept(Base):
    __tablename__ = "concepts"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_term: Mapped[str] = mapped_column(String(256), nullable=False)


class TopicOccurrence(Base):
    __tablename__ = "topic_occurrences"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    topic_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("topics.id"), nullable=False
    )
    video_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("videos.id"), nullable=False
    )
    source_ref_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("source_references.id"), nullable=True
    )
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)


class TopicRelationship(Base):
    __tablename__ = "topic_relationships"
    __table_args__ = (
        UniqueConstraint(
            "from_topic_id", "to_topic_id", "type", name="uq_topic_rel_from_to_type"
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    from_topic_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("topics.id"), nullable=False
    )
    to_topic_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("topics.id"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="auto")


class LearningObjective(Base):
    __tablename__ = "learning_objectives"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    topic_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("topics.id"), nullable=False
    )
    text_tr: Mapped[str] = mapped_column(Text, nullable=False)
    bloom_level: Mapped[str | None] = mapped_column(String(64), nullable=True)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")


class ContentBlock(Base):
    __tablename__ = "content_blocks"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    topic_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("topics.id"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    body_md: Mapped[str] = mapped_column(Text, nullable=False)
    layer: Mapped[str] = mapped_column(String(32), nullable=False, default="generated")
    provenance_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    enrichment_status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class KnowledgeGap(Base):
    __tablename__ = "knowledge_gaps"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    topic_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("topics.id"), nullable=False
    )
    gap_class: Mapped[str] = mapped_column(String(32), nullable=False)
    dimension: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class EnrichmentTask(Base):
    __tablename__ = "enrichment_tasks"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    gap_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("knowledge_gaps.id"), nullable=True
    )
    topic_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("topics.id"), nullable=False
    )
    task_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    assigned_model: Mapped[str | None] = mapped_column(String(128), nullable=True)


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    topic_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("topics.id"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    is_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ReviewDecision(Base):
    __tablename__ = "review_decisions"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    reviewer: Mapped[str] = mapped_column(String(128), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
