"""Tests for repo root discovery via settings."""
from __future__ import annotations

from pathlib import Path

import pytest

from llm_cli.core.repo import RepoRootMissing, repo_root
from llm_cli.core.settings import save_settings


def test_repo_root_reads_from_settings(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    save_settings({"data_root": str(tmp_path / "d"), "repo_root": str(repo)})
    assert repo_root() == repo.resolve()


def test_repo_root_raises_when_missing(tmp_path: Path) -> None:
    with pytest.raises(RepoRootMissing):
        repo_root()


def test_repo_root_raises_when_pointed_at_nonexistent_dir(tmp_path: Path) -> None:
    save_settings({"data_root": str(tmp_path / "d"), "repo_root": str(tmp_path / "ghost")})
    with pytest.raises(RepoRootMissing):
        repo_root()
