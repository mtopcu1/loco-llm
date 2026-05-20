"""Shared test setup: src/ on path; isolate LOCO_HOME for every test."""
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
def loco_data_isolated(tmp_path_factory, monkeypatch):
    """Redirect LOCO_HOME so tests never touch ~/.loco."""
    data = tmp_path_factory.mktemp("loco-data")
    monkeypatch.setenv("LOCO_HOME", str(data))
    monkeypatch.delenv("LOCO_INSTALL", raising=False)
    monkeypatch.delenv("LOCO_LLM_DATA", raising=False)
    monkeypatch.delenv("LOCO_LLM_HOME", raising=False)
    return data


@pytest.fixture(autouse=True)
def cli_output_env(monkeypatch):
    """Match GitHub Actions: plain CLI output without Rich TTY styling."""
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("TERM", "dumb")
    monkeypatch.delenv("FORCE_COLOR", raising=False)
