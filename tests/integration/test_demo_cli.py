from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from course.cli.app import app

runner = CliRunner()


def test_demo_command(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    result = runner.invoke(
        app,
        ["--data-dir", str(data_dir), "--quiet", "demo", "--course", "demo"],
    )
    assert result.exit_code == 0, result.output
    assert "Demo complete" in result.output
    assert (data_dir / "exports" / "curriculum.json").is_file()
    assert (data_dir / "exports" / "coverage_report.md").is_file()
