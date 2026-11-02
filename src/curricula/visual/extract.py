"""Visual evidence extraction service."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from curricula.config import Settings
from curricula.db.models import CodeSnippet, SourceReference, Video, VisualEvidence
from curricula.db.repositories.courses import list_videos
from curricula.domain.enums import (
    EvidenceLayer,
    PipelineStage,
    ProcessingStatus,
    SourceRefType,
)
from curricula.domain.ids import new_id
from curricula.pipeline.contracts import StageResult
from curricula.pipeline.jobs import complete_job, fingerprint_parts, get_or_create_job
from curricula.visual.ocr import StubOCR, classify_scene, extract_abap_snippets
from curricula.visual.scenes import resolve_scene_extractor

logger = logging.getLogger(__name__)


class ExtractVisualsRequest:
    def __init__(
        self,
        *,
        course_slug: str | None = None,
        video_ids: list[UUID] | None = None,
        force: bool = False,
        extractor: str = "stub",
    ) -> None:
        self.course_slug = course_slug
        self.video_ids = video_ids
        self.force = force
        self.extractor = extractor


class ExtractVisualsService:
    def __init__(
        self,
        settings: Settings,
        session_factory: sessionmaker[Session],
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.ocr = StubOCR()

    def run(self, req: ExtractVisualsRequest) -> list[StageResult]:
        self.settings.ensure_dirs()
        extractor = resolve_scene_extractor(
            req.extractor,
            threshold=self.settings.visual.scene_threshold,
        )
        with self.session_factory() as session:
            videos = self._select_videos(session, req)
            session.expunge_all()

        return [
            self._process_one(video, extractor=extractor, force=req.force)
            for video in videos
        ]

    def _select_videos(self, session: Session, req: ExtractVisualsRequest) -> list[Video]:
        if req.video_ids:
            found: list[Video] = []
            for vid in req.video_ids:
                video = session.get(Video, vid)
                if video is not None:
                    found.append(video)
            return found
        return list_videos(session, course_slug=req.course_slug)

    def _process_one(
        self,
        video: Video,
        *,
        extractor: object,
        force: bool,
    ) -> StageResult:
        started = time.perf_counter()
        fp = fingerprint_parts(
            video.sha256,
            getattr(extractor, "name", "scene"),
            getattr(extractor, "version", "1"),
            self.ocr.name,
            self.ocr.version,
        )
        with self.session_factory() as session:
            db_video = session.get(Video, video.id)
            if db_video is None:
                raise RuntimeError(f"Missing video {video.id}")
            job, should_skip = get_or_create_job(
                session,
                stage=PipelineStage.EXTRACT_VISUALS.value,
                fingerprint=fp,
                video_id=db_video.id,
                model_name=getattr(extractor, "name", "scene"),
                model_version=getattr(extractor, "version", "1"),
                force=force,
            )
            if should_skip:
                session.commit()
                return StageResult(
                    stage=PipelineStage.EXTRACT_VISUALS.value,
                    status="skipped",
                    job_id=job.id,
                    fingerprint=fp,
                    metrics={"reason": "fingerprint_match"},
                )
            try:
                out_dir = self.settings.paths.frames_dir / db_video.sha256[:12]
                frames = extractor.extract(Path(db_video.path), out_dir)  # type: ignore[attr-defined]
                artifacts: list[str] = []
                evidence_count = 0
                code_count = 0
                for frame in frames:
                    text, confidence = self.ocr.extract(frame.path)
                    scene_type = classify_scene(text)
                    uncertainty = []
                    if confidence < 0.8:
                        uncertainty.append("low_ocr_confidence")
                    evidence = VisualEvidence(
                        id=new_id(),
                        video_id=db_video.id,
                        timestamp_ms=frame.timestamp_ms,
                        frame_path=str(frame.path),
                        scene_type=scene_type,
                        ocr_text=text,
                        confidence=confidence,
                        uncertainty_flags_json=json.dumps(uncertainty),
                    )
                    session.add(evidence)
                    ref = SourceReference(
                        id=new_id(),
                        video_id=db_video.id,
                        start_ms=frame.timestamp_ms,
                        end_ms=frame.timestamp_ms,
                        layer=EvidenceLayer.RAW.value,
                        ref_type=SourceRefType.FRAME.value,
                        uri=str(frame.path),
                        note=scene_type,
                    )
                    session.add(ref)
                    session.flush()
                    for snippet in extract_abap_snippets(text):
                        session.add(
                            CodeSnippet(
                                id=new_id(),
                                video_id=db_video.id,
                                source_ref_id=ref.id,
                                language="abap",
                                code_text=snippet,
                                ocr_confidence=confidence,
                                is_generated=False,
                            )
                        )
                        code_count += 1
                    artifacts.append(str(frame.path))
                    evidence_count += 1
                complete_job(
                    session,
                    job,
                    status=ProcessingStatus.COMPLETED,
                    artifacts=artifacts,
                    metrics={"frames": evidence_count, "code_snippets": code_count},
                    duration_ms=int((time.perf_counter() - started) * 1000),
                )
                session.commit()
                return StageResult(
                    stage=PipelineStage.EXTRACT_VISUALS.value,
                    status="completed",
                    job_id=job.id,
                    fingerprint=fp,
                    artifacts=[Path(p) for p in artifacts],
                    metrics={"frames": evidence_count, "code_snippets": code_count},
                )
            except Exception as exc:  # noqa: BLE001
                complete_job(
                    session,
                    job,
                    status=ProcessingStatus.FAILED,
                    error=str(exc),
                    duration_ms=int((time.perf_counter() - started) * 1000),
                )
                session.commit()
                logger.exception("extract-visuals failed")
                return StageResult(
                    stage=PipelineStage.EXTRACT_VISUALS.value,
                    status="failed",
                    job_id=job.id,
                    fingerprint=fp,
                    error=str(exc),
                )
