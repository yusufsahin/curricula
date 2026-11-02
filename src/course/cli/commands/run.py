"""course run — pipeline orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from course.cli.context import AppContext
from course.curriculum.mapper import MapCurriculumRequest, MapCurriculumService
from course.domain.enums import PipelineStage
from course.enrichment.engine import EnrichRequest, EnrichService
from course.export.engine import ExportRequest, ExportService
from course.gaps.analyzer import AnalyzeGapsRequest, AnalyzeGapsService
from course.media.ingest import IngestService
from course.pipeline.contracts import IngestRequest, StageResult, TranscribeRequest
from course.pipeline.runner import (
    StageNotImplementedError,
    parse_stage,
    resolve_stage_range,
    run_stages,
)
from course.topics.discovery import DiscoverTopicsRequest, DiscoverTopicsService
from course.transcription.engine import TranscribeService
from course.visual.extract import ExtractVisualsRequest, ExtractVisualsService

console = Console()


def run_command(
    ctx: typer.Context,
    course: Annotated[str, typer.Option("--course", help="Course slug")],
    path: Annotated[
        list[Path] | None,
        typer.Option("--path", help="Video paths for ingest stage"),
    ] = None,
    from_stage: Annotated[
        str,
        typer.Option("--from", help="Start stage"),
    ] = "ingest",
    to_stage: Annotated[
        str,
        typer.Option("--to", help="End stage"),
    ] = "transcribe",
    force: Annotated[bool, typer.Option("--force")] = False,
    adapter: Annotated[str | None, typer.Option("--adapter")] = None,
    reference: Annotated[
        Path | None,
        typer.Option("--reference", help="Gap analysis reference JSON"),
    ] = None,
) -> None:
    """Run an inclusive pipeline stage range."""
    app: AppContext = ctx.obj
    start = parse_stage(from_stage)
    end = parse_stage(to_stage)
    stages = resolve_stage_range(start, end)

    def handle_ingest() -> list[StageResult]:
        if not path:
            console.print("[red]--path is required when running ingest[/red]")
            raise typer.Exit(code=2)
        service = IngestService(app.settings, app.session_factory)
        return service.run(
            IngestRequest(course_slug=course, video_paths=path, force=force)
        )

    def handle_transcribe() -> list[StageResult]:
        service = TranscribeService(app.settings, app.session_factory)
        return service.run(
            TranscribeRequest(
                course_slug=course,
                force=force,
                adapter=adapter or "fake",
                language=app.settings.transcription.language,
                model_size=app.settings.transcription.model_size,
            )
        )

    def handle_visuals() -> list[StageResult]:
        service = ExtractVisualsService(app.settings, app.session_factory)
        return service.run(
            ExtractVisualsRequest(
                course_slug=course,
                force=force,
                extractor="stub",
            )
        )

    def handle_topics() -> list[StageResult]:
        service = DiscoverTopicsService(app.settings, app.session_factory)
        return service.run(DiscoverTopicsRequest(course_slug=course, force=force))

    def handle_map() -> list[StageResult]:
        service = MapCurriculumService(app.settings, app.session_factory)
        return service.run(MapCurriculumRequest(force=force))

    def handle_gaps() -> list[StageResult]:
        ref = reference
        if ref is None:
            candidates = [
                Path.cwd() / "tests" / "fixtures" / "curriculum_ref" / "reference.json",
                Path(__file__).resolve().parents[4]
                / "tests"
                / "fixtures"
                / "curriculum_ref"
                / "reference.json",
            ]
            ref = next((p for p in candidates if p.is_file()), None)
        if ref is None:
            console.print("[red]--reference is required for analyze-gaps[/red]")
            raise typer.Exit(code=2)
        service = AnalyzeGapsService(app.settings, app.session_factory)
        return service.run(AnalyzeGapsRequest(reference_path=ref, force=force))

    def handle_enrich() -> list[StageResult]:
        service = EnrichService(app.settings, app.session_factory)
        return service.run(EnrichRequest(force=force))

    def handle_export() -> list[StageResult]:
        from uuid import uuid4

        service = ExportService(app.settings, app.session_factory)
        written = service.run(ExportRequest(formats=["all"]))
        return [
            StageResult(
                stage=PipelineStage.EXPORT.value,
                status="completed",
                job_id=uuid4(),
                fingerprint="export",
                artifacts=written,
                metrics={"files": len(written)},
            )
        ]

    handlers = {
        PipelineStage.INGEST: handle_ingest,
        PipelineStage.TRANSCRIBE: handle_transcribe,
        PipelineStage.EXTRACT_VISUALS: handle_visuals,
        PipelineStage.DISCOVER_TOPICS: handle_topics,
        PipelineStage.MAP_CURRICULUM: handle_map,
        PipelineStage.ANALYZE_GAPS: handle_gaps,
        PipelineStage.ENRICH: handle_enrich,
        PipelineStage.EXPORT: handle_export,
    }

    try:
        results = run_stages(stages, handlers)
    except StageNotImplementedError as exc:
        console.print(f"[yellow]{exc}[/yellow]")
        raise typer.Exit(code=2) from exc

    failed = sum(1 for r in results if r.status == "failed")
    for result in results:
        console.print(
            f"{result.stage}: {result.status} "
            f"({result.fingerprint[:12]}) {result.error or result.metrics}"
        )
    if failed:
        raise typer.Exit(code=1)
