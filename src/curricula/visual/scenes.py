"""Scene-change frame extraction."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FrameSample:
    timestamp_ms: int
    path: Path


class StubSceneExtractor:
    """Offline extractor: writes placeholder frame markers at fixed timestamps."""

    name = "stub_scene"
    version = "1"

    def extract(self, video_path: Path, out_dir: Path) -> list[FrameSample]:
        out_dir.mkdir(parents=True, exist_ok=True)
        samples: list[FrameSample] = []
        for idx, ts in enumerate((0, 1500, 3000)):
            frame_path = out_dir / f"{video_path.stem}_frame_{idx:03d}.txt"
            frame_path.write_text(f"frame@{ts}ms from {video_path.name}\n", encoding="utf-8")
            samples.append(FrameSample(timestamp_ms=ts, path=frame_path))
        return samples


class OpenCVSceneExtractor:
    """Optional OpenCV-based extractor; falls back if OpenCV missing."""

    name = "opencv_scene"
    version = "1"

    def __init__(self, threshold: float = 27.0) -> None:
        self.threshold = threshold

    def extract(self, video_path: Path, out_dir: Path) -> list[FrameSample]:
        try:
            import cv2
        except ImportError:
            return StubSceneExtractor().extract(video_path, out_dir)

        out_dir.mkdir(parents=True, exist_ok=True)
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return StubSceneExtractor().extract(video_path, out_dir)

        samples: list[FrameSample] = []
        prev_hist = None
        idx = 0
        frame_idx = 0
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            hist = cv2.calcHist([frame], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
            hist = cv2.normalize(hist, hist).flatten()
            take = prev_hist is None
            if prev_hist is not None:
                diff = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CHISQR)
                take = float(diff) > self.threshold
            if take:
                ts_ms = int((frame_idx / fps) * 1000)
                path = out_dir / f"{video_path.stem}_frame_{idx:03d}.png"
                cv2.imwrite(str(path), frame)
                samples.append(FrameSample(timestamp_ms=ts_ms, path=path))
                idx += 1
                prev_hist = hist
            frame_idx += 1
        cap.release()
        if not samples:
            return StubSceneExtractor().extract(video_path, out_dir)
        return samples


def resolve_scene_extractor(
    name: str,
    threshold: float = 27.0,
) -> StubSceneExtractor | OpenCVSceneExtractor:
    if name in {"stub", "fake", "test"}:
        return StubSceneExtractor()
    return OpenCVSceneExtractor(threshold=threshold)
