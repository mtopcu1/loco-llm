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


def test_top_level_build_pull_removed():
    root_help = runner.invoke(app, ["--help"])
    assert root_help.exit_code == 0
    assert "│ build " not in root_help.stdout
    assert "│ pull " not in root_help.stdout

    r1 = runner.invoke(app, ["build", "rt-a"])
    assert r1.exit_code != 0
    r2 = runner.invoke(app, ["pull", "md-a"])
    assert r2.exit_code != 0


def test_runtime_and_model_subapps_registered():
    r1 = runner.invoke(app, ["runtime", "--help"])
    assert r1.exit_code == 0
    assert "install" in r1.stdout
    r2 = runner.invoke(app, ["model", "--help"])
    assert r2.exit_code == 0
    assert "pull" in r2.stdout
