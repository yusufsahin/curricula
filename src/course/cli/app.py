"""Typer application entrypoint."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from course.cli.commands.analyze_gaps import analyze_gaps_command
from course.cli.commands.content import content_app
from course.cli.commands.demo import demo_command
from course.cli.commands.discover_topics import discover_topics_command
from course.cli.commands.enrich import enrich_command
from course.cli.commands.export import export_command
from course.cli.commands.extract_visuals import extract_visuals_command
from course.cli.commands.ingest import ingest_command
from course.cli.commands.map_curriculum import map_curriculum_command
from course.cli.commands.quality import quality_command
from course.cli.commands.relations import relations_app
from course.cli.commands.review import review_command
from course.cli.commands.run import run_command
from course.cli.commands.serve import serve_command
from course.cli.commands.status import status_command
from course.cli.commands.topics import topics_app
from course.cli.commands.transcribe import transcribe_command
from course.cli.context import build_context

app = typer.Typer(
    name="course",
    help="Local-first Turkish SAP ABAP curriculum intelligence",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback()
def main_callback(
    ctx: typer.Context,
    config: Annotated[
        Path | None,
        typer.Option("--config", help="Path to TOML config"),
    ] = None,
    db: Annotated[
        Path | None,
        typer.Option("--db", help="SQLite database path"),
    ] = None,
    data_dir: Annotated[
        Path | None,
        typer.Option("--data-dir", help="Runtime data directory"),
    ] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q")] = False,
    json_logs: Annotated[bool, typer.Option("--json-logs")] = False,
) -> None:
    """Global options shared by all commands."""
    ctx.obj = build_context(
        config=config,
        db=db,
        data_dir=data_dir,
        verbose=verbose,
        quiet=quiet,
        json_logs=json_logs,
    )


app.command("ingest")(ingest_command)
app.command("transcribe")(transcribe_command)
app.command("extract-visuals")(extract_visuals_command)
app.command("discover-topics")(discover_topics_command)
app.command("map-curriculum")(map_curriculum_command)
app.command("analyze-gaps")(analyze_gaps_command)
app.command("enrich")(enrich_command)
app.command("review")(review_command)
app.command("export")(export_command)
app.command("status")(status_command)
app.command("quality")(quality_command)
app.command("serve")(serve_command)
app.add_typer(relations_app, name="relations")
app.add_typer(topics_app, name="topics")
app.add_typer(content_app, name="content")
app.command("demo")(demo_command)
app.command("run")(run_command)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
