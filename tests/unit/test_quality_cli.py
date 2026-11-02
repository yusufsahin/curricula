from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from course.cli.app import app
from course.cli.context import build_context
from course.db.models import Topic
from course.domain.ids import new_id

runner = CliRunner()


def test_quality_command(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    ctx = build_context(data_dir=data_dir, quiet=True)
    with ctx.session_factory() as session:
        session.add(
            Topic(
                id=new_id(),
                stable_id="abap-data",
                title_tr="DATA",
                title_canonical="DATA",
                review_status="unreviewed",
                enrichment_status="none",
            )
        )
        session.commit()

    result = runner.invoke(
        app,
        ["--data-dir", str(data_dir), "--quiet", "quality", "--write-report"],
    )
    assert result.exit_code == 0, result.output
    assert "Quality summary" in result.output
    assert (data_dir / "exports" / "coverage_report.md").is_file()
