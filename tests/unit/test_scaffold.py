"""Tests for scaffold and user asset path resolution."""
from __future__ import annotations

from pathlib import Path

import pytest

from llm_cli.core.scaffold import (
    default_scaffold_dir,
    scaffold_dir,
    scaffold_root,
    user_assets_root,
    user_configs_dir,
    user_runtimes_dir,
)
from llm_cli.core.settings import resolve


def test_default_scaffold_dir_under_xdg(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    monkeypatch.delenv("LLM_SCAFFOLD_DIR", raising=False)
    assert default_scaffold_dir() == tmp_path / "xdg" / "localllm" / "scaffold"


def test_scaffold_dir_honors_env_override(monkeypatch, tmp_path) -> None:
    custom = tmp_path / "my-scaffold"
    monkeypatch.setenv("LLM_SCAFFOLD_DIR", str(custom))
    assert scaffold_dir() == custom


def test_scaffold_root_uses_repo_when_configured(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "clone"
    repo.mkdir()
    (repo / "runtimes").mkdir()
    cfg = tmp_path / "cfg" / "llm"
    cfg.mkdir(parents=True)
    (cfg / "config.yaml").write_text(
        f"data_root: {tmp_path / 'data'}\nrepo_root: {repo}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    assert scaffold_root() == repo.resolve()


def test_scaffold_root_without_repo_uses_scaffold_dir(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    monkeypatch.delenv("LLM_SCAFFOLD_DIR", raising=False)
    cfg = tmp_path / "cfg" / "llm"
    cfg.mkdir(parents=True)
    (cfg / "config.yaml").write_text(f"data_root: {tmp_path / 'data'}\n", encoding="utf-8")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    assert scaffold_root() == (tmp_path / "xdg" / "localllm" / "scaffold").resolve()


def test_user_asset_dirs_under_data_root() -> None:
    settings = resolve({"data_root": "/dr"})
    assert user_assets_root(settings) == Path("/dr/user")
    assert user_runtimes_dir(settings) == Path("/dr/user/runtimes")
    assert user_configs_dir(settings) == Path("/dr/user/configs")


def test_resolve_without_repo_root() -> None:
    out = resolve({"data_root": "/dr"})
    assert out.repo_root is None
