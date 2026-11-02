"""Whisper adapters: fake (tests) and faster-whisper (optional)."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class FakeWhisperAdapter:
    """Deterministic offline adapter for tests and CI."""

    name = "fake"
    version = "1"

    def __init__(self, segments: list[dict[str, Any]] | None = None) -> None:
        self._segments = segments or [
            {
                "start": 0.0,
                "end": 1.5,
                "text": "  Merhaba , bu bir SELECT ifadesidir.  ",
                "avg_logprob": -0.2,
            },
            {
                "start": 1.5,
                "end": 3.0,
                "text": "ABAP'ta DATA anahtar kelimesi kullanılır.",
                "avg_logprob": -0.15,
            },
        ]

    def transcribe(
        self,
        audio_or_video: Path,
        *,
        language: str,
        model_size: str,
    ) -> list[dict[str, object]]:
        _ = (audio_or_video, language, model_size)
        return [dict(seg) for seg in self._segments]


class FasterWhisperAdapter:
    """Optional faster-whisper backend."""

    name = "faster_whisper"
    version = "1"

    def __init__(self, *, device: str = "cpu", compute_type: str = "int8") -> None:
        self.device = device
        self.compute_type = compute_type

    def transcribe(
        self,
        audio_or_video: Path,
        *,
        language: str,
        model_size: str,
    ) -> list[dict[str, object]]:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "faster-whisper is not installed. Install with: pip install 'curricula[whisper]'"
            ) from exc

        model = WhisperModel(
            model_size,
            device=self.device,
            compute_type=self.compute_type,
        )
        segments_iter, _info = model.transcribe(
            str(audio_or_video),
            language=language,
            vad_filter=True,
        )
        results: list[dict[str, object]] = []
        for seg in segments_iter:
            results.append(
                {
                    "start": float(seg.start),
                    "end": float(seg.end),
                    "text": seg.text,
                    "avg_logprob": float(seg.avg_logprob)
                    if seg.avg_logprob is not None
                    else None,
                }
            )
        return results


def resolve_adapter(
    name: str,
    *,
    device: str = "cpu",
    compute_type: str = "int8",
) -> FakeWhisperAdapter | FasterWhisperAdapter:
    normalized = name.lower().strip()
    if normalized in {"fake", "test"}:
        return FakeWhisperAdapter()
    if normalized in {"faster_whisper", "faster-whisper", "whisper"}:
        return FasterWhisperAdapter(device=device, compute_type=compute_type)
    if normalized == "auto":
        try:
            import faster_whisper  # noqa: F401

            return FasterWhisperAdapter(device=device, compute_type=compute_type)
        except ImportError:
            return FakeWhisperAdapter()
    raise ValueError(f"Unknown whisper adapter: {name}")
