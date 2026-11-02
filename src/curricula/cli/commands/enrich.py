"""curricula enrich"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

import typer
from rich.console import Console

from curricula.cli.context import AppContext
from curricula.enrichment.engine import EnrichRequest, EnrichService

console = Console()


def enrich_command(
    ctx: typer.Context,
    topic_id: Annotated[UUID | None, typer.Option("--topic-id")] = None,
    kinds: Annotated[
        list[str] | None,
        typer.Option("--kinds", help="Content kinds to generate"),
    ] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    """Generate draft enrichment content with provenance."""
    app: AppContext = ctx.obj
    service = EnrichService(app.settings, app.session_factory)
    results = service.run(
        EnrichRequest(
            topic_id=topic_id,
            kinds=kinds,
            dry_run=dry_run,
            force=force,
        )
    )
    for result in results:
        console.print(f"{result.status}: {result.error or result.metrics}")
        if result.status == "failed":
            raise typer.Exit(code=1)
