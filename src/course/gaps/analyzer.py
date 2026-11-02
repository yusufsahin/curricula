"""Knowledge gap analysis against a reference curriculum."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from course.config import Settings
from course.db.models import Assessment, ContentBlock, KnowledgeGap, Topic, TopicOccurrence
from course.domain.enums import GapClass, PipelineStage, ProcessingStatus
from course.domain.ids import new_id
from course.pipeline.contracts import StageResult
from course.pipeline.jobs import complete_job, fingerprint_parts, get_or_create_job

logger = logging.getLogger(__name__)


class AnalyzeGapsRequest:
    def __init__(
        self,
        *,
        reference_path: Path,
        force: bool = False,
    ) -> None:
        self.reference_path = reference_path
        self.force = force


class AnalyzeGapsService:
    def __init__(
        self,
        settings: Settings,
        session_factory: sessionmaker[Session],
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory

    def run(self, req: AnalyzeGapsRequest) -> list[StageResult]:
        started = time.perf_counter()
        reference = json.loads(req.reference_path.read_text(encoding="utf-8"))
        ref_topics = reference.get("topics", [])
        fp = fingerprint_parts(
            req.reference_path.read_text(encoding="utf-8"),
            "gap-analyzer-1",
        )
        with self.session_factory() as session:
            job, should_skip = get_or_create_job(
                session,
                stage=PipelineStage.ANALYZE_GAPS.value,
                fingerprint=fp,
                model_name="gap_analyzer",
                model_version="1",
                force=req.force,
            )
            if should_skip:
                session.commit()
                return [
                    StageResult(
                        stage=PipelineStage.ANALYZE_GAPS.value,
                        status="skipped",
                        job_id=job.id,
                        fingerprint=fp,
                        metrics={"reason": "fingerprint_match"},
                    )
                ]
            try:
                # Clear previous gaps for determinism on force re-run
                for old in session.scalars(select(KnowledgeGap)).all():
                    session.delete(old)
                session.flush()

                created = 0
                for item in ref_topics:
                    stable_id = item["stable_id"]
                    dims = item.get("required_dimensions", [])
                    topic = session.scalar(
                        select(Topic).where(Topic.stable_id == stable_id)
                    )
                    if topic is None:
                        # Do NOT claim absent from source videos — mark uncertain reference miss
                        # Create a placeholder topic only as inferred gap anchor
                        topic = Topic(
                            id=new_id(),
                            stable_id=stable_id,
                            title_tr=item.get("title_tr", stable_id),
                            title_canonical=item.get("title_canonical"),
                            summary="Referans müfredatta var; kaynak videolarda doğrulanmadı.",
                            confidence=0.2,
                            review_status="unreviewed",
                            enrichment_status="none",
                        )
                        session.add(topic)
                        session.flush()
                        for dim in dims:
                            session.add(
                                KnowledgeGap(
                                    id=new_id(),
                                    topic_id=topic.id,
                                    gap_class=GapClass.UNCERTAIN.value,
                                    dimension=dim,
                                    evidence_note=(
                                        "Referans konu kaynak materyalde görülmedi; "
                                        "yokluğu kesin iddia edilmiyor."
                                    ),
                                    priority=10,
                                )
                            )
                            created += 1
                        continue

                    occ_count = session.scalar(
                        select(func.count())
                        .select_from(TopicOccurrence)
                        .where(TopicOccurrence.topic_id == topic.id)
                    ) or 0
                    for dim in dims:
                        gap_class, note, priority = self._classify_dimension(
                            session, topic.id, dim, int(occ_count)
                        )
                        session.add(
                            KnowledgeGap(
                                id=new_id(),
                                topic_id=topic.id,
                                gap_class=gap_class.value,
                                dimension=dim,
                                evidence_note=note,
                                priority=priority,
                            )
                        )
                        created += 1

                complete_job(
                    session,
                    job,
                    status=ProcessingStatus.COMPLETED,
                    metrics={"gaps": created},
                    duration_ms=int((time.perf_counter() - started) * 1000),
                )
                session.commit()
                return [
                    StageResult(
                        stage=PipelineStage.ANALYZE_GAPS.value,
                        status="completed",
                        job_id=job.id,
                        fingerprint=fp,
                        metrics={"gaps": created},
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
                logger.exception("analyze-gaps failed")
                return [
                    StageResult(
                        stage=PipelineStage.ANALYZE_GAPS.value,
                        status="failed",
                        job_id=job.id,
                        fingerprint=fp,
                        error=str(exc),
                    )
                ]

    def _classify_dimension(
        self,
        session: Session,
        topic_id: object,
        dimension: str,
        occ_count: int,
    ) -> tuple[GapClass, str, int]:
        if dimension == "explanation":
            blocks = session.scalar(
                select(func.count())
                .select_from(ContentBlock)
                .where(
                    ContentBlock.topic_id == topic_id,
                    ContentBlock.kind == "explanation",
                )
            ) or 0
            if blocks > 0:
                return GapClass.COMPLETE, "Açıklama içeriği mevcut.", 0
            if occ_count > 0:
                return (
                    GapClass.INSUFFICIENT,
                    "Konu kaynakta geçiyor ancak yapılandırılmış açıklama yok.",
                    5,
                )
            return GapClass.UNCERTAIN, "Açıklama için yeterli kanıt yok.", 7

        if dimension == "example":
            blocks = session.scalar(
                select(func.count())
                .select_from(ContentBlock)
                .where(
                    ContentBlock.topic_id == topic_id,
                    ContentBlock.kind == "example",
                )
            ) or 0
            if blocks > 0:
                return GapClass.COMPLETE, "Örnek mevcut.", 0
            if occ_count > 0:
                return GapClass.INSUFFICIENT, "Örnek eksik veya yetersiz.", 6
            return GapClass.UNCERTAIN, "Örnek yokluğu kesinleştirilmedi.", 7

        if dimension == "exercise":
            blocks = session.scalar(
                select(func.count())
                .select_from(ContentBlock)
                .where(
                    ContentBlock.topic_id == topic_id,
                    ContentBlock.kind == "exercise",
                )
            ) or 0
            if blocks > 0:
                return GapClass.COMPLETE, "Alıştırma mevcut.", 0
            return GapClass.MISSING, "Alıştırma içeriği bulunamadı.", 8

        if dimension == "assessment":
            assessments = session.scalar(
                select(func.count())
                .select_from(Assessment)
                .where(Assessment.topic_id == topic_id)
            ) or 0
            if assessments > 0:
                return GapClass.COMPLETE, "Değerlendirme mevcut.", 0
            return GapClass.MISSING, "Değerlendirme bankası boş.", 9

        return GapClass.UNCERTAIN, f"Bilinmeyen boyut: {dimension}", 1
