"""course status"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table
from sqlalchemy import func, select

from course.cli.context import AppContext
from course.db.models import (
    ContentBlock,
    Course,
    KnowledgeGap,
    ProcessingJob,
    Topic,
    Video,
)

console = Console()


def status_command(ctx: typer.Context) -> None:
    """Show repository counts and recent job health."""
    app: AppContext = ctx.obj
    with app.session_factory() as session:
        counts = {
            "courses": session.scalar(select(func.count()).select_from(Course)) or 0,
            "videos": session.scalar(select(func.count()).select_from(Video)) or 0,
            "topics": session.scalar(select(func.count()).select_from(Topic)) or 0,
            "gaps": session.scalar(select(func.count()).select_from(KnowledgeGap)) or 0,
            "content_blocks": session.scalar(select(func.count()).select_from(ContentBlock))
            or 0,
        }
        jobs = list(
            session.scalars(
                select(ProcessingJob).order_by(ProcessingJob.started_at.desc()).limit(10)
            ).all()
        )

    table = Table(title="Repository status")
    table.add_column("Metric")
    table.add_column("Count")
    for key, value in counts.items():
        table.add_row(key, str(value))
    console.print(table)

    jobs_table = Table(title="Recent jobs")
    jobs_table.add_column("Stage")
    jobs_table.add_column("Status")
    jobs_table.add_column("Model")
    jobs_table.add_column("ms")
    for job in jobs:
        jobs_table.add_row(
            job.stage,
            job.status,
            job.model_name or "-",
            str(job.duration_ms or "-"),
        )
    console.print(jobs_table)
    console.print(f"db: {app.settings.paths.db_path}")
    console.print(f"data: {app.settings.paths.data_dir}")
