from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from llm_cli.core.settings import save_settings
from llm_cli.main import app

runner = CliRunner()


def _scaffold(repo: Path) -> None:
    md = repo / "models" / "md-a"
    md.mkdir(parents=True)
    (md / "manifest.yaml").write_text(
        "id: md-a\ndisplay_name: M\nsource: { kind: huggingface, repo: foo/bar }\n",
        encoding="utf-8",
    )
    (md / "pull.sh").write_text("#!/usr/bin/env bash\necho ok\n", encoding="utf-8")


def test_model_list(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _scaffold(repo)
    save_settings({"data_root": str(tmp_path / "data"), "repo_root": str(repo)})
    result = runner.invoke(app, ["model", "list"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "md-a" in result.stdout


def test_model_info(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _scaffold(repo)
    save_settings({"data_root": str(tmp_path / "data"), "repo_root": str(repo)})
    result = runner.invoke(app, ["model", "info", "md-a"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "md-a" in result.stdout
    assert "huggingface" in result.stdout


@patch("llm_cli.commands.model_cmd.run_repo_bash", return_value=0)
def test_model_pull_calls_run_repo_bash(mock_run, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _scaffold(repo)
    save_settings({"data_root": str(tmp_path / "data"), "repo_root": str(repo)})
    result = runner.invoke(app, ["model", "pull", "md-a"], catch_exceptions=False)
    assert result.exit_code == 0
    assert mock_run.call_args[0][1] == "models/md-a/pull.sh"
