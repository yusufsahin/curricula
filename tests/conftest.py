"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.orm import Session, sessionmaker

from course.config import Settings, load_settings
from course.db.session import create_schema, make_engine, make_session_factory
from course.media.metadata import StaticMediaProbe


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    data = tmp_path / "data"
    for name in ("videos", "audio", "transcripts", "frames", "exports"):
        (data / name).mkdir(parents=True)
    return data


@pytest.fixture
def settings(tmp_data_dir: Path) -> Settings:
    settings = load_settings(data_dir=tmp_data_dir)
    settings.transcription.adapter = "fake"
    settings.ensure_dirs()
    return settings


@pytest.fixture
def session_factory(settings: Settings) -> sessionmaker[Session]:
    engine = make_engine(settings.paths.db_path)
    create_schema(engine)
    return make_session_factory(engine)


@pytest.fixture
def media_probe() -> StaticMediaProbe:
    return StaticMediaProbe(
        {
            "duration_sec": 3.0,
            "codec": "h264",
            "width": 320,
            "height": 240,
            "filesize": 0,
            "raw": {"test": True},
        }
    )


@pytest.fixture
def synthetic_video(tmp_path: Path) -> Path:
    path = tmp_path / "sample.mp4"
    # Minimal non-empty stub bytes (not a real MP4; probe is mocked in tests)
    path.write_bytes(b"FAKEVIDEO" + b"\x00" * 64)
    return path
