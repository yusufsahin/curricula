"""Typed service protocols."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from curricula.pipeline.contracts import (
    IngestRequest,
    StageResult,
    TranscribeRequest,
)


class IngestServiceProtocol(Protocol):
    def run(self, req: IngestRequest) -> list[StageResult]: ...


class TranscribeServiceProtocol(Protocol):
    def run(self, req: TranscribeRequest) -> list[StageResult]: ...


class WhisperAdapter(Protocol):
    name: str
    version: str

    def transcribe(
        self,
        audio_or_video: Path,
        *,
        language: str,
        model_size: str,
    ) -> list[dict[str, object]]:
        """Return segment dicts with start, end, text, avg_logprob."""
        ...


class MediaProbe(Protocol):
    def probe(self, path: Path) -> dict[str, object]: ...


class LLMClient(Protocol):
    def complete(self, prompt: str, *, model: str | None = None) -> str: ...
