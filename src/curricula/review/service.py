"""Human review decisions and publish gate."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from curricula.config import Settings
from curricula.db.models import Assessment, ContentBlock, ReviewDecision
from curricula.domain.enums import EnrichmentStatus, ReviewStatus
from curricula.domain.ids import new_id

Reviewable = ContentBlock | Assessment


class PublishWithoutApprovalError(PermissionError):
    pass


class ReviewService:
    def __init__(
        self,
        settings: Settings,
        session_factory: sessionmaker[Session],
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory

    def list_pending(self) -> list[dict[str, str]]:
        with self.session_factory() as session:
            rows: list[dict[str, str]] = []
            for block in session.scalars(
                select(ContentBlock).where(
                    ContentBlock.review_status.in_(
                        [ReviewStatus.DRAFT.value, ReviewStatus.IN_REVIEW.value]
                    )
                )
            ).all():
                rows.append(
                    {
                        "entity_type": "content_block",
                        "entity_id": str(block.id),
                        "kind": block.kind,
                        "status": block.review_status,
                    }
                )
            for assessment in session.scalars(
                select(Assessment).where(
                    Assessment.review_status.in_(
                        [ReviewStatus.DRAFT.value, ReviewStatus.IN_REVIEW.value]
                    )
                )
            ).all():
                rows.append(
                    {
                        "entity_type": "assessment",
                        "entity_id": str(assessment.id),
                        "kind": assessment.kind,
                        "status": assessment.review_status,
                    }
                )
            return rows

    def decide(
        self,
        *,
        entity_type: str,
        entity_id: UUID,
        decision: str,
        reviewer: str,
        comment: str | None = None,
    ) -> None:
        with self.session_factory() as session:
            entity = self._load_entity(session, entity_type, entity_id)
            if decision == "approve":
                entity.review_status = ReviewStatus.APPROVED.value
                if isinstance(entity, ContentBlock):
                    entity.enrichment_status = EnrichmentStatus.APPROVED.value
            elif decision == "reject":
                entity.review_status = ReviewStatus.REJECTED.value
            elif decision == "publish":
                self._publish(session, entity_type, entity)
            else:
                raise ValueError(f"Unknown decision: {decision}")

            session.add(
                ReviewDecision(
                    id=new_id(),
                    entity_type=entity_type,
                    entity_id=str(entity_id),
                    decision=decision,
                    reviewer=reviewer,
                    comment=comment,
                    decided_at=datetime.now(UTC),
                )
            )
            session.commit()

    def _load_entity(
        self,
        session: Session,
        entity_type: str,
        entity_id: UUID,
    ) -> Reviewable:
        if entity_type == "content_block":
            block = session.get(ContentBlock, entity_id)
            if block is None:
                raise KeyError(entity_id)
            return block
        if entity_type == "assessment":
            assessment = session.get(Assessment, entity_id)
            if assessment is None:
                raise KeyError(entity_id)
            return assessment
        raise ValueError(f"Unknown entity_type: {entity_type}")

    def _publish(
        self,
        session: Session,
        entity_type: str,
        entity: Reviewable,
    ) -> None:
        require = self.settings.enrichment.require_review_for_publish
        status = entity.review_status
        entity_id = str(entity.id)
        if require and status != ReviewStatus.APPROVED.value:
            approved = session.scalar(
                select(ReviewDecision).where(
                    ReviewDecision.entity_type == entity_type,
                    ReviewDecision.entity_id == entity_id,
                    ReviewDecision.decision == "approve",
                )
            )
            if approved is None:
                raise PublishWithoutApprovalError(
                    "Cannot publish without an approve ReviewDecision."
                )
        entity.review_status = ReviewStatus.PUBLISHED.value
        if isinstance(entity, ContentBlock):
            entity.enrichment_status = EnrichmentStatus.PUBLISHED.value
