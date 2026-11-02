"""course demo — one-shot synthetic pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from course.cli.context import AppContext
from course.curriculum.mapper import MapCurriculumRequest, MapCurriculumService
from course.enrichment.engine import EnrichRequest, EnrichService
from course.export.engine import ExportRequest, ExportService
from course.gaps.analyzer import AnalyzeGapsRequest, AnalyzeGapsService
from course.media.ingest import IngestService
from course.media.metadata import StaticMediaProbe
from course.pipeline.contracts import IngestRequest, TranscribeRequest
from course.topics.discovery import DiscoverTopicsRequest, DiscoverTopicsService
from course.transcription.engine import TranscribeService
from course.visual.extract import ExtractVisualsRequest, ExtractVisualsService

console = Console()


def _fixture_video() -> Path:
    here = Path(__file__).resolve()
    candidates = [
        Path.cwd() / "tests" / "fixtures" / "synthetic_video" / "sample.mp4",
        here.parents[4] / "tests" / "fixtures" / "synthetic_video" / "sample.mp4",
    ]
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError("synthetic sample.mp4 fixture not found")


def _fixture_reference() -> Path:
    candidates = [
        Path.cwd() / "tests" / "fixtures" / "curriculum_ref" / "reference.json",
        Path(__file__).resolve().parents[4]
        / "tests"
        / "fixtures"
        / "curriculum_ref"
        / "reference.json",
    ]
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError("reference.json fixture not found")


def demo_command(
    ctx: typer.Context,
    course: Annotated[str, typer.Option("--course")] = "demo",
    export_formats: Annotated[
        list[str] | None,
        typer.Option("--format"),
    ] = None,
) -> None:
    """Run the full offline pipeline on the synthetic fixture video."""
    app: AppContext = ctx.obj
    video = _fixture_video()
    reference = _fixture_reference()
    formats = export_formats or ["json", "md", "mermaid", "coverage"]

    console.print(f"[bold]Demo course[/bold] slug={course}")
    console.print(f"video={video}")
    console.print(f"reference={reference}")

    ingest = IngestService(app.settings, app.session_factory, probe=StaticMediaProbe())
    for result in ingest.run(
        IngestRequest(course_slug=course, video_paths=[video], force=True)
    ):
        console.print(f"ingest: {result.status}")

    for result in TranscribeService(app.settings, app.session_factory).run(
        TranscribeRequest(course_slug=course, adapter="fake", force=True)
    ):
        console.print(f"transcribe: {result.status}")

    for result in ExtractVisualsService(app.settings, app.session_factory).run(
        ExtractVisualsRequest(course_slug=course, extractor="stub", force=True)
    ):
        console.print(f"extract-visuals: {result.status}")

    for result in DiscoverTopicsService(app.settings, app.session_factory).run(
        DiscoverTopicsRequest(course_slug=course, force=True)
    ):
        console.print(f"discover-topics: {result.status} {result.metrics}")

    for result in MapCurriculumService(app.settings, app.session_factory).run(
        MapCurriculumRequest(force=True)
    ):
        console.print(f"map-curriculum: {result.status} {result.metrics}")

    for result in AnalyzeGapsService(app.settings, app.session_factory).run(
        AnalyzeGapsRequest(reference_path=reference, force=True)
    ):
        console.print(f"analyze-gaps: {result.status} {result.metrics}")

    for result in EnrichService(app.settings, app.session_factory).run(
        EnrichRequest(force=True)
    ):
        console.print(f"enrich: {result.status} {result.metrics}")

    written = ExportService(app.settings, app.session_factory).run(
        ExportRequest(formats=formats)
    )
    console.print(f"export: {len(written)} files -> {app.settings.paths.exports_dir}")
    console.print("[green]Demo complete. Try: course topics list && course status[/green]")
