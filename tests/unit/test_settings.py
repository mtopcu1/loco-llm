"""Tests for the user-level settings module."""
from __future__ import annotations

from pathlib import Path

import pytest

from llm_cli.core.settings import (
    KEY_REGISTRY,
    Settings,
    UnknownSettingError,
    default_settings,
    load_settings,
    settings_path,
)


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


def test_settings_path_defaults_to_home_config(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert settings_path() == tmp_path / ".config" / "llm" / "config.yaml"


def test_settings_path_honors_xdg_config_home(monkeypatch, tmp_path) -> None:
    xdg = tmp_path / "xdg"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    assert settings_path() == xdg / "llm" / "config.yaml"


def test_load_settings_missing_file_returns_empty_dict(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    assert load_settings() == {}


def test_load_settings_reads_yaml(tmp_path, monkeypatch) -> None:
    cfg = tmp_path / "cfg" / "llm"
    cfg.mkdir(parents=True)
    (cfg / "config.yaml").write_text(
        "data_root: ~/x\nrepo_root: /tmp/repo\n", encoding="utf-8"
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    assert load_settings() == {"data_root": "~/x", "repo_root": "/tmp/repo"}


def test_load_settings_rejects_unknown_keys(tmp_path, monkeypatch) -> None:
    cfg = tmp_path / "cfg" / "llm"
    cfg.mkdir(parents=True)
    (cfg / "config.yaml").write_text("oops: yes\n", encoding="utf-8")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    with pytest.raises(UnknownSettingError) as exc:
        load_settings()
    assert "oops" in str(exc.value)


def test_load_settings_rejects_non_mapping(tmp_path, monkeypatch) -> None:
    cfg = tmp_path / "cfg" / "llm"
    cfg.mkdir(parents=True)
    (cfg / "config.yaml").write_text("- a\n- b\n", encoding="utf-8")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    with pytest.raises(ValueError):
        load_settings()
