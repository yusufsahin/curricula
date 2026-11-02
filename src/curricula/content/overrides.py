"""Human content overrides with versioning and provenance."""

from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from curricula.config import Settings
from curricula.db.models import ContentBlock, Topic
from curricula.db.repositories.artifacts import next_artifact_version
from curricula.domain.enums import EnrichmentStatus, EvidenceLayer, ReviewStatus
from curricula.domain.ids import new_id


class ContentError(ValueError):
    pass


@dataclass(frozen=True)
class ContentView:
    id: UUID
    topic_stable_id: str
    kind: str
    version: int
    review_status: str
    layer: str
    preview: str


class ContentService:
    def __init__(
        self,
        settings: Settings,
        session_factory: sessionmaker[Session],
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory

    def list_blocks(
        self,
        *,
        topic_stable_id: str | None = None,
        kind: str | None = None,
        status: str | None = None,
    ) -> list[ContentView]:
        with self.session_factory() as session:
            topics = {t.id: t.stable_id for t in session.scalars(select(Topic)).all()}
            stmt = select(ContentBlock)
            if kind:
                stmt = stmt.where(ContentBlock.kind == kind)
            if status:
                stmt = stmt.where(ContentBlock.review_status == status)
            rows = list(session.scalars(stmt).all())
            if topic_stable_id:
                wanted = {
                    tid for tid, sid in topics.items() if sid == topic_stable_id
                }
                rows = [r for r in rows if r.topic_id in wanted]
            return [
                ContentView(
                    id=r.id,
                    topic_stable_id=topics.get(r.topic_id, "?"),
                    kind=r.kind,
                    version=r.version,
                    review_status=r.review_status,
                    layer=r.layer,
                    preview=(r.body_md[:80] + "…") if len(r.body_md) > 80 else r.body_md,
                )
                for r in rows
            ]

    def override(
        self,
        *,
        block_id: UUID,
        body_md: str,
        reviewer: str,
        mark_approved: bool = True,
    ) -> ContentView:
        with self.session_factory() as session:
            block = session.get(ContentBlock, block_id)
            if block is None:
                raise ContentError(f"Content block not found: {block_id}")
            topic = session.get(Topic, block.topic_id)
            if topic is None:
                raise ContentError("Topic missing for content block")

            provenance = {}
            if block.provenance_json:
                try:
                    provenance = json.loads(block.provenance_json)
                except json.JSONDecodeError:
                    provenance = {"raw_provenance": block.provenance_json}
            provenance.update(
                {
                    "human_override": True,
                    "overridden_by": reviewer,
                    "previous_layer": block.layer,
                    "previous_version": block.version,
                    "source_video_claim": False,
                }
            )

            block.body_md = body_md
            block.version = block.version + 1
            block.layer = EvidenceLayer.GENERATED.value
            block.provenance_json = json.dumps(provenance, ensure_ascii=False)
            block.review_status = (
                ReviewStatus.APPROVED.value
                if mark_approved
                else ReviewStatus.DRAFT.value
            )
            block.enrichment_status = (
                EnrichmentStatus.APPROVED.value
                if mark_approved
                else EnrichmentStatus.DRAFT.value
            )

            versions_dir = self.settings.paths.exports_dir / "versions"
            versions_dir.mkdir(parents=True, exist_ok=True)
            payload = versions_dir / f"content_{block.id}_v{block.version}.md"
            payload.write_text(body_md, encoding="utf-8")
            next_artifact_version(
                session,
                entity_type="content_block",
                entity_id=str(block.id),
                payload_path=str(payload),
                created_by=f"user:{reviewer}",
            )
            session.commit()
            return ContentView(
                id=block.id,
                topic_stable_id=topic.stable_id,
                kind=block.kind,
                version=block.version,
                review_status=block.review_status,
                layer=block.layer,
                preview=(body_md[:80] + "…") if len(body_md) > 80 else body_md,
            )

    def create_manual(
        self,
        *,
        topic_stable_id: str,
        kind: str,
        body_md: str,
        reviewer: str,
    ) -> ContentView:
        with self.session_factory() as session:
            topic = session.scalar(
                select(Topic).where(Topic.stable_id == topic_stable_id)
            )
            if topic is None:
                raise ContentError(f"Topic not found: {topic_stable_id}")
            block_id = new_id()
            provenance = {
                "human_override": True,
                "created_by": reviewer,
                "layer": EvidenceLayer.GENERATED.value,
                "source_video_claim": False,
                "manual": True,
            }
            block = ContentBlock(
                id=block_id,
                topic_id=topic.id,
                kind=kind,
                body_md=body_md,
                layer=EvidenceLayer.GENERATED.value,
                provenance_json=json.dumps(provenance, ensure_ascii=False),
                review_status=ReviewStatus.APPROVED.value,
                enrichment_status=EnrichmentStatus.APPROVED.value,
                version=1,
            )
            session.add(block)
            versions_dir = self.settings.paths.exports_dir / "versions"
            versions_dir.mkdir(parents=True, exist_ok=True)
            payload = versions_dir / f"content_{block_id}_v1.md"
            payload.write_text(body_md, encoding="utf-8")
            next_artifact_version(
                session,
                entity_type="content_block",
                entity_id=str(block_id),
                payload_path=str(payload),
                created_by=f"user:{reviewer}",
            )
            session.commit()
            return ContentView(
                id=block_id,
                topic_stable_id=topic.stable_id,
                kind=kind,
                version=1,
                review_status=block.review_status,
                layer=block.layer,
                preview=(body_md[:80] + "…") if len(body_md) > 80 else body_md,
            )
