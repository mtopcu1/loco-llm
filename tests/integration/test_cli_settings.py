"""Integration tests for `llm settings ...`."""
from __future__ import annotations

from pathlib import Path

import yaml
from typer.testing import CliRunner

from llm_cli.core.settings import settings_path
from llm_cli.main import app

runner = CliRunner()


def _write_settings(**kv: str) -> Path:
    cfg = settings_path()
    cfg.parent.mkdir(parents=True)
    cfg.write_text(yaml.safe_dump(kv), encoding="utf-8")
    return cfg


def test_settings_show_prints_path_and_resolved(tmp_path) -> None:
    cfg = _write_settings(
        data_root=str(tmp_path / "d"), repo_root=str(tmp_path / "r")
    )

    result = runner.invoke(app, ["settings", "show"], catch_exceptions=False)

    assert result.exit_code == 0, result.stdout
    assert str(cfg) in result.stdout
    assert str(tmp_path / "d") in result.stdout
    assert str(tmp_path / "r") in result.stdout
    assert "runtimes_dir" in result.stdout


def test_settings_env_prints_export_lines(tmp_path) -> None:
    _write_settings(
        data_root=str(tmp_path / "d"), repo_root=str(tmp_path / "r")
    )

    result = runner.invoke(app, ["settings", "env"], catch_exceptions=False)

    assert result.exit_code == 0, result.stdout
    lines = result.stdout.strip().splitlines()
    assert f"export LLM_DATA_ROOT={(tmp_path / 'd').as_posix()}" in lines
    assert f"export LLM_REPO_ROOT={(tmp_path / 'r').as_posix()}" in lines
    assert f"export LLM_RUNTIMES={(tmp_path / 'd' / 'runtimes').as_posix()}" in lines
    assert f"export LLM_MODELS={(tmp_path / 'd' / 'models').as_posix()}" in lines
    assert f"export LLM_CACHE={(tmp_path / 'd' / 'cache').as_posix()}" in lines


def test_settings_env_shell_escapes_values(tmp_path) -> None:
    weird = tmp_path / "with space"
    _write_settings(data_root=str(weird), repo_root=str(tmp_path / "r"))

    result = runner.invoke(app, ["settings", "env"], catch_exceptions=False)

    assert result.exit_code == 0
    assert "'" in result.stdout


def test_settings_edit_updates_existing_key(tmp_path) -> None:
    _write_settings(data_root="~/llm", repo_root=str(tmp_path / "r"))
    new_data_root = tmp_path / "new"

    result = runner.invoke(
        app,
        ["settings", "edit", "data_root"],
        input=f"{new_data_root}\n",
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.stdout
    stored = yaml.safe_load(settings_path().read_text(encoding="utf-8"))
    assert stored["data_root"] == str(new_data_root)


def test_settings_edit_unknown_key_errors(tmp_path) -> None:
    _write_settings(data_root="~/llm", repo_root=str(tmp_path / "r"))

    result = runner.invoke(app, ["settings", "edit", "nope"], catch_exceptions=False)

    assert result.exit_code != 0
    assert "nope" in result.stdout
