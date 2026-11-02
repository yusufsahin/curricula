"""Video ingestion service."""

from __future__ import annotations

import json
import logging
import shutil
import time
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from curricula.config import Settings
from curricula.db.repositories.courses import get_or_create_course, upsert_video
from curricula.domain.enums import PipelineStage, ProcessingStatus
from curricula.domain.protocols import MediaProbe
from curricula.media.hashing import sha256_file
from curricula.media.metadata import FfprobeMediaProbe
from curricula.pipeline.contracts import IngestRequest, StageResult
from curricula.pipeline.jobs import complete_job, get_or_create_job

logger = logging.getLogger(__name__)


class IngestService:
    def __init__(
        self,
        settings: Settings,
        session_factory: sessionmaker[Session],
        probe: MediaProbe | None = None,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.probe = probe or FfprobeMediaProbe()

    def run(self, req: IngestRequest) -> list[StageResult]:
        results: list[StageResult] = []
        self.settings.ensure_dirs()
        with self.session_factory() as session:
            get_or_create_course(
                session,
                req.course_slug,
                locale=self.settings.app.locale,
            )
            session.commit()

        for video_path in req.video_paths:
            results.append(self._ingest_one(video_path, req.course_slug, req.force))
        return results

    def _ingest_one(self, video_path: Path, course_slug: str, force: bool) -> StageResult:
        started = time.perf_counter()
        path = video_path.resolve()
        if not path.is_file():
            # Create a failed job-less style result with ephemeral id via DB
            with self.session_factory() as session:
                course = get_or_create_course(session, course_slug)
                fp = f"missing:{path}"
                job, _ = get_or_create_job(
                    session,
                    stage=PipelineStage.INGEST.value,
                    fingerprint=fp,
                    force=True,
                )
                complete_job(
                    session,
                    job,
                    status=ProcessingStatus.FAILED,
                    error=f"File not found: {path}",
                    duration_ms=int((time.perf_counter() - started) * 1000),
                )
                session.commit()
                return StageResult(
                    stage=PipelineStage.INGEST.value,
                    status="failed",
                    job_id=job.id,
                    fingerprint=fp,
                    error=f"File not found: {path}",
                )

        digest = sha256_file(path)
        with self.session_factory() as session:
            course = get_or_create_course(session, course_slug)
            job, should_skip = get_or_create_job(
                session,
                stage=PipelineStage.INGEST.value,
                fingerprint=digest,
                force=force,
                model_name="ffprobe",
                model_version="1",
            )
            if should_skip:
                session.commit()
                logger.info("Skipping ingest for %s (fingerprint match)", path.name)
                return StageResult(
                    stage=PipelineStage.INGEST.value,
                    status="skipped",
                    job_id=job.id,
                    fingerprint=digest,
                    metrics={"reason": "fingerprint_match"},
                )

            try:
                meta = self.probe.probe(path)
                dest = path
                if self.settings.ingest.copy_into_data:
                    dest_dir = self.settings.paths.videos_dir
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    dest = dest_dir / f"{digest[:12]}_{path.name}"
                    if not dest.exists():
                        shutil.copy2(path, dest)

                video, created = upsert_video(
                    session,
                    course=course,
                    path=dest,
                    sha256=digest,
                    filename=path.name,
                    duration_sec=meta.get("duration_sec"),  # type: ignore[arg-type]
                    codec=meta.get("codec"),  # type: ignore[arg-type]
                    width=meta.get("width"),  # type: ignore[arg-type]
                    height=meta.get("height"),  # type: ignore[arg-type]
                    filesize=meta.get("filesize"),  # type: ignore[arg-type]
                    meta_json=json.dumps(meta.get("raw") or {}, ensure_ascii=False),
                )
                job.video_id = video.id
                duration_ms = int((time.perf_counter() - started) * 1000)
                complete_job(
                    session,
                    job,
                    status=ProcessingStatus.COMPLETED,
                    artifacts=[str(dest)],
                    metrics={
                        "created": created,
                        "duration_sec": meta.get("duration_sec"),
                        "filesize": meta.get("filesize"),
                    },
                    duration_ms=duration_ms,
                )
                session.commit()
                return StageResult(
                    stage=PipelineStage.INGEST.value,
                    status="completed",
                    job_id=job.id,
                    fingerprint=digest,
                    artifacts=[dest],
                    metrics={"video_id": str(video.id), "created": created},
                )
            except Exception as exc:  # noqa: BLE001 — stage boundary
                complete_job(
                    session,
                    job,
                    status=ProcessingStatus.FAILED,
                    error=str(exc),
                    duration_ms=int((time.perf_counter() - started) * 1000),
                )
                session.commit()
                logger.exception("Ingest failed for %s", path)
                return StageResult(
                    stage=PipelineStage.INGEST.value,
                    status="failed",
                    job_id=job.id,
                    fingerprint=digest,
                    error=str(exc),
                )
