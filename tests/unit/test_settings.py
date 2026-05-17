"""Tests for the user-level settings module."""
from __future__ import annotations

from pathlib import Path

import pytest

from llm_cli.core.settings import (
    KEY_REGISTRY,
    MissingSettingError,
    Settings,
    UnknownSettingError,
    default_settings,
    ensure_data_dirs,
    load_settings,
    resolve,
    save_settings,
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


def test_save_settings_round_trip(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    save_settings({"data_root": "~/llm", "repo_root": "/some/repo"})
    assert load_settings() == {"data_root": "~/llm", "repo_root": "/some/repo"}


def test_save_settings_creates_parent_dirs(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "deep" / "xdg"))
    save_settings({"data_root": "~/llm", "repo_root": "/r"})
    assert (tmp_path / "deep" / "xdg" / "llm" / "config.yaml").is_file()


def test_save_settings_rejects_unknown_keys(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    with pytest.raises(UnknownSettingError):
        save_settings({"oops": "yes"})


def test_resolve_derives_dir_keys_from_data_root() -> None:
    out = resolve({"data_root": "/dr", "repo_root": "/repo"})
    assert out.data_root == Path("/dr")
    assert out.repo_root == Path("/repo")
    assert out.runtimes_dir == Path("/dr/runtimes")
    assert out.models_dir == Path("/dr/models")
    assert out.cache_dir == Path("/dr/cache")


def test_resolve_honors_explicit_dir_overrides() -> None:
    out = resolve(
        {
            "data_root": "/dr",
            "repo_root": "/repo",
            "runtimes_dir": "/mnt/d/rt",
        }
    )
    assert out.runtimes_dir == Path("/mnt/d/rt")
    assert out.models_dir == Path("/dr/models")


def test_resolve_expands_tilde(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    out = resolve({"data_root": "~/llm", "repo_root": "~/r"})
    assert out.data_root == tmp_path / "llm"
    assert out.repo_root == tmp_path / "r"
    assert out.runtimes_dir == tmp_path / "llm" / "runtimes"


def test_resolve_uses_default_for_data_root_when_missing() -> None:
    out = resolve({"repo_root": "/r"})
    assert out.data_root == Path("~/llm").expanduser()


def test_resolve_raises_when_repo_root_missing() -> None:
    with pytest.raises(MissingSettingError) as exc:
        resolve({"data_root": "/dr"})
    assert "repo_root" in str(exc.value)


def test_ensure_data_dirs_creates_all_resolved_dirs(tmp_path) -> None:
    s = resolve({"data_root": str(tmp_path / "dr"), "repo_root": str(tmp_path)})
    ensure_data_dirs(s)
    assert (tmp_path / "dr").is_dir()
    assert (tmp_path / "dr" / "runtimes").is_dir()
    assert (tmp_path / "dr" / "models").is_dir()
    assert (tmp_path / "dr" / "cache").is_dir()


def test_ensure_data_dirs_is_idempotent(tmp_path) -> None:
    s = resolve({"data_root": str(tmp_path / "dr"), "repo_root": str(tmp_path)})
    ensure_data_dirs(s)
    ensure_data_dirs(s)
    assert (tmp_path / "dr").is_dir()
