"""course review"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

import typer
from rich.console import Console
from rich.table import Table

from course.cli.context import AppContext
from course.review.service import PublishWithoutApprovalError, ReviewService

console = Console()


def review_command(
    ctx: typer.Context,
    list_pending: Annotated[bool, typer.Option("--list")] = False,
    approve: Annotated[UUID | None, typer.Option("--approve")] = None,
    reject: Annotated[UUID | None, typer.Option("--reject")] = None,
    publish: Annotated[UUID | None, typer.Option("--publish")] = None,
    entity_type: Annotated[str, typer.Option("--entity-type")] = "content_block",
    reviewer: Annotated[str, typer.Option("--reviewer")] = "local",
    comment: Annotated[str | None, typer.Option("--comment")] = None,
) -> None:
    """List pending items and record human review decisions."""
    app: AppContext = ctx.obj
    service = ReviewService(app.settings, app.session_factory)
    if list_pending:
        rows = service.list_pending()
        table = Table(title="Pending review")
        table.add_column("Type")
        table.add_column("ID")
        table.add_column("Kind")
        table.add_column("Status")
        for row in rows:
            table.add_row(row["entity_type"], row["entity_id"], row["kind"], row["status"])
        console.print(table)
        return

    decision = None
    entity_id = None
    if approve is not None:
        decision, entity_id = "approve", approve
    elif reject is not None:
        decision, entity_id = "reject", reject
    elif publish is not None:
        decision, entity_id = "publish", publish
    else:
        console.print("[red]Use --list, --approve, --reject, or --publish[/red]")
        raise typer.Exit(code=2)

    try:
        service.decide(
            entity_type=entity_type,
            entity_id=entity_id,
            decision=decision,
            reviewer=reviewer,
            comment=comment,
        )
    except PublishWithoutApprovalError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print(f"{decision} recorded for {entity_type}:{entity_id}")
