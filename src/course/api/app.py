"""FastAPI application for future HTTP integration."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from course import __version__
from course.config import Settings, load_settings
from course.db.models import (
    ContentBlock,
    Course,
    KnowledgeGap,
    ProcessingJob,
    Topic,
    Video,
)
from course.db.session import create_schema, make_engine, make_session_factory


class HealthResponse(BaseModel):
    status: str
    version: str


class CourseOut(BaseModel):
    id: UUID
    slug: str
    title: str
    locale: str


class VideoOut(BaseModel):
    id: UUID
    course_id: UUID
    filename: str
    sha256: str
    status: str
    duration_sec: float | None = None


class TopicOut(BaseModel):
    id: UUID
    stable_id: str
    title_tr: str
    title_canonical: str | None = None
    review_status: str
    enrichment_status: str
    learning_order: int | None = None


class GapOut(BaseModel):
    id: UUID
    topic_id: UUID
    gap_class: str
    dimension: str
    priority: int
    evidence_note: str | None = None


class JobOut(BaseModel):
    id: UUID
    stage: str
    status: str
    model_name: str | None = None
    duration_ms: int | None = None
    error_message: str | None = None


class StatusSummary(BaseModel):
    courses: int
    videos: int
    topics: int
    gaps: int
    content_blocks: int
    jobs_completed: int
    jobs_failed: int


def create_app(
    settings: Settings | None = None,
    session_factory: sessionmaker[Session] | None = None,
) -> FastAPI:
    settings = settings or load_settings()
    settings.ensure_dirs()
    if session_factory is None:
        engine = make_engine(settings.paths.db_path)
        create_schema(engine)
        session_factory = make_session_factory(engine)

    app = FastAPI(
        title="SAP ABAP Curriculum Intelligence API",
        version=__version__,
        description="Local-first curriculum API over the SQLite repository",
    )
    app.state.settings = settings
    app.state.session_factory = session_factory

    def get_session() -> Iterator[Session]:
        factory: sessionmaker[Session] = app.state.session_factory
        with factory() as session:
            yield session

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", version=__version__)

    @app.get("/v1/status", response_model=StatusSummary)
    def status(session: Session = Depends(get_session)) -> StatusSummary:
        return StatusSummary(
            courses=session.scalar(select(func.count()).select_from(Course)) or 0,
            videos=session.scalar(select(func.count()).select_from(Video)) or 0,
            topics=session.scalar(select(func.count()).select_from(Topic)) or 0,
            gaps=session.scalar(select(func.count()).select_from(KnowledgeGap)) or 0,
            content_blocks=session.scalar(select(func.count()).select_from(ContentBlock))
            or 0,
            jobs_completed=session.scalar(
                select(func.count())
                .select_from(ProcessingJob)
                .where(ProcessingJob.status == "completed")
            )
            or 0,
            jobs_failed=session.scalar(
                select(func.count())
                .select_from(ProcessingJob)
                .where(ProcessingJob.status == "failed")
            )
            or 0,
        )

    @app.get("/v1/courses", response_model=list[CourseOut])
    def list_courses(session: Session = Depends(get_session)) -> list[CourseOut]:
        rows = session.scalars(select(Course).order_by(Course.slug)).all()
        return [
            CourseOut(id=c.id, slug=c.slug, title=c.title, locale=c.locale) for c in rows
        ]

    @app.get("/v1/courses/{slug}/videos", response_model=list[VideoOut])
    def list_course_videos(
        slug: str,
        session: Session = Depends(get_session),
    ) -> list[VideoOut]:
        course = session.scalar(select(Course).where(Course.slug == slug))
        if course is None:
            raise HTTPException(status_code=404, detail="Course not found")
        rows = session.scalars(
            select(Video).where(Video.course_id == course.id).order_by(Video.filename)
        ).all()
        return [
            VideoOut(
                id=v.id,
                course_id=v.course_id,
                filename=v.filename,
                sha256=v.sha256,
                status=v.status,
                duration_sec=v.duration_sec,
            )
            for v in rows
        ]

    @app.get("/v1/topics", response_model=list[TopicOut])
    def list_topics(
        session: Session = Depends(get_session),
        q: str | None = Query(default=None, description="Filter by stable_id/title"),
    ) -> list[TopicOut]:
        stmt = select(Topic).order_by(Topic.learning_order, Topic.stable_id)
        rows = list(session.scalars(stmt).all())
        if q:
            needle = q.lower()
            rows = [
                t
                for t in rows
                if needle in t.stable_id.lower()
                or needle in t.title_tr.lower()
                or needle in (t.title_canonical or "").lower()
            ]
        return [
            TopicOut(
                id=t.id,
                stable_id=t.stable_id,
                title_tr=t.title_tr,
                title_canonical=t.title_canonical,
                review_status=t.review_status,
                enrichment_status=t.enrichment_status,
                learning_order=t.learning_order,
            )
            for t in rows
        ]

    @app.get("/v1/topics/{stable_id}", response_model=TopicOut)
    def get_topic(
        stable_id: str,
        session: Session = Depends(get_session),
    ) -> TopicOut:
        topic = session.scalar(select(Topic).where(Topic.stable_id == stable_id))
        if topic is None:
            raise HTTPException(status_code=404, detail="Topic not found")
        return TopicOut(
            id=topic.id,
            stable_id=topic.stable_id,
            title_tr=topic.title_tr,
            title_canonical=topic.title_canonical,
            review_status=topic.review_status,
            enrichment_status=topic.enrichment_status,
            learning_order=topic.learning_order,
        )

    @app.get("/v1/gaps", response_model=list[GapOut])
    def list_gaps(
        session: Session = Depends(get_session),
        gap_class: str | None = None,
    ) -> list[GapOut]:
        stmt = select(KnowledgeGap).order_by(KnowledgeGap.priority.desc())
        if gap_class:
            stmt = stmt.where(KnowledgeGap.gap_class == gap_class)
        rows = session.scalars(stmt).all()
        return [
            GapOut(
                id=g.id,
                topic_id=g.topic_id,
                gap_class=g.gap_class,
                dimension=g.dimension,
                priority=g.priority,
                evidence_note=g.evidence_note,
            )
            for g in rows
        ]

    @app.get("/v1/jobs", response_model=list[JobOut])
    def list_jobs(
        session: Session = Depends(get_session),
        stage: str | None = None,
        limit: int = Query(default=50, ge=1, le=500),
    ) -> list[JobOut]:
        stmt = (
            select(ProcessingJob).order_by(ProcessingJob.started_at.desc()).limit(limit)
        )
        if stage:
            stmt = stmt.where(ProcessingJob.stage == stage)
        rows = session.scalars(stmt).all()
        return [
            JobOut(
                id=j.id,
                stage=j.stage,
                status=j.status,
                model_name=j.model_name,
                duration_ms=j.duration_ms,
                error_message=j.error_message,
            )
            for j in rows
        ]

    return app


def build_app_from_paths(
    *,
    config: Path | None = None,
    db: Path | None = None,
    data_dir: Path | None = None,
) -> FastAPI:
    settings = load_settings(config, db_path=db, data_dir=data_dir)
    return create_app(settings=settings)
