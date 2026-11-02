"""curricula ingest"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from curricula.cli.context import AppContext
from curricula.media.ingest import IngestService
from curricula.pipeline.contracts import IngestRequest

console = Console()


def ingest_command(
    ctx: typer.Context,
    course: Annotated[str, typer.Option("--course", help="Course slug")],
    path: Annotated[
        list[Path],
        typer.Option("--path", help="Video file path (repeatable)", exists=True),
    ],
    force: Annotated[
        bool,
        typer.Option("--force", help="Re-run even if fingerprint matches"),
    ] = False,
) -> None:
    """Import video files into the curriculum repository."""
    app: AppContext = ctx.obj
    service = IngestService(app.settings, app.session_factory)
    results = service.run(
        IngestRequest(course_slug=course, video_paths=path, force=force)
    )
    table = Table(title="Ingest results")
    table.add_column("Status")
    table.add_column("Fingerprint")
    table.add_column("Detail")
    failed = 0
    for result in results:
        detail = result.error or str(result.metrics)
        table.add_row(result.status, result.fingerprint[:12], detail)
        if result.status == "failed":
            failed += 1
    console.print(table)
    if failed:
        raise typer.Exit(code=1)
