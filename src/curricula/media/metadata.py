"""Media metadata probing via ffprobe (mockable)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


class FfprobeError(RuntimeError):
    pass


class FfprobeMediaProbe:
    """Probe video metadata using ffprobe when available."""

    def probe(self, path: Path) -> dict[str, Any]:
        if shutil.which("ffprobe") is None:
            return self._fallback(path)
        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
        try:
            completed = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            raise FfprobeError(f"ffprobe failed for {path}: {exc}") from exc
        payload = json.loads(completed.stdout or "{}")
        return self._normalize(path, payload)

    def _fallback(self, path: Path) -> dict[str, Any]:
        size = path.stat().st_size if path.exists() else 0
        return {
            "duration_sec": None,
            "codec": None,
            "width": None,
            "height": None,
            "filesize": size,
            "raw": {"fallback": True},
        }

    def _normalize(self, path: Path, payload: dict[str, Any]) -> dict[str, Any]:
        format_block = payload.get("format") or {}
        duration = format_block.get("duration")
        streams = payload.get("streams") or []
        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        codec = None
        width = None
        height = None
        if video_stream:
            codec = video_stream.get("codec_name")
            width = video_stream.get("width")
            height = video_stream.get("height")
        return {
            "duration_sec": float(duration) if duration is not None else None,
            "codec": codec,
            "width": int(width) if width is not None else None,
            "height": int(height) if height is not None else None,
            "filesize": path.stat().st_size if path.exists() else None,
            "raw": payload,
        }


class StaticMediaProbe:
    """Deterministic probe for tests."""

    def __init__(self, metadata: dict[str, Any] | None = None) -> None:
        self.metadata = metadata or {
            "duration_sec": 1.0,
            "codec": "h264",
            "width": 320,
            "height": 240,
            "filesize": 0,
            "raw": {"test": True},
        }

    def probe(self, path: Path) -> dict[str, Any]:
        result = dict(self.metadata)
        if path.exists():
            result["filesize"] = path.stat().st_size
        return result
