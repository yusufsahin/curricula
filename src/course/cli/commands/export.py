"""course export"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from course.cli.context import AppContext
from course.export.engine import ExportRequest, ExportService

console = Console()


def export_command(
    ctx: typer.Context,
    format_name: Annotated[
        list[str] | None,
        typer.Option("--format", help="json|md|mermaid|graphml|docx|pdf|all"),
    ] = None,
    out: Annotated[Path | None, typer.Option("--out")] = None,
) -> None:
    """Export curriculum artifacts."""
    app: AppContext = ctx.obj
    formats = format_name or list(app.settings.export.default_formats)
    service = ExportService(app.settings, app.session_factory)
    written = service.run(ExportRequest(formats=formats, out_dir=out))
    for path in written:
        console.print(f"wrote {path}")
