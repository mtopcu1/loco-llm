"""Integration tests for `loco setup` (onboarding chain entry)."""
from __future__ import annotations

import yaml
from typer.testing import CliRunner

from llm_cli.core.settings import save_settings
from llm_cli.main import app

runner = CliRunner()


def test_setup_requires_initialized_data_home(loco_data_isolated) -> None:
    result = runner.invoke(app, ["setup"], catch_exceptions=False)

    assert result.exit_code == 1, result.stdout
    assert "installer" in result.stdout.lower()
    assert "loco settings edit data_root" in result.stdout


def test_setup_requires_data_root_in_config(loco_data_isolated) -> None:
    cfg = loco_data_isolated / "config.yaml"
    cfg.write_text("{}\n", encoding="utf-8")

    result = runner.invoke(app, ["setup"], catch_exceptions=False)

    assert result.exit_code == 1
    assert "installer" in result.stdout.lower()


def test_setup_invokes_chain_when_prerequisites_met(loco_data_isolated, monkeypatch) -> None:
    save_settings({"data_root": str(loco_data_isolated)})

    invoked: list[int] = []
    import llm_cli.commands.setup as setup_cmd

    monkeypatch.setattr(setup_cmd, "run_setup_chain", lambda: invoked.append(1) or 0)

    result = runner.invoke(app, ["setup"], catch_exceptions=False)

    assert result.exit_code == 0, result.stdout
    assert invoked == [1]


def test_setup_chain_exit_code_propagates(loco_data_isolated, monkeypatch) -> None:
    save_settings({"data_root": str(loco_data_isolated)})

    import llm_cli.commands.setup as setup_cmd

    monkeypatch.setattr(setup_cmd, "run_setup_chain", lambda: 2)

    result = runner.invoke(app, ["setup"], catch_exceptions=False)

    assert result.exit_code == 2


def test_setup_ensures_data_dirs(loco_data_isolated, monkeypatch) -> None:
    save_settings({"data_root": str(loco_data_isolated)})

    import llm_cli.commands.setup as setup_cmd

    monkeypatch.setattr(setup_cmd, "run_setup_chain", lambda: 0)

    runner.invoke(app, ["setup"], catch_exceptions=False)

    assert (loco_data_isolated / "configs").is_dir()
    assert (loco_data_isolated / "state").is_dir()
    stored = yaml.safe_load((loco_data_isolated / "config.yaml").read_text(encoding="utf-8"))
    from pathlib import Path

    assert Path(stored["data_root"]).resolve() == loco_data_isolated.resolve()
