from __future__ import annotations

from fastapi.testclient import TestClient

from curricula.api.app import create_app
from curricula.db.models import Topic
from curricula.db.repositories.courses import get_or_create_course
from curricula.domain.ids import new_id


def test_health_and_status(settings, session_factory) -> None:
    app = create_app(settings=settings, session_factory=session_factory)
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    with session_factory() as session:
        course = get_or_create_course(session, "demo", title="Demo")
        session.add(
            Topic(
                id=new_id(),
                stable_id="abap-select",
                title_tr="SELECT ifadesi",
                title_canonical="SELECT",
                review_status="unreviewed",
                enrichment_status="none",
            )
        )
        session.commit()
        assert course.slug == "demo"

    status = client.get("/v1/status")
    assert status.status_code == 200
    body = status.json()
    assert body["courses"] >= 1
    assert body["topics"] >= 1

    courses = client.get("/v1/courses")
    assert courses.status_code == 200
    assert any(c["slug"] == "demo" for c in courses.json())

    topics = client.get("/v1/topics", params={"q": "select"})
    assert topics.status_code == 200
    assert topics.json()[0]["stable_id"] == "abap-select"

    missing = client.get("/v1/topics/does-not-exist")
    assert missing.status_code == 404
