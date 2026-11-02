"""curricula map-curriculum"""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console

from curricula.cli.context import AppContext
from curricula.curriculum.mapper import MapCurriculumRequest, MapCurriculumService

console = Console()


def map_curriculum_command(
    ctx: typer.Context,
    force: Annotated[bool, typer.Option("--force")] = False,
    approve_auto: Annotated[
        bool,
        typer.Option("--approve-auto/--no-approve-auto"),
    ] = False,
) -> None:
    """Build prerequisite/related topic graph and learning order."""
    app: AppContext = ctx.obj
    service = MapCurriculumService(app.settings, app.session_factory)
    results = service.run(
        MapCurriculumRequest(force=force, approve_auto=approve_auto)
    )
    for result in results:
        console.print(f"{result.status}: {result.error or result.metrics}")
        if result.status == "failed":
            raise typer.Exit(code=1)
