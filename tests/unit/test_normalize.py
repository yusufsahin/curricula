from course.transcription.normalize import normalize_text


def test_normalize_preserves_abap_tokens() -> None:
    raw = "  Merhaba , bu bir SELECT ifadesidir.  "
    normalized = normalize_text(raw)
    assert "SELECT" in normalized
    assert normalized.startswith("Merhaba")
    assert "  " not in normalized
    assert normalized != raw
