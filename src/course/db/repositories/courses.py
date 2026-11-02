"""Course and video repository helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from course.db.models import Course, TranscriptSegment, Video
from course.domain.enums import VideoStatus
from course.domain.ids import new_id


def get_or_create_course(
    session: Session,
    slug: str,
    *,
    title: str | None = None,
    locale: str = "tr",
) -> Course:
    course = session.scalar(select(Course).where(Course.slug == slug))
    if course is not None:
        return course
    course = Course(
        id=new_id(),
        slug=slug,
        title=title or slug.replace("-", " ").title(),
        locale=locale,
    )
    session.add(course)
    session.flush()
    return course


def get_video_by_sha(session: Session, sha256: str) -> Video | None:
    return session.scalar(select(Video).where(Video.sha256 == sha256))


def get_video(session: Session, video_id: UUID) -> Video | None:
    return session.get(Video, video_id)


def list_videos(
    session: Session,
    *,
    course_slug: str | None = None,
) -> list[Video]:
    stmt = select(Video)
    if course_slug is not None:
        stmt = stmt.join(Course).where(Course.slug == course_slug)
    return list(session.scalars(stmt).all())


def upsert_video(
    session: Session,
    *,
    course: Course,
    path: Path,
    sha256: str,
    filename: str,
    duration_sec: float | None,
    codec: str | None,
    width: int | None,
    height: int | None,
    filesize: int | None,
    meta_json: str | None,
) -> tuple[Video, bool]:
    """Return (video, created)."""
    existing = get_video_by_sha(session, sha256)
    if existing is not None:
        return existing, False
    video = Video(
        id=new_id(),
        course_id=course.id,
        path=str(path),
        filename=filename,
        sha256=sha256,
        duration_sec=duration_sec,
        codec=codec,
        width=width,
        height=height,
        filesize=filesize,
        status=VideoStatus.INGESTED.value,
        ingested_at=datetime.now(UTC),
        meta_json=meta_json,
    )
    session.add(video)
    session.flush()
    return video, True


def replace_transcript_segments(
    session: Session,
    video: Video,
    segments: list[dict[str, object]],
    *,
    language: str,
) -> int:
    for old in list(video.transcript_segments):
        session.delete(old)
    session.flush()
    count = 0
    for idx, seg in enumerate(segments):
        start_s = float(seg["start"])  # type: ignore[arg-type]
        end_s = float(seg["end"])  # type: ignore[arg-type]
        text_raw = str(seg["text"])
        text_normalized = seg.get("text_normalized")
        avg_logprob_raw = seg.get("avg_logprob")
        avg_logprob = (
            None if avg_logprob_raw is None else float(str(avg_logprob_raw))
        )
        row = TranscriptSegment(
            id=new_id(),
            video_id=video.id,
            seg_index=idx,
            start_ms=int(start_s * 1000),
            end_ms=int(end_s * 1000),
            text_raw=text_raw,
            text_normalized=str(text_normalized) if text_normalized is not None else None,
            language=language,
            avg_logprob=avg_logprob,
        )
        session.add(row)
        count += 1
    session.flush()
    return count
