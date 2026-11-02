from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from curricula.cli.app import app
from curricula.cli.context import build_context
from curricula.db.models import Topic
from curricula.domain.ids import new_id

runner = CliRunner()


def test_topics_list_and_show(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    ctx = build_context(data_dir=data_dir, quiet=True)
    with ctx.session_factory() as session:
        session.add(
            Topic(
                id=new_id(),
                stable_id="abap-select",
                title_tr="SELECT ifadesi",
                title_canonical="SELECT",
                summary="Demo",
                review_status="unreviewed",
                enrichment_status="none",
                learning_order=0,
            )
        )
        session.commit()

    common = ["--data-dir", str(data_dir), "--quiet"]
    listed = runner.invoke(app, [*common, "topics", "list", "--q", "select"])
    assert listed.exit_code == 0, listed.output
    assert "SELECT" in listed.output
    assert "unreviewed" in listed.output

    shown = runner.invoke(app, [*common, "topics", "show", "abap-select"])
    assert shown.exit_code == 0, shown.output
    assert "SELECT ifadesi" in shown.output
    assert "abap-select" in shown.output

    missing = runner.invoke(app, [*common, "topics", "show", "missing"])
    assert missing.exit_code == 1
