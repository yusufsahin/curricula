from __future__ import annotations

from sqlalchemy import select

from curricula.db.models import ProcessingJob, TranscriptSegment, Video
from curricula.domain.enums import ProcessingStatus
from curricula.media.ingest import IngestService
from curricula.pipeline.contracts import IngestRequest, TranscribeRequest
from curricula.transcription.engine import TranscribeService
from curricula.transcription.whisper_adapter import FakeWhisperAdapter


def test_ingest_idempotent(settings, session_factory, synthetic_video, media_probe) -> None:
    service = IngestService(settings, session_factory, probe=media_probe)
    req = IngestRequest(course_slug="demo", video_paths=[synthetic_video], force=False)
    first = service.run(req)
    second = service.run(req)
    assert first[0].status == "completed"
    assert second[0].status == "skipped"
    with session_factory() as session:
        videos = list(session.scalars(select(Video)).all())
        assert len(videos) == 1


def test_transcribe_preserves_raw(
    settings, session_factory, synthetic_video, media_probe
) -> None:
    ingest = IngestService(settings, session_factory, probe=media_probe)
    ingest.run(IngestRequest(course_slug="demo", video_paths=[synthetic_video]))

    adapter = FakeWhisperAdapter()
    service = TranscribeService(settings, session_factory, adapter=adapter)
    results = service.run(
        TranscribeRequest(course_slug="demo", adapter="fake", force=False)
    )
    assert results[0].status == "completed"

    with session_factory() as session:
        video = session.scalars(select(Video)).one()
        segments = list(session.scalars(select(TranscriptSegment)).all())
        assert segments
        for seg in segments:
            assert seg.text_raw is not None
            assert seg.text_normalized is not None
            assert seg.text_raw != ""
        raw_path = settings.paths.transcripts_dir / f"{video.sha256}.raw.json"
        assert raw_path.is_file()

    # Second run skips
    again = service.run(TranscribeRequest(course_slug="demo", adapter="fake"))
    assert again[0].status == "skipped"
    with session_factory() as session:
        jobs = list(
            session.scalars(
                select(ProcessingJob).where(ProcessingJob.stage == "transcribe")
            ).all()
        )
        assert any(j.status == ProcessingStatus.COMPLETED.value for j in jobs)
