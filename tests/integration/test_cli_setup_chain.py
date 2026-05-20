"""Setup must delegate to the onboarding chain when prerequisites are met."""
from __future__ import annotations

from typer.testing import CliRunner

from llm_cli.core.settings import save_settings
from llm_cli.main import app

runner = CliRunner()


def test_setup_invokes_chain(loco_data_isolated, monkeypatch) -> None:
    save_settings({"data_root": str(loco_data_isolated)})

    invoked: list[int] = []
    import llm_cli.commands.setup as setup_cmd

    monkeypatch.setattr(setup_cmd, "run_setup_chain", lambda: invoked.append(1) or 0)

    result = runner.invoke(app, ["setup"], catch_exceptions=False)

    assert result.exit_code == 0
    assert invoked == [1]
