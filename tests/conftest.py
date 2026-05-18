"""Shared test setup: src/ on path; isolate XDG_CONFIG_HOME for every test."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

collect_ignore = ["tui"]


@pytest.fixture
def tui_repo(tmp_path, monkeypatch):
    from tests.tui.seed import seed_repo

    return seed_repo(tmp_path, monkeypatch, with_qwen=False)


@pytest.fixture
def tui_repo_with_model(tmp_path, monkeypatch):
    from tests.tui.seed import seed_repo

    return seed_repo(tmp_path, monkeypatch, with_qwen=True)


@pytest.fixture(autouse=True)
def xdg_isolated(tmp_path_factory, monkeypatch):
    """Redirect $XDG_CONFIG_HOME so tests never touch real user settings."""
    cfg = tmp_path_factory.mktemp("xdg")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(cfg))
    return cfg
