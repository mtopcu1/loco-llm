"""User-level settings stored at ~/.config/llm/config.yaml."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Settings:
    data_root: Path
    repo_root: Path | None
    runtimes_dir: Path
    models_dir: Path
    cache_dir: Path


KEY_REGISTRY: dict[str, dict[str, Any]] = {
    "data_root": {
        "default": "~/llm",
        "required": True,
        "prompt": "Where should LocalLLM store runtimes, models, and cache?",
        "kind": "path",
    },
    "repo_root": {
        "default": None,
        "required": False,
        "prompt": "Path to the LocalLLM repo clone (dev/editable installs only)",
        "kind": "path",
    },
    "runtimes_dir": {
        "default": None,
        "required": False,
        "derived_from": "data_root",
        "derived_suffix": "runtimes",
        "prompt": "Override runtimes directory? (leave empty to derive from data_root)",
        "kind": "path",
    },
    "models_dir": {
        "default": None,
        "required": False,
        "derived_from": "data_root",
        "derived_suffix": "models",
        "prompt": "Override models directory? (leave empty to derive from data_root)",
        "kind": "path",
    },
    "cache_dir": {
        "default": None,
        "required": False,
        "derived_from": "data_root",
        "derived_suffix": "cache",
        "prompt": "Override cache directory? (leave empty to derive from data_root)",
        "kind": "path",
    },
}


def default_settings() -> dict[str, str]:
    """The minimum stored dict; repo_root is filled in by `llm setup`."""
    return {"data_root": KEY_REGISTRY["data_root"]["default"]}


def settings_path() -> Path:
    """Resolve the settings file path honoring $XDG_CONFIG_HOME."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "llm" / "config.yaml"


class UnknownSettingError(ValueError):
    """Raised when the settings file contains a key that is not in KEY_REGISTRY."""


def load_settings() -> dict[str, str]:
    """Load raw settings from disk. Missing file -> empty dict."""
    path = settings_path()
    if not path.is_file():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: top-level must be a mapping")
    unknown = sorted(k for k in raw if k not in KEY_REGISTRY)
    if unknown:
        raise UnknownSettingError(
            f"{path}: unknown setting(s): {', '.join(unknown)}. "
            f"Valid keys: {', '.join(sorted(KEY_REGISTRY))}"
        )
    return {str(k): str(v) for k, v in raw.items()}


def save_settings(values: dict[str, str]) -> Path:
    """Write the settings dict to disk; returns the path written."""
    unknown = sorted(k for k in values if k not in KEY_REGISTRY)
    if unknown:
        raise UnknownSettingError(
            f"unknown setting(s): {', '.join(unknown)}. "
            f"Valid keys: {', '.join(sorted(KEY_REGISTRY))}"
        )
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = {k: values[k] for k in KEY_REGISTRY if k in values}
    path.write_text(
        yaml.safe_dump(ordered, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


class MissingSettingError(ValueError):
    """Raised when a required setting (e.g. repo_root) is absent."""


def _expand(value: str) -> Path:
    return Path(value).expanduser()


def resolve_settings() -> Settings:
    """Load settings from disk and return fully-resolved paths."""
    return resolve(load_settings())


def resolve(values: dict[str, str]) -> Settings:
    """Return a fully-populated Settings, filling defaults + derived dir keys."""
    data_root_raw = values.get("data_root", KEY_REGISTRY["data_root"]["default"])
    data_root = _expand(data_root_raw)

    repo_root_raw = values.get("repo_root")
    repo_root = _expand(repo_root_raw) if repo_root_raw else None

    def _dir(key: str, suffix: str) -> Path:
        override = values.get(key)
        return _expand(override) if override else data_root / suffix

    return Settings(
        data_root=data_root,
        repo_root=repo_root,
        runtimes_dir=_dir("runtimes_dir", "runtimes"),
        models_dir=_dir("models_dir", "models"),
        cache_dir=_dir("cache_dir", "cache"),
    )


def ensure_data_dirs(settings: Settings) -> None:
    """Create data_root + resolved data subdirectories and user asset dirs."""
    for target in (
        settings.data_root,
        settings.runtimes_dir,
        settings.models_dir,
        settings.cache_dir,
    ):
        target.mkdir(parents=True, exist_ok=True)
    user_root = settings.data_root / "user"
    for sub in ("runtimes", "configs", "benchmarks"):
        (user_root / sub).mkdir(parents=True, exist_ok=True)


class SettingsValidationError(ValueError):
    """Raised when a setting value fails KEY_REGISTRY validation."""


def set(key: str, value: str | None) -> dict[str, str]:
    """Set or clear a single settings key; returns the stored dict."""
    if key not in KEY_REGISTRY:
        raise UnknownSettingError(
            f"unknown setting {key!r}. Valid keys: {', '.join(sorted(KEY_REGISTRY))}"
        )
    meta = KEY_REGISTRY[key]
    stored = load_settings()
    if value is None:
        if meta.get("required"):
            raise SettingsValidationError(f"{key!r} is required and cannot be cleared")
        stored.pop(key, None)
    else:
        if meta.get("kind") == "path":
            expanded = _expand(value)
            if key == "repo_root":
                if not expanded.is_dir():
                    raise SettingsValidationError(
                        f"{key!r} must be an existing directory: {value}"
                    )
            elif not str(value).strip():
                raise SettingsValidationError(f"{key!r} path cannot be empty")
        stored[key] = value
    save_settings(stored)
    return load_settings()
