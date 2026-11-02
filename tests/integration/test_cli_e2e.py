from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from course.cli.app import app

runner = CliRunner()


def test_cli_pipeline_smoke(tmp_path: Path, synthetic_video: Path) -> None:
    data_dir = tmp_path / "data"
    common = ["--data-dir", str(data_dir), "--quiet"]

    result = runner.invoke(
        app,
        [
            *common,
            "run",
            "--course",
            "demo",
            "--path",
            str(synthetic_video),
            "--from",
            "ingest",
            "--to",
            "enrich",
            "--adapter",
            "fake",
            "--reference",
            str(Path("tests/fixtures/curriculum_ref/reference.json").resolve()),
        ],
    )
    assert result.exit_code == 0, result.output

    status = runner.invoke(app, [*common, "status"])
    assert status.exit_code == 0, status.output
    assert "topics" in status.output

    out_dir = tmp_path / "out"
    export = runner.invoke(
        app,
        [
            *common,
            "export",
            "--format",
            "json",
            "--format",
            "mermaid",
            "--out",
            str(out_dir),
        ],
    )
    assert export.exit_code == 0, export.output
    assert (out_dir / "curriculum.json").is_file()

    rels = runner.invoke(app, [*common, "relations", "list"])
    assert rels.exit_code == 0, rels.output
