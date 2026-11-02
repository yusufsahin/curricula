"""Editable topic relationship operations."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import networkx as nx
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from course.db.models import Topic, TopicRelationship
from course.domain.enums import RelationshipType
from course.domain.ids import new_id


class RelationError(ValueError):
    pass


@dataclass(frozen=True)
class RelationView:
    id: UUID
    from_stable_id: str
    to_stable_id: str
    type: str
    approved: bool
    source: str
    confidence: float | None


class RelationsService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def list_relations(
        self,
        *,
        rel_type: str | None = None,
        approved: bool | None = None,
    ) -> list[RelationView]:
        with self.session_factory() as session:
            topics = {t.id: t.stable_id for t in session.scalars(select(Topic)).all()}
            stmt = select(TopicRelationship)
            if rel_type:
                stmt = stmt.where(TopicRelationship.type == rel_type)
            if approved is not None:
                stmt = stmt.where(TopicRelationship.approved.is_(approved))
            rows = session.scalars(stmt).all()
            return [
                RelationView(
                    id=r.id,
                    from_stable_id=topics.get(r.from_topic_id, "?"),
                    to_stable_id=topics.get(r.to_topic_id, "?"),
                    type=r.type,
                    approved=r.approved,
                    source=r.source,
                    confidence=r.confidence,
                )
                for r in rows
            ]

    def add_relation(
        self,
        *,
        from_stable_id: str,
        to_stable_id: str,
        rel_type: str,
        approved: bool = True,
        confidence: float = 1.0,
    ) -> RelationView:
        try:
            RelationshipType(rel_type)
        except ValueError as exc:
            raise RelationError(f"Unknown relationship type: {rel_type}") from exc
        if from_stable_id == to_stable_id:
            raise RelationError("Self-relations are not allowed")

        with self.session_factory() as session:
            src = session.scalar(select(Topic).where(Topic.stable_id == from_stable_id))
            dst = session.scalar(select(Topic).where(Topic.stable_id == to_stable_id))
            if src is None or dst is None:
                raise RelationError("Both topics must exist")

            existing = session.scalar(
                select(TopicRelationship).where(
                    TopicRelationship.from_topic_id == src.id,
                    TopicRelationship.to_topic_id == dst.id,
                    TopicRelationship.type == rel_type,
                )
            )
            if existing is not None:
                raise RelationError("Relationship already exists")

            if rel_type == RelationshipType.PREREQUISITE.value:
                self._assert_no_cycle(session, src.stable_id, dst.stable_id)

            row = TopicRelationship(
                id=new_id(),
                from_topic_id=src.id,
                to_topic_id=dst.id,
                type=rel_type,
                confidence=confidence,
                approved=approved,
                source="manual",
            )
            session.add(row)
            session.commit()
            return RelationView(
                id=row.id,
                from_stable_id=from_stable_id,
                to_stable_id=to_stable_id,
                type=rel_type,
                approved=approved,
                source="manual",
                confidence=confidence,
            )

    def approve(self, relation_id: UUID, *, approved: bool = True) -> None:
        with self.session_factory() as session:
            row = session.get(TopicRelationship, relation_id)
            if row is None:
                raise RelationError(f"Relation not found: {relation_id}")
            row.approved = approved
            session.commit()

    def delete(self, relation_id: UUID) -> None:
        with self.session_factory() as session:
            row = session.get(TopicRelationship, relation_id)
            if row is None:
                raise RelationError(f"Relation not found: {relation_id}")
            session.delete(row)
            session.commit()

    def _assert_no_cycle(
        self,
        session: Session,
        from_stable: str,
        to_stable: str,
    ) -> None:
        topics = list(session.scalars(select(Topic)).all())
        id_to_stable = {t.id: t.stable_id for t in topics}
        graph: nx.DiGraph = nx.DiGraph()
        for topic in topics:
            graph.add_node(topic.stable_id)
        for rel in session.scalars(
            select(TopicRelationship).where(
                TopicRelationship.type == RelationshipType.PREREQUISITE.value
            )
        ).all():
            src = id_to_stable.get(rel.from_topic_id)
            dst = id_to_stable.get(rel.to_topic_id)
            if src and dst:
                graph.add_edge(src, dst)
        graph.add_edge(from_stable, to_stable)
        if list(nx.simple_cycles(graph)):
            raise RelationError(
                f"Adding {from_stable} -> {to_stable} would create a prerequisite cycle"
            )
