"""Shared test setup: src/ on path; isolate XDG_CONFIG_HOME for every test."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture(autouse=True)
def xdg_isolated(tmp_path_factory, monkeypatch):
    """Redirect $XDG_CONFIG_HOME so tests never touch real user settings."""
    cfg = tmp_path_factory.mktemp("xdg")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(cfg))
    return cfg
