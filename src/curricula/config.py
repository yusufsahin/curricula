"""Application configuration loading."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


class AppSettings(BaseModel):
    locale: str = "tr"
    log_level: str = "INFO"
    json_logs: bool = False


class PathSettings(BaseModel):
    data_dir: Path = Path("data")
    db_path: Path = Path("data/course.db")
    videos_dir: Path = Path("data/videos")
    audio_dir: Path = Path("data/audio")
    transcripts_dir: Path = Path("data/transcripts")
    frames_dir: Path = Path("data/frames")
    exports_dir: Path = Path("data/exports")


class IngestSettings(BaseModel):
    copy_into_data: bool = True


class TranscriptionSettings(BaseModel):
    model_size: str = "medium"
    language: str = "tr"
    device: str = "cpu"
    compute_type: str = "int8"
    normalize_version: str = "1"
    adapter: str = "auto"


class VisualSettings(BaseModel):
    scene_threshold: float = 27.0
    ocr_engine: str = "stub"


class TopicsSettings(BaseModel):
    taxonomy_version: str = "1"
    prompt_version: str = "1"


class EnrichmentSettings(BaseModel):
    default_model: str = "gpt-4o-mini"
    llm_adapter: str = "fake"  # fake | litellm | auto | noop
    require_review_for_publish: bool = True


class ExportSettings(BaseModel):
    default_formats: list[str] = Field(default_factory=lambda: ["json", "md", "mermaid"])


class Settings(BaseModel):
    app: AppSettings = Field(default_factory=AppSettings)
    paths: PathSettings = Field(default_factory=PathSettings)
    ingest: IngestSettings = Field(default_factory=IngestSettings)
    transcription: TranscriptionSettings = Field(default_factory=TranscriptionSettings)
    visual: VisualSettings = Field(default_factory=VisualSettings)
    topics: TopicsSettings = Field(default_factory=TopicsSettings)
    enrichment: EnrichmentSettings = Field(default_factory=EnrichmentSettings)
    export: ExportSettings = Field(default_factory=ExportSettings)

    def ensure_dirs(self) -> None:
        for path in (
            self.paths.data_dir,
            self.paths.videos_dir,
            self.paths.audio_dir,
            self.paths.transcripts_dir,
            self.paths.frames_dir,
            self.paths.exports_dir,
            self.paths.db_path.parent,
        ):
            path.mkdir(parents=True, exist_ok=True)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _env_overrides() -> dict[str, Any]:
    mapping: dict[str, tuple[str, ...]] = {
        "CURRICULA_LOCALE": ("app", "locale"),
        "CURRICULA_LOG_LEVEL": ("app", "log_level"),
        "CURRICULA_JSON_LOGS": ("app", "json_logs"),
        "CURRICULA_DATA_DIR": ("paths", "data_dir"),
        "CURRICULA_DB_PATH": ("paths", "db_path"),
        "CURRICULA_WHISPER_MODEL": ("transcription", "model_size"),
        "CURRICULA_WHISPER_ADAPTER": ("transcription", "adapter"),
        "CURRICULA_LANGUAGE": ("transcription", "language"),
    }
    result: dict[str, Any] = {}
    for env_key, path in mapping.items():
        raw = os.environ.get(env_key)
        if raw is None:
            continue
        cursor: dict[str, Any] = result
        for part in path[:-1]:
            cursor = cursor.setdefault(part, {})
        value: Any = raw
        if env_key == "CURRICULA_JSON_LOGS":
            value = raw.lower() in {"1", "true", "yes", "on"}
        cursor[path[-1]] = value
    return result


def load_settings(
    config_path: Path | None = None,
    *,
    db_path: Path | None = None,
    data_dir: Path | None = None,
    json_logs: bool | None = None,
    log_level: str | None = None,
) -> Settings:
    root = _repo_root()
    path = config_path or root / "config" / "default.toml"
    data: dict[str, Any] = {}
    if path.is_file():
        with path.open("rb") as fh:
            data = tomllib.load(fh)
    data = _deep_merge(data, _env_overrides())

    cli_override: dict[str, Any] = {}
    if data_dir is not None:
        cli_override.setdefault("paths", {})["data_dir"] = str(data_dir)
        cli_override["paths"]["db_path"] = str(data_dir / "course.db")
        cli_override["paths"]["videos_dir"] = str(data_dir / "videos")
        cli_override["paths"]["audio_dir"] = str(data_dir / "audio")
        cli_override["paths"]["transcripts_dir"] = str(data_dir / "transcripts")
        cli_override["paths"]["frames_dir"] = str(data_dir / "frames")
        cli_override["paths"]["exports_dir"] = str(data_dir / "exports")
    if db_path is not None:
        cli_override.setdefault("paths", {})["db_path"] = str(db_path)
    if json_logs is not None:
        cli_override.setdefault("app", {})["json_logs"] = json_logs
    if log_level is not None:
        cli_override.setdefault("app", {})["log_level"] = log_level
    data = _deep_merge(data, cli_override)

    settings = Settings.model_validate(data)
    # Resolve relative paths against repo root when not absolute
    for field in (
        "data_dir",
        "db_path",
        "videos_dir",
        "audio_dir",
        "transcripts_dir",
        "frames_dir",
        "exports_dir",
    ):
        current = getattr(settings.paths, field)
        if not current.is_absolute():
            setattr(settings.paths, field, (root / current).resolve())
    return settings
