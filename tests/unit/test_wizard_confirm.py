"""Tests for binary Yes/No button prompts."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from llm_cli.core import wizard_confirm, wizards


@pytest.fixture(autouse=True)
def _reset_wizard_force_plain():
    wizards.force_plain(False)
    yield
    wizards.force_plain(False)


def test_plain_confirm_defaults_to_yes(monkeypatch):
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setattr(wizard_confirm, "_can_run_confirm_tui", lambda: False)
    with patch("llm_cli.core.wizard_confirm.Prompt.ask", return_value="") as ask:
        out = wizards.confirm("Install runtime?", default=True)
    assert out is True
    ask.assert_called_once()
    assert ask.call_args.kwargs.get("default") == "2"


def test_plain_confirm_accepts_n(monkeypatch):
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setattr(wizard_confirm, "_can_run_confirm_tui", lambda: False)
    with patch("llm_cli.core.wizard_confirm.Prompt.ask", return_value="n"):
        out = wizards.confirm("Install runtime?", default=True)
    assert out is False


def test_plain_confirm_accepts_1_for_no(monkeypatch):
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setattr(wizard_confirm, "_can_run_confirm_tui", lambda: False)
    with patch("llm_cli.core.wizard_confirm.Prompt.ask", return_value="1"):
        out = wizards.confirm("Purge?", default=False)
    assert out is False


def test_non_tty_returns_default(monkeypatch):
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)
    assert wizards.confirm("Skip?", default=True) is True
    assert wizards.confirm("Skip?", default=False) is False


def test_tui_path_delegates(monkeypatch):
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setattr(wizard_confirm, "_can_run_confirm_tui", lambda: True)
    with patch(
        "llm_cli.core.wizard_confirm._run_binary_confirm_tui",
        return_value=True,
    ) as tui:
        out = wizards.confirm("Continue?", default=False)
    assert out is True
    tui.assert_called_once_with("Continue?", default=False)
