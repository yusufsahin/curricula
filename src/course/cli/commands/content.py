"""course content — list and human-override generated blocks."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated
from uuid import UUID

import typer
from rich.console import Console
from rich.table import Table

from course.cli.context import AppContext
from course.content.overrides import ContentError, ContentService

console = Console()
content_app = typer.Typer(
    name="content",
    help="Inspect and override generated content blocks",
    no_args_is_help=True,
)


@content_app.command("list")
def list_content(
    ctx: typer.Context,
    topic: Annotated[str | None, typer.Option("--topic")] = None,
    kind: Annotated[str | None, typer.Option("--kind")] = None,
    status: Annotated[str | None, typer.Option("--status")] = None,
) -> None:
    """List content blocks."""
    app_ctx: AppContext = ctx.obj
    service = ContentService(app_ctx.settings, app_ctx.session_factory)
    rows = service.list_blocks(topic_stable_id=topic, kind=kind, status=status)
    table = Table(title="Content blocks", expand=True)
    table.add_column("id", overflow="fold", min_width=36)
    table.add_column("topic")
    table.add_column("kind")
    table.add_column("v")
    table.add_column("status")
    table.add_column("preview", overflow="fold")
    for row in rows:
        table.add_row(
            str(row.id),
            row.topic_stable_id,
            row.kind,
            str(row.version),
            row.review_status,
            row.preview.replace("\n", " "),
        )
    console.print(table)


@content_app.command("override")
def override_content(
    ctx: typer.Context,
    block_id: Annotated[UUID, typer.Argument(help="Content block UUID")],
    file: Annotated[
        Path | None,
        typer.Option("--file", exists=True, help="Markdown file with replacement body"),
    ] = None,
    text: Annotated[str | None, typer.Option("--text", help="Inline replacement body")] = None,
    reviewer: Annotated[str, typer.Option("--reviewer")] = "local",
    draft: Annotated[bool, typer.Option("--draft", help="Keep as draft")] = False,
) -> None:
    """Replace AI draft body with a human override (versioned)."""
    if (file is None and text is None) or (file is not None and text is not None):
        console.print("[red]Provide exactly one of --file or --text[/red]")
        raise typer.Exit(code=2)
    body = text if text is not None else file.read_text(encoding="utf-8")  # type: ignore[union-attr]
    app_ctx: AppContext = ctx.obj
    service = ContentService(app_ctx.settings, app_ctx.session_factory)
    try:
        view = service.override(
            block_id=block_id,
            body_md=body,
            reviewer=reviewer,
            mark_approved=not draft,
        )
    except ContentError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print(
        f"overrode {view.id} -> v{view.version} ({view.review_status}) "
        f"[{view.topic_stable_id}/{view.kind}]"
    )


@content_app.command("add")
def add_content(
    ctx: typer.Context,
    topic: Annotated[str, typer.Option("--topic", help="Topic stable_id")],
    kind: Annotated[str, typer.Option("--kind")] = "explanation",
    file: Annotated[
        Path | None,
        typer.Option("--file", exists=True),
    ] = None,
    text: Annotated[str | None, typer.Option("--text")] = None,
    reviewer: Annotated[str, typer.Option("--reviewer")] = "local",
) -> None:
    """Add a manual content block for a topic."""
    if (file is None and text is None) or (file is not None and text is not None):
        console.print("[red]Provide exactly one of --file or --text[/red]")
        raise typer.Exit(code=2)
    body = text if text is not None else file.read_text(encoding="utf-8")  # type: ignore[union-attr]
    app_ctx: AppContext = ctx.obj
    service = ContentService(app_ctx.settings, app_ctx.session_factory)
    try:
        view = service.create_manual(
            topic_stable_id=topic,
            kind=kind,
            body_md=body,
            reviewer=reviewer,
        )
    except ContentError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print(f"created {view.id} [{view.topic_stable_id}/{view.kind}]")
