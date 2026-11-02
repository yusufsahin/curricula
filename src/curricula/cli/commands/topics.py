"""curricula topics — inspect discovered curriculum topics."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table
from sqlalchemy import func, select

from curricula.cli.context import AppContext
from curricula.db.models import Topic, TopicOccurrence

console = Console()
topics_app = typer.Typer(
    name="topics",
    help="Inspect discovered topics",
    no_args_is_help=True,
)


@topics_app.command("list")
def list_topics(
    ctx: typer.Context,
    q: Annotated[str | None, typer.Option("--q", help="Filter stable_id/title")] = None,
) -> None:
    """List topics with occurrence counts."""
    app_ctx: AppContext = ctx.obj
    with app_ctx.session_factory() as session:
        rows = list(
            session.scalars(
                select(Topic).order_by(Topic.learning_order, Topic.stable_id)
            ).all()
        )
        if q:
            needle = q.lower()
            rows = [
                t
                for t in rows
                if needle in t.stable_id.lower()
                or needle in t.title_tr.lower()
                or needle in (t.title_canonical or "").lower()
            ]
        table = Table(title="Topics", expand=True)
        table.add_column("stable_id", overflow="fold", no_wrap=False, min_width=14)
        table.add_column("title_tr", overflow="fold", no_wrap=False)
        table.add_column("canonical", overflow="fold", no_wrap=False)
        table.add_column("learn#")
        table.add_column("occ")
        table.add_column("review")
        table.add_column("enrichment")
        for topic in rows:
            occ = session.scalar(
                select(func.count())
                .select_from(TopicOccurrence)
                .where(TopicOccurrence.topic_id == topic.id)
            ) or 0
            table.add_row(
                topic.stable_id,
                topic.title_tr,
                topic.title_canonical or "-",
                str(topic.learning_order if topic.learning_order is not None else "-"),
                str(occ),
                topic.review_status,
                topic.enrichment_status,
            )
        console.print(table)


@topics_app.command("show")
def show_topic(
    ctx: typer.Context,
    stable_id: Annotated[str, typer.Argument(help="Topic stable_id")],
) -> None:
    """Show one topic and its source occurrences."""
    app_ctx: AppContext = ctx.obj
    with app_ctx.session_factory() as session:
        topic = session.scalar(select(Topic).where(Topic.stable_id == stable_id))
        if topic is None:
            console.print(f"[red]Topic not found: {stable_id}[/red]")
            raise typer.Exit(code=1)
        console.print(f"[bold]{topic.title_tr}[/bold] ({topic.title_canonical})")
        console.print(f"stable_id: {topic.stable_id}")
        console.print(f"summary: {topic.summary or '-'}")
        console.print(f"confidence: {topic.confidence}")
        console.print(f"source_order: {topic.source_order}")
        console.print(f"learning_order: {topic.learning_order}")
        console.print(f"review: {topic.review_status}")
        console.print(f"enrichment: {topic.enrichment_status}")
        occs = list(
            session.scalars(
                select(TopicOccurrence).where(TopicOccurrence.topic_id == topic.id)
            ).all()
        )
        console.print(f"occurrences: {len(occs)}")
        for occ in occs:
            console.print(
                f"  - video={occ.video_id} confidence={occ.confidence} "
                f"ref={occ.source_ref_id}"
            )
