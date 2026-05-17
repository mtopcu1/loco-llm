"""Tests for the user-level settings module."""
from __future__ import annotations

from pathlib import Path

from llm_cli.core.settings import KEY_REGISTRY, Settings, default_settings


def test_settings_dataclass_has_expected_fields() -> None:
    s = Settings(
        data_root=Path("/r"),
        repo_root=Path("/repo"),
        runtimes_dir=Path("/r/runtimes"),
        models_dir=Path("/r/models"),
        cache_dir=Path("/r/cache"),
    )
    assert s.data_root == Path("/r")
    assert s.repo_root == Path("/repo")
    assert s.runtimes_dir == Path("/r/runtimes")
    assert s.models_dir == Path("/r/models")
    assert s.cache_dir == Path("/r/cache")


def test_default_settings_has_data_root_only_and_no_repo_root() -> None:
    d = default_settings()
    assert d == {"data_root": "~/llm"}


def test_key_registry_has_required_keys() -> None:
    keys = set(KEY_REGISTRY.keys())
    assert keys == {"data_root", "repo_root", "runtimes_dir", "models_dir", "cache_dir"}
    assert KEY_REGISTRY["data_root"]["default"] == "~/llm"
    assert KEY_REGISTRY["repo_root"]["default"] is None
    assert KEY_REGISTRY["repo_root"]["required"] is True
    assert KEY_REGISTRY["data_root"]["required"] is True
    for k in ("runtimes_dir", "models_dir", "cache_dir"):
        assert KEY_REGISTRY[k]["required"] is False
        assert KEY_REGISTRY[k]["derived_from"] == "data_root"
