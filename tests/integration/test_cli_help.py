from typer.testing import CliRunner

from llm_cli.main import app

runner = CliRunner()


def test_help_shows_program_name():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "llm" in result.stdout.lower()


def test_version_flag_prints_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.stdout
