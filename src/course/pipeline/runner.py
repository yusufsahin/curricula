"""Pipeline orchestration for `course run`."""

from __future__ import annotations

from collections.abc import Callable

from course.domain.enums import PipelineStage
from course.pipeline.contracts import STAGE_ORDER, StageResult


class StageNotImplementedError(NotImplementedError):
    def __init__(self, stage: PipelineStage, phase: int) -> None:
        self.stage = stage
        self.phase = phase
        super().__init__(
            f"Stage '{stage.value}' is not implemented yet (planned for Phase {phase})."
        )


PHASE_FOR_STAGE: dict[PipelineStage, int] = {
    PipelineStage.INGEST: 1,
    PipelineStage.TRANSCRIBE: 1,
    PipelineStage.EXTRACT_VISUALS: 2,
    PipelineStage.DISCOVER_TOPICS: 3,
    PipelineStage.MAP_CURRICULUM: 3,
    PipelineStage.ANALYZE_GAPS: 4,
    PipelineStage.ENRICH: 4,
    PipelineStage.REVIEW: 4,
    PipelineStage.EXPORT: 5,
}


def resolve_stage_range(
    from_stage: PipelineStage,
    to_stage: PipelineStage,
) -> list[PipelineStage]:
    order = STAGE_ORDER
    try:
        start = order.index(from_stage)
        end = order.index(to_stage)
    except ValueError as exc:
        raise ValueError(f"Unknown stage in range: {from_stage}, {to_stage}") from exc
    if start > end:
        raise ValueError(f"Invalid range: {from_stage.value} comes after {to_stage.value}")
    return order[start : end + 1]


def run_stages(
    stages: list[PipelineStage],
    handlers: dict[PipelineStage, Callable[[], list[StageResult]]],
) -> list[StageResult]:
    results: list[StageResult] = []
    for stage in stages:
        handler = handlers.get(stage)
        if handler is None:
            raise StageNotImplementedError(stage, PHASE_FOR_STAGE.get(stage, 0))
        results.extend(handler())
    return results


def parse_stage(value: str) -> PipelineStage:
    return PipelineStage(value)
