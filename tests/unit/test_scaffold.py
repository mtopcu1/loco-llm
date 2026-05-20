"""Tests for scaffold and user asset path resolution."""
from __future__ import annotations

from pathlib import Path

from llm_cli.core.scaffold import (
    configs_dir,
    user_assets_root,
    user_runtimes_dir,
)
from llm_cli.core.settings import resolve


def test_configs_dir_under_data_root() -> None:
    settings = resolve({"data_root": "/dr"})
    assert configs_dir(settings) == Path("/dr/configs")


def test_user_asset_dirs_under_data_root() -> None:
    settings = resolve({"data_root": "/dr"})
    assert user_assets_root(settings) == Path("/dr/user")
    assert user_runtimes_dir(settings) == Path("/dr/user/runtimes")


def test_resolve_without_repo_root() -> None:
    out = resolve({"data_root": "/dr"})
    assert out.repo_root is None
