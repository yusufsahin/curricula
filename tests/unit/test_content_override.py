from __future__ import annotations

from course.content.overrides import ContentService
from course.db.models import ContentBlock, Topic
from course.domain.ids import new_id


def test_human_override_versions(settings, session_factory) -> None:
    with session_factory() as session:
        topic = Topic(
            id=new_id(),
            stable_id="abap-select",
            title_tr="SELECT ifadesi",
            title_canonical="SELECT",
            review_status="unreviewed",
            enrichment_status="draft",
        )
        block_id = new_id()
        session.add(topic)
        session.flush()
        session.add(
            ContentBlock(
                id=block_id,
                topic_id=topic.id,
                kind="explanation",
                body_md="AI draft",
                layer="generated",
                provenance_json='{"source_video_claim": false}',
                review_status="draft",
                enrichment_status="draft",
                version=1,
            )
        )
        session.commit()

    service = ContentService(settings, session_factory)
    view = service.override(
        block_id=block_id,
        body_md="İnsan tarafından düzeltilmiş SELECT açıklaması.",
        reviewer="yusuf",
        mark_approved=True,
    )
    assert view.version == 2
    assert view.review_status == "approved"

    rows = service.list_blocks(topic_stable_id="abap-select")
    assert len(rows) == 1
    assert rows[0].version == 2
