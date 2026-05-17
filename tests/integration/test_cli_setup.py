"""Integration tests for `llm setup`."""
from __future__ import annotations

from pathlib import Path

import yaml
from typer.testing import CliRunner

from llm_cli.core.settings import settings_path
from llm_cli.main import app

runner = CliRunner()


def test_setup_default_writes_settings_and_creates_dirs(
    tmp_path, monkeypatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    data = tmp_path / "data"
    monkeypatch.chdir(repo)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("LLM_DEFAULT_DATA_ROOT", str(data))

    result = runner.invoke(app, ["setup", "--default"], catch_exceptions=False)
    assert result.exit_code == 0, result.stdout

    cfg = settings_path()
    assert cfg.is_file()
    stored = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    assert stored["repo_root"] == str(repo)
    assert stored["data_root"] == str(data)
    assert data.is_dir()
    assert (data / "runtimes").is_dir()
