"""Tests for `llm update` command."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from llm_cli.main import app

runner = CliRunner()


def _settings_env(tmp_path: Path, monkeypatch) -> None:
    cfg = tmp_path / "cfg" / "llm"
    cfg.mkdir(parents=True)
    (cfg / "config.yaml").write_text(
        f"data_root: {tmp_path / 'data'}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    monkeypatch.delenv("LLM_SCAFFOLD_DIR", raising=False)


def test_update_check_exits_nonzero_when_behind(tmp_path: Path, monkeypatch) -> None:
    _settings_env(tmp_path, monkeypatch)
    scaffold = tmp_path / "xdg" / "localllm" / "scaffold"
    scaffold.mkdir(parents=True)
    (scaffold / ".scaffold-version").write_text("v0.2.0\n", encoding="utf-8")

    with (
        patch(
            "llm_cli.commands.update_cmd.fetch_pypi_latest_version",
            return_value="0.4.1",
        ),
        patch(
            "llm_cli.commands.update_cmd.fetch_github_latest_release",
            return_value={"tag_name": "v0.4.1", "body": "", "assets": []},
        ),
    ):
        result = runner.invoke(app, ["update", "--check"])
    assert result.exit_code == 1
    assert "0.4.1" in result.stdout


def test_update_check_up_to_date(tmp_path: Path, monkeypatch) -> None:
    _settings_env(tmp_path, monkeypatch)
    scaffold = tmp_path / "xdg" / "localllm" / "scaffold"
    scaffold.mkdir(parents=True)
    (scaffold / ".scaffold-version").write_text("v0.2.0\n", encoding="utf-8")

    with (
        patch(
            "llm_cli.commands.update_cmd.fetch_pypi_latest_version",
            return_value="0.2.0",
        ),
        patch(
            "llm_cli.commands.update_cmd.fetch_github_latest_release",
            return_value={"tag_name": "v0.2.0", "body": "", "assets": []},
        ),
    ):
        result = runner.invoke(app, ["update", "--check"])
    assert result.exit_code == 0
    assert "Already up to date" in result.stdout


def test_update_refuses_when_service_running(tmp_path: Path, monkeypatch) -> None:
    _settings_env(tmp_path, monkeypatch)
    with (
        patch(
            "llm_cli.commands.update_cmd.fetch_pypi_latest_version",
            return_value="0.4.1",
        ),
        patch(
            "llm_cli.commands.update_cmd.fetch_github_latest_release",
            return_value={"tag_name": "v0.4.1", "body": "", "assets": []},
        ),
        patch(
            "llm_cli.commands.update_cmd.service_is_running_for_settings",
            return_value=True,
        ),
    ):
        result = runner.invoke(app, ["update", "--yes"])
    assert result.exit_code == 1
    assert "Stop the running service" in result.stdout


def test_update_refuses_cli_in_dev_mode(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    cfg = tmp_path / "cfg" / "llm"
    cfg.mkdir(parents=True)
    (cfg / "config.yaml").write_text(
        f"data_root: {tmp_path / 'data'}\nrepo_root: {repo}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))

    with (
        patch(
            "llm_cli.commands.update_cmd.fetch_pypi_latest_version",
            return_value="0.4.1",
        ),
        patch(
            "llm_cli.commands.update_cmd.fetch_github_latest_release",
            return_value={"tag_name": "v0.4.1", "body": "", "assets": []},
        ),
        patch(
            "llm_cli.commands.update_cmd.service_is_running_for_settings",
            return_value=False,
        ),
        patch("llm_cli.commands.update_cmd._confirm"),
    ):
        result = runner.invoke(app, ["update", "--yes", "--cli-only"])
    assert result.exit_code == 1
    assert "editable dev install" in result.stdout
