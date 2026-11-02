"""Pipeline request/response contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from curricula.domain.enums import PipelineStage


class StageResult(BaseModel):
    stage: str
    status: Literal["completed", "failed", "skipped"]
    job_id: UUID
    fingerprint: str
    artifacts: list[Path] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class IngestRequest(BaseModel):
    course_slug: str
    video_paths: list[Path]
    force: bool = False


class TranscribeRequest(BaseModel):
    video_ids: list[UUID] | None = None
    course_slug: str | None = None
    model_size: str = "medium"
    language: str = "tr"
    force: bool = False
    adapter: str | None = None


STAGE_ORDER: list[PipelineStage] = [
    PipelineStage.INGEST,
    PipelineStage.TRANSCRIBE,
    PipelineStage.EXTRACT_VISUALS,
    PipelineStage.DISCOVER_TOPICS,
    PipelineStage.MAP_CURRICULUM,
    PipelineStage.ANALYZE_GAPS,
    PipelineStage.ENRICH,
    PipelineStage.EXPORT,
]
