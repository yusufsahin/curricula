from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from curricula.curriculum.mapper import MapCurriculumRequest, MapCurriculumService
from curricula.db.models import (
    ContentBlock,
    KnowledgeGap,
    Topic,
    TopicRelationship,
    VisualEvidence,
)
from curricula.domain.enums import ReviewStatus
from curricula.enrichment.engine import EnrichRequest, EnrichService
from curricula.export.engine import ExportRequest, ExportService
from curricula.gaps.analyzer import AnalyzeGapsRequest, AnalyzeGapsService
from curricula.media.ingest import IngestService
from curricula.pipeline.contracts import IngestRequest, TranscribeRequest
from curricula.review.service import PublishWithoutApprovalError, ReviewService
from curricula.topics.discovery import DiscoverTopicsRequest, DiscoverTopicsService
from curricula.transcription.engine import TranscribeService
from curricula.transcription.whisper_adapter import FakeWhisperAdapter
from curricula.visual.extract import ExtractVisualsRequest, ExtractVisualsService


def _seed(settings, session_factory, synthetic_video, media_probe) -> None:
    IngestService(settings, session_factory, probe=media_probe).run(
        IngestRequest(course_slug="demo", video_paths=[synthetic_video])
    )
    TranscribeService(
        settings, session_factory, adapter=FakeWhisperAdapter()
    ).run(TranscribeRequest(course_slug="demo", adapter="fake"))


def test_phase2_visual_extraction(
    settings, session_factory, synthetic_video, media_probe
) -> None:
    _seed(settings, session_factory, synthetic_video, media_probe)
    results = ExtractVisualsService(settings, session_factory).run(
        ExtractVisualsRequest(course_slug="demo", extractor="stub")
    )
    assert results[0].status == "completed"
    with session_factory() as session:
        evidence = list(session.scalars(select(VisualEvidence)).all())
        assert evidence
        assert evidence[0].confidence is not None


def test_phase3_topics_and_map(
    settings, session_factory, synthetic_video, media_probe
) -> None:
    _seed(settings, session_factory, synthetic_video, media_probe)
    ExtractVisualsService(settings, session_factory).run(
        ExtractVisualsRequest(course_slug="demo", extractor="stub")
    )
    DiscoverTopicsService(settings, session_factory).run(
        DiscoverTopicsRequest(course_slug="demo")
    )
    MapCurriculumService(settings, session_factory).run(MapCurriculumRequest())
    with session_factory() as session:
        topics = list(session.scalars(select(Topic)).all())
        assert any(t.stable_id == "abap-select" for t in topics)
        assert any(t.stable_id == "abap-data" for t in topics)
        rels = list(session.scalars(select(TopicRelationship)).all())
        assert rels
        assert all(t.learning_order is not None or t.source_order is not None for t in topics)


def test_phase4_gaps_enrich_review(
    settings, session_factory, synthetic_video, media_probe
) -> None:
    _seed(settings, session_factory, synthetic_video, media_probe)
    ExtractVisualsService(settings, session_factory).run(
        ExtractVisualsRequest(course_slug="demo", extractor="stub")
    )
    DiscoverTopicsService(settings, session_factory).run(
        DiscoverTopicsRequest(course_slug="demo")
    )
    MapCurriculumService(settings, session_factory).run(MapCurriculumRequest())
    ref = Path("tests/fixtures/curriculum_ref/reference.json")
    AnalyzeGapsService(settings, session_factory).run(
        AnalyzeGapsRequest(reference_path=ref, force=True)
    )
    EnrichService(settings, session_factory).run(EnrichRequest(force=True))

    with session_factory() as session:
        gaps = list(session.scalars(select(KnowledgeGap)).all())
        assert gaps
        unseen_notes = [
            g for g in gaps if "görülmedi" in (g.evidence_note or "")
        ]
        assert unseen_notes
        assert all(g.gap_class == "uncertain" for g in unseen_notes)
        blocks = list(session.scalars(select(ContentBlock)).all())
        assert blocks
        assert all(b.layer == "generated" for b in blocks)
        assert all(b.review_status == ReviewStatus.DRAFT.value for b in blocks)
        block_id = blocks[0].id

    review = ReviewService(settings, session_factory)
    with pytest.raises(PublishWithoutApprovalError):
        review.decide(
            entity_type="content_block",
            entity_id=block_id,
            decision="publish",
            reviewer="tester",
        )
    review.decide(
        entity_type="content_block",
        entity_id=block_id,
        decision="approve",
        reviewer="tester",
    )
    review.decide(
        entity_type="content_block",
        entity_id=block_id,
        decision="publish",
        reviewer="tester",
    )
    with session_factory() as session:
        block = session.get(ContentBlock, block_id)
        assert block is not None
        assert block.review_status == ReviewStatus.PUBLISHED.value


def test_phase5_export(
    settings, session_factory, synthetic_video, media_probe, tmp_path
) -> None:
    _seed(settings, session_factory, synthetic_video, media_probe)
    ExtractVisualsService(settings, session_factory).run(
        ExtractVisualsRequest(course_slug="demo", extractor="stub")
    )
    DiscoverTopicsService(settings, session_factory).run(
        DiscoverTopicsRequest(course_slug="demo")
    )
    MapCurriculumService(settings, session_factory).run(MapCurriculumRequest())
    out = tmp_path / "exports"
    written = ExportService(settings, session_factory).run(
        ExportRequest(formats=["json", "md", "mermaid", "graphml", "coverage"], out_dir=out)
    )
    assert written
    assert (out / "curriculum.json").is_file()
    assert (out / "topic_map.mmd").is_file()
    assert (out / "coverage_report.md").is_file()
