"""Transcription service."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from curricula.config import Settings
from curricula.db.models import Video
from curricula.db.repositories.courses import list_videos, replace_transcript_segments
from curricula.domain.enums import PipelineStage, ProcessingStatus, VideoStatus
from curricula.domain.protocols import WhisperAdapter
from curricula.pipeline.contracts import StageResult, TranscribeRequest
from curricula.pipeline.jobs import complete_job, fingerprint_parts, get_or_create_job
from curricula.transcription.normalize import NORMALIZE_VERSION, normalize_text
from curricula.transcription.whisper_adapter import resolve_adapter

logger = logging.getLogger(__name__)


class TranscribeService:
    def __init__(
        self,
        settings: Settings,
        session_factory: sessionmaker[Session],
        adapter: WhisperAdapter | None = None,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.adapter = adapter

    def run(self, req: TranscribeRequest) -> list[StageResult]:
        self.settings.ensure_dirs()
        adapter_name = req.adapter or self.settings.transcription.adapter
        adapter = self.adapter or resolve_adapter(
            adapter_name,
            device=self.settings.transcription.device,
            compute_type=self.settings.transcription.compute_type,
        )
        model_size = req.model_size or self.settings.transcription.model_size
        language = req.language or self.settings.transcription.language

        with self.session_factory() as session:
            videos = self._select_videos(session, req)
            session.expunge_all()

        results: list[StageResult] = []
        for video in videos:
            results.append(
                self._transcribe_one(
                    video,
                    adapter=adapter,
                    model_size=model_size,
                    language=language,
                    force=req.force,
                )
            )
        return results

    def _select_videos(self, session: Session, req: TranscribeRequest) -> list[Video]:
        if req.video_ids:
            found: list[Video] = []
            for vid in req.video_ids:
                video = session.get(Video, vid)
                if video is not None:
                    found.append(video)
            return found
        return list_videos(session, course_slug=req.course_slug)

    def _transcribe_one(
        self,
        video: Video,
        *,
        adapter: WhisperAdapter,
        model_size: str,
        language: str,
        force: bool,
    ) -> StageResult:
        started = time.perf_counter()
        fp = fingerprint_parts(
            video.sha256,
            adapter.name,
            adapter.version,
            model_size,
            language,
            NORMALIZE_VERSION,
        )
        with self.session_factory() as session:
            db_video = session.get(Video, video.id)
            if db_video is None:
                raise RuntimeError(f"Video disappeared: {video.id}")

            job, should_skip = get_or_create_job(
                session,
                stage=PipelineStage.TRANSCRIBE.value,
                fingerprint=fp,
                video_id=db_video.id,
                model_name=f"{adapter.name}:{model_size}",
                model_version=adapter.version,
                force=force,
            )
            if should_skip:
                session.commit()
                return StageResult(
                    stage=PipelineStage.TRANSCRIBE.value,
                    status="skipped",
                    job_id=job.id,
                    fingerprint=fp,
                    metrics={"reason": "fingerprint_match"},
                )

            try:
                db_video.status = VideoStatus.TRANSCRIBING.value
                session.flush()
                raw_segments = adapter.transcribe(
                    Path(db_video.path),
                    language=language,
                    model_size=model_size,
                )
                enriched: list[dict[str, object]] = []
                for seg in raw_segments:
                    text_raw = str(seg["text"])
                    enriched.append(
                        {
                            **seg,
                            "text": text_raw,
                            "text_normalized": normalize_text(text_raw),
                        }
                    )

                count = replace_transcript_segments(
                    session,
                    db_video,
                    enriched,
                    language=language,
                )
                artifacts = self._write_artifacts(db_video.sha256, enriched, language)
                db_video.status = VideoStatus.TRANSCRIBED.value
                duration_ms = int((time.perf_counter() - started) * 1000)
                complete_job(
                    session,
                    job,
                    status=ProcessingStatus.COMPLETED,
                    artifacts=[str(p) for p in artifacts],
                    metrics={"segments": count},
                    duration_ms=duration_ms,
                )
                session.commit()
                return StageResult(
                    stage=PipelineStage.TRANSCRIBE.value,
                    status="completed",
                    job_id=job.id,
                    fingerprint=fp,
                    artifacts=artifacts,
                    metrics={"segments": count, "video_id": str(db_video.id)},
                )
            except Exception as exc:  # noqa: BLE001
                db_video.status = VideoStatus.FAILED.value
                db_video.error_message = str(exc)
                complete_job(
                    session,
                    job,
                    status=ProcessingStatus.FAILED,
                    error=str(exc),
                    duration_ms=int((time.perf_counter() - started) * 1000),
                )
                session.commit()
                logger.exception("Transcribe failed for video %s", video.id)
                return StageResult(
                    stage=PipelineStage.TRANSCRIBE.value,
                    status="failed",
                    job_id=job.id,
                    fingerprint=fp,
                    error=str(exc),
                )

    def _write_artifacts(
        self,
        sha256: str,
        segments: list[dict[str, object]],
        language: str,
    ) -> list[Path]:
        out_dir = self.settings.paths.transcripts_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        raw_path = out_dir / f"{sha256}.raw.json"
        md_path = out_dir / f"{sha256}.normalized.md"

        raw_payload = {
            "sha256": sha256,
            "language": language,
            "normalize_version": NORMALIZE_VERSION,
            "segments": [
                {
                    "start": seg["start"],
                    "end": seg["end"],
                    "text_raw": seg["text"],
                    "avg_logprob": seg.get("avg_logprob"),
                }
                for seg in segments
            ],
        }
        raw_path.write_text(
            json.dumps(raw_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        lines = [f"# Transcript ({language})", ""]
        for seg in segments:
            start = float(seg["start"])  # type: ignore[arg-type]
            end = float(seg["end"])  # type: ignore[arg-type]
            text = str(seg.get("text_normalized") or seg["text"])
            lines.append(f"[{start:.2f}–{end:.2f}] {text}")
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return [raw_path, md_path]
