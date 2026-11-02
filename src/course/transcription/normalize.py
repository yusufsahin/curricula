"""Transcript normalization — never mutates raw text."""

from __future__ import annotations

import re
import unicodedata

NORMALIZE_VERSION = "1"

_WHITESPACE_RE = re.compile(r"\s+")
_PUNCT_SPACE_RE = re.compile(r"\s+([,.!?;:])")


def normalize_text(text: str) -> str:
    """Light Turkish-friendly cleanup preserving SAP/ABAP tokens."""
    value = unicodedata.normalize("NFC", text)
    value = value.replace("\u00a0", " ")
    value = _WHITESPACE_RE.sub(" ", value).strip()
    value = _PUNCT_SPACE_RE.sub(r"\1", value)
    return value
