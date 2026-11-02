"""Curriculum mapping with NetworkX prerequisite detection."""

from __future__ import annotations

import logging
import time

import networkx as nx
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from curricula.config import Settings
from curricula.db.models import Topic, TopicRelationship
from curricula.domain.enums import PipelineStage, ProcessingStatus, RelationshipType
from curricula.domain.ids import new_id
from curricula.pipeline.contracts import StageResult
from curricula.pipeline.jobs import complete_job, fingerprint_parts, get_or_create_job

logger = logging.getLogger(__name__)

# Canonical learning prerequisites (to_topic requires from_topic first)
PREREQ_RULES: list[tuple[str, str]] = [
    ("abap-data", "abap-select"),
    ("abap-types", "abap-data"),
    ("abap-data", "abap-internal-tables"),
    ("abap-internal-tables", "abap-loop"),
    ("abap-form", "abap-method"),
    ("abap-class", "abap-method"),
    ("abap-select", "abap-write"),
]


class MapCurriculumRequest:
    def __init__(self, *, force: bool = False, approve_auto: bool = False) -> None:
        self.force = force
        self.approve_auto = approve_auto


class MapCurriculumService:
    def __init__(
        self,
        settings: Settings,
        session_factory: sessionmaker[Session],
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory

    def run(self, req: MapCurriculumRequest) -> list[StageResult]:
        started = time.perf_counter()
        with self.session_factory() as session:
            topics = list(session.scalars(select(Topic)).all())
            stable_ids = sorted(t.stable_id for t in topics)
            fp = fingerprint_parts(*stable_ids, "mapper-1")
            job, should_skip = get_or_create_job(
                session,
                stage=PipelineStage.MAP_CURRICULUM.value,
                fingerprint=fp,
                model_name="rule_mapper",
                model_version="1",
                force=req.force,
            )
            if should_skip:
                session.commit()
                return [
                    StageResult(
                        stage=PipelineStage.MAP_CURRICULUM.value,
                        status="skipped",
                        job_id=job.id,
                        fingerprint=fp,
                        metrics={"reason": "fingerprint_match"},
                    )
                ]
            try:
                by_stable = {t.stable_id: t for t in topics}
                created = 0
                for src, dst in PREREQ_RULES:
                    if src not in by_stable or dst not in by_stable:
                        continue
                    existing = session.scalar(
                        select(TopicRelationship).where(
                            TopicRelationship.from_topic_id == by_stable[src].id,
                            TopicRelationship.to_topic_id == by_stable[dst].id,
                            TopicRelationship.type
                            == RelationshipType.PREREQUISITE.value,
                        )
                    )
                    if existing is not None:
                        continue
                    session.add(
                        TopicRelationship(
                            id=new_id(),
                            from_topic_id=by_stable[src].id,
                            to_topic_id=by_stable[dst].id,
                            type=RelationshipType.PREREQUISITE.value,
                            confidence=0.75,
                            approved=req.approve_auto,
                            source="auto",
                        )
                    )
                    created += 1

                # Related edges between co-present topics without prereq
                topic_list = list(by_stable.values())
                for i, left in enumerate(topic_list):
                    for right in topic_list[i + 1 :]:
                        if self._has_prereq_pair(left.stable_id, right.stable_id):
                            continue
                        existing = session.scalar(
                            select(TopicRelationship).where(
                                TopicRelationship.from_topic_id == left.id,
                                TopicRelationship.to_topic_id == right.id,
                                TopicRelationship.type
                                == RelationshipType.RELATED.value,
                            )
                        )
                        if existing is not None:
                            continue
                        session.add(
                            TopicRelationship(
                                id=new_id(),
                                from_topic_id=left.id,
                                to_topic_id=right.id,
                                type=RelationshipType.RELATED.value,
                                confidence=0.4,
                                approved=False,
                                source="auto",
                            )
                        )
                        created += 1

                session.flush()
                graph = self.build_graph(session)
                cycles = list(nx.simple_cycles(graph)) if graph.number_of_nodes() else []
                learning_order = self.topological_learning_order(session)
                for idx, stable_id in enumerate(learning_order):
                    topic = by_stable.get(stable_id)
                    if topic is not None:
                        topic.learning_order = idx

                complete_job(
                    session,
                    job,
                    status=ProcessingStatus.COMPLETED,
                    metrics={
                        "relationships_created": created,
                        "cycles": len(cycles),
                        "learning_order": learning_order,
                    },
                    duration_ms=int((time.perf_counter() - started) * 1000),
                )
                session.commit()
                return [
                    StageResult(
                        stage=PipelineStage.MAP_CURRICULUM.value,
                        status="completed",
                        job_id=job.id,
                        fingerprint=fp,
                        metrics={
                            "relationships_created": created,
                            "cycles": len(cycles),
                            "learning_order": learning_order,
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
                logger.exception("map-curriculum failed")
                return [
                    StageResult(
                        stage=PipelineStage.MAP_CURRICULUM.value,
                        status="failed",
                        job_id=job.id,
                        fingerprint=fp,
                        error=str(exc),
                    )
                ]

    def _has_prereq_pair(self, a: str, b: str) -> bool:
        return (a, b) in PREREQ_RULES or (b, a) in PREREQ_RULES

    def build_graph(self, session: Session) -> nx.DiGraph:
        graph: nx.DiGraph = nx.DiGraph()
        topics = list(session.scalars(select(Topic)).all())
        id_to_stable = {t.id: t.stable_id for t in topics}
        for topic in topics:
            graph.add_node(topic.stable_id)
        rels = session.scalars(
            select(TopicRelationship).where(
                TopicRelationship.type == RelationshipType.PREREQUISITE.value
            )
        ).all()
        for rel in rels:
            src = id_to_stable.get(rel.from_topic_id)
            dst = id_to_stable.get(rel.to_topic_id)
            if src and dst:
                graph.add_edge(src, dst)
        return graph

    def topological_learning_order(self, session: Session) -> list[str]:
        graph = self.build_graph(session)
        if graph.number_of_nodes() == 0:
            return []
        try:
            return list(nx.topological_sort(graph))
        except nx.NetworkXUnfeasible:
            # Fall back to source_order when cycles exist
            topics = list(session.scalars(select(Topic)).all())
            topics.sort(key=lambda t: (t.source_order is None, t.source_order or 0))
            return [t.stable_id for t in topics]

    def detect_cycles(self, session: Session) -> list[list[str]]:
        graph = self.build_graph(session)
        return [list(c) for c in nx.simple_cycles(graph)]
