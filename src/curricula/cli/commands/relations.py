"""curricula relations — inspect and edit topic relationships."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

import typer
from rich.console import Console
from rich.table import Table

from curricula.cli.context import AppContext
from curricula.curriculum.relations import RelationError, RelationsService

console = Console()
relations_app = typer.Typer(
    name="relations",
    help="Edit curriculum topic relationships",
    no_args_is_help=True,
)


@relations_app.command("list")
def list_relations(
    ctx: typer.Context,
    rel_type: Annotated[str | None, typer.Option("--type")] = None,
    approved_only: Annotated[bool, typer.Option("--approved-only")] = False,
    pending_only: Annotated[bool, typer.Option("--pending-only")] = False,
) -> None:
    """List topic relationships."""
    app_ctx: AppContext = ctx.obj
    approved: bool | None = None
    if approved_only:
        approved = True
    elif pending_only:
        approved = False
    service = RelationsService(app_ctx.session_factory)
    rows = service.list_relations(rel_type=rel_type, approved=approved)
    table = Table(title="Topic relationships")
    table.add_column("ID")
    table.add_column("From")
    table.add_column("To")
    table.add_column("Type")
    table.add_column("Approved")
    table.add_column("Source")
    for row in rows:
        table.add_row(
            str(row.id),
            row.from_stable_id,
            row.to_stable_id,
            row.type,
            str(row.approved),
            row.source,
        )
    console.print(table)


@relations_app.command("add")
def add_relation(
    ctx: typer.Context,
    from_id: Annotated[str, typer.Option("--from")],
    to_id: Annotated[str, typer.Option("--to")],
    rel_type: Annotated[str, typer.Option("--type")] = "prerequisite",
    approved: Annotated[bool, typer.Option("--approved/--draft")] = True,
) -> None:
    """Add a manual topic relationship (rejects prerequisite cycles)."""
    app_ctx: AppContext = ctx.obj
    service = RelationsService(app_ctx.session_factory)
    try:
        row = service.add_relation(
            from_stable_id=from_id,
            to_stable_id=to_id,
            rel_type=rel_type,
            approved=approved,
        )
    except RelationError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print(
        f"added {row.from_stable_id} -[{row.type}]-> {row.to_stable_id} ({row.id})"
    )


@relations_app.command("approve")
def approve_relation(
    ctx: typer.Context,
    relation_id: Annotated[UUID, typer.Argument(help="Relationship UUID")],
    revoke: Annotated[bool, typer.Option("--revoke")] = False,
) -> None:
    """Approve or revoke a relationship."""
    app_ctx: AppContext = ctx.obj
    service = RelationsService(app_ctx.session_factory)
    try:
        service.approve(relation_id, approved=not revoke)
    except RelationError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print(f"{'revoked' if revoke else 'approved'} {relation_id}")


@relations_app.command("delete")
def delete_relation(
    ctx: typer.Context,
    relation_id: Annotated[UUID, typer.Argument(help="Relationship UUID")],
) -> None:
    """Delete a topic relationship."""
    app_ctx: AppContext = ctx.obj
    service = RelationsService(app_ctx.session_factory)
    try:
        service.delete(relation_id)
    except RelationError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print(f"deleted {relation_id}")
