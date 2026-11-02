"""Heuristic topic discovery from transcripts and visual OCR (offline)."""

from __future__ import annotations

import logging
import re
import time
from collections import defaultdict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from course.config import Settings
from course.db.models import (
    Concept,
    SourceReference,
    Topic,
    TopicOccurrence,
    TranscriptSegment,
    VisualEvidence,
)
from course.db.repositories.courses import list_videos
from course.domain.enums import (
    EvidenceLayer,
    PipelineStage,
    ProcessingStatus,
    SourceRefType,
)
from course.domain.ids import new_id
from course.pipeline.contracts import StageResult
from course.pipeline.jobs import complete_job, fingerprint_parts, get_or_create_job

logger = logging.getLogger(__name__)

# Canonical SAP/ABAP terms → Turkish labels
TOPIC_CATALOG: dict[str, tuple[str, str, str]] = {
    "SELECT": ("abap-select", "SELECT ifadesi", "SELECT"),
    "DATA": ("abap-data", "DATA bildirimi", "DATA"),
    "TYPES": ("abap-types", "TYPES tanımı", "TYPES"),
    "LOOP": ("abap-loop", "LOOP döngüsü", "LOOP"),
    "INTERNAL TABLE": ("abap-internal-tables", "Internal table'lar", "Internal Tables"),
    "FORM": ("abap-form", "FORM rutini", "FORM"),
    "CLASS": ("abap-class", "CLASS tanımı", "CLASS"),
    "METHOD": ("abap-method", "METHOD tanımı", "METHOD"),
    "WRITE": ("abap-write", "WRITE çıktısı", "WRITE"),
}

KEYWORD_RE = re.compile(
    r"\b(SELECT|DATA|TYPES|LOOP|FORM|CLASS|METHOD|WRITE|INTERNAL\s+TABLES?)\b",
    re.IGNORECASE,
)


class DiscoverTopicsRequest:
    def __init__(
        self,
        *,
        course_slug: str | None = None,
        force: bool = False,
    ) -> None:
        self.course_slug = course_slug
        self.force = force


class DiscoverTopicsService:
    def __init__(
        self,
        settings: Settings,
        session_factory: sessionmaker[Session],
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory

    def run(self, req: DiscoverTopicsRequest) -> list[StageResult]:
        started = time.perf_counter()
        with self.session_factory() as session:
            videos = list_videos(session, course_slug=req.course_slug)
            video_ids = [v.id for v in videos]
            hashes = sorted(v.sha256 for v in videos)
            fp = fingerprint_parts(
                *hashes,
                self.settings.topics.taxonomy_version,
                self.settings.topics.prompt_version,
                "heuristic-1",
            )
            job, should_skip = get_or_create_job(
                session,
                stage=PipelineStage.DISCOVER_TOPICS.value,
                fingerprint=fp,
                model_name="heuristic",
                model_version="1",
                force=req.force,
            )
            if should_skip:
                session.commit()
                return [
                    StageResult(
                        stage=PipelineStage.DISCOVER_TOPICS.value,
                        status="skipped",
                        job_id=job.id,
                        fingerprint=fp,
                        metrics={"reason": "fingerprint_match"},
                    )
                ]
            try:
                hits = self._collect_hits(session, video_ids)
                topics_created = 0
                occurrences = 0
                order = 0
                for key, refs in sorted(hits.items()):
                    catalog_key = key.upper()
                    if catalog_key.startswith("INTERNAL"):
                        catalog_key = "INTERNAL TABLE"
                    meta = TOPIC_CATALOG.get(catalog_key)
                    if meta is None:
                        stable_id = f"topic-{catalog_key.lower().replace(' ', '-')}"
                        title_tr = catalog_key
                        title_canonical = catalog_key
                    else:
                        stable_id, title_tr, title_canonical = meta

                    topic = session.scalar(
                        select(Topic).where(Topic.stable_id == stable_id)
                    )
                    if topic is None:
                        topic = Topic(
                            id=new_id(),
                            stable_id=stable_id,
                            title_tr=title_tr,
                            title_canonical=title_canonical,
                            summary=f"{title_tr} ({title_canonical})",
                            confidence=min(1.0, 0.5 + 0.1 * len(refs)),
                            review_status="unreviewed",
                            enrichment_status="none",
                            source_order=order,
                            learning_order=None,
                        )
                        session.add(topic)
                        session.flush()
                        session.add(
                            Concept(
                                id=new_id(),
                                name=title_tr,
                                kind="abap_keyword",
                                canonical_term=title_canonical,
                            )
                        )
                        topics_created += 1
                        order += 1

                    for video_id, start_ms, end_ms, uri in refs:
                        ref = SourceReference(
                            id=new_id(),
                            video_id=video_id,
                            start_ms=start_ms,
                            end_ms=end_ms,
                            layer=EvidenceLayer.INFERRED.value,
                            ref_type=SourceRefType.TRANSCRIPT.value
                            if uri is None
                            else SourceRefType.FRAME.value,
                            uri=uri,
                            note=stable_id,
                        )
                        session.add(ref)
                        session.flush()
                        session.add(
                            TopicOccurrence(
                                id=new_id(),
                                topic_id=topic.id,
                                video_id=video_id,
                                source_ref_id=ref.id,
                                confidence=0.8,
                            )
                        )
                        occurrences += 1

                complete_job(
                    session,
                    job,
                    status=ProcessingStatus.COMPLETED,
                    metrics={
                        "topics_created": topics_created,
                        "occurrences": occurrences,
                    },
                    duration_ms=int((time.perf_counter() - started) * 1000),
                )
                session.commit()
                return [
                    StageResult(
                        stage=PipelineStage.DISCOVER_TOPICS.value,
                        status="completed",
                        job_id=job.id,
                        fingerprint=fp,
                        metrics={
                            "topics_created": topics_created,
                            "occurrences": occurrences,
                        },
                    )
                ]
            except Exception as exc:  # noqa: BLE001
                complete_job(
                    session,
                    job,
                    status=ProcessingStatus.FAILED,
                    error=str(exc),
                    duration_ms=int((time.perf_counter() - started) * 1000),
                )
                session.commit()
                logger.exception("discover-topics failed")
                return [
                    StageResult(
                        stage=PipelineStage.DISCOVER_TOPICS.value,
                        status="failed",
                        job_id=job.id,
                        fingerprint=fp,
                        error=str(exc),
                    )
                ]

    def _collect_hits(
        self,
        session: Session,
        video_ids: list[UUID],
    ) -> dict[str, list[tuple[UUID, int, int, str | None]]]:
        hits: dict[str, list[tuple[UUID, int, int, str | None]]] = defaultdict(list)
        if not video_ids:
            return hits
        segments = session.scalars(
            select(TranscriptSegment).where(TranscriptSegment.video_id.in_(video_ids))
        ).all()
        for seg in segments:
            text = seg.text_normalized or seg.text_raw
            for match in KEYWORD_RE.finditer(text):
                key = match.group(1).upper()
                if key.startswith("INTERNAL"):
                    key = "INTERNAL TABLE"
                hits[key].append((seg.video_id, seg.start_ms, seg.end_ms, None))
        visuals = session.scalars(
            select(VisualEvidence).where(VisualEvidence.video_id.in_(video_ids))
        ).all()
        for vis in visuals:
            text = vis.ocr_text or ""
            for match in KEYWORD_RE.finditer(text):
                key = match.group(1).upper()
                if key.startswith("INTERNAL"):
                    key = "INTERNAL TABLE"
                hits[key].append(
                    (vis.video_id, vis.timestamp_ms, vis.timestamp_ms, vis.frame_path)
                )
        return hits
