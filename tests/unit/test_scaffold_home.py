"""Tests for the LOCO_LLM_HOME-based scaffold_root resolution."""
from __future__ import annotations

from pathlib import Path

import pytest

from llm_cli.core import scaffold


def test_scaffold_root_uses_loco_llm_home_env_var(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOCO_LLM_HOME", str(tmp_path))
    monkeypatch.setattr(scaffold, "configured_repo_root", lambda: None)
    assert scaffold.scaffold_root() == tmp_path.resolve()


def test_scaffold_root_prefers_configured_repo_root_when_no_env(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.delenv("LOCO_LLM_HOME", raising=False)
    dev = tmp_path / "dev"
    dev.mkdir()
    monkeypatch.setattr(scaffold, "configured_repo_root", lambda: dev.resolve())
    assert scaffold.scaffold_root() == dev.resolve()


def test_scaffold_root_falls_back_to_module_git_toplevel(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("LOCO_LLM_HOME", raising=False)
    monkeypatch.setattr(scaffold, "configured_repo_root", lambda: None)
    monkeypatch.setattr(scaffold, "_module_git_toplevel", lambda: tmp_path)
    assert scaffold.scaffold_root() == tmp_path.resolve()


def test_scaffold_root_raises_when_no_source(monkeypatch) -> None:
    monkeypatch.delenv("LOCO_LLM_HOME", raising=False)
    monkeypatch.setattr(scaffold, "configured_repo_root", lambda: None)
    monkeypatch.setattr(scaffold, "_module_git_toplevel", lambda: None)
    with pytest.raises(RuntimeError, match="LOCO_LLM_HOME"):
        scaffold.scaffold_root()
