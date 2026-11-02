"""course quality — local quality / coverage summary."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table
from sqlalchemy import func, select

from course.cli.context import AppContext
from course.db.models import (
    Assessment,
    ContentBlock,
    KnowledgeGap,
    ReviewDecision,
    Topic,
    TopicRelationship,
)
from course.export.engine import ExportRequest, ExportService

console = Console()


def quality_command(
    ctx: typer.Context,
    write_report: Annotated[
        bool,
        typer.Option("--write-report/--no-write-report", help="Also write coverage_report.md"),
    ] = True,
) -> None:
    """Summarize curriculum quality signals for the local repository."""
    app: AppContext = ctx.obj
    with app.session_factory() as session:
        topic_count = session.scalar(select(func.count()).select_from(Topic)) or 0
        gap_rows = list(session.scalars(select(KnowledgeGap)).all())
        blocks = list(session.scalars(select(ContentBlock)).all())
        assessments = session.scalar(select(func.count()).select_from(Assessment)) or 0
        rels = session.scalar(select(func.count()).select_from(TopicRelationship)) or 0
        approved_rels = session.scalar(
            select(func.count())
            .select_from(TopicRelationship)
            .where(TopicRelationship.approved.is_(True))
        ) or 0
        reviews = session.scalar(select(func.count()).select_from(ReviewDecision)) or 0
        published = sum(1 for b in blocks if b.review_status == "published")
        approved = sum(1 for b in blocks if b.review_status == "approved")
        drafts = sum(1 for b in blocks if b.review_status == "draft")

        by_class: dict[str, int] = {}
        for gap in gap_rows:
            by_class[gap.gap_class] = by_class.get(gap.gap_class, 0) + 1

    table = Table(title="Quality summary")
    table.add_column("Signal")
    table.add_column("Value")
    rows = [
        ("topics", str(topic_count)),
        ("relationships", f"{approved_rels}/{rels} approved"),
        ("content drafts", str(drafts)),
        ("content approved", str(approved)),
        ("content published", str(published)),
        ("assessments", str(assessments)),
        ("review decisions", str(reviews)),
    ]
    for key, value in rows:
        table.add_row(key, value)
    console.print(table)

    gaps_table = Table(title="Gaps by class")
    gaps_table.add_column("Class")
    gaps_table.add_column("Count")
    for cls in ("missing", "insufficient", "uncertain", "complete"):
        gaps_table.add_row(cls, str(by_class.get(cls, 0)))
    console.print(gaps_table)

    warnings: list[str] = []
    if drafts and published == 0 and approved == 0:
        warnings.append("AI drafts exist but none are approved/published yet.")
    if by_class.get("missing", 0):
        warnings.append(f"{by_class['missing']} missing-dimension gaps need enrichment.")
    if rels and approved_rels == 0:
        warnings.append("Topic relationships exist but none are approved.")
    for warning in warnings:
        console.print(f"[yellow]• {warning}[/yellow]")
    if not warnings:
        console.print("[green]No blocking quality warnings.[/green]")

    if write_report:
        written = ExportService(app.settings, app.session_factory).run(
            ExportRequest(formats=["coverage"])
        )
        for path in written:
            console.print(f"wrote {path}")
