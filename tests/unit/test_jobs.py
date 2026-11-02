from curricula.pipeline.jobs import fingerprint_parts


def test_fingerprint_parts_stable() -> None:
    a = fingerprint_parts("x", "y", "z")
    b = fingerprint_parts("x", "y", "z")
    c = fingerprint_parts("x", "y", "other")
    assert a == b
    assert a != c
