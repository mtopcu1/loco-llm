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
    data = tmp_path / "data"
    monkeypatch.setenv("LOCO_HOME", str(data))
    monkeypatch.delenv("LOCO_INSTALL", raising=False)

    result = runner.invoke(app, ["setup", "--default"], catch_exceptions=False)
    assert result.exit_code == 0, result.stdout

    cfg = settings_path()
    assert cfg == data / "config.yaml"
    assert cfg.is_file()
    stored = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    assert stored["data_root"] == data.resolve().as_posix()
    assert "repo_root" not in stored
    assert (data / "configs").is_dir()
    assert (data / "state").is_dir()
    assert (data / "runtimes").is_dir()


def test_setup_interactive_default_layout(tmp_path, monkeypatch) -> None:
    data = tmp_path / "mydata"
    monkeypatch.setenv("LOCO_HOME", str(tmp_path / "isolated"))
    monkeypatch.chdir(tmp_path)

    user_input = f"{data.resolve().as_posix()}\ny\n"
    result = runner.invoke(app, ["setup"], input=user_input, catch_exceptions=False)
    assert result.exit_code == 0, result.stdout

    cfg = settings_path()
    stored = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    assert stored["data_root"] == data.resolve().as_posix()
    assert (data / "runtimes").is_dir()
    assert (data / "configs").is_dir()


def test_setup_interactive_granular_layout(tmp_path, monkeypatch) -> None:
    data = tmp_path / "dr"
    rt_override = tmp_path / "rtcustom"
    monkeypatch.setenv("LOCO_HOME", str(tmp_path / "isolated"))
    monkeypatch.chdir(tmp_path)

    user_input = (
        f"{data.resolve().as_posix()}\n"
        "n\n"
        f"{rt_override.resolve().as_posix()}\n"
        "\n"
        "\n"
        "n\n"
    )
    result = runner.invoke(app, ["setup"], input=user_input, catch_exceptions=False)
    assert result.exit_code == 0, result.stdout

    cfg = settings_path()
    stored = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    assert stored["data_root"] == data.resolve().as_posix()
    assert "repo_root" not in stored
    assert stored["runtimes_dir"] == rt_override.resolve().as_posix()
    assert "models_dir" not in stored
    assert "cache_dir" not in stored
    assert rt_override.is_dir()
    assert (data / "models").is_dir()


def test_setup_prints_next_steps_panel(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOCO_HOME", str(tmp_path / "data"))

    result = runner.invoke(app, ["setup", "--default"], catch_exceptions=False)

    assert result.exit_code == 0
    assert "Recommended next steps" in result.stdout
    assert "loco runtime setup" in result.stdout
    assert "loco model pull" in result.stdout
    assert "loco serve" in result.stdout
