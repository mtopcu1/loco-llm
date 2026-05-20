from typer.testing import CliRunner

from llm_cli.main import app

runner = CliRunner()


def test_llm_dashboard_help_lists_subcommands():
    result = runner.invoke(app, ["dashboard", "--help"])
    assert result.exit_code == 0
    out = result.stdout
    for sub in ("install", "serve", "status", "stop", "uninstall"):
        assert sub in out


def test_llm_dashboard_status_when_not_installed(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    result = runner.invoke(app, ["dashboard", "status"])
    assert "dashboard" in result.stdout.lower() or "dashboard" in (result.stderr or "").lower()
