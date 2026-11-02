from __future__ import annotations

import pytest
from sqlalchemy.orm import Session, sessionmaker

from curricula.curriculum.relations import RelationError, RelationsService
from curricula.db.models import Topic
from curricula.domain.ids import new_id


def _topic(session: Session, stable_id: str, title: str) -> Topic:
    topic = Topic(
        id=new_id(),
        stable_id=stable_id,
        title_tr=title,
        title_canonical=stable_id,
        review_status="unreviewed",
        enrichment_status="none",
    )
    session.add(topic)
    session.flush()
    return topic


def test_add_and_reject_cycle(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        _topic(session, "abap-data", "DATA")
        _topic(session, "abap-select", "SELECT")
        session.commit()

    service = RelationsService(session_factory)
    service.add_relation(
        from_stable_id="abap-data",
        to_stable_id="abap-select",
        rel_type="prerequisite",
    )
    with pytest.raises(RelationError, match="cycle"):
        service.add_relation(
            from_stable_id="abap-select",
            to_stable_id="abap-data",
            rel_type="prerequisite",
        )

    rows = service.list_relations()
    assert len(rows) == 1
    service.approve(rows[0].id, approved=False)
    pending = service.list_relations(approved=False)
    assert len(pending) == 1
    service.delete(rows[0].id)
    assert service.list_relations() == []
