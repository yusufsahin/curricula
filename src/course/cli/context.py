"""Shared CLI runtime context."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from course.config import Settings, load_settings
from course.db.session import create_schema, make_engine, make_session_factory
from course.logging import setup_logging


@dataclass
class AppContext:
    settings: Settings
    session_factory: sessionmaker[Session]


def build_context(
    *,
    config: Path | None = None,
    db: Path | None = None,
    data_dir: Path | None = None,
    verbose: bool = False,
    quiet: bool = False,
    json_logs: bool = False,
) -> AppContext:
    log_level = "DEBUG" if verbose else "WARNING" if quiet else "INFO"
    settings = load_settings(
        config,
        db_path=db,
        data_dir=data_dir,
        json_logs=json_logs,
        log_level=log_level,
    )
    setup_logging(level=settings.app.log_level, json_logs=settings.app.json_logs)
    settings.ensure_dirs()
    engine = make_engine(settings.paths.db_path)
    create_schema(engine)
    factory = make_session_factory(engine)
    return AppContext(settings=settings, session_factory=factory)
