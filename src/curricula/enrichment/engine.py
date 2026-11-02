"""Draft content enrichment with provenance (never published automatically)."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from curricula.config import Settings
from curricula.db.models import (
    Assessment,
    ContentBlock,
    EnrichmentTask,
    KnowledgeGap,
    LearningObjective,
    Topic,
)
from curricula.db.repositories.artifacts import next_artifact_version
from curricula.domain.enums import (
    ContentKind,
    EnrichmentStatus,
    EvidenceLayer,
    PipelineStage,
    ProcessingStatus,
    ReviewStatus,
)
from curricula.domain.ids import new_id
from curricula.domain.protocols import LLMClient
from curricula.llm.client import resolve_llm_client
from curricula.pipeline.contracts import StageResult
from curricula.pipeline.jobs import complete_job, fingerprint_parts, get_or_create_job

logger = logging.getLogger(__name__)


class EnrichRequest:
    def __init__(
        self,
        *,
        topic_id: UUID | None = None,
        kinds: list[str] | None = None,
        force: bool = False,
        dry_run: bool = False,
    ) -> None:
        self.topic_id = topic_id
        self.kinds = kinds or [
            ContentKind.EXPLANATION.value,
            ContentKind.EXAMPLE.value,
            ContentKind.EXERCISE.value,
            ContentKind.QUIZ.value,
            ContentKind.GLOSSARY.value,
            ContentKind.OBJECTIVE.value,
        ]
        self.force = force
        self.dry_run = dry_run


class EnrichService:
    def __init__(
        self,
        settings: Settings,
        session_factory: sessionmaker[Session],
        llm: LLMClient | None = None,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.llm: LLMClient = llm or resolve_llm_client(
            settings.enrichment.llm_adapter,
            default_model=settings.enrichment.default_model,
        )

    def run(self, req: EnrichRequest) -> list[StageResult]:
        started = time.perf_counter()
        with self.session_factory() as session:
            topics = self._topics(session, req.topic_id)
            topic_keys = sorted(str(t.id) for t in topics)
            fp = fingerprint_parts(
                *topic_keys,
                ",".join(sorted(req.kinds)),
                self.settings.enrichment.default_model,
                "enrich-1",
            )
            job, should_skip = get_or_create_job(
                session,
                stage=PipelineStage.ENRICH.value,
                fingerprint=fp,
                model_name=self.settings.enrichment.default_model,
                model_version="fake-1",
                force=req.force,
            )
            if should_skip and not req.dry_run:
                session.commit()
                return [
                    StageResult(
                        stage=PipelineStage.ENRICH.value,
                        status="skipped",
                        job_id=job.id,
                        fingerprint=fp,
                        metrics={"reason": "fingerprint_match"},
                    )
                ]
            try:
                created_blocks = 0
                created_assessments = 0
                created_objectives = 0
                artifact_paths: list[str] = []
                for topic in topics:
                    gaps = list(
                        session.scalars(
                            select(KnowledgeGap).where(KnowledgeGap.topic_id == topic.id)
                        ).all()
                    )
                    for kind in req.kinds:
                        if req.dry_run:
                            continue
                        prompt = (
                            f"Konu: {topic.title_tr} ({topic.title_canonical}). "
                            f"Tür: {kind}. Türkçe açıkla; ABAP terimlerini koru."
                        )
                        body = self.llm.complete(
                            prompt, model=self.settings.enrichment.default_model
                        )
                        provenance = {
                            "generator": type(self.llm).__name__,
                            "model": self.settings.enrichment.default_model,
                            "adapter": self.settings.enrichment.llm_adapter,
                            "layer": EvidenceLayer.GENERATED.value,
                            "source_video_claim": False,
                            "prompt_excerpt": prompt[:200],
                        }
                        if kind == ContentKind.QUIZ.value:
                            assessment_id = new_id()
                            session.add(
                                Assessment(
                                    id=assessment_id,
                                    topic_id=topic.id,
                                    kind="quiz",
                                    payload_json=json.dumps(
                                        {
                                            "question": (
                                                f"{topic.title_canonical} ne işe yarar?"
                                            ),
                                            "answer": body,
                                            "is_generated": True,
                                        },
                                        ensure_ascii=False,
                                    ),
                                    review_status=ReviewStatus.DRAFT.value,
                                    is_generated=True,
                                )
                            )
                            payload = (
                                self.settings.paths.exports_dir
                                / "versions"
                                / f"assessment_{assessment_id}.json"
                            )
                            payload.parent.mkdir(parents=True, exist_ok=True)
                            payload.write_text(
                                json.dumps(provenance, ensure_ascii=False, indent=2),
                                encoding="utf-8",
                            )
                            next_artifact_version(
                                session,
                                entity_type="assessment",
                                entity_id=str(assessment_id),
                                payload_path=str(payload),
                            )
                            artifact_paths.append(str(payload))
                            created_assessments += 1
                        elif kind == ContentKind.OBJECTIVE.value:
                            session.add(
                                LearningObjective(
                                    id=new_id(),
                                    topic_id=topic.id,
                                    text_tr=body.splitlines()[0][:500],
                                    bloom_level="understand",
                                    review_status=ReviewStatus.DRAFT.value,
                                )
                            )
                            created_objectives += 1
                        else:
                            existing = session.scalar(
                                select(ContentBlock).where(
                                    ContentBlock.topic_id == topic.id,
                                    ContentBlock.kind == kind,
                                )
                            )
                            version = 1
                            parent_version_id = None
                            block_id = new_id()
                            if existing is not None:
                                version = existing.version + 1
                                existing.review_status = ReviewStatus.DRAFT.value
                                existing.enrichment_status = EnrichmentStatus.DRAFT.value
                                existing.body_md = body
                                existing.provenance_json = json.dumps(
                                    provenance, ensure_ascii=False
                                )
                                existing.version = version
                                block_id = existing.id
                            else:
                                session.add(
                                    ContentBlock(
                                        id=block_id,
                                        topic_id=topic.id,
                                        kind=kind,
                                        body_md=body,
                                        layer=EvidenceLayer.GENERATED.value,
                                        provenance_json=json.dumps(
                                            provenance, ensure_ascii=False
                                        ),
                                        review_status=ReviewStatus.DRAFT.value,
                                        enrichment_status=EnrichmentStatus.DRAFT.value,
                                        version=version,
                                    )
                                )
                            payload = (
                                self.settings.paths.exports_dir
                                / "versions"
                                / f"content_{block_id}_v{version}.md"
                            )
                            payload.parent.mkdir(parents=True, exist_ok=True)
                            payload.write_text(body, encoding="utf-8")
                            next_artifact_version(
                                session,
                                entity_type="content_block",
                                entity_id=str(block_id),
                                payload_path=str(payload),
                                parent_version_id=parent_version_id,
                            )
                            artifact_paths.append(str(payload))
                            created_blocks += 1
                        gap = next((g for g in gaps if g.dimension == kind), None)
                        session.add(
                            EnrichmentTask(
                                id=new_id(),
                                gap_id=gap.id if gap else None,
                                topic_id=topic.id,
                                task_type=kind,
                                status="draft",
                                assigned_model=self.settings.enrichment.default_model,
                            )
                        )
                    topic.enrichment_status = EnrichmentStatus.DRAFT.value

                complete_job(
                    session,
                    job,
                    status=ProcessingStatus.COMPLETED,
                    artifacts=artifact_paths,
                    metrics={
                        "content_blocks": created_blocks,
                        "assessments": created_assessments,
                        "objectives": created_objectives,
                        "dry_run": req.dry_run,
                    },
                    duration_ms=int((time.perf_counter() - started) * 1000),
                    cost_usd=0.0,
                )
                session.commit()
                return [
                    StageResult(
                        stage=PipelineStage.ENRICH.value,
                        status="completed",
                        job_id=job.id,
                        fingerprint=fp,
                        artifacts=[Path(p) for p in artifact_paths],
                        metrics={
                            "content_blocks": created_blocks,
                            "assessments": created_assessments,
                            "objectives": created_objectives,
                            "dry_run": req.dry_run,
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
                logger.exception("enrich failed")
                return [
                    StageResult(
                        stage=PipelineStage.ENRICH.value,
                        status="failed",
                        job_id=job.id,
                        fingerprint=fp,
                        error=str(exc),
                    )
                ]

    def _topics(self, session: Session, topic_id: UUID | None) -> list[Topic]:
        if topic_id is not None:
            topic = session.get(Topic, topic_id)
            return [topic] if topic else []
        return list(session.scalars(select(Topic)).all())
