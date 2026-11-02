"""course discover-topics"""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console

from course.cli.context import AppContext
from course.topics.discovery import DiscoverTopicsRequest, DiscoverTopicsService

console = Console()


def discover_topics_command(
    ctx: typer.Context,
    course: Annotated[str | None, typer.Option("--course")] = None,
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    """Discover topics from transcripts and visual evidence."""
    app: AppContext = ctx.obj
    service = DiscoverTopicsService(app.settings, app.session_factory)
    results = service.run(DiscoverTopicsRequest(course_slug=course, force=force))
    for result in results:
        console.print(f"{result.status}: {result.error or result.metrics}")
        if result.status == "failed":
            raise typer.Exit(code=1)
