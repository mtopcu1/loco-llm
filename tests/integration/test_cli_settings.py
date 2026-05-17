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
