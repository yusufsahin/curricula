"""ProcessingJob helpers for idempotent stages."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from course.db.models import ProcessingJob
from course.domain.enums import ProcessingStatus
from course.domain.ids import new_id


def fingerprint_parts(*parts: str) -> str:
    payload = "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def find_job(session: Session, stage: str, fingerprint: str) -> ProcessingJob | None:
    stmt = select(ProcessingJob).where(
        ProcessingJob.stage == stage,
        ProcessingJob.input_fingerprint == fingerprint,
    )
    return session.scalar(stmt)


def get_or_create_job(
    session: Session,
    *,
    stage: str,
    fingerprint: str,
    video_id: UUID | None = None,
    model_name: str | None = None,
    model_version: str | None = None,
    force: bool = False,
) -> tuple[ProcessingJob, bool]:
    """Return (job, should_skip)."""
    existing = find_job(session, stage, fingerprint)
    if existing is not None:
        if (
            not force
            and existing.status == ProcessingStatus.COMPLETED.value
        ):
            return existing, True
        job = existing
        job.status = ProcessingStatus.RUNNING.value
        job.error_message = None
        job.started_at = datetime.now(UTC)
        job.finished_at = None
        job.model_name = model_name
        job.model_version = model_version
        if video_id is not None:
            job.video_id = video_id
    else:
        job = ProcessingJob(
            id=new_id(),
            stage=stage,
            video_id=video_id,
            input_fingerprint=fingerprint,
            status=ProcessingStatus.RUNNING.value,
            started_at=datetime.now(UTC),
            model_name=model_name,
            model_version=model_version,
            artifact_paths_json="[]",
            metrics_json="{}",
        )
        session.add(job)
    session.flush()
    return job, False


def complete_job(
    session: Session,
    job: ProcessingJob,
    *,
    status: ProcessingStatus,
    artifacts: list[str] | None = None,
    metrics: dict[str, Any] | None = None,
    error: str | None = None,
    duration_ms: int | None = None,
    cost_usd: float | None = None,
) -> None:
    job.status = status.value
    job.finished_at = datetime.now(UTC)
    if artifacts is not None:
        job.artifact_paths_json = json.dumps(artifacts)
    if metrics is not None:
        job.metrics_json = json.dumps(metrics)
    if error is not None:
        job.error_message = error
    if duration_ms is not None:
        job.duration_ms = duration_ms
    if cost_usd is not None:
        job.cost_usd = cost_usd
    session.flush()
