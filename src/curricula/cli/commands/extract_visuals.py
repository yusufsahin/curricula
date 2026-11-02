"""curricula extract-visuals"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

import typer
from rich.console import Console
from rich.table import Table

from curricula.cli.context import AppContext
from curricula.visual.extract import ExtractVisualsRequest, ExtractVisualsService

console = Console()


def extract_visuals_command(
    ctx: typer.Context,
    course: Annotated[str | None, typer.Option("--course")] = None,
    video_id: Annotated[list[UUID] | None, typer.Option("--video-id")] = None,
    all_videos: Annotated[bool, typer.Option("--all")] = False,
    extractor: Annotated[str, typer.Option("--extractor")] = "stub",
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    """Detect scenes, extract frames, OCR text and ABAP snippets."""
    if not video_id and not all_videos and course is None:
        console.print("[red]Provide --video-id, --course, or --all[/red]")
        raise typer.Exit(code=2)
    app: AppContext = ctx.obj
    service = ExtractVisualsService(app.settings, app.session_factory)
    results = service.run(
        ExtractVisualsRequest(
            course_slug=course,
            video_ids=video_id,
            force=force,
            extractor=extractor,
        )
    )
    table = Table(title="extract-visuals")
    table.add_column("Status")
    table.add_column("Detail")
    failed = 0
    for result in results:
        table.add_row(result.status, result.error or str(result.metrics))
        if result.status == "failed":
            failed += 1
    console.print(table)
    if failed:
        raise typer.Exit(code=1)
