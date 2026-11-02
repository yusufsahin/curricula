from pathlib import Path

from curricula.media.hashing import sha256_file


def test_sha256_file_deterministic(tmp_path: Path) -> None:
    path = tmp_path / "a.bin"
    path.write_bytes(b"abc")
    first = sha256_file(path)
    second = sha256_file(path)
    assert first == second
    assert len(first) == 64
