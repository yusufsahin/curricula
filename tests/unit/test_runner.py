import pytest

from course.domain.enums import PipelineStage
from course.pipeline.runner import resolve_stage_range


def test_resolve_stage_range() -> None:
    stages = resolve_stage_range(PipelineStage.INGEST, PipelineStage.TRANSCRIBE)
    assert stages == [PipelineStage.INGEST, PipelineStage.TRANSCRIBE]


def test_resolve_stage_range_invalid() -> None:
    with pytest.raises(ValueError):
        resolve_stage_range(PipelineStage.TRANSCRIBE, PipelineStage.INGEST)
