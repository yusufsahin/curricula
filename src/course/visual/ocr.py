"""OCR adapters — stub for tests, optional real engines later."""

from __future__ import annotations

import re
from pathlib import Path

ABAP_HINTS = re.compile(
    r"\b(SELECT|DATA|TYPES|FORM|ENDFORM|LOOP|ENDLOOP|WRITE|METHOD|CLASS)\b",
    re.IGNORECASE,
)


class StubOCR:
    """Reads optional sidecar `.ocr.txt` next to a frame, else synthetic text."""

    name = "stub"
    version = "1"

    def extract(self, frame_path: Path) -> tuple[str, float]:
        sidecar = frame_path.with_suffix(frame_path.suffix + ".ocr.txt")
        if not sidecar.exists():
            sidecar = Path(str(frame_path) + ".ocr.txt")
        if sidecar.exists():
            text = sidecar.read_text(encoding="utf-8")
            return text.strip(), 0.95
        # Deterministic synthetic content for CI without real frames
        text = "SAP GUI — SELECT * FROM mara. DATA: lv_matnr TYPE matnr."
        return text, 0.7


def classify_scene(ocr_text: str) -> str:
    if ABAP_HINTS.search(ocr_text):
        return "code_editor"
    lowered = ocr_text.lower()
    if "sap" in lowered or "gui" in lowered:
        return "sap_gui"
    if "slide" in lowered or "sunum" in lowered:
        return "slide"
    return "unknown"


def extract_abap_snippets(ocr_text: str) -> list[str]:
    snippets: list[str] = []
    for line in ocr_text.splitlines():
        if ABAP_HINTS.search(line):
            snippets.append(line.strip())
    if not snippets and ABAP_HINTS.search(ocr_text):
        snippets.append(ocr_text.strip())
    return snippets
