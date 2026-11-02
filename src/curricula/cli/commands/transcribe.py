"""curricula transcribe"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

import typer
from rich.console import Console
from rich.table import Table

from curricula.cli.context import AppContext
from curricula.pipeline.contracts import TranscribeRequest
from curricula.transcription.engine import TranscribeService

console = Console()


def transcribe_command(
    ctx: typer.Context,
    video_id: Annotated[
        list[UUID] | None,
        typer.Option("--video-id", help="Video UUID (repeatable)"),
    ] = None,
    course: Annotated[
        str | None,
        typer.Option("--course", help="Limit to course slug"),
    ] = None,
    all_videos: Annotated[
        bool,
        typer.Option("--all", help="Transcribe all ingested videos"),
    ] = False,
    model: Annotated[
        str | None,
        typer.Option("--model", help="Whisper model size or 'fake'"),
    ] = None,
    language: Annotated[
        str | None,
        typer.Option("--language", help="Language code"),
    ] = None,
    adapter: Annotated[
        str | None,
        typer.Option("--adapter", help="fake|faster_whisper|auto"),
    ] = None,
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    """Transcribe Turkish audio with segment timestamps."""
    if not video_id and not all_videos and course is None:
        console.print("[red]Provide --video-id, --course, or --all[/red]")
        raise typer.Exit(code=2)

    app: AppContext = ctx.obj
    model_size = model or app.settings.transcription.model_size
    # Allow --model fake as adapter shortcut
    resolved_adapter = adapter
    if model_size == "fake":
        resolved_adapter = "fake"
        model_size = "tiny"

    service = TranscribeService(app.settings, app.session_factory)
    results = service.run(
        TranscribeRequest(
            video_ids=video_id,
            course_slug=course,
            model_size=model_size,
            language=language or app.settings.transcription.language,
            force=force,
            adapter=resolved_adapter,
        )
    )
    if all_videos and not video_id and course is None:
        # --all already covered by course_slug=None selecting all
        pass

    table = Table(title="Transcribe results")
    table.add_column("Status")
    table.add_column("Fingerprint")
    table.add_column("Detail")
    failed = 0
    for result in results:
        detail = result.error or str(result.metrics)
        table.add_row(result.status, result.fingerprint[:12], detail)
        if result.status == "failed":
            failed += 1
    console.print(table)
    if failed:
        raise typer.Exit(code=1)
