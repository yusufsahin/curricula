"""course analyze-gaps"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from course.cli.context import AppContext
from course.gaps.analyzer import AnalyzeGapsRequest, AnalyzeGapsService

console = Console()


def analyze_gaps_command(
    ctx: typer.Context,
    reference: Annotated[
        Path,
        typer.Option("--reference", exists=True, help="Reference curriculum JSON"),
    ],
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    """Compare extracted content against a reference curriculum."""
    app: AppContext = ctx.obj
    service = AnalyzeGapsService(app.settings, app.session_factory)
    results = service.run(
        AnalyzeGapsRequest(reference_path=reference, force=force)
    )
    for result in results:
        console.print(f"{result.status}: {result.error or result.metrics}")
        if result.status == "failed":
            raise typer.Exit(code=1)
