"""Integration test for `llm setup` chain orchestration."""
from __future__ import annotations

from typer.testing import CliRunner

from llm_cli.main import app

runner = CliRunner()


def test_setup_default_skips_chain(monkeypatch):
    invoked: list[int] = []
    from llm_cli.core import chain

    monkeypatch.setattr(chain, "run_setup_chain", lambda: invoked.append(1) or 0)

    result = runner.invoke(app, ["setup", "--default"])
    assert result.exit_code == 0
    assert not invoked


def test_setup_invokes_chain_on_interactive_path(monkeypatch):
    invoked: list[int] = []
    from llm_cli.core import chain

    monkeypatch.setattr(chain, "run_setup_chain", lambda: invoked.append(1) or 0)
    monkeypatch.setattr("typer.prompt", lambda *a, **k: k.get("default", ""))
    monkeypatch.setattr("typer.confirm", lambda *a, **k: True)

    result = runner.invoke(app, ["setup"])
    assert result.exit_code == 0
    assert invoked == [1]
