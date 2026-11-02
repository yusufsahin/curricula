"""curricula serve — run FastAPI with uvicorn."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console

from curricula.cli.context import AppContext

console = Console()


def serve_command(
    ctx: typer.Context,
    host: Annotated[str, typer.Option("--host")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port")] = 8000,
    reload: Annotated[bool, typer.Option("--reload")] = False,
) -> None:
    """Start the local FastAPI server."""
    try:
        import uvicorn
    except ImportError as exc:
        console.print(
            "[red]uvicorn/fastapi missing. Install with: "
            "pip install 'curricula[api]'[/red]"
        )
        raise typer.Exit(code=2) from exc

    app_ctx: AppContext = ctx.obj
    from curricula.api.app import create_app

    api = create_app(settings=app_ctx.settings, session_factory=app_ctx.session_factory)
    console.print(f"Serving on http://{host}:{port}")
    uvicorn.run(api, host=host, port=port, reload=reload)
